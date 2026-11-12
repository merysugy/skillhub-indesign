---
name: indesign-layout-prep
description: Prepares documents for professional layout in Adobe InDesign instead of laying them out with AI. Extracts the design system (paragraph/character styles, colours, grid) from the user's reference PDF, or reads it from their own InDesign file exported as IDML, and delivers an IDML with every style, swatch and table style plus the Word .docx content already laid out in those styles (titles, body, lists, emphasis, tables, threaded pages). Then proposes visual resources (key figures, diagrams, mind maps) as editable InDesign scripts. Also writes ExtendScript (ES3) scripts to import new text or to translate a laid-out .indd in a copy, keeping layout and styles. Use when the user mentions InDesign, IDML, .indd/.indt, ExtendScript or .jsx for InDesign, maquetar/maquetación, a whitepaper, report, magazine or brochure to lay out, a style sheet or "sistema de estilos" from a PDF, putting a Word document into InDesign, or translating an InDesign document (traducir una maqueta).
---

# InDesign layout prep

Claude does not design the document. Claude **prepares** it so the designer
can design it in InDesign. When InDesign opens the file, the styles and
swatches are already set up, the text is placed and styled (titles, body,
lists, emphasis, tables), and a proposal of visual resources comes with it.
The mechanical work shrinks, and the design stays with a person.

Always answer in the user's language. Use the style names the user and the
brand already use in files, styles and code.

## First: is this workflow the right tool?

- **Use it** when the result has to be professional: print-ready or
  device-ready, long or important documents (whitepapers, reports, magazines,
  catalogues), or anything that will be iterated on in InDesign.
- **Don't use it** for quick, low-stakes pieces Claude can produce on its
  own, such as a one-page summary or an internal note. Say so and offer to
  make it directly.
- Laying out a whole document with Claude and regenerating it for every
  small fix wastes tokens. This workflow moves the detail work into InDesign.

## Inputs and routes

Ask only for what is missing, in one message:

1. **Content**: the Word document (.docx) to lay out.
2. **Where the design comes from**. Ask which route applies:
   - **Route A, a reference to replicate**: a PDF, or a PDF export of a
     design made in Figma, InDesign, Canva and so on.
   - **Route B, styles that already exist in InDesign**: a template or a
     previous document. Ask for it as **IDML** (File > Save As > InDesign
     Markup (IDML)). If they also share a PDF of a finished piece, use it to
     decide which of their styles and master pages go where.
3. **Format** (route A, if not obvious): page size, margins, columns, facing
   pages, print or screen.

No style system is bundled with this skill. Every project's styles come from
its own reference (route A) or its own IDML (route B). Never reuse styles,
colours or fonts from another project.

## The four steps

Work through one step at a time. End each step with what was produced and
what the user should check, then wait for their go-ahead.

### Step 1: Styles and laid-out text in one IDML

**Route A.** Read `references/01-style-analysis.md`, then
`references/02-idml-document.md`.
1. Analyse the PDF and the Word file. Write `style-system.json` (schema in
   `assets/style-system.schema.json`) with the grid, colours, paragraph and
   character styles, the `roles` that say which style each part of the
   content gets, and a `tables` block if the content has tables.
2. Build the document and the empty template, then check both:
   ```bash
   python3 scripts/build_idml.py style-system.json -o <name>.idml --content content.docx
   python3 scripts/build_idml.py style-system.json -o <name>-template.idml
   python3 scripts/check_idml.py <name>.idml <name>-template.idml
   ```
3. Deliver everything together: the style table (with estimated values
   flagged), the laid-out IDML and the empty template. Corrections are
   cheap: fix the JSON and run the scripts again.

**Route B.** Read `references/existing-idml.md`.
```bash
python3 scripts/extract_idml.py their.idml -o style-system.json   # then add roles
python3 scripts/fill_idml.py their.idml style-system.json content.docx -o <name>.idml
python3 scripts/check_idml.py <name>.idml
```
Show which of their styles you mapped to each role, before or with the result.

In both routes:
- Never hand-write IDML XML. Always use the scripts, and fix the JSON when
  they report an error.
- Never deliver an IDML that `check_idml.py` rejects.
- The page count is an estimate with one spare page. InDesign composes the
  final text, and anything that does not fit stays as overset text, so
  nothing is ever lost. Tell the user.
- Pass on the script's report: the styles, lists, tables and hashtags it
  handled, and anything the user should edit, such as images in the Word
  file (they are not placed) or social-media phrases.

### Step 2: Propose visual resources

Read `references/03-visual-resources.md`. Using the content and the identity
already analysed, propose resources section by section: key figures,
diagrams, mind maps, comparisons, callout boxes, cards, screenshots, images.
For each one, say what it represents and why it helps the reader, and give a
sketch in the brand colours and fonts. Don't lay out the full document: only
the resources, in content order. Compositions in the reference that are not
plain text or tables (boxes, cards, bands, mind maps) belong here, not in
step 1.

For each resource the user picks, adapt `assets/visual_resource.jsx` so it
builds that element inside InDesign with the document's swatches and styles,
fully editable. Check it with `scripts/check_es3.py`.

### Step 3: Hand over to design

Summarise what is ready and what is left to the designer: page rhythm,
emphasis and breathing room, images, white space, final details. Offer help
with specific scripts (a TOC, page fitting), but don't try to finish the
layout.

### Step 4: Language versions

When a document laid out in InDesign needs another language, keeping the
layout, read `references/translate-document.md`. It also works on its own,
for any finished InDesign document. In short:
1. Ask for the PDF of the source document and confirm the user has the
   `.indd`. Translate page by page, marking formatting runs with `**`, and
   report the problems found in the source. Wait for the review.
2. Write `translations.json`, check it against the source PDF
   (`scripts/check_translation_pdf.py source`), build the script
   (`scripts/build_translation_jsx.py`), then run `scripts/check_es3.py` and
   `scripts/test_translate_mock.js`.
3. The user runs it on the source `.indd`: it saves a copy, translates the
   copy and writes a report.
4. Check the translated PDF (`scripts/check_translation_pdf.py result`) and
   list the manual layout fixes, page by page.

## Alternative: import text with a script inside InDesign

Read `references/import-script.md` when the user:
- already has a document started in InDesign and new text arrives,
- has a very long Word file and prefers InDesign to create the pages, or
- asks for the script approach.

Fill in `assets/import_docx.jsx` (its `CONFIG` mirrors the `roles` block),
read `references/extendscript-rules.md`, and run `scripts/check_es3.py`
before delivering.

## Files in this skill

| File | Use |
| --- | --- |
| `references/01-style-analysis.md` | Route A: measure the reference, write the table and the JSON |
| `references/02-idml-document.md` | Route A: roles, tables, build and check the IDML |
| `references/existing-idml.md` | Route B: work inside the user's own IDML |
| `references/03-visual-resources.md` | Step 2: resource proposal and resource scripts |
| `references/translate-document.md` | Step 4: translate a laid-out InDesign document in a copy |
| `references/import-script.md` | Alternative: ExtendScript import inside InDesign |
| `references/extendscript-rules.md` | ES3 rules and InDesign scripting pitfalls |
| `scripts/build_idml.py` | Route A: style system (+ Word) to `.idml` |
| `scripts/extract_idml.py` | Route B: existing `.idml` to style-system JSON |
| `scripts/fill_idml.py` | Route B: Word content laid out inside the user's `.idml` |
| `scripts/idml_content.py` | Shared: Word reading, roles, story, tables, pages |
| `scripts/check_idml.py` | Structural check of any `.idml` before delivery |
| `scripts/inspect_docx.py` | Report on the Word file's structure |
| `scripts/build_translation_jsx.py` | Step 4: JSON of paragraphs to `.jsx` (escaped, validated) |
| `scripts/check_translation_pdf.py` | Step 4: check the JSON against the source PDF, and the translated PDF |
| `scripts/test_translate_mock.js` | Step 4: run the built script on a simulated document (Node) |
| `scripts/check_es3.py` | Catches modern JavaScript in `.jsx` files |
| `assets/style-system.schema.json` | Format of the style system, roles and tables |
| `assets/import_docx.jsx` | Alternative import script template |
| `assets/visual_resource.jsx` | Step 2 resource script template with drawing helpers |
| `assets/translate_document.jsx` | Step 4 translation script template (`CONFIG` + logic) |

If code execution is not available, still deliver the table, the JSON and
the scripts, and tell the user how to run them locally. They only need
Python 3 (plus `pdfplumber` for the translation checks, and Node for the
optional mock test).
