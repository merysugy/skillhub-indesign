#!/usr/bin/env python3
"""
snippet_model.py - Shared by build_snippet.py and preview_model.py.

Loads a block model (JSON) and normalises it, so both scripts read exactly
the same thing. The format is documented in references/04-idms-blocks.md;
assets/snippet-model.example.json is a complete example.

Coordinates are points, origin at the block's top-left corner, y downwards.
"""

import json
import os

ALIGNS = ("left", "center", "right")
VALIGNS = ("top", "center", "bottom")
CORNERS = ("TopLeft", "TopRight", "BottomLeft", "BottomRight")
BUILTIN_COLORS = ("Paper", "Black", "None")


class ModelError(ValueError):
    pass


def _num(v, where):
    if not isinstance(v, (int, float)):
        raise ModelError("%s must be a number, got %r" % (where, v))
    return float(v)


def _para(p, where):
    """Accept {"style": S, "runs": [...]} or the shorthand [S, run, run...]."""
    if isinstance(p, list):
        if not p or not isinstance(p[0], str):
            raise ModelError("%s: shorthand paragraph must start with the style name" % where)
        p = {"style": p[0], "runs": p[1:]}
    if not isinstance(p, dict) or "style" not in p:
        raise ModelError("%s: paragraph needs a 'style'" % where)
    runs = []
    for r in p.get("runs", []):
        if isinstance(r, str):
            runs.append({"style": None, "text": r})
        elif isinstance(r, dict) and "text" in r:
            runs.append({"style": r.get("style"), "text": str(r["text"])})
        else:
            raise ModelError("%s: a run is a string or {\"style\", \"text\"}" % where)
    if not runs:
        runs = [{"style": None, "text": ""}]
    return {"style": p["style"], "runs": runs}


def load(path):
    with open(path, encoding="utf-8") as fh:
        m = json.load(fh)
    return normalise(m, base_dir=os.path.dirname(os.path.abspath(path)))


def normalise(m, base_dir="."):
    out = {
        "name": m.get("name", "Block"),
        "font_family": m.get("font_family"),
        "layer": m.get("layer", "Layer 1"),
        "colors": {},
        "paragraph_styles": {},
        "character_styles": {},
        "items": [],
        "base_dir": base_dir,
    }
    if not out["font_family"]:
        raise ModelError("font_family is required: take it from the project's style analysis or IDML")
    for name, v in m.get("colors", {}).items():
        if name in BUILTIN_COLORS:
            raise ModelError("colour %r is built in; do not define it" % name)
        if not isinstance(v, list) or len(v) not in (3, 4):
            raise ModelError("colour %r: give [r, g, b] (0-255) or [c, m, y, k] (0-100)" % name)
        out["colors"][name] = [float(x) for x in v]

    def color_ok(c, where):
        if c is None or c in BUILTIN_COLORS or c in out["colors"]:
            return c
        raise ModelError("%s uses colour %r, which is not defined" % (where, c))

    for name, s in m.get("paragraph_styles", {}).items():
        where = "paragraph style %r" % name
        st = {
            "family": s.get("family", out["font_family"]),
            "font": s.get("font", "Regular"),
            "size": _num(s.get("size", 10), where + " size"),
            "leading": _num(s.get("leading", s.get("size", 10) * 1.2), where + " leading"),
            "color": color_ok(s.get("color", "Black"), where),
            "align": s.get("align", "left"),
            "space_before": float(s.get("space_before", 0)),
            "space_after": float(s.get("space_after", 0)),
            "left_indent": float(s.get("left_indent", 0)),
            "caps": bool(s.get("caps", False)),
            "tracking": float(s.get("tracking", 0)),
        }
        if st["align"] not in ALIGNS:
            raise ModelError("%s: align must be one of %s" % (where, ALIGNS))
        out["paragraph_styles"][name] = st

    for name, s in m.get("character_styles", {}).items():
        where = "character style %r" % name
        st = {}
        if "font" in s:
            st["font"] = s["font"]
        if "family" in s:
            st["family"] = s["family"]
        if "color" in s:
            st["color"] = color_ok(s["color"], where)
        out["character_styles"][name] = st

    for i, it in enumerate(m.get("items", [])):
        where = "item %d (%s)" % (i, it.get("name") or it.get("type"))
        t = it.get("type")
        if t == "text":
            paras = [_para(p, where) for p in it.get("paragraphs", [])]
            for p in paras:
                if p["style"] not in out["paragraph_styles"]:
                    raise ModelError("%s uses paragraph style %r, not defined" % (where, p["style"]))
                for r in p["runs"]:
                    if r["style"] and r["style"] not in out["character_styles"]:
                        raise ModelError("%s uses character style %r, not defined" % (where, r["style"]))
            inset = it.get("inset", [0, 0, 0, 0])
            if isinstance(inset, (int, float)):
                inset = [inset] * 4
            n = dict(type="text", x=_num(it["x"], where), y=_num(it["y"], where),
                     w=_num(it["w"], where), h=_num(it["h"], where), paragraphs=paras,
                     columns=int(it.get("columns", 1)), gutter=float(it.get("gutter", 12)),
                     inset=[float(v) for v in inset], valign=it.get("valign", "top"),
                     balance_columns=bool(it.get("balance_columns", False)))
            if n["valign"] not in VALIGNS:
                raise ModelError("%s: valign must be one of %s" % (where, VALIGNS))
        elif t == "rect":
            n = dict(type="rect", x=_num(it["x"], where), y=_num(it["y"], where),
                     w=_num(it["w"], where), h=_num(it["h"], where), image=it.get("image"))
            if n["image"]:
                p = n["image"] if os.path.isabs(n["image"]) else os.path.join(base_dir, n["image"])
                if not os.path.exists(p):
                    raise ModelError("%s: image %s not found" % (where, p))
                n["image_path"] = p
        elif t == "line":
            pts = it.get("points")
            if not pts or len(pts) != 2:
                raise ModelError("%s: a line has exactly 2 points; draw elbows as several lines" % where)
            n = dict(type="line", points=[[float(a), float(b)] for a, b in pts],
                     color=color_ok(it.get("color", "Black"), where), weight=float(it.get("weight", 1)))
        elif t == "polygon":
            pts = it.get("points")
            if not pts or len(pts) < 3:
                raise ModelError("%s: a polygon needs at least 3 points" % where)
            n = dict(type="polygon", points=[[float(a), float(b)] for a, b in pts])
        elif t == "oval":
            n = dict(type="oval", cx=_num(it["cx"], where), cy=_num(it["cy"], where), r=_num(it["r"], where))
        else:
            raise ModelError("%s: unknown type %r (text, rect, line, polygon, oval)" % (where, t))
        if t != "line":
            n["fill"] = color_ok(it.get("fill"), where)
            n["stroke"] = color_ok(it.get("stroke"), where)
            n["stroke_weight"] = float(it.get("stroke_weight", 1 if it.get("stroke") else 0))
        if t in ("text", "rect"):
            n["radius"] = float(it.get("radius", 0))
            corners = it.get("corners") or list(CORNERS)
            for c in corners:
                if c not in CORNERS:
                    raise ModelError("%s: corner %r not in %s" % (where, c, CORNERS))
            n["corners"] = corners
        n["name"] = it.get("name")
        out["items"].append(n)
    return out
