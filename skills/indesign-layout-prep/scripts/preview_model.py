#!/usr/bin/env python3
"""
preview_model.py - PNG preview of a block model, to compare with the user's
capture before delivering the .idms.

    python3 preview_model.py model.json -o preview.png --fonts DIR [--fonts DIR2] [--scale 2]
    python3 preview_model.py model.json -o in-context.png --fonts DIR --page page.json

It draws the same model build_snippet.py writes, and composes text the way
InDesign roughly does (greedy line breaks, leading, space before/after,
columns). It warns when a frame's text does not fit (overset). InDesign may
break lines differently: say so when you show it.

--page draws the block inside a page described by another model (header,
text frames, other blocks) at the block's offset (--at X Y), to show a
proposal in context.

Fonts are found by family and style name in the --fonts folders (TTF/OTF).
A missing font falls back to DejaVu Sans with a warning.

Needs Pillow and fontTools.
"""

import argparse
import glob
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import snippet_model  # noqa: E402


def font_index(dirs):
    from fontTools.ttLib import TTFont
    idx = {}
    for d in dirs:
        for path in glob.glob(os.path.join(d, "**", "*.[ot]tf"), recursive=True):
            try:
                names = TTFont(path, lazy=True)["name"]
            except Exception:
                continue
            fam = names.getDebugName(16) or names.getDebugName(1)
            sty = names.getDebugName(17) or names.getDebugName(2)
            if fam and sty:
                idx[(fam.lower(), sty.lower())] = path
    return idx


class Preview:
    def __init__(self, model, font_dirs, scale=2.0):
        self.m, self.S = model, scale
        self.idx = font_index(font_dirs)
        self.cache, self.warnings, self.missing = {}, [], set()

    def font(self, family, style, size):
        key = (family, style, size)
        if key not in self.cache:
            path = self.idx.get((family.lower(), style.lower()))
            if not path:
                if (family, style) not in self.missing:
                    self.missing.add((family, style))
                    self.warnings.append("font %s %s not found: preview uses a fallback" % (family, style))
                try:
                    f = ImageFont.truetype("DejaVuSans.ttf", max(1, round(size * self.S)))
                except OSError:
                    f = ImageFont.load_default()
            else:
                f = ImageFont.truetype(path, max(1, round(size * self.S)))
            self.cache[key] = f
        return self.cache[key]

    def col(self, name):
        if name is None or name == "None":
            return None
        if name == "Paper":
            return (255, 255, 255)
        if name == "Black":
            return (0, 0, 0)
        v = self.m["colors"][name]
        if len(v) == 3:
            return tuple(int(round(x)) for x in v)
        c, m, y, k = [x / 100.0 for x in v]
        return tuple(int(round(255 * (1 - a) * (1 - k))) for a in (c, m, y))

    def box(self, dr, it, ox, oy):
        S = self.S
        if not (it.get("fill") or it.get("stroke")):
            return
        xy = [(it["x"] + ox) * S, (it["y"] + oy) * S, (it["x"] + ox + it["w"]) * S, (it["y"] + oy + it["h"]) * S]
        corners = tuple(c in it["corners"] for c in ("TopLeft", "TopRight", "BottomRight", "BottomLeft"))
        dr.rounded_rectangle(xy, radius=it.get("radius", 0) * S, fill=self.col(it.get("fill")),
                             outline=self.col(it.get("stroke")),
                             width=max(1, round(it["stroke_weight"] * S)) if it.get("stroke") else 0,
                             corners=corners)

    def run_style(self, ps, cs_name):
        fam, sty, color = ps["family"], ps["font"], ps["color"]
        if cs_name:
            cs = self.m["character_styles"][cs_name]
            fam, sty, color = cs.get("family", fam), cs.get("font", sty), cs.get("color", color)
        return fam, sty, color

    def layout(self, it):
        S = self.S
        top, left, bottom, right = it["inset"]
        cols, gut = it["columns"], it["gutter"]
        cw = (it["w"] - left - right - gut * (cols - 1)) / cols
        inner_h = it["h"] - top - bottom
        plines = []
        for p in it["paragraphs"]:
            ps = self.m["paragraph_styles"][p["style"]]
            words = []
            for r in p["runs"]:
                text = r["text"].upper() if ps["caps"] else r["text"]
                fam, sty, color = self.run_style(ps, r["style"])
                for k, part in enumerate(text.split(" ")):
                    if k:
                        words.append((" ", fam, sty, color))
                    if part:
                        words.append((part, fam, sty, color))
            lines, cur, curw = [], [], 0.0
            avail = cw - ps["left_indent"]
            for w in words:
                ww = self.font(w[1], w[2], ps["size"]).getlength(w[0]) / S
                if w[0] == " ":
                    if cur:
                        cur.append(w); curw += ww
                    continue
                if cur and curw + ww > avail + 0.01:
                    while cur and cur[-1][0] == " ":
                        curw -= self.font(cur[-1][1], cur[-1][2], ps["size"]).getlength(" ") / S; cur.pop()
                    lines.append((cur, curw)); cur, curw = [], 0.0
                cur.append(w); curw += ww
            while cur and cur[-1][0] == " ":
                curw -= self.font(cur[-1][1], cur[-1][2], ps["size"]).getlength(" ") / S; cur.pop()
            lines.append((cur, curw))
            plines.append((ps, lines))
        # balanced columns: fill evenly; otherwise fill the first column first
        total = sum(len(l) for _, l in plines)
        per_col = -(-total // cols) if it["balance_columns"] and cols > 1 else None
        placed, overflow, col, y, first, in_col = [], False, 0, 0.0, True, 0
        for ps, lines in plines:
            if not first:
                y += ps["space_before"]
            for segs, wsum in lines:
                asc = ps["size"] * 0.93
                base = y + (asc if first else ps["leading"])
                full = base + ps["size"] * 0.25 > inner_h + 0.5 or (per_col and in_col >= per_col)
                if full:
                    if col + 1 < cols:
                        col += 1; y = 0.0; first = True; in_col = 0; base = asc
                    else:
                        overflow = True
                        break
                placed.append((col, base, ps, segs, wsum))
                y, first, in_col = base, False, in_col + 1
            if overflow:
                break
            y += ps["space_after"]
        return placed, overflow, cw

    def draw(self, im, dr, ox=0.0, oy=0.0):
        S = self.S
        for it in self.m["items"]:
            t = it["type"]
            if t in ("text", "rect"):
                self.box(dr, it, ox, oy)
            if t == "rect" and it.get("image_path"):
                src = Image.open(it["image_path"]).convert("RGBA").resize((round(it["w"] * S), round(it["h"] * S)))
                im.paste(src, (round((it["x"] + ox) * S), round((it["y"] + oy) * S)), src)
            elif t == "line":
                dr.line([((x + ox) * S, (y + oy) * S) for x, y in it["points"]], fill=self.col(it["color"]),
                        width=max(1, round(it["weight"] * S)))
            elif t == "polygon":
                dr.polygon([((x + ox) * S, (y + oy) * S) for x, y in it["points"]], fill=self.col(it.get("fill")))
            elif t == "oval":
                cx, cy, r = it["cx"] + ox, it["cy"] + oy, it["r"]
                dr.ellipse([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S], fill=self.col(it.get("fill")),
                           outline=self.col(it.get("stroke")),
                           width=max(1, round(it["stroke_weight"] * S)) if it.get("stroke") else 0)
            elif t == "text":
                self.text(dr, it, ox, oy)

    def text(self, dr, it, ox, oy):
        S = self.S
        placed, overflow, cw = self.layout(it)
        top, left, bottom, right = it["inset"]
        self.lines = getattr(self, "lines", [])
        if overflow:
            label = it.get("name") or it["paragraphs"][0]["runs"][0]["text"][:30]
            self.warnings.append("OVERSET text in frame %r" % label)
            x1, y1 = (it["x"] + ox + it["w"]) * S, (it["y"] + oy + it["h"]) * S
            dr.rectangle([x1 - 6 * S, y1 - 6 * S, x1, y1], fill=(230, 0, 0))
        dy = 0.0
        if placed and it["valign"] != "top":
            content = max(p[1] for p in placed) + placed[-1][2]["size"] * 0.25
            free = it["h"] - top - bottom - content
            dy = free / 2 if it["valign"] == "center" else free
        for col, base, ps, segs, wsum in placed:
            x = it["x"] + ox + left + col * (cw + it["gutter"]) + ps["left_indent"]
            avail = cw - ps["left_indent"]
            if ps["align"] == "center":
                x += (avail - wsum) / 2
            elif ps["align"] == "right":
                x += avail - wsum
            yb = it["y"] + oy + top + base + dy
            self.lines.append((x, yb - ps["size"] * 0.8, x + wsum, yb + ps["size"] * 0.2))
            for text, fam, sty, color in segs:
                f = self.font(fam, sty, ps["size"])
                dr.text((x * S, yb * S), text, font=f, fill=self.col(color), anchor="ls")
                x += f.getlength(text) / S


def extent(m):
    import build_snippet
    return build_snippet.bounds(m)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("model")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--fonts", action="append", default=[], help="folder with the fonts (repeatable)")
    ap.add_argument("--scale", type=float, default=2.0, help="pixels per point")
    ap.add_argument("--page", help="page model to draw the block on (proposal in context)")
    ap.add_argument("--at", nargs=2, type=float, default=[0, 0], metavar=("X", "Y"),
                    help="block offset on the page, in pt")
    ap.add_argument("--page-size", nargs=2, type=float, default=[595.276, 841.89], metavar=("W", "H"))
    args = ap.parse_args(argv)
    try:
        m = snippet_model.load(args.model)
        page = snippet_model.load(args.page) if args.page else None
    except (snippet_model.ModelError, KeyError) as exc:
        print("error: %s" % exc)
        return 1
    S, margin = args.scale, 10.0
    warnings = []
    if page:
        W, H = args.page_size
        im = Image.new("RGB", (round(W * S), round(H * S)), "white")
        dr = ImageDraw.Draw(im)
        pv = Preview(page, args.fonts, S); pv.draw(im, dr); warnings += ["page: " + w for w in pv.warnings]
        pv2 = Preview(m, args.fonts, S); pv2.draw(im, dr, args.at[0], args.at[1]); warnings += pv2.warnings
        x0, y0, x1, y1 = extent(m)
        bx0, by0, bx1, by1 = x0 + args.at[0], y0 + args.at[1], x1 + args.at[0], y1 + args.at[1]
        hits = [l for l in getattr(pv, "lines", []) if l[0] < bx1 and l[2] > bx0 and l[1] < by1 and l[3] > by0]
        if hits:
            warnings.append("the block overlaps %d line(s) of page text: move it or apply text wrap "
                            "(Window > Text Wrap) to the group" % len(hits))
    else:
        x0, y0, x1, y1 = extent(m)
        im = Image.new("RGB", (round((x1 - x0 + 2 * margin) * S), round((y1 - y0 + 2 * margin) * S)), "white")
        dr = ImageDraw.Draw(im)
        pv = Preview(m, args.fonts, S); pv.draw(im, dr, margin - x0, margin - y0); warnings += pv.warnings
    im.save(args.output)
    print("%s: %d x %d px" % (args.output, im.width, im.height))
    for w in warnings:
        print("warning: %s" % w)
    if not warnings:
        print("no overset text")
    return 0


if __name__ == "__main__":
    sys.exit(main())
