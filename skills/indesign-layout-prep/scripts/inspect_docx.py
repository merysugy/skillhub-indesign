#!/usr/bin/env python3
"""
inspect_docx.py - Report how a Word document is structured before importing it.

Tells you which case of step 3 you are in:
  * Well-styled Word (Heading 1/2, Normal...): import with InDesign's own
    style mapping, no script needed.
  * Hand-made Word (bold lines as headings, "-" lists, manual indents):
    use import_docx.jsx.

Usage:
    python3 inspect_docx.py content.docx
    python3 inspect_docx.py content.docx --style-system style-system.json

With --style-system, it also prints a ready-to-paste `styleMap` for
import_docx.jsx, built from the `maps_from` lists in the style system.
Only the Python 3 standard library is used.
"""

import argparse
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

BULLET_RE = re.compile(r"^\s*[\-–—•●\*]\s+")
NUMBER_RE = re.compile(r"^\s*\d{1,3}[\.\)]\s+")


def on(element):
    """True if a w:b / w:i style toggle is switched on."""
    if element is None:
        return False
    return element.get(W + "val", "true").lower() not in ("0", "false", "off")


def load_style_names(zf):
    names = {}
    try:
        root = ET.fromstring(zf.read("word/styles.xml"))
    except KeyError:
        return names
    for style in root.iter(W + "style"):
        sid = style.get(W + "styleId")
        name = style.find(W + "name")
        if sid:
            names[sid] = name.get(W + "val") if name is not None else sid
    return names


def pretty(name):
    # Built-in Word names are stored lower-case ("heading 1"); InDesign shows them capitalised.
    return name[:1].upper() + name[1:] if name else name


def inspect(path):
    with zipfile.ZipFile(path) as zf:
        names = load_style_names(zf)
        root = ET.fromstring(zf.read("word/document.xml"))

    body = root.find(W + "body")
    report = {"styles": {}, "manual_headings": [], "manual_lists": [], "word_lists": 0,
              "indented": [], "tables": 0, "images": 0, "paragraphs": 0,
              "bold_runs": 0, "italic_runs": 0}

    report["tables"] = len(list(body.iter(W + "tbl")))
    report["images"] = len(list(body.iter(W + "drawing"))) + len(list(body.iter(W + "pict")))

    for para in body.iter(W + "p"):
        ppr = para.find(W + "pPr")
        sid = None
        if ppr is not None and ppr.find(W + "pStyle") is not None:
            sid = ppr.find(W + "pStyle").get(W + "val")
        style = pretty(names.get(sid, sid or "Normal"))

        runs = []
        for run in para.iter(W + "r"):
            text = "".join(t.text or "" for t in run.iter(W + "t"))
            if not text:
                continue
            rpr = run.find(W + "rPr")
            bold = rpr is not None and on(rpr.find(W + "b"))
            italic = rpr is not None and on(rpr.find(W + "i"))
            runs.append((text, bold, italic))
        text = "".join(r[0] for r in runs).strip()
        if not text:
            continue

        report["paragraphs"] += 1
        report["styles"][style] = report["styles"].get(style, 0) + 1
        report["bold_runs"] += sum(1 for r in runs if r[1])
        report["italic_runs"] += sum(1 for r in runs if r[2])

        if ppr is not None and ppr.find(W + "numPr") is not None:
            report["word_lists"] += 1
        if BULLET_RE.match(text) or NUMBER_RE.match(text):
            report["manual_lists"].append((style, text))
        visible = [r for r in runs if r[0].strip()]
        if (len(text) <= 90 and visible and all(r[1] for r in visible)
                and not re.search(r"[\.:;,]$", text) and not style.lower().startswith(("heading", "título", "title"))):
            report["manual_headings"].append((style, text))
        if ppr is not None and ppr.find(W + "ind") is not None:
            left = ppr.find(W + "ind").get(W + "left") or ppr.find(W + "ind").get(W + "start")
            try:
                left_pt = int(left) / 20.0  # twips -> points
            except (TypeError, ValueError):
                left_pt = 0
            if left_pt >= 18 and ppr.find(W + "numPr") is None:
                report["indented"].append((style, left_pt, text))
    return report


def style_map(report, style_system_path):
    with open(style_system_path, encoding="utf-8") as fh:
        data = json.load(fh)
    lookup = {}
    for style in data.get("paragraph_styles", []):
        path = ":".join([g.strip() for g in str(style.get("group", "")).split("/") if g.strip()]
                        + [style["name"]])
        for word_name in style.get("maps_from", []):
            lookup[word_name.strip().lower()] = path
    rows, unmatched = [], []
    for word_style in sorted(report["styles"]):
        target = lookup.get(word_style.lower())
        if target:
            rows.append('        ["%s", "%s"]' % (word_style.replace('"', '\\"'),
                                                 target.replace('"', '\\"')))
        else:
            unmatched.append(word_style)
    return rows, unmatched


def short(text, limit=70):
    return text if len(text) <= limit else text[:limit - 1] + "…"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Inspect the structure of a .docx file.")
    parser.add_argument("docx")
    parser.add_argument("--style-system", help="style-system JSON with maps_from lists")
    parser.add_argument("--examples", type=int, default=5, help="examples to show per finding")
    args = parser.parse_args(argv)

    try:
        report = inspect(args.docx)
    except (OSError, KeyError, zipfile.BadZipFile, ET.ParseError) as exc:
        print("Error: cannot read %s: %s" % (args.docx, exc), file=sys.stderr)
        return 1

    n = args.examples
    print("Paragraphs with text: %d | tables: %d | images: %d"
          % (report["paragraphs"], report["tables"], report["images"]))
    print("Runs with local bold: %d | local italic: %d"
          % (report["bold_runs"], report["italic_runs"]))
    print("\nParagraph styles used:")
    for name, count in sorted(report["styles"].items(), key=lambda kv: -kv[1]):
        print("  %-28s %d" % (name, count))

    print("\nWord lists (real numbering): %d" % report["word_lists"])
    sections = (("Possible hand-made headings (short, all bold)", report["manual_headings"]),
                ("Hand-made list items (typed '-' or '1.')", report["manual_lists"]))
    for title, items in sections:
        print("\n%s: %d" % (title, len(items)))
        for style, text in items[:n]:
            print("  [%s] %s" % (style, short(text)))
    print("\nManually indented paragraphs (possible quotes): %d" % len(report["indented"]))
    for style, left, text in report["indented"][:n]:
        print("  [%s, %.0f pt] %s" % (style, left, short(text)))

    heading_styles = [s for s in report["styles"]
                      if s.lower().startswith(("heading", "título", "title"))]
    hand_made = len(report["manual_headings"]) + len(report["manual_lists"]) + len(report["indented"])
    print("\nVerdict:")
    if heading_styles and hand_made == 0:
        print("  Well-styled document: import with InDesign's style mapping "
              "(File > Place > Show Import Options), no script needed.")
    else:
        print("  Hand-made structure found: use import_docx.jsx (detects headings, "
              "lists and quotes).")

    if args.style_system:
        rows, unmatched = style_map(report, args.style_system)
        print("\nstyleMap for import_docx.jsx:")
        print("    styleMap: [\n%s\n    ]," % ",\n".join(rows))
        if unmatched:
            print("\nWord styles with no maps_from match (they will fall back to bodyStyle):")
            for name in unmatched:
                print("  " + name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
