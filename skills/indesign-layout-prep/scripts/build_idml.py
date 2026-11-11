#!/usr/bin/env python3
"""
build_idml.py - Turn a style-system JSON file into an InDesign template (.idml).

The output contains NO content: just the page setup (size, margins, columns,
bleed), the brand swatches, and every paragraph and character style organised
in style groups (folders). Open it in InDesign, check it, and save it as .indt
to reuse it as a template.

Usage:
    python3 build_idml.py style-system.json -o template.idml
    python3 build_idml.py style-system.json -o template.idml --specimen

--specimen fills the first text frame with one sample paragraph per paragraph
style, so you can review the whole type system at a glance.

Only the Python 3 standard library is used. See ../assets/style-system.schema.json
for the input format and ../assets/style-system.example.json for an example.
"""

import argparse
import json
import sys
import zipfile
from xml.sax.saxutils import escape, quoteattr

DOM_VERSION = "8.0"  # CS6 IDML: opens in every InDesign from CS6 to current CC
PKG_NS = "http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging"
XML_HEAD = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'

MM_TO_PT = 72.0 / 25.4

PAGE_SIZES_MM = {
    "A3": (297.0, 420.0),
    "A4": (210.0, 297.0),
    "A5": (148.0, 210.0),
    "B5": (176.0, 250.0),
    "LETTER": (215.9, 279.4),
    "LEGAL": (215.9, 355.6),
    "TABLOID": (279.4, 431.8),
}

ALIGN = {
    "left": "LeftAlign",
    "center": "CenterAlign",
    "right": "RightAlign",
    "justify": "LeftJustified",
    "justify-all": "FullyJustified",
    "towards-spine": "ToBindingSide",
    "away-from-spine": "AwayFromBindingSide",
}

CASE = {
    "normal": "Normal",
    "uppercase": "AllCaps",
    "small-caps": "SmallCaps",
    "caps-to-small-caps": "CapToSmallCap",
}

START = {
    "anywhere": "Anywhere",
    "next-column": "NextColumn",
    "next-frame": "NextFrame",
    "next-page": "NextPage",
    "next-odd-page": "NextOddPage",
    "next-even-page": "NextEvenPage",
}

LIST = {
    "none": "NoList",
    "bullet": "BulletList",
    "numbered": "NumberedList",
}

POSITION = {
    "normal": "Normal",
    "superscript": "Superscript",
    "subscript": "Subscript",
}

BUILTIN_COLORS = {"Black": "Color/Black", "Paper": "Color/Paper",
                  "Registration": "Color/Registration", "None": "Swatch/None"}

NO_PARA = "ParagraphStyle/$ID/[No paragraph style]"
BASIC_PARA = "ParagraphStyle/$ID/NormalParagraphStyle"
NO_CHAR = "CharacterStyle/$ID/[No character style]"


class StyleSystemError(Exception):
    pass


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def num(value):
    """Format a number for IDML (no trailing zeros, max 4 decimals)."""
    text = ("%.4f" % float(value)).rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def mm(value):
    return float(value) * MM_TO_PT


def attr(name, value):
    return " %s=%s" % (name, quoteattr(str(value)))


def self_id(kind, path):
    """IDML self id for a style: groups are joined with ':' encoded as %3a."""
    encoded = [p.replace("%", "%25").replace(":", "%3a") for p in path]
    return "%s/%s" % (kind, "%3a".join(encoded))


def split_group(group):
    if not group:
        return []
    return [part.strip() for part in str(group).split("/") if part.strip()]


def hex_to_rgb(value):
    h = value.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        raise StyleSystemError("Invalid hex colour: %r" % value)
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


# --------------------------------------------------------------------------
# Validation / normalisation
# --------------------------------------------------------------------------

def load_document_settings(data):
    doc = data.get("document", {})
    size = doc.get("page_size", "A4")
    if isinstance(size, str):
        key = size.upper()
        if key not in PAGE_SIZES_MM:
            raise StyleSystemError("Unknown page_size %r. Use one of %s or "
                                   "{\"width_mm\": .., \"height_mm\": ..}"
                                   % (size, ", ".join(sorted(PAGE_SIZES_MM))))
        width_mm, height_mm = PAGE_SIZES_MM[key]
    else:
        width_mm, height_mm = float(size["width_mm"]), float(size["height_mm"])
    if doc.get("orientation", "portrait") == "landscape":
        width_mm, height_mm = max(width_mm, height_mm), min(width_mm, height_mm)

    margins = doc.get("margins_mm", 20)
    if isinstance(margins, (int, float)):
        margins = {"top": margins, "bottom": margins,
                   "inside": margins, "outside": margins}
    for side in ("top", "bottom", "inside", "outside"):
        if side not in margins:
            raise StyleSystemError("margins_mm is missing %r" % side)

    columns = int(doc.get("columns", 1))
    if columns < 1:
        raise StyleSystemError("columns must be 1 or more")

    return {
        "width": mm(width_mm),
        "height": mm(height_mm),
        "facing": bool(doc.get("facing_pages", False)),
        "top": mm(margins["top"]),
        "bottom": mm(margins["bottom"]),
        "inside": mm(margins["inside"]),
        "outside": mm(margins["outside"]),
        "columns": columns,
        "gutter": mm(doc.get("gutter_mm", 5)),
        "bleed": mm(doc.get("bleed_mm", 3)),
        "units": doc.get("units", "mm"),
        "default_style": doc.get("default_paragraph_style"),
    }


def load_colors(data):
    colors = []
    refs = dict(BUILTIN_COLORS)
    for index, color in enumerate(data.get("colors", []), start=1):
        name = color.get("name")
        if not name:
            raise StyleSystemError("Colour #%d has no name" % index)
        if name in refs:
            raise StyleSystemError("Duplicate or reserved colour name: %r" % name)
        if "cmyk" in color:
            space, values = "CMYK", [float(v) for v in color["cmyk"]]
            if len(values) != 4 or not all(0 <= v <= 100 for v in values):
                raise StyleSystemError("%r: cmyk needs 4 values from 0 to 100" % name)
        elif "rgb" in color:
            space, values = "RGB", [float(v) for v in color["rgb"]]
            if len(values) != 3 or not all(0 <= v <= 255 for v in values):
                raise StyleSystemError("%r: rgb needs 3 values from 0 to 255" % name)
        elif "hex" in color:
            space, values = "RGB", hex_to_rgb(color["hex"])
        else:
            raise StyleSystemError("%r: give cmyk, rgb or hex" % name)
        self_ref = "Color/u%d" % (100 + index)
        refs[name] = self_ref
        colors.append({
            "self": self_ref,
            "name": name,
            "space": space,
            "values": values,
            "model": "Spot" if color.get("spot") else "Process",
        })
    return colors, refs


def resolve_styles(items, kind, label):
    """Give every style its group path and self id; check names are unique."""
    styles = []
    by_name = {}
    for index, item in enumerate(items, start=1):
        name = item.get("name")
        if not name:
            raise StyleSystemError("%s style #%d has no name" % (label, index))
        if ":" in name:
            raise StyleSystemError("%r: ':' is not allowed in style names" % name)
        if name in by_name:
            raise StyleSystemError("Duplicate %s style name: %r" % (label, name))
        path = split_group(item.get("group")) + [name]
        style = dict(item)
        style["_path"] = path
        style["_self"] = self_id(kind, path)
        styles.append(style)
        by_name[name] = style
    return styles, by_name


def check_based_on(styles, by_name, label):
    for style in styles:
        seen = set()
        current = style
        while current.get("based_on"):
            parent = current["based_on"]
            if parent not in by_name:
                raise StyleSystemError("%s style %r is based on unknown style %r"
                                       % (label, current["name"], parent))
            if parent in seen or parent == style["name"]:
                raise StyleSystemError("Circular based_on chain at %r" % style["name"])
            seen.add(parent)
            current = by_name[parent]


def color_ref(name, refs, owner):
    if name not in refs:
        raise StyleSystemError("Style %r uses unknown colour %r" % (owner, name))
    return refs[name]


# --------------------------------------------------------------------------
# XML builders
# --------------------------------------------------------------------------

def style_attributes(style, refs, is_paragraph):
    """Return (xml attributes, list of <Properties> children) for a style."""
    a = []
    props = []
    owner = style["name"]

    if "font_style" in style:
        a.append(attr("FontStyle", style["font_style"]))
    if "size_pt" in style:
        a.append(attr("PointSize", num(style["size_pt"])))
    if "color" in style:
        a.append(attr("FillColor", color_ref(style["color"], refs, owner)))
    if "tint" in style:
        a.append(attr("FillTint", num(style["tint"])))
    if "tracking" in style:
        a.append(attr("Tracking", int(style["tracking"])))
    if "case" in style:
        a.append(attr("Capitalization", CASE[style["case"]]))
    if "position" in style:
        a.append(attr("Position", POSITION[style["position"]]))
    if style.get("underline") is not None:
        a.append(attr("Underline", "true" if style["underline"] else "false"))
    if style.get("strikethrough") is not None:
        a.append(attr("StrikeThru", "true" if style["strikethrough"] else "false"))

    if is_paragraph:
        if "space_before_pt" in style:
            a.append(attr("SpaceBefore", num(style["space_before_pt"])))
        if "space_after_pt" in style:
            a.append(attr("SpaceAfter", num(style["space_after_pt"])))
        if "first_line_indent_pt" in style:
            a.append(attr("FirstLineIndent", num(style["first_line_indent_pt"])))
        if "left_indent_pt" in style:
            a.append(attr("LeftIndent", num(style["left_indent_pt"])))
        if "right_indent_pt" in style:
            a.append(attr("RightIndent", num(style["right_indent_pt"])))
        if "align" in style:
            a.append(attr("Justification", ALIGN[style["align"]]))
        if style.get("hyphenate") is not None:
            a.append(attr("Hyphenation", "true" if style["hyphenate"] else "false"))
        if "keep_with_next" in style:
            a.append(attr("KeepWithNext", int(style["keep_with_next"])))
        if style.get("keep_lines_together") is not None:
            a.append(attr("KeepLinesTogether",
                          "true" if style["keep_lines_together"] else "false"))
        if "start" in style:
            a.append(attr("StartParagraph", START[style["start"]]))
        if "list" in style:
            a.append(attr("BulletsAndNumberingListType", LIST[style["list"]]))
        if style.get("span_columns"):
            a.append(attr("SpanColumnType", "SpanColumns"))
            a.append(attr("SpanSplitColumnCount", "All"))

    if "font" in style:
        props.append('<AppliedFont type="string">%s</AppliedFont>' % escape(style["font"]))
    if "leading_pt" in style:
        if str(style["leading_pt"]).lower() == "auto":
            props.append('<Leading type="enumeration">Auto</Leading>')
        else:
            props.append('<Leading type="unit">%s</Leading>' % num(style["leading_pt"]))
    if "language" in style:
        props.append('<AppliedLanguage type="string">%s</AppliedLanguage>'
                     % escape(style["language"]))
    return "".join(a), props


def build_style_tree(styles):
    """Nest styles in group dicts: {"groups": {name: subtree}, "styles": [...]}."""
    root = {"groups": {}, "order": [], "styles": []}
    for style in styles:
        node = root
        for depth, group in enumerate(style["_path"][:-1]):
            if group not in node["groups"]:
                node["groups"][group] = {"groups": {}, "order": [], "styles": [],
                                         "path": style["_path"][:depth + 1]}
                node["order"].append(("group", group))
            node = node["groups"][group]
        node["order"].append(("style", style))
    return root


def render_style_tree(node, element, group_element, kind, render, indent):
    out = []
    pad = "  " * indent
    for entry_type, entry in node["order"]:
        if entry_type == "style":
            out.append(render(entry, pad))
        else:
            child = node["groups"][entry]
            group_self = self_id(kind + "Group", child["path"])
            out.append('%s<%s Self=%s Name=%s>' % (pad, group_element,
                                                   quoteattr(group_self), quoteattr(entry)))
            out.extend(render_style_tree(child, element, group_element, kind,
                                         render, indent + 1))
            out.append('%s</%s>' % (pad, group_element))
    return out


def styles_xml(paragraph_styles, para_by_name, character_styles, char_by_name, refs):
    def render_para(style, pad):
        attrs, props = style_attributes(style, refs, True)
        if style.get("based_on"):
            props.insert(0, '<BasedOn type="object">%s</BasedOn>'
                         % escape(para_by_name[style["based_on"]]["_self"]))
        else:
            props.insert(0, '<BasedOn type="object">%s</BasedOn>' % escape(BASIC_PARA))
        if style.get("next_style"):
            props.append('<NextStyle type="object">%s</NextStyle>'
                         % escape(para_by_name[style["next_style"]]["_self"]))
        return ('%s<ParagraphStyle Self=%s Name=%s Imported="false"%s>\n'
                '%s  <Properties>%s</Properties>\n%s</ParagraphStyle>'
                % (pad, quoteattr(style["_self"]), quoteattr(":".join(style["_path"])),
                   attrs, pad, "".join(props), pad))

    def render_char(style, pad):
        attrs, props = style_attributes(style, refs, False)
        if style.get("based_on"):
            props.insert(0, '<BasedOn type="object">%s</BasedOn>'
                         % escape(char_by_name[style["based_on"]]["_self"]))
        else:
            props.insert(0, '<BasedOn type="string">$ID/[No character style]</BasedOn>')
        return ('%s<CharacterStyle Self=%s Name=%s Imported="false"%s>\n'
                '%s  <Properties>%s</Properties>\n%s</CharacterStyle>'
                % (pad, quoteattr(style["_self"]), quoteattr(":".join(style["_path"])),
                   attrs, pad, "".join(props), pad))

    lines = [XML_HEAD + '<idPkg:Styles xmlns:idPkg="%s" DOMVersion="%s">'
             % (PKG_NS, DOM_VERSION)]
    lines.append('  <RootCharacterStyleGroup Self="u79">')
    lines.append('    <CharacterStyle Self="%s" Imported="false" '
                 'Name="$ID/[No character style]"/>' % NO_CHAR)
    lines.extend(render_style_tree(build_style_tree(character_styles), "CharacterStyle",
                                   "CharacterStyleGroup", "CharacterStyle", render_char, 2))
    lines.append('  </RootCharacterStyleGroup>')
    lines.append('  <RootParagraphStyleGroup Self="u78">')
    lines.append('    <ParagraphStyle Self="%s" Name="$ID/[No paragraph style]" '
                 'Imported="false"/>' % NO_PARA)
    lines.append('    <ParagraphStyle Self="%s" Name="$ID/NormalParagraphStyle" '
                 'Imported="false">\n      <Properties><BasedOn type="string">'
                 '$ID/[No paragraph style]</BasedOn></Properties>\n    </ParagraphStyle>'
                 % BASIC_PARA)
    lines.extend(render_style_tree(build_style_tree(paragraph_styles), "ParagraphStyle",
                                   "ParagraphStyleGroup", "ParagraphStyle", render_para, 2))
    lines.append('  </RootParagraphStyleGroup>')
    lines.append('  <RootObjectStyleGroup Self="u7a">\n'
                 '    <ObjectStyle Self="ObjectStyle/$ID/[None]" Name="$ID/[None]"/>\n'
                 '    <ObjectStyle Self="ObjectStyle/$ID/[Normal Graphics Frame]" '
                 'Name="$ID/[Normal Graphics Frame]"/>\n'
                 '    <ObjectStyle Self="ObjectStyle/$ID/[Normal Text Frame]" '
                 'Name="$ID/[Normal Text Frame]"/>\n'
                 '  </RootObjectStyleGroup>')
    lines.append('  <RootTableStyleGroup Self="u7b">\n'
                 '    <TableStyle Self="TableStyle/$ID/[No table style]" '
                 'Name="$ID/[No table style]"/>\n'
                 '    <TableStyle Self="TableStyle/$ID/[Basic Table]" Name="$ID/[Basic Table]"/>\n'
                 '  </RootTableStyleGroup>')
    lines.append('  <RootCellStyleGroup Self="u7c">\n'
                 '    <CellStyle Self="CellStyle/$ID/[None]" Name="$ID/[None]"/>\n'
                 '  </RootCellStyleGroup>')
    lines.append('</idPkg:Styles>\n')
    return "\n".join(lines)


def graphic_xml(colors):
    lines = [XML_HEAD + '<idPkg:Graphic xmlns:idPkg="%s" DOMVersion="%s">'
             % (PKG_NS, DOM_VERSION)]
    lines.append(
        '  <Color Self="Color/Black" Model="Process" Space="CMYK" ColorValue="0 0 0 100" '
        'ColorOverride="Specialblack" AlternateSpace="NoAlternateColor" AlternateColorValue="" '
        'Name="Black" ColorEditable="false" ColorRemovable="false" Visible="true" '
        'SwatchCreatorID="7937"/>\n'
        '  <Color Self="Color/Paper" Model="Process" Space="CMYK" ColorValue="0 0 0 0" '
        'ColorOverride="Specialpaper" AlternateSpace="NoAlternateColor" AlternateColorValue="" '
        'Name="Paper" ColorEditable="true" ColorRemovable="false" Visible="true" '
        'SwatchCreatorID="7937"/>\n'
        '  <Color Self="Color/Registration" Model="Registration" Space="CMYK" '
        'ColorValue="100 100 100 100" ColorOverride="Specialregistration" '
        'AlternateSpace="NoAlternateColor" AlternateColorValue="" Name="Registration" '
        'ColorEditable="false" ColorRemovable="false" Visible="true" SwatchCreatorID="7937"/>')
    for color in colors:
        lines.append(
            '  <Color Self=%s Model="%s" Space="%s" ColorValue="%s" ColorOverride="Normal" '
            'AlternateSpace="NoAlternateColor" AlternateColorValue="" Name=%s '
            'ColorEditable="true" ColorRemovable="true" Visible="true" SwatchCreatorID="7937"/>'
            % (quoteattr(color["self"]), color["model"], color["space"],
               " ".join(num(v) for v in color["values"]), quoteattr(color["name"])))
    for name, angle, density, order in (("Cyan", 75, 0.61, 1), ("Magenta", 15, 0.76, 2),
                                         ("Yellow", 0, 0.16, 3), ("Black", 45, 1.7, 4)):
        lines.append(
            '  <Ink Self="Ink/$ID/Process %s" Name="$ID/Process %s" Angle="%s" '
            'ConvertToProcess="false" Frequency="70" NeutralDensity="%s" PrintInk="true" '
            'TrapOrder="%s" InkType="Normal"/>' % (name, name, angle, density, order))
    lines.append('  <Swatch Self="Swatch/None" Name="None" ColorEditable="false" '
                 'ColorRemovable="false" Visible="true" SwatchCreatorID="7937"/>')
    lines.append('  <StrokeStyle Self="StrokeStyle/$ID/Solid" Name="$ID/Solid"/>')
    lines.append('</idPkg:Graphic>\n')
    return "\n".join(lines)


def preferences_xml(s):
    units = {"mm": "Millimeters", "pt": "Points", "cm": "Centimeters",
             "in": "Inches", "pica": "Picas"}.get(s["units"], "Millimeters")
    return (XML_HEAD +
            '<idPkg:Preferences xmlns:idPkg="%s" DOMVersion="%s">\n'
            '  <DocumentPreference PageHeight="%s" PageWidth="%s" PagesPerDocument="1" '
            'FacingPages="%s" DocumentBleedTopOffset="%s" DocumentBleedBottomOffset="%s" '
            'DocumentBleedInsideOrLeftOffset="%s" DocumentBleedOutsideOrRightOffset="%s" '
            'DocumentBleedUniformSize="true" PageBinding="LeftToRight" AllowPageShuffle="true" '
            'ColumnGuideLocked="true" PageOrientation="%s"/>\n'
            '  <MarginPreference ColumnCount="%d" ColumnGutter="%s" Top="%s" Bottom="%s" '
            'Left="%s" Right="%s" ColumnDirection="Horizontal"/>\n'
            '  <ViewPreference HorizontalMeasurementUnits="%s" VerticalMeasurementUnits="%s"/>\n'
            '</idPkg:Preferences>\n'
            % (PKG_NS, DOM_VERSION, num(s["height"]), num(s["width"]),
               "true" if s["facing"] else "false",
               num(s["bleed"]), num(s["bleed"]), num(s["bleed"]), num(s["bleed"]),
               "Landscape" if s["width"] > s["height"] else "Portrait",
               s["columns"], num(s["gutter"]), num(s["top"]), num(s["bottom"]),
               num(s["inside"]), num(s["outside"]), units, units))


def margin_pref(s, left_page=False):
    left, right = (s["outside"], s["inside"]) if left_page else (s["inside"], s["outside"])
    return ('<MarginPreference ColumnCount="%d" ColumnGutter="%s" Top="%s" Bottom="%s" '
            'Left="%s" Right="%s" ColumnDirection="Horizontal"/>'
            % (s["columns"], num(s["gutter"]), num(s["top"]), num(s["bottom"]),
               num(left), num(right)))


def page_xml(self_ref, name, s, transform, left_page=False, master=None, pad="    "):
    applied = ' AppliedMaster="%s"' % master if master else ""
    return ('%s<Page Self="%s" Name="%s"%s GeometricBounds="0 0 %s %s" ItemTransform="%s" '
            'MasterPageTransform="1 0 0 1 0 0" OverrideList="" TabOrder="" '
            'GridStartingPoint="TopOutside" UseMasterGrid="true">\n'
            '%s  <Properties><PageColor type="enumeration">UseMasterColor</PageColor></Properties>\n'
            '%s  %s\n%s</Page>'
            % (pad, self_ref, name, applied, num(s["height"]), num(s["width"]), transform,
               pad, pad, margin_pref(s, left_page), pad))


def master_spread_xml(s):
    if s["facing"]:
        pages = "\n".join([
            page_xml("uMasterL", "A", s, "1 0 0 1 %s 0" % num(-s["width"]), left_page=True),
            page_xml("uMasterR", "A", s, "1 0 0 1 0 0"),
        ])
        count = 2
    else:
        pages = page_xml("uMasterR", "A", s, "1 0 0 1 0 0")
        count = 1
    return (XML_HEAD +
            '<idPkg:MasterSpread xmlns:idPkg="%s" DOMVersion="%s">\n'
            '  <MasterSpread Self="uMaster" Name="A-Master" NamePrefix="A" BaseName="Master" '
            'ShowMasterItems="true" PageCount="%d" OverriddenPageItemProps="" '
            'ItemTransform="1 0 0 1 0 0">\n'
            '    <Properties><PageColor type="enumeration">UseMasterColor</PageColor></Properties>\n'
            '%s\n  </MasterSpread>\n</idPkg:MasterSpread>\n'
            % (PKG_NS, DOM_VERSION, count, pages))


def spread_xml(s):
    top, left = s["top"], s["inside"]
    bottom, right = s["height"] - s["bottom"], s["width"] - s["outside"]
    corners = [(left, top), (left, bottom), (right, bottom), (right, top)]
    points = "\n".join(
        '              <PathPointType Anchor="{0} {1}" LeftDirection="{0} {1}" '
        'RightDirection="{0} {1}"/>'.format(num(x), num(y)) for x, y in corners)
    return (XML_HEAD +
            '<idPkg:Spread xmlns:idPkg="%s" DOMVersion="%s">\n'
            '  <Spread Self="uSpread1" PageCount="1" BindingLocation="0" ShowMasterItems="true" '
            'AllowPageShuffle="true" ItemTransform="1 0 0 1 0 0" FlattenerOverride="Default">\n'
            '%s\n'
            '    <TextFrame Self="uFrame1" ParentStory="uStory1" PreviousTextFrame="n" '
            'NextTextFrame="n" ContentType="TextType" ItemLayer="uLayer1" '
            'ItemTransform="1 0 0 1 0 0">\n'
            '      <Properties>\n        <PathGeometry>\n'
            '          <GeometryPathType PathOpen="false">\n            <PathPointArray>\n'
            '%s\n            </PathPointArray>\n          </GeometryPathType>\n'
            '        </PathGeometry>\n      </Properties>\n'
            '      <TextFramePreference TextColumnCount="%d" TextColumnGutter="%s"/>\n'
            '    </TextFrame>\n  </Spread>\n</idPkg:Spread>\n'
            % (PKG_NS, DOM_VERSION,
               page_xml("uPage1", "1", s, "1 0 0 1 0 0", master="uMaster"),
               points, s["columns"], num(s["gutter"])))


def story_xml(paragraph_styles, default_self, specimen):
    paragraphs = []
    if specimen and paragraph_styles:
        for style in paragraph_styles:
            label = " > ".join(style["_path"])
            sample = style.get("sample_text") or (
                "%s. The quick brown fox jumps over the lazy dog." % label)
            paragraphs.append(
                '    <ParagraphStyleRange AppliedParagraphStyle=%s>\n'
                '      <CharacterStyleRange AppliedCharacterStyle="%s">\n'
                '        <Content>%s</Content>\n        <Br/>\n'
                '      </CharacterStyleRange>\n    </ParagraphStyleRange>'
                % (quoteattr(style["_self"]), NO_CHAR, escape(sample)))
    else:
        paragraphs.append(
            '    <ParagraphStyleRange AppliedParagraphStyle=%s>\n'
            '      <CharacterStyleRange AppliedCharacterStyle="%s"/>\n'
            '    </ParagraphStyleRange>' % (quoteattr(default_self), NO_CHAR))
    return (XML_HEAD +
            '<idPkg:Story xmlns:idPkg="%s" DOMVersion="%s">\n'
            '  <Story Self="uStory1" AppliedTOCStyle="n" TrackChanges="false" '
            'StoryTitle="$ID/" AppliedNamedGrid="n">\n'
            '    <StoryPreference OpticalMarginAlignment="false" OpticalMarginSize="12" '
            'FrameType="TextFrameType" StoryOrientation="Horizontal" '
            'StoryDirection="LeftToRightDirection"/>\n'
            '    <InCopyExportOption IncludeGraphicProxies="true" IncludeAllResources="false"/>\n'
            '%s\n  </Story>\n</idPkg:Story>\n'
            % (PKG_NS, DOM_VERSION, "\n".join(paragraphs)))


def designmap_xml(name):
    return (XML_HEAD +
            '<?aid style="50" type="document" readerVersion="6.0" featureSet="257" '
            'product="8.0(370)" ?>\n'
            '<Document xmlns:idPkg="%s" DOMVersion="%s" Self="d" StoryList="uStory1" '
            'Name=%s ZeroPoint="0 0" ActiveLayer="uLayer1" '
            'CMYKProfile="Coated FOGRA39 (ISO 12647-2:2004)" RGBProfile="sRGB IEC61966-2.1" '
            'SolidColorIntent="UseColorSettings" AfterBlendingIntent="UseColorSettings" '
            'DefaultImageIntent="UseColorSettings" RGBPolicy="PreserveEmbeddedProfiles" '
            'CMYKPolicy="CombinationOfPreserveAndSafeCmyk" AccurateLABSpots="false">\n'
            '  <idPkg:Graphic src="Resources/Graphic.xml"/>\n'
            '  <idPkg:Styles src="Resources/Styles.xml"/>\n'
            '  <idPkg:Preferences src="Resources/Preferences.xml"/>\n'
            '  <Layer Self="uLayer1" Name="Layer 1" Visible="true" Locked="false" '
            'IgnoreWrap="false" ShowGuides="true" LockGuides="false" UI="true" '
            'Expendable="true" Printable="true">\n'
            '    <Properties><LayerColor type="enumeration">LightBlue</LayerColor></Properties>\n'
            '  </Layer>\n'
            '  <idPkg:MasterSpread src="MasterSpreads/MasterSpread_uMaster.xml"/>\n'
            '  <idPkg:Spread src="Spreads/Spread_uSpread1.xml"/>\n'
            '  <Section Self="uSection1" Length="1" Name="" ContinueNumbering="true" '
            'IncludeSectionPrefix="false" Marker="" PageStart="uPage1" SectionPrefix="">\n'
            '    <Properties><PageNumberStyle type="enumeration">Arabic</PageNumberStyle>'
            '</Properties>\n  </Section>\n'
            '  <idPkg:Story src="Stories/Story_uStory1.xml"/>\n'
            '</Document>\n' % (PKG_NS, DOM_VERSION, quoteattr(name + ".indd")))


CONTAINER_XML = (XML_HEAD +
                 '<container version="1.0" '
                 'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
                 '  <rootfiles>\n'
                 '    <rootfile full-path="designmap.xml" media-type="text/xml"/>\n'
                 '  </rootfiles>\n</container>\n')


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def build(data, specimen=False):
    settings = load_document_settings(data)
    colors, refs = load_colors(data)
    paras, para_by_name = resolve_styles(data.get("paragraph_styles", []),
                                         "ParagraphStyle", "Paragraph")
    chars, char_by_name = resolve_styles(data.get("character_styles", []),
                                         "CharacterStyle", "Character")
    check_based_on(paras, para_by_name, "Paragraph")
    check_based_on(chars, char_by_name, "Character")
    for style in paras:
        if style.get("next_style") and style["next_style"] not in para_by_name:
            raise StyleSystemError("Paragraph style %r has unknown next_style %r"
                                   % (style["name"], style["next_style"]))
        for key, table in (("align", ALIGN), ("case", CASE), ("start", START),
                           ("list", LIST)):
            if key in style and style[key] not in table:
                raise StyleSystemError("%r: %s must be one of %s"
                                       % (style["name"], key, ", ".join(table)))
    for style in chars:
        for key, table in (("case", CASE), ("position", POSITION)):
            if key in style and style[key] not in table:
                raise StyleSystemError("%r: %s must be one of %s"
                                       % (style["name"], key, ", ".join(table)))

    default_name = settings["default_style"]
    if default_name:
        if default_name not in para_by_name:
            raise StyleSystemError("default_paragraph_style %r is not defined" % default_name)
        default_self = para_by_name[default_name]["_self"]
    else:
        default_self = BASIC_PARA

    files = [
        ("META-INF/container.xml", CONTAINER_XML),
        ("designmap.xml", designmap_xml(data.get("name", "Template"))),
        ("Resources/Graphic.xml", graphic_xml(colors)),
        ("Resources/Styles.xml", styles_xml(paras, para_by_name, chars, char_by_name, refs)),
        ("Resources/Preferences.xml", preferences_xml(settings)),
        ("MasterSpreads/MasterSpread_uMaster.xml", master_spread_xml(settings)),
        ("Spreads/Spread_uSpread1.xml", spread_xml(settings)),
        ("Stories/Story_uStory1.xml", story_xml(paras, default_self, specimen)),
    ]
    return files, {"paragraph": len(paras), "character": len(chars), "colors": len(colors)}


def write_idml(files, path):
    with zipfile.ZipFile(path, "w") as zf:
        # The mimetype entry must be first and stored without compression.
        zf.writestr(zipfile.ZipInfo("mimetype"), "application/vnd.adobe.indesign-idml-package",
                    compress_type=zipfile.ZIP_STORED)
        for name, content in files:
            zf.writestr(name, content.encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED)


def list_estimates(data):
    notes = []
    for key in ("paragraph_styles", "character_styles", "colors"):
        for item in data.get(key, []):
            estimated = item.get("estimated")
            if estimated:
                fields = ", ".join(estimated) if isinstance(estimated, list) else "values"
                notes.append("  - %s: %s" % (item.get("name"), fields))
    return notes


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build an InDesign .idml template "
                                                 "from a style-system JSON file.")
    parser.add_argument("style_system", help="Path to the style-system JSON file")
    parser.add_argument("-o", "--output", required=True, help="Output .idml path")
    parser.add_argument("--specimen", action="store_true",
                        help="Add one sample paragraph per paragraph style")
    args = parser.parse_args(argv)

    try:
        with open(args.style_system, encoding="utf-8") as fh:
            data = json.load(fh)
        files, counts = build(data, specimen=args.specimen)
    except (OSError, ValueError, KeyError, StyleSystemError) as exc:
        print("Error: %s" % exc, file=sys.stderr)
        return 1

    write_idml(files, args.output)
    print("Wrote %s: %d paragraph styles, %d character styles, %d colours."
          % (args.output, counts["paragraph"], counts["character"], counts["colors"]))
    estimates = list_estimates(data)
    if estimates:
        print("Estimated values to check in InDesign:")
        print("\n".join(estimates))
    return 0


if __name__ == "__main__":
    sys.exit(main())
