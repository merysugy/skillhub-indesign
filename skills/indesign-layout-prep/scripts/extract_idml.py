#!/usr/bin/env python3
"""
extract_idml.py - Read the style system out of an existing InDesign file.

For users who already have their styles in InDesign: they export the document
or template as IDML (File > Save As > InDesign Markup (IDML)) and this script
writes the same style-system JSON that step 1 produces from a PDF:
page setup, swatches, and every paragraph and character style with its group,
based-on style, font, size, leading, spacing, colour and alignment.

Usage:
    python3 extract_idml.py brand.idml -o style-system.json
    python3 extract_idml.py brand.idml            # prints a summary + JSON to stdout

Values the generator cannot express (paragraph rules, borders, shading, GREP
styles, tab stops, nested styles...) are not extracted. Only the Python 3
standard library is used.
"""

import argparse
import json
import posixpath
import sys
import zipfile
import xml.etree.ElementTree as ET

PT_TO_MM = 25.4 / 72.0

ALIGN = {"LeftAlign": "left", "CenterAlign": "center", "RightAlign": "right",
         "LeftJustified": "justify", "FullyJustified": "justify-all",
         "ToBindingSide": "towards-spine", "AwayFromBindingSide": "away-from-spine",
         "CenterJustified": "justify", "RightJustified": "justify"}
CASE = {"Normal": "normal", "AllCaps": "uppercase", "SmallCaps": "small-caps",
        "CapToSmallCap": "caps-to-small-caps"}
START = {"Anywhere": "anywhere", "NextColumn": "next-column", "NextFrame": "next-frame",
         "NextPage": "next-page", "NextOddPage": "next-odd-page",
         "NextEvenPage": "next-even-page"}
LIST = {"NoList": "none", "BulletList": "bullet", "NumberedList": "numbered"}
POSITION = {"Normal": "normal", "Superscript": "superscript", "Subscript": "subscript",
            "OTSuperscript": "superscript", "OTSubscript": "subscript"}
BUILTIN = {"Color/Black": "Black", "Color/Paper": "Paper",
           "Color/Registration": "Registration", "Swatch/None": "None"}


def local(tag):
    return tag.rsplit("}", 1)[-1]


def rnd(value, digits=2):
    value = round(float(value), digits)
    return int(value) if value == int(value) else value


def read_xml(zf, name):
    try:
        return ET.fromstring(zf.read(name))
    except KeyError:
        return None


def package_parts(zf):
    """Map idPkg element names (Graphic, Styles, MasterSpread...) to part paths."""
    root = ET.fromstring(zf.read("designmap.xml"))
    parts = {}
    for child in root:
        src = child.get("src")
        if src:
            parts.setdefault(local(child.tag), []).append(posixpath.normpath(src))
    return parts


def extract_colors(graphic):
    colors, names = [], dict(BUILTIN)
    warnings = []
    if graphic is None:
        return colors, names, warnings
    for el in graphic:
        if local(el.tag) != "Color":
            continue
        self_ref, name = el.get("Self"), el.get("Name", "")
        if self_ref in BUILTIN or name.startswith("$ID/") or not name:
            if self_ref and name:
                names[self_ref] = name.replace("$ID/", "")
            continue
        if el.get("Visible", "true") == "false":
            continue
        values = [float(v) for v in el.get("ColorValue", "").split()]
        space = el.get("Space")
        color = {"name": name}
        if space == "CMYK" and len(values) == 4:
            color["cmyk"] = [rnd(v, 1) for v in values]
        elif space == "RGB" and len(values) == 3:
            color["rgb"] = [int(round(v)) for v in values]
        else:
            warnings.append("Colour %r uses %s and was skipped (convert it to CMYK or RGB)"
                            % (name, space))
            continue
        if el.get("Model") == "Spot":
            color["spot"] = True
        colors.append(color)
        names[self_ref] = name
    # Tints: keep the base colour reference.
    for el in graphic:
        if local(el.tag) == "Tint" and el.get("BaseColor") in names:
            names[el.get("Self")] = names[el.get("BaseColor")]
    return colors, names, warnings


def style_props(el):
    props = {}
    container = el.find("Properties")
    if container is not None:
        for child in container:
            props[local(child.tag)] = child
    return props


def parse_style(el, path, kind, color_names, self_to_name):
    style = {"name": path[-1]}
    if len(path) > 1:
        style["group"] = "/".join(path[:-1])
    a = el.attrib
    props = style_props(el)

    based = props.get("BasedOn")
    if based is not None and based.text and "[No " not in based.text \
            and "NormalParagraphStyle" not in based.text:
        style["based_on"] = based.text  # resolved to a name later
    if "AppliedFont" in props and props["AppliedFont"].text:
        style["font"] = props["AppliedFont"].text
    if "FontStyle" in a:
        style["font_style"] = a["FontStyle"]
    if "PointSize" in a:
        style["size_pt"] = rnd(a["PointSize"])
    leading = props.get("Leading")
    if leading is not None and leading.text:
        style["leading_pt"] = "auto" if leading.text == "Auto" else rnd(leading.text)
    if "FillColor" in a:
        style["color"] = color_names.get(a["FillColor"], a["FillColor"])
    if "FillTint" in a and float(a["FillTint"]) >= 0:
        style["tint"] = rnd(a["FillTint"])
    if "Tracking" in a:
        style["tracking"] = int(float(a["Tracking"]))
    if a.get("Capitalization") in CASE:
        style["case"] = CASE[a["Capitalization"]]
    if a.get("Position") in POSITION:
        style["position"] = POSITION[a["Position"]]
    for attr_name, key in (("Underline", "underline"), ("StrikeThru", "strikethrough")):
        if attr_name in a:
            style[key] = a[attr_name] == "true"

    if kind == "paragraph":
        for attr_name, key in (("SpaceBefore", "space_before_pt"),
                               ("SpaceAfter", "space_after_pt"),
                               ("FirstLineIndent", "first_line_indent_pt"),
                               ("LeftIndent", "left_indent_pt"),
                               ("RightIndent", "right_indent_pt")):
            if attr_name in a:
                style[key] = rnd(a[attr_name])
        if a.get("Justification") in ALIGN:
            style["align"] = ALIGN[a["Justification"]]
        if "Hyphenation" in a:
            style["hyphenate"] = a["Hyphenation"] == "true"
        if "KeepWithNext" in a:
            style["keep_with_next"] = int(float(a["KeepWithNext"]))
        if "KeepLinesTogether" in a:
            style["keep_lines_together"] = a["KeepLinesTogether"] == "true"
        if a.get("StartParagraph") in START:
            style["start"] = START[a["StartParagraph"]]
        if a.get("SpanColumnType") == "SpanColumns":
            style["span_columns"] = True
        if a.get("BulletsAndNumberingListType") in LIST:
            style["list"] = LIST[a["BulletsAndNumberingListType"]]
        nxt = props.get("NextStyle")
        if nxt is not None and nxt.text and nxt.text != a.get("Self"):
            style["next_style"] = nxt.text

    self_to_name[a.get("Self")] = path[-1]
    return style


def walk_styles(group, style_tag, group_tag, path, kind, out, color_names, self_to_name):
    for el in group:
        tag = local(el.tag)
        if tag == style_tag:
            name = el.get("Name", "")
            if name.startswith("$ID/") or name.startswith("["):
                continue
            leaf = name.split(":")[-1]
            out.append(parse_style(el, path + [leaf], kind, color_names, self_to_name))
        elif tag == group_tag:
            walk_styles(el, style_tag, group_tag, path + [el.get("Name", "Group")], kind,
                        out, color_names, self_to_name)


def resolve_refs(styles, self_to_name, warnings, label):
    names = {s["name"] for s in styles}
    for s in styles:
        for key in ("based_on", "next_style"):
            if key in s:
                ref = self_to_name.get(s[key])
                if ref and ref in names:
                    s[key] = ref
                else:
                    warnings.append("%s style %r: %s %r not found, dropped"
                                    % (label, s["name"], key, s[key]))
                    del s[key]
    seen, dupes = set(), set()
    for s in styles:
        if s["name"] in seen:
            dupes.add(s["name"])
        seen.add(s["name"])
    if dupes:
        warnings.append("%s style names used in more than one group: %s. Rename them "
                        "before running build_idml.py." % (label, ", ".join(sorted(dupes))))


def extract_document(zf, parts):
    doc = {}
    prefs = None
    for name in parts.get("Preferences", []):
        prefs = read_xml(zf, name)
    if prefs is not None:
        for el in prefs:
            tag = local(el.tag)
            if tag == "DocumentPreference":
                w, h = float(el.get("PageWidth", 595.276)), float(el.get("PageHeight", 841.89))
                doc["page_size"] = {"width_mm": rnd(w * PT_TO_MM, 1),
                                    "height_mm": rnd(h * PT_TO_MM, 1)}
                doc["orientation"] = "landscape" if w > h else "portrait"
                doc["facing_pages"] = el.get("FacingPages") == "true"
                if el.get("DocumentBleedTopOffset"):
                    doc["bleed_mm"] = rnd(float(el.get("DocumentBleedTopOffset")) * PT_TO_MM, 1)
            elif tag == "MarginPreference":
                doc["_margins"] = el
    # Prefer the first master page's margins over the default preference.
    for name in parts.get("MasterSpread", [])[:1]:
        master = read_xml(zf, name)
        if master is not None:
            for mp in master.iter("MarginPreference"):
                doc["_margins"] = mp
                break
    mp = doc.pop("_margins", None)
    if mp is not None:
        doc["margins_mm"] = {"top": rnd(float(mp.get("Top", 36)) * PT_TO_MM, 1),
                             "bottom": rnd(float(mp.get("Bottom", 36)) * PT_TO_MM, 1),
                             "inside": rnd(float(mp.get("Left", 36)) * PT_TO_MM, 1),
                             "outside": rnd(float(mp.get("Right", 36)) * PT_TO_MM, 1)}
        doc["columns"] = int(mp.get("ColumnCount", 1))
        doc["gutter_mm"] = rnd(float(mp.get("ColumnGutter", 12)) * PT_TO_MM, 1)
    doc["units"] = "mm"
    return doc


def extract(path):
    warnings = []
    with zipfile.ZipFile(path) as zf:
        parts = package_parts(zf)
        graphic = None
        for name in parts.get("Graphic", []):
            graphic = read_xml(zf, name)
        colors, color_names, color_warnings = extract_colors(graphic)
        warnings.extend(color_warnings)
        styles_root = None
        for name in parts.get("Styles", []):
            styles_root = read_xml(zf, name)
        if styles_root is None:
            raise ValueError("No Resources/Styles.xml in this IDML")
        document = extract_document(zf, parts)

    self_to_name = {}
    paragraph, character = [], []
    for el in styles_root:
        tag = local(el.tag)
        if tag == "RootParagraphStyleGroup":
            walk_styles(el, "ParagraphStyle", "ParagraphStyleGroup", [], "paragraph",
                        paragraph, color_names, self_to_name)
        elif tag == "RootCharacterStyleGroup":
            walk_styles(el, "CharacterStyle", "CharacterStyleGroup", [], "character",
                        character, color_names, self_to_name)
    resolve_refs(paragraph, self_to_name, warnings, "Paragraph")
    resolve_refs(character, self_to_name, warnings, "Character")

    known = {c["name"] for c in colors} | set(BUILTIN.values())
    for s in paragraph + character:
        if "color" in s and s["color"] not in known:
            warnings.append("Style %r uses colour %r, which is not a named swatch: dropped"
                            % (s["name"], s["color"]))
            del s["color"]

    name = posixpath.splitext(posixpath.basename(path))[0]
    data = {"name": name, "source": "Extracted from %s" % posixpath.basename(path),
            "document": document, "colors": colors,
            "paragraph_styles": paragraph, "character_styles": character}
    return data, warnings


def main(argv=None):
    parser = argparse.ArgumentParser(description="Extract the style system from an IDML file.")
    parser.add_argument("idml")
    parser.add_argument("-o", "--output", help="Write the style-system JSON here")
    args = parser.parse_args(argv)
    try:
        data, warnings = extract(args.idml)
    except (OSError, KeyError, ValueError, zipfile.BadZipFile, ET.ParseError) as exc:
        print("Error: cannot read %s: %s" % (args.idml, exc), file=sys.stderr)
        return 1

    text = json.dumps(data, ensure_ascii=False, indent=2)
    summary = ("%d paragraph styles, %d character styles, %d colours"
               % (len(data["paragraph_styles"]), len(data["character_styles"]),
                  len(data["colors"])))
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print("Wrote %s: %s." % (args.output, summary))
    else:
        print(text)
        print(summary, file=sys.stderr)
    for w in warnings:
        print("Warning: " + w, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
