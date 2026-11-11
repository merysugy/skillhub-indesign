---
name: indesign-layout-prep
description: Prepares documents for professional layout in Adobe InDesign instead of laying them out with AI. Extracts the design system (paragraph/character styles, colours, grid) from the user's reference PDF, or reads it from their existing InDesign file exported as IDML, generates an IDML template with grouped styles and brand swatches, writes ExtendScript (ES3) scripts that import a Word .docx with the template styles applied, and proposes visual resources (key figures, diagrams, mind maps) section by section as InDesign scripts. Use when the user mentions InDesign, IDML, .indd/.indt, ExtendScript or .jsx for InDesign, maquetar/maquetación, a whitepaper, report, magazine or brochure to lay out, a style sheet or "sistema de estilos" from a PDF, or importing a Word document into InDesign.
---

# InDesign layout prep

Claude does not lay out the document. Claude **prepares** it so the designer
can lay it out in InDesign: before design starts, the designer already has a
template with styles and swatches, the text placed and styled, and a proposal
of visual resources. The mechanical work shrinks; the design stays human.

Always answer in the user's language. Files, style names and code follow the
names the user and the brand already use.

## First: is this workflow the right tool?

- **Use it** when the result must be professional: print-ready or
  device-ready, long or important documents (whitepapers, reports, magazines,
  catalogues), or anything that will be iterated on in InDesign.
- **Don't use it** for quick, low-stakes pieces Claude can produce entirely
  (a one-page summary, an internal note). Say so and offer to make it directly.
- Laying out the whole document with Claude and regenerating it for every
  small fix wastes tokens; this workflow avoids that by moving the detail work
  into InDesign.

## Inputs

Ask for what is missing, one message, no more than needed:

1. **Content**: the Word document (.docx) or text to lay out.
2. **Where the design comes from** - ask which case applies:
   - **A. A reference to replicate**: a PDF (or a PDF export of a design in
     Figma, InDesign, Canva...). Go through steps 1 and 2.
   - **B. Styles that already exist in InDesign** (a template or a previous
     document): ask for it as **IDML** (File > Save As > InDesign Markup
     (IDML)). Read `references/existing-idml.md`, extract the style system
     with `scripts/extract_idml.py`, and continue at step 3 using their file
     as the template.
3. **Format** (case A, if not obvious): page size, margins, columns, facing
   pages, print or screen.

No style system is bundled with this skill: every project's styles come from
its own reference (case A) or its own IDML (case B). Never reuse styles,
colours or fonts from another project.

## The five steps

Work one step at a time. End each step with what was produced and what the
user should check, then wait for their go-ahead before the next step.

### Step 1 - Analyse identity and styles

Read `references/01-style-analysis.md` and follow it. Deliver:
- A style table: paragraph and character styles, each with font and weight,
  size, leading, space before/after, colour, based-on style and group,
  in hierarchy order; plus repeated resources (callouts, quotes, captions,
  tables) and the colour palette.
- Anything not measurable with confidence is marked **estimated**.
- A `style-system.json` file following `assets/style-system.schema.json`,
  built only from what this reference shows.

**Checkpoint:** do not generate the template until the user validates or
corrects the table. Apply their corrections to the JSON.

### Step 2 - Generate the IDML template

Read `references/02-idml-template.md`. Run:

```bash
python3 scripts/build_idml.py style-system.json -o <name>-template.idml
python3 scripts/build_idml.py style-system.json -o <name>-specimen.idml --specimen
```

Never hand-write IDML XML: always use the generator, and fix the JSON if it
reports an error. Deliver both files. The template has no content; the
specimen shows one sample paragraph per style for review. Tell the user to
open the template in InDesign and save it as `.indt` to reuse it.

### Step 3 - Import the text with a script

Read `references/03-text-import.md`. First inspect the Word file:

```bash
python3 scripts/inspect_docx.py content.docx --style-system style-system.json
```

- **Well-styled Word** (real Heading 1/2, Normal): no script needed. Explain
  how to map styles in InDesign's import options.
- **Hand-made Word** (bold lines as headings, typed dashes, manual indents):
  copy `assets/import_docx.jsx`, fill its `CONFIG` (style map from the
  inspector output, style paths as `Group:Style`, non-ASCII characters as
  `\uXXXX` escapes), and deliver it.

Before delivering any `.jsx`, read `references/extendscript-rules.md` and run
`python3 scripts/check_es3.py <file>.jsx`. Fix every error.

### Step 4 - Propose visual resources

Read `references/04-visual-resources.md`. Using the content and identity
already analysed, propose resources section by section (key figure, diagram,
mind map, comparison, screenshot, image): what each represents, why it helps
the reader, and a sketch in the brand colours and fonts. Do not lay out the
full document: only the resources, in content order.

For each resource the user picks, adapt `assets/visual_resource.jsx` so it
builds that element inside InDesign with the document's swatches and styles,
fully editable. Check it with `check_es3.py`.

### Step 5 - Hand over to design

Summarise what is ready (template, styled text, resources) and what is left
to the designer: page rhythm, emphasis and breathing room, images, white
space, final details. Offer help with specific scripts (e.g. a table style,
a TOC) but do not try to finish the layout.

## Files in this skill

| File | Use |
| --- | --- |
| `references/01-style-analysis.md` | How to extract the style system and write the table + JSON |
| `references/02-idml-template.md` | Running the generator, options, limits |
| `references/03-text-import.md` | Word import: both cases, configuring `import_docx.jsx`, installing scripts |
| `references/04-visual-resources.md` | Resource proposal format and turning resources into scripts |
| `references/extendscript-rules.md` | ES3 rules and InDesign scripting pitfalls |
| `references/existing-idml.md` | Case B: the user already has styles in InDesign |
| `scripts/build_idml.py` | style-system JSON to `.idml` template |
| `scripts/extract_idml.py` | Existing `.idml` to style-system JSON (case B) |
| `scripts/inspect_docx.py` | Word structure report + ready-made style map |
| `scripts/check_es3.py` | Catches modern JavaScript in `.jsx` files |
| `assets/style-system.schema.json` | Format of the style system |
| `assets/import_docx.jsx` | Step 3 import script template |
| `assets/visual_resource.jsx` | Step 4 resource script template with drawing helpers |

If code execution is not available, still deliver the table, the JSON and the
scripts, and tell the user how to run `build_idml.py` locally (Python 3, no
extra packages).
