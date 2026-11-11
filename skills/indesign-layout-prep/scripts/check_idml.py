#!/usr/bin/env python3
"""
check_idml.py - Structural check of an .idml package before handing it over.

InDesign is not available to Claude, so this catches the mistakes that would
make InDesign refuse or damage the file:

  * package: `mimetype` first and uncompressed, every XML part well formed,
    every part listed in designmap.xml present;
  * ids: no duplicate Self ids;
  * references: every applied paragraph/character/cell/table style, colour,
    master page, layer, parent story and threaded frame exists;
  * stories: StoryList matches the story parts; text frame chains are linked
    both ways; sections start on an existing page and cover every page.

    python3 check_idml.py file.idml [more.idml ...]

Exit code 0 = no errors. Only the Python 3 standard library is used.
"""

import posixpath
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

REF_ATTRS = {
    "AppliedParagraphStyle": "style", "AppliedCharacterStyle": "style",
    "AppliedCellStyle": "style", "AppliedTableStyle": "style",
    "HeaderRegionCellStyle": "style", "BodyRegionCellStyle": "style",
    "FillColor": "color", "StrokeColor": "color", "BottomEdgeStrokeColor": "color",
    "TopEdgeStrokeColor": "color", "LeftEdgeStrokeColor": "color",
    "RightEdgeStrokeColor": "color", "TopBorderStrokeColor": "color",
    "BottomBorderStrokeColor": "color", "LeftBorderStrokeColor": "color",
    "RightBorderStrokeColor": "color", "AppliedMaster": "any", "ItemLayer": "any",
    "ParentStory": "any", "NextTextFrame": "any", "PreviousTextFrame": "any",
}
BUILTIN_OK = {"n", "$ID/[None]", "ParagraphStyle/$ID/[No paragraph style]",
              "CharacterStyle/$ID/[No character style]", "CellStyle/$ID/[None]",
              "TableStyle/$ID/[Basic Table]", "TableStyle/$ID/[No table style]",
              "ParagraphStyle/$ID/NormalParagraphStyle", "Swatch/None", "Color/Black",
              "Color/Paper", "Color/Registration"}


def local(tag):
    return tag.rsplit("}", 1)[-1]


def check(path):
    errors, warnings = [], []
    try:
        zf = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        return ["cannot open: %s" % exc], []
    infos = zf.infolist()
    if not infos or infos[0].filename != "mimetype" or infos[0].compress_type != zipfile.ZIP_STORED:
        errors.append("'mimetype' must be the first entry, stored without compression")
    names = set(zf.namelist())
    if "designmap.xml" not in names:
        return errors + ["no designmap.xml"], warnings

    trees = {}
    for name in sorted(names):
        if name.endswith(".xml"):
            try:
                trees[name] = ET.fromstring(zf.read(name))
            except ET.ParseError as exc:
                errors.append("%s is not well-formed XML: %s" % (name, exc))
    if errors:
        return errors, warnings

    designmap = zf.read("designmap.xml").decode("utf-8")
    for src in re.findall(r'<idPkg:\w+\s+src="([^"]+)"', designmap):
        if posixpath.normpath(src) not in names:
            errors.append("designmap.xml lists %s, which is not in the package" % src)

    selfs, kinds = {}, {}
    for name, root in trees.items():
        for el in root.iter():
            sid = el.get("Self")
            if not sid:
                continue
            if sid in selfs and local(el.tag) not in ("Properties",):
                errors.append("duplicate Self id %r (%s and %s)" % (sid, selfs[sid], name))
            selfs[sid] = name
            kinds[sid] = local(el.tag)

    for name, root in trees.items():
        for el in root.iter():
            for attr, kind in REF_ATTRS.items():
                value = el.get(attr)
                if not value or value in BUILTIN_OK or value in selfs:
                    continue
                if kind == "color" and value.startswith("Swatch/"):
                    continue
                errors.append("%s: %s=%r on <%s> points to nothing"
                              % (name, attr, value, local(el.tag)))
            for prop in ("BasedOn", "NextStyle"):
                if local(el.tag) == prop and el.get("type") == "object" and el.text \
                        and el.text not in selfs and el.text not in BUILTIN_OK:
                    errors.append("%s: %s %r points to nothing" % (name, prop, el.text))

    # Stories
    doc = trees["designmap.xml"]
    story_list = (doc.get("StoryList") or "").split()
    story_selfs = [sid for sid, k in kinds.items() if k == "Story"]
    for sid in story_selfs:
        if sid not in story_list:
            warnings.append("story %s is not in the StoryList" % sid)
    for sid in story_list:
        if sid not in selfs:
            errors.append("StoryList names %s, which does not exist" % sid)

    # Frames and threads
    frames = {}
    for name, root in trees.items():
        for el in root.iter():
            if local(el.tag) == "TextFrame":
                frames[el.get("Self")] = el
    for fid, el in frames.items():
        nxt, prev = el.get("NextTextFrame", "n"), el.get("PreviousTextFrame", "n")
        if nxt != "n" and (nxt not in frames or frames[nxt].get("PreviousTextFrame") != fid):
            errors.append("frame %s -> %s is not linked back" % (fid, nxt))
        if prev != "n" and (prev not in frames or frames[prev].get("NextTextFrame") != fid):
            errors.append("frame %s <- %s is not linked forward" % (fid, prev))
        if nxt != "n" and frames.get(nxt) is not None and \
                frames[nxt].get("ParentStory") != el.get("ParentStory"):
            errors.append("frames %s and %s are threaded but belong to different stories"
                          % (fid, nxt))

    # Pages and sections
    page_ids = []
    for name in re.findall(r'<idPkg:Spread\s+src="([^"]+)"', designmap):
        root = trees.get(posixpath.normpath(name))
        if root is not None:
            page_ids += [p.get("Self") for p in root.iter() if local(p.tag) == "Page"]
    sections = [el for el in doc if local(el.tag) == "Section"]
    if page_ids:
        if not sections:
            warnings.append("no Section: InDesign will number pages by default")
        total = 0
        for sec in sections:
            if sec.get("PageStart") not in page_ids:
                errors.append("Section %s starts on %r, which is not a page"
                              % (sec.get("Self"), sec.get("PageStart")))
            total += int(sec.get("Length", "0"))
        if sections and total != len(page_ids):
            warnings.append("sections cover %d pages but the document has %d"
                            % (total, len(page_ids)))

    # Tables
    for name, root in trees.items():
        for table in root.iter():
            if local(table.tag) != "Table":
                continue
            rows = int(table.get("HeaderRowCount", 0)) + int(table.get("BodyRowCount", 0)) + \
                int(table.get("FooterRowCount", 0))
            cols = int(table.get("ColumnCount", 0))
            row_els = [c for c in table if local(c.tag) == "Row"]
            col_els = [c for c in table if local(c.tag) == "Column"]
            if row_els and len(row_els) != rows:
                errors.append("table %s declares %d rows but has %d" % (table.get("Self"), rows,
                                                                        len(row_els)))
            if col_els and len(col_els) != cols:
                errors.append("table %s declares %d columns but has %d"
                              % (table.get("Self"), cols, len(col_els)))
            covered = set()
            for cell in table:
                if local(cell.tag) != "Cell":
                    continue
                c, r = [int(v) for v in cell.get("Name", "0:0").split(":")]
                for dc in range(int(cell.get("ColumnSpan", 1))):
                    for dr in range(int(cell.get("RowSpan", 1))):
                        key = (c + dc, r + dr)
                        if key in covered:
                            errors.append("table %s: cell %d:%d overlaps another cell"
                                          % (table.get("Self"), key[0], key[1]))
                        covered.add(key)
            if len(covered) != rows * cols:
                errors.append("table %s: cells cover %d of %d positions"
                              % (table.get("Self"), len(covered), rows * cols))
    return errors, warnings


def main(argv):
    if not argv:
        print(__doc__.strip())
        return 2
    failed = False
    for path in argv:
        errors, warnings = check(path)
        for e in errors:
            print("%s: error: %s" % (path, e))
        for w in warnings:
            print("%s: warning: %s" % (path, w))
        if errors:
            failed = True
        else:
            print("%s: OK%s" % (path, " with %d warning(s)" % len(warnings) if warnings else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
