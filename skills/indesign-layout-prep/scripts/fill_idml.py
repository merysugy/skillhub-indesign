#!/usr/bin/env python3
"""
fill_idml.py - Route B: lay out a Word document inside the user's own IDML.

The user's IDML keeps its styles, swatches, master pages and resources. This
script adds the Word content as a new threaded story, styled with the user's
own styles, on new pages that use one of their master pages.

    python3 fill_idml.py their.idml style-system.json content.docx -o laid-out.idml
    python3 fill_idml.py their.idml style-system.json content.docx -o out.idml --master "B-Content"

style-system.json is the output of extract_idml.py on the same IDML, plus a
`roles` block naming which of the user's styles to use for body, title,
headings, lists, emphasis... (see the schema) and, optionally, a `tables`
block. Style names in roles can be "Style" or "Group:Style".

Existing pages:
  * If the IDML only has empty pages (a template), they are replaced.
  * If it already has text, the new pages are added after the existing ones
    and nothing is removed (use --replace-pages to replace them anyway when
    no other part of the document refers to their stories).

The original file is never modified. Only the Python 3 standard library is used.
"""

import argparse
import json
import os
import posixpath
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from xml.sax.saxutils import quoteattr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import idml_content  # noqa: E402
import build_idml  # noqa: E402

PKG_NS = "http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging"
MM = 72.0 / 25.4


class FillError(Exception):
    pass


def local(tag):
    return tag.rsplit("}", 1)[-1]


def attr_of(xml, name):
    m = re.search(r'\b%s="([^"]*)"' % name, xml)
    return m.group(1) if m else None


class Package(object):
    def __init__(self, path):
        with zipfile.ZipFile(path) as zf:
            self.order = zf.namelist()
            self.files = {n: zf.read(n) for n in self.order}
        if "designmap.xml" not in self.files:
            raise FillError("%s has no designmap.xml: is it an IDML file?" % path)
        self.designmap = self.files["designmap.xml"].decode("utf-8")

    def text(self, name):
        return self.files[name].decode("utf-8")

    def parts(self, kind):
        return [posixpath.normpath(m) for m in
                re.findall(r'<idPkg:%s\s+src="([^"]+)"\s*/>' % kind, self.designmap)]

    def all_selfs(self):
        found = set()
        for name, data in self.files.items():
            if name.endswith(".xml"):
                found.update(re.findall(r'\bSelf="([^"]+)"', data.decode("utf-8", "replace")))
        return found


def style_index(styles_xml):
    """Name lookups -> Self for paragraph, character, table and cell styles."""
    root = ET.fromstring(styles_xml)
    index = {"ParagraphStyle": {}, "CharacterStyle": {}, "TableStyle": {}, "CellStyle": {}}
    for el in root.iter():
        kind = local(el.tag)
        if kind in index and el.get("Self"):
            full = el.get("Name", "")
            index[kind][full] = el.get("Self")
            index[kind].setdefault(full.split(":")[-1], el.get("Self"))
    return index


def color_index(graphic_xml):
    names = dict(build_idml.BUILTIN_COLORS)
    if graphic_xml:
        for el in ET.fromstring(graphic_xml):
            if local(el.tag) in ("Color", "Tint", "Swatch") and el.get("Name") and el.get("Self"):
                names[el.get("Name").replace("$ID/", "")] = el.get("Self")
    return names


def masters(pkg):
    found = []
    for part in pkg.parts("MasterSpread"):
        xml = pkg.text(part)
        root = ET.fromstring(xml)
        for ms in root.iter("MasterSpread"):
            page = ms.find("Page")
            margin = page.find("MarginPreference") if page is not None else None
            found.append({"self": ms.get("Self"), "name": ms.get("Name", ""), "margin": margin,
                          "bounds": page.get("GeometricBounds") if page is not None else None})
    return found


def geometry(pkg, data, master):
    prefs = None
    for part in pkg.parts("Preferences"):
        prefs = ET.fromstring(pkg.files[part])
    doc_pref = prefs.find("DocumentPreference") if prefs is not None else None
    if doc_pref is not None:
        width = float(doc_pref.get("PageWidth", 595.276))
        height = float(doc_pref.get("PageHeight", 841.89))
        facing = doc_pref.get("FacingPages") == "true"
    else:
        width, height, facing = 595.276, 841.89, False
    if master["bounds"]:
        b = [float(v) for v in master["bounds"].split()]
        height, width = b[2] - b[0], b[3] - b[1]
    mp = master["margin"]
    if mp is None and prefs is not None:
        mp = prefs.find("MarginPreference")
    get = (lambda k, d: float(mp.get(k, d))) if mp is not None else (lambda k, d: d)
    columns = int(get("ColumnCount", 1))
    doc = data.get("document", {})
    return {"width": width, "height": height, "facing": facing,
            "top": get("Top", 36), "bottom": get("Bottom", 36),
            "inside": get("Left", 36), "outside": get("Right", 36),
            "columns": columns, "gutter": get("ColumnGutter", 12),
            "frame_columns": int(doc.get("text_frame_columns", columns))}


def existing_pages(pkg):
    """Spread parts, their pages and stories, and whether any story has text."""
    spreads, story_ids, page_count = [], set(), 0
    for part in pkg.parts("Spread"):
        xml = pkg.text(part)
        spreads.append(part)
        page_count += len(re.findall(r"<Page\s", xml))
        story_ids.update(re.findall(r'ParentStory="([^"]+)"', xml))
    has_text = False
    for part in pkg.parts("Story"):
        xml = pkg.text(part)
        sid = attr_of(xml[xml.find("<Story"):], "Self")
        if sid in story_ids and re.search(r"<Content>[^<]*\S[^<]*</Content>", xml):
            has_text = True
    return spreads, story_ids, page_count, has_text


def referenced_elsewhere(pkg, story_ids, spread_parts):
    """True if a story id appears outside its own story part and the spreads."""
    for name, data in pkg.files.items():
        if not name.endswith(".xml") or name in spread_parts:
            continue
        text = data.decode("utf-8", "replace")
        for sid in story_ids:
            if name == "Stories/Story_%s.xml" % sid:
                continue
            if re.search(r'"%s"' % re.escape(sid), text) and name != "designmap.xml":
                return True
            if name == "designmap.xml":
                cleaned = re.sub(r'StoryList="[^"]*"', "", text)
                cleaned = re.sub(r'<idPkg:Story\s+src="[^"]*"\s*/>', "", cleaned)
                if re.search(r'"%s"' % re.escape(sid), cleaned):
                    return True
    return False


class TheirRefs(object):
    """StyleRefs-like adapter over the user's own style names."""

    def __init__(self, index, roles, table_names):
        self.index, self.body = index, roles.get("body")
        self.table_names = table_names

    def _lookup(self, kind, name):
        table = self.index[kind]
        for key in (name, name.replace("/", ":")):
            if key in table:
                return table[key]
        raise FillError("%s %r is not in the IDML" % (kind, name))

    def para(self, name):
        return self._lookup("ParagraphStyle", name) if name else \
            "ParagraphStyle/$ID/NormalParagraphStyle"

    def char(self, name):
        return self._lookup("CharacterStyle", name) if name else idml_content.NO_CHAR

    def table_style(self):
        return self.table_names[0] if self.table_names else "TableStyle/$ID/[Basic Table]"

    def cell_style(self, header):
        if not self.table_names:
            return "CellStyle/$ID/[None]"
        return self.table_names[1] if header else self.table_names[2]


def table_styles(pkg, data, index, colors, styles_part):
    """Use the user's table style if it exists, otherwise add one built from `tables`."""
    cfg = data.get("tables")
    if not cfg:
        return None
    name = cfg.get("style_name", "Table")
    if name in index["TableStyle"]:
        header = index["CellStyle"].get(cfg.get("header_cell_style") or "%s header" % name,
                                        "CellStyle/$ID/[None]")
        body = index["CellStyle"].get(cfg.get("body_cell_style") or "%s body" % name,
                                      "CellStyle/$ID/[None]")
        return index["TableStyle"][name], header, body
    para_by_name = {}
    roles = data.get("roles") or {}
    for key in ("table_header", "table_body", "body"):
        if roles.get(key):
            para_by_name[roles[key]] = {"_self": TheirRefs(index, roles, None).para(roles[key])}
    names, xml = build_idml.table_styles_xml(data, para_by_name, colors)
    cell_xml, table_xml = xml
    styles = pkg.text(styles_part)
    for closing, extra in (("</RootCellStyleGroup>", cell_xml),
                           ("</RootTableStyleGroup>", table_xml)):
        if closing in styles:
            styles = styles.replace(closing, extra + "\n  " + closing, 1)
        else:
            root_tag = closing.strip("</>")
            styles = styles.replace("</idPkg:Styles>", '  <%s Self="ucl%s">\n%s\n  </%s>\n'
                                    "</idPkg:Styles>" % (root_tag, root_tag, extra, root_tag), 1)
    pkg.files[styles_part] = styles.encode("utf-8")
    return names


def fill(idml_path, data, docx_path, master_name=None, replace=False):
    pkg = Package(idml_path)
    dom = attr_of(pkg.designmap[pkg.designmap.find("<Document"):], "DOMVersion") or "8.0"
    styles_part = (pkg.parts("Styles") or [None])[0]
    if not styles_part:
        raise FillError("The IDML has no Styles part")
    index = style_index(pkg.files[styles_part])
    graphic_part = (pkg.parts("Graphic") or [None])[0]
    colors = color_index(pkg.files[graphic_part] if graphic_part else None)

    roles = data.get("roles") or {}
    refs = TheirRefs(index, roles, None)
    for key, value in roles.items():  # fail early on unknown names
        if key in ("body", "lead", "title", "subtitle", "heading", "bullet", "numbered", "quote",
                   "table_header", "table_body") and value:
            refs.para(value)
        if key in ("bold", "italic", "bold_italic", "superscript", "hashtag") and value:
            refs.char(value)

    all_masters = masters(pkg)
    if not all_masters:
        raise FillError("The IDML has no master pages")
    master = all_masters[0]
    if master_name:
        matches = [m for m in all_masters if m["name"] == master_name]
        if not matches:
            raise FillError("No master named %r. Masters: %s"
                            % (master_name, ", ".join(m["name"] for m in all_masters)))
        master = matches[0]
    geom = geometry(pkg, data, master)

    classifier = idml_content.Classifier(data)
    items = classifier.classify(idml_content.read_docx(docx_path))
    pages, column_width = idml_content.pages_needed(items, data, geom)

    old_spreads, old_stories, old_page_count, has_text = existing_pages(pkg)
    mode = "replace" if (old_spreads and (not has_text or replace)) else "append"
    if not old_spreads:
        mode = "new"
    notes = []
    if mode == "replace" and referenced_elsewhere(pkg, old_stories, old_spreads):
        mode = "append"
        notes.append("Existing pages are referenced elsewhere in the document (XML structure, "
                     "hyperlinks, TOC...): kept them and added the new pages after them.")
    if mode == "append" and has_text:
        notes.append("The IDML already has text: the new pages were added after page %d. "
                     "Delete the old pages in InDesign if you don't need them."
                     % old_page_count)

    refs.table_names = table_styles(pkg, data, index, colors, styles_part)
    ids = idml_content.Ids("ucl", pkg.all_selfs())
    story_self = ids.next("story")
    layer = attr_of(pkg.designmap[pkg.designmap.find("<Document"):], "ActiveLayer") or \
        attr_of(pkg.designmap[pkg.designmap.find("<Layer"):], "Self")
    metrics = idml_content.resolve_metrics(data)
    body_m = metrics(roles.get("body"))
    table_width = column_width - float(body_m["left_indent_pt"]) - float(body_m["right_indent_pt"])
    body = idml_content.story_body(items, refs, ids, table_width, metrics,
                                   data.get("tables") or {})
    spreads, page_selfs = idml_content.spreads_xml(
        geom, pages, master["self"], layer, story_self, ids, dom, PKG_NS, geom["facing"])

    dm = pkg.designmap
    spread_entries = "\n".join('\t<idPkg:Spread src="Spreads/Spread_%s.xml"/>' % s for s, _ in spreads)
    if mode == "replace":
        for part in old_spreads:
            pkg.files.pop(part, None)
        dm = re.sub(r'[ \t]*<idPkg:Spread\s+src="[^"]+"\s*/>\s*\n?', "", dm)
        for sid in old_stories:
            pkg.files.pop("Stories/Story_%s.xml" % sid, None)
            dm = re.sub(r'[ \t]*<idPkg:Story\s+src="Stories/Story_%s\.xml"\s*/>\s*\n?'
                        % re.escape(sid), "", dm)
        dm = re.sub(r'StoryList="([^"]*)"', lambda m: 'StoryList="%s"' % " ".join(
            s for s in m.group(1).split() if s not in old_stories), dm, count=1)
        dm = re.sub(r"[ \t]*<Section\b[^>]*?(/>|>.*?</Section>)\s*\n?", "", dm, flags=re.S)
    section = ('\t<Section Self="%s" Length="%d" Name="" ContinueNumbering="true" '
               'IncludeSectionPrefix="false" Marker="" PageStart="%s" SectionPrefix="">'
               '<Properties><PageNumberStyle type="enumeration">Arabic</PageNumberStyle>'
               '</Properties></Section>' % (ids.next("sec"), pages, page_selfs[0]))
    if mode == "append":
        # Extend the last section so it covers the new pages.
        sections = list(re.finditer(r'<Section\b[^>]*\bLength="(\d+)"', dm))
        if sections:
            last = sections[-1]
            new_len = int(last.group(1)) + pages
            dm = dm[:last.start(1)] + str(new_len) + dm[last.end(1):]
            section = ""
    anchor = list(re.finditer(r'<idPkg:(?:Spread|MasterSpread)\s+src="[^"]+"\s*/>', dm))
    insert_at = anchor[-1].end() if anchor else dm.index("</Document>")
    dm = dm[:insert_at] + "\n" + spread_entries + ("\n" + section if section else "") + dm[insert_at:]
    story_entry = '\t<idPkg:Story src="Stories/Story_%s.xml"/>\n' % story_self
    dm = dm.replace("</Document>", story_entry + "</Document>", 1)
    if re.search(r'StoryList="', dm):
        dm = re.sub(r'StoryList="([^"]*)"',
                    lambda m: 'StoryList="%s"' % (m.group(1) + " " + story_self).strip(), dm, count=1)
    pkg.files["designmap.xml"] = dm.encode("utf-8")
    for spread_self, xml in spreads:
        pkg.files["Spreads/Spread_%s.xml" % spread_self] = xml.encode("utf-8")
    pkg.files["Stories/Story_%s.xml" % story_self] = \
        idml_content.story_xml(story_self, body, dom, PKG_NS).encode("utf-8")
    report = idml_content.report_lines(classifier.report, pages)
    report.insert(0, "Master page: %s | existing pages: %s" % (master["name"], {
        "replace": "replaced (they were empty)" if not has_text else "replaced",
        "append": "kept", "new": "none"}[mode]))
    return pkg, report + ["Note: " + n for n in notes]


def write(pkg, path):
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(zipfile.ZipInfo("mimetype"), pkg.files.get(
            "mimetype", b"application/vnd.adobe.indesign-idml-package"),
            compress_type=zipfile.ZIP_STORED)
        written = {"mimetype"}
        for name in pkg.order + sorted(pkg.files):
            if name in written or name not in pkg.files:
                continue
            zf.writestr(name, pkg.files[name], compress_type=zipfile.ZIP_DEFLATED)
            written.add(name)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Lay out a Word document inside an existing IDML.")
    parser.add_argument("idml", help="The user's IDML (template or document)")
    parser.add_argument("style_system", help="style-system JSON with a roles block")
    parser.add_argument("docx", help="Word document to lay out")
    parser.add_argument("-o", "--output", required=True, help="New .idml to write")
    parser.add_argument("--master", help="Master page name to apply (default: the first one)")
    parser.add_argument("--replace-pages", action="store_true",
                        help="Replace existing pages even if they contain text")
    args = parser.parse_args(argv)
    if os.path.abspath(args.output) == os.path.abspath(args.idml):
        print("Error: write to a new file, not over the original IDML", file=sys.stderr)
        return 1
    try:
        with open(args.style_system, encoding="utf-8") as fh:
            data = json.load(fh)
        pkg, report = fill(args.idml, data, args.docx, args.master, args.replace_pages)
    except (OSError, ValueError, KeyError, FillError, idml_content.ContentError,
            build_idml.StyleSystemError, zipfile.BadZipFile, ET.ParseError) as exc:
        print("Error: %s" % exc, file=sys.stderr)
        return 1
    write(pkg, args.output)
    print("Wrote %s" % args.output)
    print("\n".join(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
