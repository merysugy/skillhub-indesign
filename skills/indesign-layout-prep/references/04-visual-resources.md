# Step 4 - Propose visual resources

Goal: a proposal the designer can use as a sketchbook, and the chosen pieces
as InDesign scripts that build editable elements.

## Prompt this step answers

> With the context and content you have analysed, and with this identity,
> propose graphic resources section by section. For each one: what content it
> represents, why it helps the reader, and a sketch with the brand colours and
> fonts. Do not lay out the full document: only the resources, in content
> order.

## Build the proposal

1. Read the content: extract the key words, the strong points, numbers,
   processes, comparisons, lists of concepts, and quotable sentences.
2. For each section, propose 0-3 resources. Types:
   - **Key figure**: a number that carries the argument (68%, 3x, 2027).
   - **Diagram / process**: steps, flows, cause and effect.
   - **Mind map**: a concept with branches.
   - **Comparison**: before/after, option A vs B, table of features.
   - **Pull quote**: a sentence worth isolating.
   - **Screenshot**: a tool or interface the text describes.
   - **Image**: a photo or illustration (describe it; do not invent stock).
3. For each resource write: section, type, what it represents, why it helps
   the reader, and a sketch. Prefer fewer, stronger resources over one per
   paragraph.
4. Sketches use only the brand palette and styles from step 1.

Deliver the proposal as a PDF (or HTML page) with one block per resource, in
content order. It is a sketch for the designer, not the layout: keep it
simple, no full pages.

## Turn a chosen resource into a script

The PDF is not editable in InDesign, so each resource the user picks becomes
a `.jsx` that draws it inside the document with the template's swatches and
styles, as a group the designer can move, resize or ungroup.

Start from `assets/visual_resource.jsx`:

- `CONFIG` holds the position (mm from the page's top-left), size, texts,
  swatch names and style paths (`Group:Style`). The user can edit it.
- Helpers: `box()` (rectangle), `textBox()` (text frame with styled
  paragraphs), `line()`, `ellipse()`. Compose them in `build()`.
- The script checks that every swatch and style exists before drawing and
  lists what is missing.
- It works in mm with page origin, restores the user's units afterwards, and
  is undoable in one step.

Examples of `build()` compositions:
- Process of N steps: N boxes in a row with `textBox` labels and `line`
  connectors; step numbers in the accent colour.
- Mind map: central `ellipse` with the concept, branches as `line`s to
  `textBox` nodes placed on a circle (use `Math.cos`/`Math.sin`).
- Comparison: two columns of boxes with a heading each.

Run `python3 scripts/check_es3.py` on every script, then deliver it with the
install steps from `03-text-import.md`.
