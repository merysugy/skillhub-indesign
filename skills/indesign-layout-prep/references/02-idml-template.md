# Step 2 - Generate the IDML template

IDML is InDesign's open exchange format: a zip of XML files that InDesign
opens like a document. It can be generated outside InDesign, which is what
`scripts/build_idml.py` does.

## Prompt this step answers

> With this style system, generate an InDesign IDML file in A4, with 20 mm
> margins and two columns. Include every paragraph and character style grouped
> in folders, and every colour in the swatches panel with the brand names.
> Do not add content: only the template.

## Run it

```bash
python3 scripts/build_idml.py style-system.json -o brand-template.idml
python3 scripts/build_idml.py style-system.json -o brand-specimen.idml --specimen
```

- Page setup comes from the `document` block: `page_size` (A3, A4, A5, B5,
  Letter, Legal, Tabloid, or `{"width_mm", "height_mm"}`), `orientation`,
  `facing_pages`, `margins_mm` (one number or top/bottom/inside/outside),
  `columns`, `gutter_mm`, `bleed_mm`, `units` (rulers), and
  `default_paragraph_style` (applied to the empty frame on page 1).
- If the user asks for a format different from the JSON, change the JSON
  first so the JSON stays the single source of truth.
- The script prints the estimated values: repeat them to the user as a
  checklist.
- Errors (unknown colour, missing parent style, circular `based_on`...) are
  printed with the style name. Fix the JSON and run again.

## What the template contains

- One A-Master with the margins and columns, and page 1 with an empty text
  frame at the margins (with the same columns), ready for step 3.
- All paragraph and character styles inside their groups; `[Basic Paragraph]`
  is the root of styles with no `based_on`.
- Brand colours as named swatches (process or spot; CMYK or RGB).
- Rulers in the chosen units. The file is IDML for InDesign CS6 and later, so
  it opens in every current version (InDesign converts it on open).

The specimen file is the same template with one sample paragraph per style.
It is the quickest way for the designer to review the type system.

## Tell the user

1. Open the `.idml` in InDesign (File > Open). It opens as a new untitled
   document.
2. Check: Paragraph Styles and Character Styles panels (groups and values),
   Swatches panel, Document Setup and Margins and Columns.
3. Fonts not installed on their machine show as missing (pink highlight):
   install them or change the font in the style.
4. Save as **InDesign Template (.indt)**. Next time, start from the template
   and skip steps 1 and 2.

## Known limits

- No ColorGroup (swatch folders): brand swatches appear at the top level.
- Bullets and numbering use InDesign's default bullet and number format;
  adjust the character in the style if the brand uses a special one.
- Tables, object styles, TOC styles, grids and baseline grid are not
  generated: the designer sets them in InDesign (or ask for a script).
- `language` is passed through as a raw InDesign id; leave it out unless the
  exact id is known (e.g. `$ID/English: USA`).
- With facing pages and different inside/outside margins, check the master's
  margins once in InDesign.
