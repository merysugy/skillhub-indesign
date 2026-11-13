#!/usr/bin/env python3
"""
idms_to_model.py - An existing .idms block back to a block model (JSON), so it
can be modified and rebuilt with build_snippet.py instead of being redrawn
from a capture.

    python3 idms_to_model.py block.idms -o block.json [--links DIR]

Blocks made with build_snippet.py convert completely. Snippets exported by
InDesign are read in the same subset (text frames, rectangles with or
without a linked image, lines, polygons, ovals, flat groups, solid colours,
paragraph and character styles); anything else is listed as skipped, so say
so to the user before rebuilding.

--links is the folder where the linked images are (default: Links next to
the .idms). Coordinates are moved so the block starts at 0,0.
"""

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET

ALIGN = {"LeftAlign": "left", "CenterAlign": "center", "RightAlign": "right"}
VALIGN = {"TopAlign": "top", "CenterAlign": "center", "BottomAlign": "bottom"}
CORNERS = ("TopLeft", "TopRight", "BottomLeft", "BottomRight")


def matrix(el):
    v = [float(x) for x in (el.get("ItemTransform") or "1 0 0 1 0 0").split()]
    return v


def apply(m, x, y):
    return m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]


def mul(a, b):  # a then b
    return [a[0] * b[0] + a[1] * b[2], a[0] * b[1] + a[1] * b[3],
            a[2] * b[0] + a[3] * b[2], a[2] * b[1] + a[3] * b[3],
            a[4] * b[0] + a[5] * b[2] + b[4], a[4] * b[1] + a[5] * b[3] + b[5]]


def anchors(el):
    pts = []
    for p in el.iter("PathPointType"):
        pts.append(tuple(float(v) for v in p.get("Anchor").split()))
    return pts


def ref(v):
    if not v or v == "Swatch/None":
        return None
    return v.split("/", 1)[1]


def num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def convert(path, links_dir):
    root = ET.parse(path).getroot()
    skipped = []
    model = {"name": "Block", "font_family": None, "layer": "Layer 1", "colors": {},
             "paragraph_styles": {}, "character_styles": {}, "items": []}
    layer = root.find("Layer")
    if layer is not None:
        model["layer"] = layer.get("Name", "Layer 1")
    for c in root.iter("Color"):
        n = c.get("Name")
        if n in ("Black", "Paper", "Registration") or not c.get("ColorValue"):
            continue
        if c.get("Space") not in ("RGB", "CMYK"):
            skipped.append("colour %s in %s space (converted as is)" % (n, c.get("Space")))
        model["colors"][n] = [num(x) for x in c.get("ColorValue").split()]
    if root.find(".//Gradient") is not None:
        skipped.append("gradients (not supported by the block model)")
    for p in root.iter("ParagraphStyle"):
        n = p.get("Name", "")
        if n.startswith("$ID"):
            continue
        props = p.find("Properties")
        lead = props.find("Leading") if props is not None else None
        font = props.find("AppliedFont") if props is not None else None
        size = num(p.get("PointSize"), 12)
        st = {"font": p.get("FontStyle", "Regular"), "size": size,
              "leading": num(lead.text, size * 1.2) if lead is not None and lead.text != "Auto" else size * 1.2,
              "color": ref(p.get("FillColor")) or "Black",
              "align": ALIGN.get(p.get("Justification", "LeftAlign"), "left"),
              "space_before": num(p.get("SpaceBefore")), "space_after": num(p.get("SpaceAfter")),
              "left_indent": num(p.get("LeftIndent")), "caps": p.get("Capitalization") == "AllCaps",
              "tracking": num(p.get("Tracking"))}
        if font is not None and font.text:
            st["family"] = font.text
            model["font_family"] = model["font_family"] or font.text
        model["paragraph_styles"][n] = st
    for c in root.iter("CharacterStyle"):
        n = c.get("Name", "")
        if n.startswith("$ID"):
            continue
        st = {}
        if c.get("FontStyle"):
            st["font"] = c.get("FontStyle")
        if c.get("FillColor"):
            st["color"] = ref(c.get("FillColor")) or "Black"
        font = c.find("Properties/AppliedFont")
        if font is not None and font.text:
            st["family"] = font.text
        model["character_styles"][n] = st
    for st in model["paragraph_styles"].values():
        if st.get("family") == model["font_family"]:
            st.pop("family")
    model["font_family"] = model["font_family"] or "Project Font"
    stories = {s.get("Self"): s for s in root.iter("Story")}

    def walk(parent, m_parent):
        for el in parent:
            tag = el.tag
            m = mul(matrix(el), m_parent)
            if tag == "Group":
                if model["name"] == "Block" and el.get("Name"):
                    model["name"] = el.get("Name")
                walk(el, m)
                continue
            if tag not in ("TextFrame", "Rectangle", "GraphicLine", "Polygon", "Oval"):
                if tag not in ("Properties",):
                    skipped.append("%s %s" % (tag, el.get("Self", "")))
                continue
            if abs(m[1]) > 1e-6 or abs(m[2]) > 1e-6:
                skipped.append("%s %s is rotated or skewed" % (tag, el.get("Self")))
                continue
            pts = [apply(m, x, y) for x, y in anchors(el)]
            it = {"name": el.get("Name")} if el.get("Name") and el.get("Name") != "$ID/" else {}
            paint = {"fill": ref(el.get("FillColor")), "stroke": ref(el.get("StrokeColor")),
                     "stroke_weight": num(el.get("StrokeWeight"))}
            if not paint["stroke"]:
                paint.pop("stroke_weight")
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            box = {"x": min(xs), "y": min(ys), "w": max(xs) - min(xs), "h": max(ys) - min(ys)}
            radius, which = 0.0, []
            for c in CORNERS:
                if el.get(c + "CornerOption") == "RoundedCorner":
                    which.append(c)
                    radius = num(el.get(c + "CornerRadius"))
            corner = {"radius": radius, "corners": which} if which else {}
            if tag == "TextFrame":
                pref = el.find("TextFramePreference")
                inset = [num(li.text) for li in pref.iter("ListItem")] if pref is not None else [0, 0, 0, 0]
                story = stories.get(el.get("ParentStory"))
                paras = []
                if el.get("PreviousTextFrame", "n") != "n":
                    continue  # threaded continuation: text belongs to the first frame
                for psr in (story.iter("ParagraphStyleRange") if story is not None else []):
                    runs = []
                    for csr in psr.iter("CharacterStyleRange"):
                        text = "".join(c.text or "" for c in csr.iter("Content"))
                        cs = csr.get("AppliedCharacterStyle", "")
                        runs.append(text if "$ID" in cs or not cs else {"style": cs.split("/", 1)[1], "text": text})
                    paras.append({"style": psr.get("AppliedParagraphStyle").split("/", 1)[1], "runs": runs})
                it.update(type="text", **box, paragraphs=paras,
                          columns=int(pref.get("TextColumnCount", 1)) if pref is not None else 1,
                          gutter=num(pref.get("TextColumnGutter"), 12) if pref is not None else 12,
                          inset=inset or [0, 0, 0, 0],
                          valign=VALIGN.get(pref.get("VerticalJustification") if pref is not None else "", "top"),
                          balance_columns=(pref is not None and pref.get("VerticalBalanceColumns") == "true"),
                          **corner, **paint)
            elif tag == "Rectangle":
                it.update(type="rect", **box, **corner, **paint)
                link = el.find(".//Link")
                if link is not None:
                    name = link.get("LinkResourceURI", "").replace("\\", "/").split("/")[-1]
                    it["image"] = os.path.join(links_dir, name)
                    if not os.path.exists(it["image"]):
                        skipped.append("image %s not found in %s: copy it there before rebuilding" % (name, links_dir))
            elif tag == "GraphicLine":
                it.update(type="line", points=[list(p) for p in pts[:2]], color=paint["stroke"] or "Black",
                          weight=num(el.get("StrokeWeight"), 1))
            elif tag == "Polygon":
                it.update(type="polygon", points=[list(p) for p in pts], **paint)
            elif tag == "Oval":
                it.update(type="oval", cx=(min(xs) + max(xs)) / 2, cy=(min(ys) + max(ys)) / 2,
                          r=(max(xs) - min(xs)) / 2, **paint)
                if abs((max(xs) - min(xs)) - (max(ys) - min(ys))) > 0.5:
                    skipped.append("oval %s is an ellipse; converted as a circle" % el.get("Self"))
            model["items"].append(it)

    spread = root.find("Spread")
    if spread is None:
        raise SystemExit("error: no <Spread> in %s" % path)
    walk(spread, [1, 0, 0, 1, 0, 0])
    if not model["items"]:
        raise SystemExit("error: no supported objects found")
    # origin at 0,0
    import build_snippet
    import snippet_model
    x0, y0, _, _ = build_snippet.bounds(snippet_model.normalise(json.loads(json.dumps(model)), base_dir="/"))
    for it in model["items"]:
        if "x" in it:
            it["x"] -= x0; it["y"] -= y0
        if "cx" in it:
            it["cx"] -= x0; it["cy"] -= y0
        if "points" in it:
            it["points"] = [[p[0] - x0, p[1] - y0] for p in it["points"]]
    return model, skipped


def main(argv=None):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("snippet")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--links", help="folder with the linked images (default: Links next to the .idms)")
    args = ap.parse_args(argv)
    links = args.links or os.path.join(os.path.dirname(os.path.abspath(args.snippet)), "Links")
    model, skipped = convert(args.snippet, os.path.abspath(links))
    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(model, fh, ensure_ascii=False, indent=1)
    print("%s: %r, %d objects, %d paragraph styles, %d character styles, %d swatches"
          % (args.output, model["name"], len(model["items"]), len(model["paragraph_styles"]),
             len(model["character_styles"]), len(model["colors"])))
    for s in skipped:
        print("skipped: %s" % s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
