#!/usr/bin/env python3
"""
build_snippet.py - Block model (JSON) to an InDesign snippet (.idms).

The snippet is one group of native, editable objects (text frames, rectangles,
linked images, lines, polygons, ovals) with its paragraph and character styles
and its swatches. The user drags it onto a page or uses File > Place. Styles
and swatches with the same name as the document's are reused; new ones are
created.

    python3 build_snippet.py model.json -o block.idms
    python3 build_snippet.py model.json -o block.idms --zip    # + block.zip with Links/

Images are copied to Links/ next to the .idms, with their resolution set so
their native size equals the frame (needs Pillow). The link is relative, so
InDesign will usually ask to relink: tell the user.

Structure taken from snippets InDesign exports and from blocks that opened
correctly in InDesign (see references/04-idms-blocks.md). Do not add
attributes that are not already here without checking them against a real
InDesign export.
"""

import argparse
import os
import shutil
import sys
import zipfile
from xml.sax.saxutils import escape, quoteattr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import snippet_model  # noqa: E402

DOM = "16.0"
IT = "1 0 0 1 0 0"
LAYER = "uLayerBlock"
FORMATS = {".png": "$ID/Portable Network Graphics (PNG)", ".jpg": "$ID/JPEG", ".jpeg": "$ID/JPEG"}


def a(v):
    return quoteattr(str(v))


def fmt(v):
    return ("%.4f" % v).rstrip("0").rstrip(".")


def cref(name):
    if name is None or name == "None":
        return "Swatch/None"
    return "Color/" + name


class Ids:
    def __init__(self):
        self.n = 0

    def __call__(self, prefix="u"):
        self.n += 1
        return "%sb%x" % (prefix, self.n)


def path_xml(points, closed=True, beziers=None):
    pts = []
    for i, (x, y) in enumerate(points):
        (lx, ly), (rx, ry) = beziers[i] if beziers else ((x, y), (x, y))
        pts.append('<PathPointType Anchor="%s %s" LeftDirection="%s %s" RightDirection="%s %s"/>'
                   % tuple(fmt(v) for v in (x, y, lx, ly, rx, ry)))
    return ('<Properties><PathGeometry><GeometryPathType PathOpen="%s"><PathPointArray>%s'
            '</PathPointArray></GeometryPathType></PathGeometry></Properties>'
            % ("false" if closed else "true", "".join(pts)))


def rect_pts(x, y, w, h):
    return [(x, y), (x, y + h), (x + w, y + h), (x + w, y)]


def corners(r, which):
    if not r:
        return ""
    return "".join(' %sCornerOption="RoundedCorner" %sCornerRadius="%s"' % (c, c, fmt(r)) for c in which)


def paint(it):
    sw = it.get("stroke_weight", 0) if it.get("stroke") else 0
    return ' FillColor=%s StrokeColor=%s StrokeWeight="%s"' % (a(cref(it.get("fill"))), a(cref(it.get("stroke"))), fmt(sw))


class Builder:
    def __init__(self, model, out_dir):
        self.m = model
        self.out_dir = out_dir
        self.ids = Ids()
        self.stories = []
        self.links = []

    def story(self, paras):
        sid = self.ids("uStory")
        body = []
        for i, p in enumerate(paras):
            parts = []
            for j, r in enumerate(p["runs"]):
                cs = "CharacterStyle/" + r["style"] if r["style"] else "CharacterStyle/$ID/[No character style]"
                br = "<Br/>" if (j == len(p["runs"]) - 1 and i < len(paras) - 1) else ""
                parts.append('<CharacterStyleRange AppliedCharacterStyle=%s><Content>%s</Content>%s</CharacterStyleRange>'
                             % (a(cs), escape(r["text"]), br))
            body.append('<ParagraphStyleRange AppliedParagraphStyle=%s>%s</ParagraphStyleRange>'
                        % (a("ParagraphStyle/" + p["style"]), "".join(parts)))
        self.stories.append(
            '<Story Self="%s" AppliedTOCStyle="n" TrackChanges="false" StoryTitle="$ID/" AppliedNamedGrid="n">'
            '<StoryPreference OpticalMarginAlignment="false" OpticalMarginSize="12" FrameType="TextFrameType" '
            'StoryOrientation="Horizontal" StoryDirection="LeftToRightDirection"/>'
            '<InCopyExportOption IncludeGraphicProxies="true" IncludeAllResources="false"/>%s</Story>'
            % (sid, "".join(body)))
        return sid

    def image(self, it):
        src = it["image_path"]
        ext = os.path.splitext(src)[1].lower()
        if ext not in FORMATS:
            raise snippet_model.ModelError("image %s: use PNG or JPEG" % src)
        links = os.path.join(self.out_dir, "Links")
        os.makedirs(links, exist_ok=True)
        dst = os.path.join(links, os.path.basename(src))
        try:
            from PIL import Image
            im = Image.open(src)
            dpi = im.width * 72.0 / it["w"]
            im.save(dst, dpi=(dpi, dpi))
            ratio = (im.height / im.width) / (it["h"] / it["w"])
            if abs(ratio - 1) > 0.01:
                print("warning: %s aspect differs %.1f%% from its frame; it will be distorted or cropped"
                      % (os.path.basename(src), (ratio - 1) * 100))
        except ImportError:
            shutil.copy(src, dst)
            dpi = None
            print("warning: Pillow not installed; %s copied without setting its resolution" % src)
        self.links.append((os.path.basename(src), dpi))
        return ('<Image Self="%s" ItemTransform="1 0 0 1 %s %s"><Properties><GraphicBounds Left="0" Top="0" '
                'Right="%s" Bottom="%s"/></Properties><Link Self="%s" LinkResourceURI=%s '
                'LinkResourceFormat="%s" StoredState="Normal"/></Image>'
                % (self.ids("uImg"), fmt(it["x"]), fmt(it["y"]), fmt(it["w"]), fmt(it["h"]), self.ids("uLnk"),
                   a("file:Links/" + os.path.basename(src)), FORMATS[ext]))

    def item(self, it):
        name = ' Name=%s' % a(it["name"]) if it.get("name") else ""
        L = ' ItemLayer="%s"' % LAYER
        t = it["type"]
        if t == "text":
            sid = self.story(it["paragraphs"])
            top, left, bottom, right = it["inset"]
            vj = {"top": "TopAlign", "center": "CenterAlign", "bottom": "BottomAlign"}[it["valign"]]
            return ('<TextFrame Self="%s" ParentStory="%s" PreviousTextFrame="n" NextTextFrame="n" '
                    'ContentType="TextType"%s%s%s%s AppliedObjectStyle="ObjectStyle/$ID/[Normal Text Frame]" '
                    'ItemTransform="%s">%s<TextFramePreference TextColumnCount="%d" TextColumnGutter="%s" '
                    'FirstBaselineOffset="AscentOffset" VerticalJustification="%s" VerticalBalanceColumns="%s" '
                    'AutoSizingType="Off"><Properties><InsetSpacing type="list"><ListItem type="unit">%s</ListItem>'
                    '<ListItem type="unit">%s</ListItem><ListItem type="unit">%s</ListItem><ListItem type="unit">%s'
                    '</ListItem></InsetSpacing></Properties></TextFramePreference></TextFrame>'
                    % (self.ids("uTf"), sid, name, L, paint(it), corners(it["radius"], it["corners"]), IT,
                       path_xml(rect_pts(it["x"], it["y"], it["w"], it["h"])), it["columns"], fmt(it["gutter"]),
                       vj, "true" if it["balance_columns"] else "false",
                       fmt(top), fmt(left), fmt(bottom), fmt(right)))
        if t == "rect":
            img = self.image(it) if it.get("image") else ""
            ctype = "GraphicType" if img else "Unassigned"
            ostyle = "[Normal Graphics Frame]" if img else "[None]"
            return ('<Rectangle Self="%s" ContentType="%s"%s%s%s%s AppliedObjectStyle="ObjectStyle/$ID/%s" '
                    'ItemTransform="%s">%s%s</Rectangle>'
                    % (self.ids("uRc"), ctype, name, L, paint(it), corners(it["radius"], it["corners"]), ostyle, IT,
                       path_xml(rect_pts(it["x"], it["y"], it["w"], it["h"])), img))
        if t == "line":
            return ('<GraphicLine Self="%s" ContentType="Unassigned"%s%s StrokeColor=%s StrokeWeight="%s" '
                    'FillColor="Swatch/None" AppliedObjectStyle="ObjectStyle/$ID/[None]" ItemTransform="%s">%s'
                    '</GraphicLine>' % (self.ids("uLn"), name, L, a(cref(it["color"])), fmt(it["weight"]), IT,
                                        path_xml(it["points"], closed=False)))
        if t == "polygon":
            return ('<Polygon Self="%s" ContentType="Unassigned"%s%s%s AppliedObjectStyle="ObjectStyle/$ID/[None]" '
                    'ItemTransform="%s">%s</Polygon>' % (self.ids("uPg"), name, L, paint(it), IT, path_xml(it["points"])))
        if t == "oval":
            cx, cy, r = it["cx"], it["cy"], it["r"]
            k = 0.5522847498 * r
            pts = [(cx, cy + r), (cx + r, cy), (cx, cy - r), (cx - r, cy)]
            bz = [((cx - k, cy + r), (cx + k, cy + r)), ((cx + r, cy + k), (cx + r, cy - k)),
                  ((cx + k, cy - r), (cx - k, cy - r)), ((cx - r, cy - k), (cx - r, cy + k))]
            return ('<Oval Self="%s" ContentType="Unassigned"%s%s%s AppliedObjectStyle="ObjectStyle/$ID/[None]" '
                    'ItemTransform="%s">%s</Oval>' % (self.ids("uOv"), name, L, paint(it), IT, path_xml(pts, beziers=bz)))
        raise ValueError(t)

    def resources(self):
        m = self.m
        out = ['<Color Self="Color/Black" Model="Process" Space="CMYK" ColorValue="0 0 0 100" ColorOverride="Specialblack" '
               'AlternateSpace="NoAlternateColor" AlternateColorValue="" Name="Black" ColorEditable="false" '
               'ColorRemovable="false" Visible="true" SwatchCreatorID="7937"/>',
               '<Color Self="Color/Paper" Model="Process" Space="CMYK" ColorValue="0 0 0 0" ColorOverride="Specialpaper" '
               'AlternateSpace="NoAlternateColor" AlternateColorValue="" Name="Paper" ColorEditable="true" '
               'ColorRemovable="false" Visible="true" SwatchCreatorID="7937"/>']
        for n, v in m["colors"].items():
            space = "RGB" if len(v) == 3 else "CMYK"
            out.append('<Color Self=%s Model="Process" Space="%s" ColorValue="%s" ColorOverride="Normal" '
                       'AlternateSpace="NoAlternateColor" AlternateColorValue="" Name=%s ColorEditable="true" '
                       'ColorRemovable="true" Visible="true" SwatchCreatorID="7937"/>'
                       % (a("Color/" + n), space, " ".join(fmt(x) for x in v), a(n)))
        out.append('<Swatch Self="Swatch/None" Name="None" ColorEditable="false" ColorRemovable="false" Visible="true" '
                   'SwatchCreatorID="7937"/>')
        out.append('<StrokeStyle Self="StrokeStyle/$ID/Solid" Name="$ID/Solid"/>')
        out.append('<RootCharacterStyleGroup Self="uCsGroup"><CharacterStyle Self="CharacterStyle/$ID/[No character style]" '
                   'Imported="false" Name="$ID/[No character style]"/>')
        for n, s in m["character_styles"].items():
            at = ""
            if "font" in s:
                at += " FontStyle=%s" % a(s["font"])
            if "color" in s:
                at += " FillColor=%s" % a(cref(s["color"]))
            fam = '<AppliedFont type="string">%s</AppliedFont>' % escape(s["family"]) if "family" in s else ""
            out.append('<CharacterStyle Self=%s Imported="false" Name=%s%s><Properties><BasedOn type="string">'
                       '$ID/[No character style]</BasedOn>%s</Properties></CharacterStyle>'
                       % (a("CharacterStyle/" + n), a(n), at, fam))
        out.append('</RootCharacterStyleGroup>')
        out.append('<RootParagraphStyleGroup Self="uPsGroup">'
                   '<ParagraphStyle Self="ParagraphStyle/$ID/[No paragraph style]" Name="$ID/[No paragraph style]" '
                   'Imported="false" NextStyle="ParagraphStyle/$ID/[No paragraph style]" KeyboardShortcut="0 0"/>'
                   '<ParagraphStyle Self="ParagraphStyle/$ID/NormalParagraphStyle" Name="$ID/NormalParagraphStyle" '
                   'Imported="false" NextStyle="ParagraphStyle/$ID/NormalParagraphStyle" KeyboardShortcut="0 0">'
                   '<Properties><BasedOn type="string">$ID/[No paragraph style]</BasedOn></Properties></ParagraphStyle>')
        align = {"left": "LeftAlign", "center": "CenterAlign", "right": "RightAlign"}
        for n, s in m["paragraph_styles"].items():
            out.append('<ParagraphStyle Self=%s Name=%s Imported="false" NextStyle=%s FontStyle=%s PointSize="%s" '
                       'FillColor=%s Justification="%s" SpaceBefore="%s" SpaceAfter="%s" LeftIndent="%s" '
                       'Hyphenation="false" Tracking="%s" Capitalization="%s" KeyboardShortcut="0 0"><Properties>'
                       '<BasedOn type="string">$ID/NormalParagraphStyle</BasedOn><Leading type="unit">%s</Leading>'
                       '<AppliedFont type="string">%s</AppliedFont></Properties></ParagraphStyle>'
                       % (a("ParagraphStyle/" + n), a(n), a("ParagraphStyle/" + n), a(s["font"]), fmt(s["size"]),
                          a(cref(s["color"])), align[s["align"]], fmt(s["space_before"]), fmt(s["space_after"]),
                          fmt(s["left_indent"]), fmt(s["tracking"]), "AllCaps" if s["caps"] else "Normal",
                          fmt(s["leading"]), escape(s["family"])))
        out.append('</RootParagraphStyleGroup>')
        out.append('<RootObjectStyleGroup Self="uObjGroup"><ObjectStyle Self="ObjectStyle/$ID/[None]" Name="$ID/[None]"/>'
                   '<ObjectStyle Self="ObjectStyle/$ID/[Normal Graphics Frame]" Name="$ID/[Normal Graphics Frame]">'
                   '<Properties><BasedOn type="string">$ID/[None]</BasedOn></Properties></ObjectStyle>'
                   '<ObjectStyle Self="ObjectStyle/$ID/[Normal Text Frame]" Name="$ID/[Normal Text Frame]">'
                   '<Properties><BasedOn type="string">$ID/[None]</BasedOn></Properties></ObjectStyle>'
                   '</RootObjectStyleGroup>')
        return "".join(out)

    def build(self):
        body = "".join(self.item(it) for it in self.m["items"])
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<?aid style="50" type="snippet" readerVersion="6.0" featureSet="257" product="16.0(32)" ?>\n'
                '<?aid SnippetType="PageItem"?>\n'
                '<Document DOMVersion="%s" Self="d">%s'
                '<Layer Self="%s" Name=%s Visible="true" Locked="false" IgnoreWrap="false" ShowGuides="true" '
                'LockGuides="false" UI="true" Expendable="true" Printable="true"><Properties>'
                '<LayerColor type="enumeration">LightBlue</LayerColor></Properties></Layer>'
                '<Spread Self="uSpreadBlock"><Group Self="uGroupBlock" Name=%s ItemLayer="%s" '
                'AppliedObjectStyle="ObjectStyle/$ID/[None]" ItemTransform="1 0 0 1 0 0">%s</Group></Spread>%s'
                '</Document>' % (DOM, self.resources(), LAYER, a(self.m["layer"]), a(self.m["name"]), LAYER, body, "".join(self.stories)))


def bounds(m):
    xs, ys = [], []
    for it in m["items"]:
        if it["type"] in ("text", "rect"):
            xs += [it["x"], it["x"] + it["w"]]; ys += [it["y"], it["y"] + it["h"]]
        elif it["type"] == "oval":
            xs += [it["cx"] - it["r"], it["cx"] + it["r"]]; ys += [it["cy"] - it["r"], it["cy"] + it["r"]]
        else:
            xs += [p[0] for p in it["points"]]; ys += [p[1] for p in it["points"]]
    return min(xs), min(ys), max(xs), max(ys)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("model")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--zip", action="store_true", help="also write <output>.zip with the .idms and Links/")
    args = ap.parse_args(argv)
    try:
        m = snippet_model.load(args.model)
        out_dir = os.path.dirname(os.path.abspath(args.output))
        b = Builder(m, out_dir)
        xml = b.build()
    except (snippet_model.ModelError, KeyError) as exc:
        print("error: %s" % exc)
        return 1
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(xml)
    x0, y0, x1, y1 = bounds(m)
    counts = {}
    for it in m["items"]:
        counts[it["type"]] = counts.get(it["type"], 0) + 1
    print("%s: group %r, %s x %s pt, %d objects (%s)" % (
        args.output, m["name"], fmt(x1 - x0), fmt(y1 - y0), len(m["items"]),
        ", ".join("%d %s" % (v, k) for k, v in sorted(counts.items()))))
    print("styles: %d paragraph, %d character; swatches: %d" % (
        len(m["paragraph_styles"]), len(m["character_styles"]), len(m["colors"])))
    for name, dpi in b.links:
        print("linked image: Links/%s%s" % (name, " at %d ppi" % round(dpi) if dpi else ""))
    if args.zip:
        zpath = os.path.splitext(args.output)[0] + ".zip"
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(args.output, os.path.basename(args.output))
            for name, _ in b.links:
                z.write(os.path.join(out_dir, "Links", name), "Links/" + name)
        print("zip: %s" % zpath)
    return 0


if __name__ == "__main__":
    sys.exit(main())
