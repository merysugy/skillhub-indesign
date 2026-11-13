# Phase 4 - Editable blocks (.idms)

Goal: the user drags a file onto their InDesign page and gets the element as
native, editable objects with the document's own styles and swatches.

An `.idms` (InDesign snippet) holds one group of page items plus the styles,
swatches and stories they use. When it is placed, styles and swatches with
the same name as the document's are **reused** (the document's definition
wins); the others are created. So naming is what connects a block to the
document.

## Contents

1. Where the styles and colours come from
2. From a capture to a model
3. The model format
4. Build, preview, check
5. Fitting a block into a page
6. Images
7. Deliver
8. Reuse an earlier block
9. Limits

## 1. Where the styles and colours come from

Never from another project, and never from this skill's example. In order:

1. The styles and swatches of **this** document: the phase 1 analysis, the
   IDML built in phase 3, or the user's own IDML (`extract_idml.py`). Use
   their exact names so the block picks up the document's definitions.
2. If the element needs something the document does not have (a box fill, a
   connector grey), add a new swatch or style in the same identity, with a
   descriptive name in the user's language, and list it in the delivery.
3. `font_family` is the document's font. Font weights (`font`) use the
   style names InDesign shows for that family (Regular, Bold, SemiBold...).

## 2. From a capture to a model

- **Recognise it first.** If the capture shows an element proposed or built
  earlier, start from that model or file, not from measuring pixels.
- **Scale.** Decide the block's real width in pt (full text width, one
  column, a given box) and convert: `pt = px * width_pt / width_px`. Measure
  the capture's key edges in pixels (boxes, rows, gaps) and convert them all
  with the same factor.
- **Colours.** Sample flat areas of the capture (not antialiased edges) and
  match them to the document's swatches. Only create a new swatch when no
  existing one is close.
- **Text.** Copy texts exactly from the capture. Use the document's text
  styles; size only changes if the capture clearly differs.
- **Structure.** Prefer fewer, richer objects: a card is one text frame with
  fill, stroke, rounded corners and insets, not a rectangle plus a frame. A
  connector with elbows is several 2-point lines; an arrow head is a small
  polygon; an icon is built from ovals, lines and polygons.
- **Names.** Give every object a `name` ("Card · Network layer", "Caption");
  it shows in the Layers panel and makes the block easy to edit.

## 3. The model format

JSON, points, origin at the block's top-left, y downwards. Complete example:
`../assets/snippet-model.example.json`.

```json
{
  "name": "Block · ...",            // group name in the Layers panel
  "font_family": "...",             // required: the document's font
  "layer": "...",                   // optional: the document's layer name
  "colors": {"Name": [r, g, b]},    // or [c, m, y, k] for print; Paper, Black, None are built in
  "paragraph_styles": {"Name": {"font": "Bold", "size": 9, "leading": 12, "color": "Name",
                       "align": "left|center|right", "space_before": 0, "space_after": 0,
                       "left_indent": 0, "caps": false, "tracking": 0, "family": "optional"}},
  "character_styles": {"Name": {"font": "Bold", "color": "Name"}},
  "items": [
    {"type": "text", "x": 0, "y": 0, "w": 100, "h": 40,
     "paragraphs": [["Style", "plain text", {"style": "CharStyle", "text": "styled run"}]],
     "columns": 1, "gutter": 12, "inset": [top, left, bottom, right], "valign": "top|center|bottom",
     "balance_columns": false, "fill": "Name", "stroke": "Name", "stroke_weight": 1,
     "radius": 8, "corners": ["TopLeft", "TopRight"], "name": "..."},
    {"type": "rect", "x": 0, "y": 0, "w": 100, "h": 40, "image": "path/to/file.png", "...": "same paint and corners"},
    {"type": "line", "points": [[x1, y1], [x2, y2]], "color": "Name", "weight": 0.8},
    {"type": "polygon", "points": [[x, y], [x, y], [x, y]], "fill": "Name"},
    {"type": "oval", "cx": 10, "cy": 10, "r": 6, "fill": "Name", "stroke": "Name", "stroke_weight": 1}
  ]
}
```

`corners` lists which corners are rounded (all four by default), useful for
a bar that only rounds its top corners.

## 4. Build, preview, check

```bash
python3 scripts/build_snippet.py block.json -o Block_name.idms --zip
python3 scripts/preview_model.py block.json -o block.png --fonts <font folder>
python3 scripts/check_idml.py Block_name.idms
```

- Look at the preview next to the capture before delivering; fix the model,
  not the XML.
- The preview composes text roughly like InDesign. A frame marked as overset
  needs more height or less text. InDesign may break lines a little
  differently: keep a few points of spare height in text frames.
- If the fonts are not available, the preview uses a fallback and says so:
  geometry is still right, line breaks are not reliable.
- Never deliver a block that `check_idml.py` rejects.

## 5. Fitting a block into a page

When the block goes into a specific area (a column, the space under a
text), size it to that area: the column width from the document's grid, the
height that is free. Show it in context:

```bash
python3 scripts/preview_model.py block.json -o in-context.png --fonts <dir> \
    --page page.json --at X Y
```

`page.json` is a model with the page's frames (header, text frame with the
real text if the user sent it). The preview warns when the block overlaps
the page text. In the delivery, tell the user to apply text wrap to the group
(Window > Text Wrap, wrap around bounding box, with a small top offset) so
the text never runs under it.

## 6. Images

- Pass the image path in the model. The build copies it to `Links/` next to
  the `.idms` and sets its resolution so its native size equals the frame.
  It reports the resulting ppi: below about 200 ppi, warn the user.
- Keep the image's aspect ratio in the frame (the build warns if not).
- Crop screenshots to the relevant panel before building; a full screen is
  only worth it once, as a hero image.
- The link is relative. InDesign usually shows it as missing: tell the user
  to relink with Window > Links > Relink, pointing to the `Links` folder.
- Deliver a zip with the `.idms` and `Links/` (`--zip`).

## 7. Deliver

Say, briefly:

1. How to place it: File > Place (or drag the `.idms` onto the page), and how
   to relink images if needed.
2. What comes in: the group name, its size in pt, the object count, and what
   each part is (cards, connectors, labels, image, caption).
3. What it reuses from the document and what it adds (new swatches and
   styles, by name).
4. What was checked (valid file, preview compared with the capture) and what
   was not (how InDesign opens it).
5. Anything you noticed in the capture worth fixing (broken emphasis, empty
   paragraphs used as spacing, text from another document, real data).

## 8. Reuse an earlier block

If the user brings an `.idms` from another conversation, or asks to change a
block delivered earlier:

```bash
python3 scripts/idms_to_model.py Block.idms -o block.json --links <Links folder>
```

Edit the model and build again. The converter reads everything
`build_snippet.py` writes; with snippets exported by InDesign it reads the
supported subset and lists what it skipped (gradients, rotated objects,
other item types). Tell the user what would be lost before rebuilding.

## 9. Limits

- Supported: text frames (columns, insets, vertical alignment, balanced
  columns), rectangles, linked PNG/JPEG images, 2-point lines, polygons,
  circles, rounded corners, solid RGB or CMYK swatches, paragraph and
  character styles.
- Not supported: gradients, transparency, effects, rotated objects, object
  styles, tables, anchored objects, text on a path. For those, describe the
  manual step, or use a script (`visual_resource.jsx`) if the user prefers.
- Master page items (headers, footers, page numbers) are not generated; a
  header or footer can be delivered as a block to place on the master page,
  and the page number marker is inserted in InDesign.
