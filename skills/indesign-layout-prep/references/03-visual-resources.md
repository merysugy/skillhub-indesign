# Visual resources: proposal (phases 1-2) and script alternative

Goal: in phase 1, a table of graphic elements the user can approve; in
phase 2, the whole document laid out as a proposal in the reference style.
Both come before any InDesign work, so decisions are made on something
visual.

## Phase 1 - Graphic-elements proposal

1. Read the content: extract the key words, the strong points, numbers,
   processes, comparisons, lists of concepts, and quotable sentences.
2. Inventory the reference: which compositions it uses (key-figure boxes,
   callouts, cards, bands with images, numbered steps, diagrams, comparison
   tables, cover, closing page) and how they are styled.
3. For each section, propose 0-3 elements. Types:
   - **Key figure**: a number that carries the argument. Only real figures
     with a source; if there are none, a qualitative box or a marked gap.
   - **Diagram / process**: steps, flows, cause and effect, layers.
   - **Mind map**: a concept with branches.
   - **Comparison**: before/after, option A vs B, table of capabilities.
   - **Pull quote**: a sentence worth isolating.
   - **Screenshot**: a tool or interface the text describes.
   - **Image**: a photo or illustration (describe it; do not invent stock).
   - **Reference compositions**: reuse the reference's boxes, cards, bands
     and steps where the content fits the same pattern.
4. **Sales space.** Include where the document sells: the closing page (a
   headline, one line, a call to action, contact people with role and
   email), where the product is first named, and any contact or demo
   prompt. If the reference has a closing page, follow its structure so the
   documents read as a series; never copy its text or contacts.
5. Deliver a table: section | element | what it represents | why it helps |
   notes (data or text still needed). Prefer fewer, stronger elements over
   one per paragraph.

## Phase 2 - Full layout proposal

Lay out the whole document as a PDF that looks like the reference: same
page size, grid, header and footer, fonts, colours and compositions. It is a
proposal to react to, built quickly, not the final design.

- **How:** one HTML file with the document's CSS (fonts embedded with
  `@font-face`, colours as variables) rendered to PDF (WeasyPrint or a
  headless browser). Diagrams as inline SVG; boxes and cards as HTML.
- **Fonts:** use the reference's fonts if their licence allows it (check:
  SIL OFL fonts can be embedded); otherwise the closest available, and say so.
- **Images:** the reference's photos belong to its project. Use generated
  abstract backgrounds or marked placeholders instead.
- **Text you write** (titles, box texts, captions, FAQ questions) is marked
  in the delivery. Claims to verify can be highlighted in the PDF.
- **Look at every page** rendered as an image before delivering: overflowing
  text, empty thirds of a page, elements covering titles, wrong breaks.
- **Rendering pitfalls seen in practice (WeasyPrint):** gradients inside an
  SVG used as a CSS background may not render (put the gradient in CSS and
  keep only the pattern in the SVG); `box-shadow` can leave streaks (use a
  border); keep diagram SVGs inline and sized in pt.
- After the PDF, list what changed from the draft (merged or dropped text),
  what you wrote, and what is pending (contacts, figures, sources).

Building elements: once the user picks elements from the proposal, they
become `.idms` blocks (phase 4, `04-idms-blocks.md`).

## Turn a chosen resource into a script (alternative)

The default for an editable element is an `.idms` block the user drags into
the page (phase 4, `04-idms-blocks.md`). Use a script only when the element
has to be computed inside the open document (repeated on many pages, placed
relative to existing frames) or the user asks for a script.

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
install steps from `import-script.md`.
