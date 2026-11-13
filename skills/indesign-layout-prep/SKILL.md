---
name: "indesign-layout-prep"
description: Prepares documents and elements for professional layout in Adobe InDesign, in any language. Reviews the Word content, analyses the reference (PDF, or the user's InDesign as IDML), proposes graphic elements and a full layout in that style, and builds an IDML with styles, swatches and text laid out. Turns any element the user picks (diagram, box, card, key figure, block with a product screenshot, or a capture of something proposed earlier) into an editable .idms snippet to drag into their InDesign, and proposes where product screenshots fit or what to put in an empty page area. Also writes ExtendScript to import Word inside InDesign or translate a laid-out .indd. Use whenever the user mentions InDesign, IDML, IDMS, .indd, .jsx for InDesign, layout/maquetación, a whitepaper or report, asks to send something to InDesign or make it editable (pásalo a InDesign, hazlo editable), sends a capture of an element, mockup or page area to make editable or fill, or wants a layout translated, even without naming the skill.
---

# InDesign layout prep

Claude does not design the document. Claude **prepares** it so the designer
can design it in InDesign: the styles and swatches are set up, the text is
placed and styled, the graphic elements arrive as editable native objects,
and every proposal is shown visually before anything is built. The
mechanical work shrinks, and the design stays with a person.

The phases below come from a real project taken from a Word draft to
InDesign. Only the method is kept: every project's identity, styles and
content come from that project's own reference and documents.

Always answer in the user's language. Use the style and swatch names the user
and the brand already use.

## First: is this workflow the right tool?

- **Use it** when the result has to be professional: print-ready or
  device-ready, long or important documents (whitepapers, reports, magazines,
  catalogues), or anything that will be iterated on in InDesign.
- **Don't use it** for quick, low-stakes pieces Claude can produce on its
  own, such as a one-page summary or an internal note. Say so and offer to
  make it directly.

## Read the request: which phase, which deliverable

Most requests after the first one are short and come with a screenshot.
Classify them by intent, in whatever language the user writes. The examples
are illustrations, not keywords to match.

| The user sends / asks for | Phase | Deliver |
| --- | --- | --- |
| A reference (PDF/IDML) and content (Word), and an analysis or proposal ("analyse this", "propose elements"; "analiza", "propón") | 1 | Content review, identity analysis, graphic-elements proposal |
| A layout proposal ("lay it out", "layout proposal"; "propuesta de maquetación", "maquétalo") | 2 | Full layout proposal as a PDF in the reference style |
| The document in InDesign ("send it to InDesign", "build the IDML"; "pásalo a InDesign", "prepara el IDML"), or their old InDesign as IDML | 3 | IDML with styles and the text laid out |
| A capture of an element (diagram, box, block, often one Claude proposed earlier) to make editable ("make it editable", "ready to place in InDesign"; "hazlo editable", "listo para colocar") | 4a | An `.idms` block, ready to drag in |
| Captures of the product (app screens, mockups) and where they would go ("where would these fit"; "dónde irían", "cómo las añadirías") | 4b | Placement proposal with pages shown in context |
| A capture of a page area and what to put there ("what could go here"; "propuesta para colocar aquí") | 4c | A proposal for that area (and the `.idms` if asked) |
| A Word file and a script that imports it inside InDesign ("a script to import this Word file"; "un script que lo importe") | Script | `import_docx.jsx` filled in |
| A laid-out document in another language, keeping the layout ("translate it keeping the layout"; "tradúcelo manteniendo la maqueta") | Translation | Translation script |

Rules that come from real corrections:

- **Propose or build.** A request for a proposal ("propose", "where would
  it go"; "propuesta", "dónde irían") gets a visual proposal, then wait. A
  request for the file ("send it to InDesign", "make it editable", "prepare
  it"; "pásalo", "hazlo editable", "prepara") gets the file built. When the
  user asks for both in one message ("propose something and prepare the
  editable file too"), deliver both together, with a preview of the proposal
  in context.
- **Recognise your own work.** If a capture shows an element proposed or
  built earlier in the conversation, say which one it is and build from that
  model (same texts, colours, proportions). If the user brings an `.idms`
  from another conversation, convert it back with `scripts/idms_to_model.py`
  and edit the model instead of rebuilding it from a capture. Never answer a
  capture with text only when the user wants it in InDesign.
- **A capture of a finished element means "make it editable"**, not "comment
  on it", unless the user asks for an opinion.
- One phase at a time otherwise: end each one with what was produced and what
  to check, then wait for the go-ahead.

## Inputs and routes

Ask only for what is missing, in one message:

1. **Content**: the Word document (.docx) to lay out.
2. **Where the design comes from**:
   - **Route A, a reference to replicate**: a PDF, or a PDF export of a
     design made in Figma, InDesign, Canva and so on.
   - **Route B, styles that already exist in InDesign**: a template or a
     previous document, exported as **IDML** (File > Save As > InDesign
     Markup (IDML)).
3. **Format** (route A, if not obvious): page size, margins, columns, facing
   pages, print or screen.

No style system is bundled with this skill. Every project's styles come from
its own reference (route A) or its own IDML (route B). Never reuse styles,
colours, fonts or content from another project.

## Phase 1: Review the content and analyse the identity

1. **Review the content first.** Read `references/00-content-review.md`.
   Drafts often contain several versions of the same text, unverified
   claims, figures with no source, text copied from another product, or
   real data in screenshots. Report what you found, list the options (for
   example: consolidate the versions, or lay them out as they are) and ask.
   Never pick silently.
2. **Analyse the identity** (route A: `references/01-style-analysis.md`;
   route B: `references/existing-idml.md`): the style table, the grid, the
   palette, and the graphic elements the reference uses (key-figure boxes,
   callouts, cards, bands, diagrams, tables, cover, closing page).
3. **Propose graphic elements, section by section**
   (`references/03-visual-resources.md`), in a table: section, element,
   what it represents, why it helps. Include the **sales space**: the closing
   call to action, contacts, and where the product is named. If the content
   has no figures, do not invent them: propose qualitative boxes, or leave a
   marked gap for a real figure with its source.

## Phase 2: Full layout proposal

Lay out the whole document as a PDF in the reference style: cover, every
page, the elements from phase 1 and the closing page. It is a proposal the
user reacts to, not the final design. Details and rendering pitfalls are in
`references/03-visual-resources.md`.

- Mark any text Claude wrote (titles, captions, box texts) and say so.
- Render every page and look at it before delivering.
- After the PDF, list what changed from the draft and what is still pending.

## Phase 3: IDML with styles and text

**Route A.** Read `references/02-idml-document.md`.
```bash
python3 scripts/build_idml.py style-system.json -o <n>.idml --content content.docx
python3 scripts/build_idml.py style-system.json -o <n>-template.idml
python3 scripts/check_idml.py <n>.idml <n>-template.idml
```

**Route B.** Read `references/existing-idml.md`.
```bash
python3 scripts/extract_idml.py their.idml -o style-system.json   # then add roles
python3 scripts/fill_idml.py their.idml style-system.json content.docx -o <n>.idml
python3 scripts/check_idml.py <n>.idml
```

In both routes:
- Never hand-write IDML or IDMS XML. Use the scripts, and fix the input
  (JSON or model) when they report an error.
- Never deliver a file that `check_idml.py` rejects.
- The page count is an estimate with one spare page. Overset text is never
  lost. Tell the user.
- Pass on the script's report: styles, lists, tables, images not placed.
- Master page items (header, footer, page number) are not generated. Tell the
  user to add them on the master page in InDesign (page number: Type > Insert
  Special Character > Markers > Current Page Number), or deliver the header
  or footer as an `.idms` block to place on the master page.

## Phase 4: Editable blocks and proposals from captures

This is where most of the iteration happens. Read
`references/04-idms-blocks.md` before building any block.

**4a. Capture or proposal → `.idms` block.** Measure the capture (or take
the model of an element proposed earlier), build it with
`scripts/build_snippet.py`, preview it with `scripts/preview_model.py`,
compare the preview with the capture, and validate it with
`scripts/check_idml.py`. Deliver the `.idms` (in a zip with a `Links` folder
when it has images) and say:
- how to place it (File > Place or drag it onto the page) and how to relink
  images if they show as missing;
- what comes in: the group name, its size in pt, the object count, and which
  parts are editable;
- which styles and swatches it adds and which it reuses from the document;
- what was checked and what was not (Claude cannot open InDesign).

**4b. Product screenshots or mockups → where they go.** Read
`references/05-proposals-from-captures.md`. Deliver a map (capture → page →
treatment), sample pages in context, and the captures you advise against,
with the reason (redundant, wrong language, real data, third-party licence).

**4c. An empty area of a page → what to put there.** Propose something
coherent with the text next to it: a diagram of that section, a box, a
screenshot, a key figure. Fit it to the area (column width, available
height) and show it in context. Build the `.idms` only if the user asked for
it. Point out problems you see in the capture (broken emphasis, empty
paragraphs used as spacing, text from another document).

## Phase 5: Hand over to design

Summarise what is ready and what is left to the designer: page rhythm,
emphasis and breathing room, images, final details. Offer specific scripts
(a TOC, page fitting), but don't try to finish the layout.

## Alternative: import text with a script inside InDesign

Read `references/import-script.md` when the user already has a document
started in InDesign and new text arrives, has a very long Word file and
prefers InDesign to create the pages, or asks for a script. Fill in
`assets/import_docx.jsx` (its `CONFIG` mirrors the `roles` block), read
`references/extendscript-rules.md`, and run `scripts/check_es3.py` before
delivering.

## Alternative: translate an existing InDesign document

Read `references/translate-document.md` when the user wants a document
already laid out in InDesign, or a PDF exported from InDesign, in another
language while keeping the layout. In short:
1. Translate page by page, marking formatting runs with `**`, and report the
   problems found in the source. Wait for the review.
2. Write `translations.json`, check it against the source PDF
   (`scripts/check_translation_pdf.py source`), build the script
   (`scripts/build_translation_jsx.py`), then run `scripts/check_es3.py` and
   `scripts/test_translate_mock.js`.
3. The user runs it on the source `.indd`: it works on a copy and writes a
   report.
4. Check the translated PDF (`scripts/check_translation_pdf.py result`) and
   list the manual layout fixes, page by page.

## Be honest about verification

Claude cannot open InDesign. Every delivery says what was checked (valid
XML, references resolved, preview compared with the capture) and what was
not (how InDesign opens and composes it). The preview approximates text
composition; InDesign may break lines differently. When the user confirms
something works, say it is now verified; until then, call it unverified.

## Files in this skill

| File | Use |
| --- | --- |
| `references/00-content-review.md` | Phase 1: review the content before laying it out |
| `references/01-style-analysis.md` | Phase 1, route A: measure the reference, write the table and the JSON |
| `references/existing-idml.md` | Route B: work inside the user's own IDML |
| `references/03-visual-resources.md` | Phases 1-2: graphic-elements proposal and full layout proposal; script alternative |
| `references/02-idml-document.md` | Phase 3, route A: roles, tables, build and check the IDML |
| `references/04-idms-blocks.md` | Phase 4: build, preview, check and deliver `.idms` blocks; reuse earlier blocks |
| `references/05-proposals-from-captures.md` | Phase 4b: where product screenshots and mockups go |
| `references/import-script.md` | Alternative: ExtendScript import inside InDesign |
| `references/translate-document.md` | Alternative: translate an existing InDesign document |
| `references/extendscript-rules.md` | ES3 rules and InDesign scripting pitfalls |
| `scripts/build_idml.py` | Route A: style system (+ Word) to `.idml` |
| `scripts/extract_idml.py` | Route B: existing `.idml` to style-system JSON |
| `scripts/fill_idml.py` | Route B: Word content laid out inside the user's `.idml` |
| `scripts/idml_content.py` | Shared: Word reading, roles, story, tables, pages |
| `scripts/build_snippet.py` | Phase 4: block model to `.idms` |
| `scripts/preview_model.py` | Phase 4: PNG preview of a block model (alone or on a page), with overset and overlap warnings |
| `scripts/idms_to_model.py` | Phase 4: an earlier `.idms` back to a model, to modify it |
| `scripts/snippet_model.py` | Shared: loads and checks a block model for the two scripts above |
| `scripts/check_idml.py` | Structural check of any `.idml` or `.idms` before delivery |
| `scripts/inspect_docx.py` | Report on the Word file's structure |
| `scripts/check_es3.py` | Catches modern JavaScript in `.jsx` files |
| `scripts/build_translation_jsx.py` | Translation: JSON of paragraphs to `.jsx` (escaped, validated) |
| `scripts/check_translation_pdf.py` | Translation: check the JSON against the source PDF, and the translated PDF |
| `scripts/test_translate_mock.js` | Translation: run the built script on a simulated document (Node) |
| `assets/style-system.schema.json` | Format of the style system, roles and tables |
| `assets/import_docx.jsx` | Import script template |
| `assets/snippet-model.example.json` | Complete block model example (neutral styles) |
| `assets/visual_resource.jsx` | Script alternative for a visual resource, with drawing helpers |
| `assets/translate_document.jsx` | Translation script template (`CONFIG` + logic) |

If code execution is not available, still deliver the tables, the JSON, the
block models and the scripts, and tell the user how to run them locally. They
need Python 3 (plus Pillow for previews, `pdfplumber` for the translation
checks, and Node for the optional mock test).
