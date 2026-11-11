"""
idml_content.py - Shared code for placing Word content inside an IDML package.

Used by build_idml.py (route A: new template + content) and fill_idml.py
(route B: the user's own IDML + content). It:

  1. reads a .docx (paragraphs, runs with bold/italic/superscript, real Word
     lists, tables with header rows and merged cells) - standard library only;
  2. classifies every paragraph into the roles of the style system
     (`roles` block of style-system.json): title, subtitle, lead, headings,
     body, lists, quotes, table text, emphasis, hashtags;
  3. writes the IDML story (styled text and tables);
  4. estimates how many pages the text needs and writes the spreads with
     threaded text frames.

The page count is an estimate: InDesign composes the text, not this script.
One spare page is added; anything that does not fit stays as overset text.
"""

import math
import re
import zipfile
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape, quoteattr

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MM_TO_PT = 72.0 / 25.4

BULLET_RE = re.compile(u"^\\s*[\\-–—•●▪\\*]\\s+")
NUMBER_RE = re.compile(r"^\s*\d{1,3}[\.\)]\s+")
HASHTAG_RE = re.compile(r"#(\w+)", re.UNICODE)
INVALID_XML = re.compile(u"[\x00-\x08\x0B\x0C\x0E-\x1F]")

NO_CHAR = "CharacterStyle/$ID/[No character style]"


class ContentError(Exception):
    pass


def num(value):
    text = ("%.4f" % float(value)).rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def local(tag):
    return tag.rsplit("}", 1)[-1]


# --------------------------------------------------------------------------
# 1. Read the .docx
# --------------------------------------------------------------------------

def _on(el):
    return el is not None and el.get(W + "val", "true").lower() not in ("0", "false", "off", "none")


def _style_names(zf, kind):
    names = {}
    try:
        root = ET.fromstring(zf.read("word/styles.xml"))
    except KeyError:
        return names
    for st in root.iter(W + "style"):
        if st.get(W + "type") != kind:
            continue
        sid = st.get(W + "styleId")
        name = st.find(W + "name")
        if sid:
            raw = name.get(W + "val") if name is not None else sid
            names[sid] = raw[:1].upper() + raw[1:]
    return names


def _numbering(zf):
    """numId -> {ilvl: 'bullet' | 'numbered'}"""
    try:
        root = ET.fromstring(zf.read("word/numbering.xml"))
    except KeyError:
        return {}
    abstract = {}
    for an in root.iter(W + "abstractNum"):
        levels = {}
        for lvl in an.iter(W + "lvl"):
            fmt = lvl.find(W + "numFmt")
            value = fmt.get(W + "val") if fmt is not None else "bullet"
            levels[lvl.get(W + "ilvl", "0")] = "bullet" if value in ("bullet", "none") else "numbered"
        abstract[an.get(W + "abstractNumId")] = levels
    result = {}
    for n in root.iter(W + "num"):
        ref = n.find(W + "abstractNumId")
        if ref is not None:
            result[n.get(W + "numId")] = abstract.get(ref.get(W + "val"), {})
    return result


def _runs(el):
    for child in el:
        tag = local(child.tag)
        if tag == "r":
            yield child
        elif tag in ("hyperlink", "ins", "smartTag", "sdt", "sdtContent", "fldSimple",
                     "customXml", "moveTo"):
            for r in _runs(child):
                yield r


def _read_paragraph(p, para_styles, char_styles, numbering):
    ppr = p.find(W + "pPr")
    style, list_type, indent, images = "Normal", None, 0.0, 0
    if ppr is not None:
        ps = ppr.find(W + "pStyle")
        if ps is not None:
            style = para_styles.get(ps.get(W + "val"), ps.get(W + "val"))
        numpr = ppr.find(W + "numPr")
        if numpr is not None and numpr.find(W + "numId") is not None:
            num_id = numpr.find(W + "numId").get(W + "val")
            ilvl = numpr.find(W + "ilvl")
            level = ilvl.get(W + "val") if ilvl is not None else "0"
            if num_id != "0":
                list_type = numbering.get(num_id, {}).get(level, "bullet")
        ind = ppr.find(W + "ind")
        if ind is not None:
            raw = ind.get(W + "left") or ind.get(W + "start")
            try:
                indent = int(raw) / 20.0
            except (TypeError, ValueError):
                indent = 0.0
    runs = []
    for r in _runs(p):
        rpr = r.find(W + "rPr")
        bold = italic = sup = False
        if rpr is not None:
            bold = _on(rpr.find(W + "b"))
            italic = _on(rpr.find(W + "i"))
            va = rpr.find(W + "vertAlign")
            sup = va is not None and va.get(W + "val") == "superscript"
            rs = rpr.find(W + "rStyle")
            if rs is not None:
                cname = char_styles.get(rs.get(W + "val"), rs.get(W + "val")).lower()
                bold = bold or "strong" in cname or "bold" in cname or "negrita" in cname
                italic = italic or "emphasis" in cname or "italic" in cname or "nfasis" in cname
        parts = []
        for child in r:
            tag = local(child.tag)
            if tag == "t":
                parts.append(child.text or "")
            elif tag == "tab":
                parts.append("\t")
            elif tag in ("br", "cr"):
                if child.get(W + "type") not in ("page", "column"):
                    parts.append(u" ")
            elif tag == "noBreakHyphen":
                parts.append(u"‑")
            elif tag in ("drawing", "pict", "object"):
                images += 1
        text = "".join(parts)
        if text:
            runs.append({"text": text, "bold": bold, "italic": italic, "sup": sup})
    return {"type": "p", "style": style, "list": list_type, "indent_pt": indent,
            "runs": runs, "images": images}


def _read_table(tbl, para_styles, char_styles, numbering):
    rows = []
    for tr in tbl.findall(W + "tr"):
        trpr = tr.find(W + "trPr")
        header = trpr is not None and trpr.find(W + "tblHeader") is not None
        cells = []
        for tc in tr.findall(W + "tc"):
            tcpr = tc.find(W + "tcPr")
            span, merged = 1, False
            if tcpr is not None:
                gs = tcpr.find(W + "gridSpan")
                if gs is not None:
                    span = max(1, int(gs.get(W + "val", "1")))
                vm = tcpr.find(W + "vMerge")
                merged = vm is not None and vm.get(W + "val", "continue") == "continue"
            paras = [_read_paragraph(p, para_styles, char_styles, numbering)
                     for p in tc.findall(W + "p")]
            cells.append({"span": span, "paras": [] if merged else paras})
        rows.append({"header": header, "cells": cells})
    return {"type": "table", "rows": rows}


def read_docx(path):
    with zipfile.ZipFile(path) as zf:
        para_styles = _style_names(zf, "paragraph")
        char_styles = _style_names(zf, "character")
        numbering = _numbering(zf)
        root = ET.fromstring(zf.read("word/document.xml"))
    body = root.find(W + "body")
    blocks = []

    def walk(el):
        for child in el:
            tag = local(child.tag)
            if tag == "p":
                blocks.append(_read_paragraph(child, para_styles, char_styles, numbering))
            elif tag == "tbl":
                blocks.append(_read_table(child, para_styles, char_styles, numbering))
            elif tag in ("sdt", "sdtContent", "customXml"):
                walk(child)
    walk(body)
    return blocks


# --------------------------------------------------------------------------
# 2. Classify into roles
# --------------------------------------------------------------------------

def _text(block):
    return "".join(r["text"] for r in block["runs"])


def _all_bold(block):
    visible = [r for r in block["runs"] if r["text"].strip()]
    return bool(visible) and all(r["bold"] for r in visible)


def _strip_prefix(runs, length):
    out, left = [], length
    for r in runs:
        if left <= 0:
            out.append(r)
            continue
        if len(r["text"]) <= left:
            left -= len(r["text"])
            continue
        nr = dict(r)
        nr["text"] = r["text"][left:]
        left = 0
        out.append(nr)
    return out


def _split_runs(runs, index, sep_len):
    """Split runs at a character index, dropping sep_len characters."""
    first, second, pos = [], [], 0
    for r in runs:
        start, end = pos, pos + len(r["text"])
        pos = end
        if end <= index:
            first.append(r)
        elif start >= index + sep_len:
            second.append(r)
        else:
            a = r["text"][:max(0, index - start)]
            b = r["text"][max(0, index + sep_len - start):]
            if a:
                first.append(dict(r, text=a))
            if b:
                second.append(dict(r, text=b))
    return first, second


class Classifier(object):
    def __init__(self, data):
        self.roles = dict(data.get("roles") or {})
        if not self.roles.get("body"):
            raise ContentError("The style system has no roles.body: add a \"roles\" block "
                               "naming the body paragraph style (see the schema).")
        self.mapping = {}
        for style in data.get("paragraph_styles", []):
            for word_name in style.get("maps_from", []):
                self.mapping[word_name.strip().lower()] = style["name"]
        self.report = {"styles": {}, "unmapped": {}, "headings": 0, "lists": 0, "quotes": 0,
                       "tables": 0, "images": 0, "empty": 0, "hashtags": 0,
                       "title_split": False, "lead": False}

    def role(self, key):
        return self.roles.get(key) or None

    def classify(self, blocks):
        items = []
        for block in blocks:
            if block["type"] == "table":
                items.append(self._table(block))
                self.report["tables"] += 1
                continue
            self.report["images"] += block["images"]
            text = _text(block)
            if not text.strip():
                self.report["empty"] += 1
                continue
            items.append(self._paragraph(block, text))
        self._title_and_lead(items)
        for item in items:
            if item["type"] == "p":
                item["runs"] = self._character_styles(item)
                self.report["styles"][item["style"]] = self.report["styles"].get(item["style"], 0) + 1
        return items

    def _paragraph(self, block, text):
        body = self.roles["body"]
        target = self.mapping.get(block["style"].strip().lower())
        if target is None:
            self.report["unmapped"][block["style"]] = self.report["unmapped"].get(block["style"], 0) + 1
            target = body
        item = {"type": "p", "style": target, "kind": "body" if target == body else "mapped",
                "runs": block["runs"]}
        if target != body:
            return item
        typed = BULLET_RE.match(text) or NUMBER_RE.match(text)
        list_role = None
        if block["list"]:
            list_role = self.role("bullet") if block["list"] == "bullet" else \
                (self.role("numbered") or self.role("bullet"))
        elif typed:
            list_role = self.role("bullet") if BULLET_RE.match(text) else self.role("numbered")
        if list_role:
            item.update(style=list_role, kind="list")
            if typed and not block["list"]:
                item["runs"] = _strip_prefix(block["runs"], typed.end())
            self.report["lists"] += 1
        elif (self.role("heading") and _all_bold(block)
              and len(text.strip()) <= int(self.roles.get("heading_max_chars", 120))
              and not re.search(r"[\.:;,]$", text.strip())):
            item.update(style=self.role("heading"), kind="heading")
            self.report["headings"] += 1
        elif self.role("quote") and block["indent_pt"] >= float(self.roles.get("quote_min_indent_pt", 18)):
            item.update(style=self.role("quote"), kind="quote")
            self.report["quotes"] += 1
        item["all_bold"] = _all_bold(block)
        return item

    def _title_and_lead(self, items):
        title_role, lead_role = self.role("title"), self.role("lead")
        for i, item in enumerate(items):
            if item["type"] == "p" and item["kind"] == "heading" and title_role:
                item.update(style=title_role, kind="title")
                self.report["headings"] -= 1
                sep = self.roles.get("title_separator")
                sub = self.role("subtitle")
                text = _text(item)
                if sep and sub and sep in text:
                    first, second = _split_runs(item["runs"], text.index(sep), len(sep))
                    item["runs"] = first
                    items.insert(i + 1, {"type": "p", "style": sub, "kind": "subtitle",
                                         "runs": second})
                    self.report["title_split"] = True
                break
            if item["type"] == "p" and item["kind"] == "body":
                break  # body text before any heading: no title to find
        if lead_role:
            for item in items:
                if item["type"] == "p" and item["kind"] == "body":
                    item.update(style=lead_role, kind="lead")
                    self.report["lead"] = True
                    break

    def _character_styles(self, item):
        no_emphasis = item["kind"] in ("title", "subtitle", "heading")
        drop_bold = item["kind"] == "lead" and item.get("all_bold")
        out = []
        for r in item["runs"]:
            style = None
            bold = r["bold"] and not no_emphasis and not drop_bold
            italic = r["italic"] and not no_emphasis
            if bold and italic:
                style = self.role("bold_italic") or self.role("bold")
            elif bold:
                style = self.role("bold")
            elif italic:
                style = self.role("italic")
            elif r.get("sup"):
                style = self.role("superscript")
            out.extend(self._hashtags(r["text"], style))
        merged = []
        for text, style in out:
            if merged and merged[-1][1] == style:
                merged[-1] = (merged[-1][0] + text, style)
            elif text:
                merged.append((text, style))
        return merged

    def _hashtags(self, text, style):
        mode = self.roles.get("hashtags", "keep")
        if mode == "remove":
            new, n = HASHTAG_RE.subn(r"\1", text)
            self.report["hashtags"] += n
            return [(new, style)]
        if mode == "style" and self.role("hashtag"):
            pieces, pos = [], 0
            for m in HASHTAG_RE.finditer(text):
                pieces.append((text[pos:m.start()], style))
                pieces.append((m.group(0), self.role("hashtag")))
                self.report["hashtags"] += 1
                pos = m.end()
            pieces.append((text[pos:], style))
            return pieces
        return [(text, style)]

    def _table(self, block):
        header_style = self.role("table_header") or self.roles["body"]
        body_style = self.role("table_body") or self.roles["body"]
        rows = block["rows"]
        header_rows = 0
        for row in rows:
            if row["header"]:
                header_rows += 1
            else:
                break
        if header_rows == 0 and rows and self.roles.get("table_first_row_header", True):
            header_rows = 1
        out_rows = []
        for r_index, row in enumerate(rows):
            is_header = r_index < header_rows
            cells = []
            for cell in row["cells"]:
                paras = []
                for p in cell["paras"]:
                    fake = {"type": "p", "style": header_style if is_header else body_style,
                            "kind": "heading" if is_header else "cell", "runs": p["runs"]}
                    fake["runs"] = self._character_styles(fake)
                    paras.append(fake)
                cells.append({"span": cell["span"], "paras": paras})
            out_rows.append({"header": is_header, "cells": cells})
        return {"type": "table", "rows": out_rows, "header_rows": header_rows}


# --------------------------------------------------------------------------
# 3. Story XML
# --------------------------------------------------------------------------

def _clean(text):
    return escape(INVALID_XML.sub("", text))


def _paragraph_xml(item, refs, last, pad):
    para_ref = refs.para(item["style"])
    runs = item["runs"] or [("", None)]
    out = ["%s<ParagraphStyleRange AppliedParagraphStyle=%s>" % (pad, quoteattr(para_ref))]
    for i, (text, style) in enumerate(runs):
        char_ref = refs.char(style) if style else NO_CHAR
        body = "<Content>%s</Content>" % _clean(text) if text else ""
        br = "<Br/>" if (i == len(runs) - 1 and not last) else ""
        out.append("%s  <CharacterStyleRange AppliedCharacterStyle=%s>%s%s</CharacterStyleRange>"
                   % (pad, quoteattr(char_ref), body, br))
    out.append("%s</ParagraphStyleRange>" % pad)
    return "\n".join(out)


def _table_xml(item, refs, ids, width, metrics, table_cfg, last, pad):
    rows = item["rows"]
    ncols = max(sum(c["span"] for c in r["cells"]) for r in rows) if rows else 1
    # Column widths proportional to the longest text in each column.
    weights = [8.0] * ncols
    for row in rows:
        col = 0
        for cell in row["cells"]:
            if cell["span"] == 1 and col < ncols:
                length = sum(len(t) for p in cell["paras"] for t, _ in p["runs"])
                weights[col] = max(weights[col], min(float(length), 60.0))
            col += cell["span"]
    total = sum(weights)
    widths = [width * w / total for w in weights]
    tid = ids.next("t")
    inset = float(table_cfg.get("cell_inset_mm", 1.5)) * MM_TO_PT
    out = ["%s<ParagraphStyleRange AppliedParagraphStyle=%s>" % (pad, quoteattr(refs.para(refs.body))),
           "%s  <CharacterStyleRange AppliedCharacterStyle=%s>" % (pad, quoteattr(NO_CHAR)),
           '%s    <Table Self="%s" HeaderRowCount="%d" FooterRowCount="0" BodyRowCount="%d" '
           'ColumnCount="%d" AppliedTableStyle=%s TableDirection="LeftToRightDirection">'
           % (pad, tid, item["header_rows"], len(rows) - item["header_rows"], ncols,
              quoteattr(refs.table_style()))]
    for r in range(len(rows)):
        out.append('%s      <Row Self="%sRow%d" Name="%d" MinimumHeight="%s" AutoGrow="true"/>'
                   % (pad, tid, r, r, num(2 * inset + 8)))
    for c in range(ncols):
        out.append('%s      <Column Self="%sColumn%d" Name="%d" SingleColumnWidth="%s"/>'
                   % (pad, tid, c, c, num(widths[c])))
    for r, row in enumerate(rows):
        col = 0
        cell_style = refs.cell_style(row["header"])
        for cell in row["cells"]:
            if col >= ncols:
                break
            span = min(cell["span"], ncols - col)
            out.append('%s      <Cell Self="%si%di%d" Name="%d:%d" RowSpan="1" ColumnSpan="%d" '
                       'AppliedCellStyle=%s AppliedCellStylePriority="1">'
                       % (pad, tid, col, r, col, r, span, quoteattr(cell_style)))
            paras = cell["paras"] or [{"style": refs.body, "runs": [("", None)]}]
            for i, p in enumerate(paras):
                out.append(_paragraph_xml(p, refs, i == len(paras) - 1, pad + "        "))
            out.append("%s      </Cell>" % pad)
            col += span
        while col < ncols:  # short rows: pad with empty cells
            out.append('%s      <Cell Self="%si%di%d" Name="%d:%d" RowSpan="1" ColumnSpan="1" '
                       'AppliedCellStyle=%s AppliedCellStylePriority="1"/>'
                       % (pad, tid, col, r, col, r, quoteattr(cell_style)))
            col += 1
    out.append("%s    </Table>%s" % (pad, "" if last else "<Br/>"))
    out.append("%s  </CharacterStyleRange>" % pad)
    out.append("%s</ParagraphStyleRange>" % pad)
    return "\n".join(out)


def story_body(items, refs, ids, table_width, metrics, table_cfg):
    out = []
    for i, item in enumerate(items):
        last = i == len(items) - 1
        if item["type"] == "table":
            out.append(_table_xml(item, refs, ids, table_width, metrics, table_cfg, last, "    "))
        else:
            out.append(_paragraph_xml(item, refs, last, "    "))
    return "\n".join(out)


# --------------------------------------------------------------------------
# 4. Page estimate and spreads
# --------------------------------------------------------------------------

def resolve_metrics(data):
    """Effective size/leading/spacing/indents per paragraph style (inheritance applied)."""
    styles = {s["name"]: s for s in data.get("paragraph_styles", [])}
    keys = ("size_pt", "leading_pt", "space_before_pt", "space_after_pt",
            "left_indent_pt", "right_indent_pt", "first_line_indent_pt")
    defaults = {"size_pt": 12, "leading_pt": "auto", "space_before_pt": 0, "space_after_pt": 0,
                "left_indent_pt": 0, "right_indent_pt": 0, "first_line_indent_pt": 0}
    cache = {}

    def get(name, depth=0):
        if name in cache:
            return cache[name]
        style = styles.get(name, {})
        parent = get(style["based_on"], depth + 1) if style.get("based_on") in styles and depth < 20 \
            else defaults
        m = {k: style.get(k, parent[k]) for k in keys}
        cache[name] = m
        return m
    return get


def estimate_height(items, metrics, column_width, avg_em, table_cfg):
    def para_height(style, text, width):
        m = metrics(style)
        size = float(m["size_pt"])
        lead = 1.2 * size if str(m["leading_pt"]).lower() == "auto" else float(m["leading_pt"])
        usable = max(width - float(m["left_indent_pt"]) - float(m["right_indent_pt"]), size * 4)
        chars = len(text) * size * avg_em + max(float(m["first_line_indent_pt"]), 0)
        lines = max(1, int(math.ceil(chars / usable)) + text.count(u" "))
        return lines * lead + float(m["space_before_pt"]) + float(m["space_after_pt"])

    total = 0.0
    inset = float(table_cfg.get("cell_inset_mm", 1.5)) * MM_TO_PT
    for item in items:
        if item["type"] == "p":
            total += para_height(item["style"], "".join(t for t, _ in item["runs"]), column_width)
            continue
        ncols = max(sum(c["span"] for c in r["cells"]) for r in item["rows"]) or 1
        cell_w = column_width / ncols
        for row in item["rows"]:
            tallest = 0.0
            for cell in row["cells"]:
                h = sum(para_height(p["style"], "".join(t for t, _ in p["runs"]),
                                    cell_w * cell["span"] - 2 * inset)
                        for p in cell["paras"]) + 2 * inset
                tallest = max(tallest, h)
            total += tallest
        total += float(table_cfg.get("space_before_pt", 6)) + float(table_cfg.get("space_after_pt", 6))
    return total


class Ids(object):
    """Unique Self ids with a prefix that no existing id starts with."""

    def __init__(self, prefix, existing=()):
        taken = set(existing)
        base, n = prefix, 0
        while any(s.startswith(base) for s in taken):
            n += 1
            base = "%s%d" % (prefix, n)
        self.prefix = base
        self.count = 0

    def next(self, kind=""):
        self.count += 1
        return "%s%s%x" % (self.prefix, kind, self.count)


def page_layout(geom, pages, facing):
    """List of spreads; each spread is a list of (page_index, is_left)."""
    spreads = []
    if facing:
        spreads.append([(0, False)])
        i = 1
        while i < pages:
            spread = [(i, True)]
            if i + 1 < pages:
                spread.append((i + 1, False))
            spreads.append(spread)
            i += 2
    else:
        spreads = [[(i, False)] for i in range(pages)]
    return spreads


def spreads_xml(geom, pages, master_self, layer_self, story_self, ids, dom_version, pkg_ns,
                facing):
    """Return ([(spread_self, xml)], [page_selfs]) with one threaded frame per page."""
    w, h = geom["width"], geom["height"]
    page_selfs = [ids.next("p") for _ in range(pages)]
    frame_selfs = [ids.next("f") for _ in range(pages)]
    result = []
    for spread in page_layout(geom, pages, facing):
        spread_self = ids.next("s")
        parts = []
        for index, is_left in spread:
            tx = -w if is_left else 0
            transform = "1 0 0 1 %s 0" % num(tx)
            left_m = geom["outside"] if is_left else geom["inside"]
            right_m = geom["inside"] if is_left else geom["outside"]
            parts.append(
                '    <Page Self="%s" Name="%d" AppliedMaster=%s GeometricBounds="0 0 %s %s" '
                'ItemTransform="%s" MasterPageTransform="1 0 0 1 0 0" OverrideList="" TabOrder="" '
                'GridStartingPoint="TopOutside" UseMasterGrid="true">\n'
                '      <Properties><PageColor type="enumeration">UseMasterColor</PageColor></Properties>\n'
                '      <MarginPreference ColumnCount="%d" ColumnGutter="%s" Top="%s" Bottom="%s" '
                'Left="%s" Right="%s" ColumnDirection="Horizontal"/>\n    </Page>'
                % (page_selfs[index], index + 1, quoteattr(master_self), num(h), num(w), transform,
                   geom["columns"], num(geom["gutter"]), num(geom["top"]), num(geom["bottom"]),
                   num(left_m), num(right_m)))
        for index, is_left in spread:
            tx = -w if is_left else 0
            left_m = geom["outside"] if is_left else geom["inside"]
            right_m = geom["inside"] if is_left else geom["outside"]
            top, bottom = geom["top"], h - geom["bottom"]
            left, right = left_m, w - right_m
            corners = [(left, top), (left, bottom), (right, bottom), (right, top)]
            points = "\n".join(
                '              <PathPointType Anchor="{0} {1}" LeftDirection="{0} {1}" '
                'RightDirection="{0} {1}"/>'.format(num(x), num(y)) for x, y in corners)
            prev = frame_selfs[index - 1] if index > 0 else "n"
            nxt = frame_selfs[index + 1] if index + 1 < pages else "n"
            parts.append(
                '    <TextFrame Self="%s" ParentStory="%s" PreviousTextFrame="%s" NextTextFrame="%s" '
                'ContentType="TextType" ItemLayer="%s" ItemTransform="1 0 0 1 %s 0">\n'
                '      <Properties>\n        <PathGeometry>\n'
                '          <GeometryPathType PathOpen="false">\n            <PathPointArray>\n'
                '%s\n            </PathPointArray>\n          </GeometryPathType>\n'
                '        </PathGeometry>\n      </Properties>\n'
                '      <TextFramePreference TextColumnCount="%d" TextColumnGutter="%s"/>\n'
                '    </TextFrame>'
                % (frame_selfs[index], story_self, prev, nxt, layer_self, num(tx), points,
                   geom["frame_columns"], num(geom["gutter"])))
        xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
               '<idPkg:Spread xmlns:idPkg="%s" DOMVersion="%s">\n'
               '  <Spread Self="%s" PageCount="%d" BindingLocation="%d" ShowMasterItems="true" '
               'AllowPageShuffle="true" ItemTransform="1 0 0 1 0 0" FlattenerOverride="Default">\n'
               '%s\n  </Spread>\n</idPkg:Spread>\n'
               % (pkg_ns, dom_version, spread_self, len(spread), 1 if len(spread) == 2 else 0,
                  "\n".join(parts)))
        result.append((spread_self, xml))
    return result, page_selfs


def story_xml(story_self, body, dom_version, pkg_ns):
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<idPkg:Story xmlns:idPkg="%s" DOMVersion="%s">\n'
            '  <Story Self="%s" AppliedTOCStyle="n" TrackChanges="false" StoryTitle="$ID/" '
            'AppliedNamedGrid="n">\n'
            '    <StoryPreference OpticalMarginAlignment="false" OpticalMarginSize="12" '
            'FrameType="TextFrameType" StoryOrientation="Horizontal" '
            'StoryDirection="LeftToRightDirection"/>\n'
            '    <InCopyExportOption IncludeGraphicProxies="true" IncludeAllResources="false"/>\n'
            '%s\n  </Story>\n</idPkg:Story>\n' % (pkg_ns, dom_version, story_self, body))


def pages_needed(items, data, geom):
    metrics = resolve_metrics(data)
    cols = geom["frame_columns"]
    frame_w = geom["width"] - geom["inside"] - geom["outside"]
    col_w = (frame_w - (cols - 1) * geom["gutter"]) / cols
    frame_h = geom["height"] - geom["top"] - geom["bottom"]
    avg_em = float(data.get("document", {}).get("avg_char_em", 0.52))
    spare = int(data.get("document", {}).get("spare_pages", 1))
    height = estimate_height(items, metrics, col_w, avg_em, data.get("tables") or {})
    return max(1, int(math.ceil(height / (frame_h * cols))) + spare), col_w


def report_lines(report, pages):
    lines = ["Content placed:"]
    for name, count in sorted(report["styles"].items(), key=lambda kv: -kv[1]):
        lines.append("  %-24s %d" % (name, count))
    if report["title_split"]:
        lines.append("  Title split into title + subtitle")
    if report["lead"]:
        lines.append("  Lead paragraph set")
    for key, label in (("lists", "List items"), ("headings", "Hand-made headings"),
                       ("quotes", "Quotes"), ("tables", "Tables"), ("hashtags", "Hashtags handled"),
                       ("empty", "Empty paragraphs removed")):
        if report[key]:
            lines.append("  %s: %d" % (label, report[key]))
    if report["images"]:
        lines.append("  Images in the Word file (not placed, add them in InDesign): %d"
                     % report["images"])
    if report["unmapped"]:
        lines.append("  Word styles with no maps_from (set to the body style): %s"
                     % ", ".join("%s (%d)" % kv for kv in sorted(report["unmapped"].items())))
    lines.append("  Pages: %d (estimated, includes 1 spare page; InDesign composes the "
                 "final text)" % pages)
    return lines
