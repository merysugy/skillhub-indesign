# Route A: build the IDML with the text laid out

IDML is InDesign's open exchange format: a zip of XML files that InDesign
opens like a document. `scripts/build_idml.py` writes it from the style
system and can lay the Word content into it.

## Prompt this step answers

> Analyse this PDF as the design and identity base, and the Word document as
> the content. Extract titles, colours and fonts into a table, then generate
> an IDML with every paragraph, character and table style based on that
> identity, with the Word document already laid out in the same visual style.

## 1. Add roles to the style system

The `roles` block says which style each part of the content gets. Base it on
what the Word inspection shows (`scripts/inspect_docx.py content.docx`):

```json
"roles": {
  "body": "Body", "lead": "Lead", "title": "Title 1", "subtitle": "Subtitle",
  "heading": "Title 3", "bullet": "Bullet", "numbered": "Numbered", "quote": "Quote",
  "table_header": "Table header", "table_body": "Table text",
  "bold": "Bold", "italic": "Italic", "bold_italic": "Bold italic",
  "superscript": "", "hashtag": "Hashtag",
  "title_separator": " - ", "hashtags": "remove"
}
```

These are the names from this project's style system. How each paragraph
gets its style, in order:
1. A Word style listed in a paragraph style's `maps_from` (e.g. "Heading 2")
   goes to that style.
2. Everything else counts as body. Within the body text, the script detects:
   - real Word lists, which go to `bullet` or `numbered`. Typed `- ` and
     `1. ` lists go there too, and the typed marker is removed;
   - short all-bold paragraphs, which become `heading`. The first one
     becomes `title`, split at `title_separator` into title and `subtitle`
     when the separator is present;
   - paragraphs indented by hand (at least `quote_min_indent_pt`), which
     become `quote`;
   - the first remaining body paragraph, which becomes `lead`. If it is all
     bold, the bold is dropped as paragraph formatting.
3. Bold, italic and superscript runs become the `bold`, `italic`,
   `bold_italic` and `superscript` character styles. This doesn't apply in
   titles and headings.
4. `hashtags`: `remove` drops the `#`, `style` applies `hashtag`, and `keep`
   leaves them as they are. Ask before removing text.
5. Empty paragraphs are removed. Images aren't placed, but the script counts
   and reports them.

Only add roles the content needs. A role left out switches its detection off.
Roles must name existing styles. If the content needs a role the reference
lacks (lists, tables...), propose a style in the same identity, mark it as a
proposal in the table, and add it to the JSON.

## 2. Tables

Word tables become real InDesign tables: header rows, merged columns, and
column widths proportional to their content, filling the text width. If the
content has tables, add a `tables` block built from the identity:

```json
"tables": {
  "style_name": "Brand table",
  "header_fill": "Cream", "rule_color": "Orange", "rule_weight_pt": 0.5,
  "border_weight_pt": 0, "cell_inset_mm": 1.5,
  "space_before_pt": 6, "space_after_pt": 8, "vertical_align": "top"
}
```

It generates a table style and two cell styles (header and body), and their
text uses `roles.table_header` and `roles.table_body`. The designer can
restyle every table at once from InDesign's Table Styles panel. Without a
`tables` block, tables use `[Basic Table]`.

Compositions that are not plain tables (cards, boxes next to an image,
bands, mind maps) are not built in the IDML (phase 3). They go to phase 4
as editable blocks.

## 3. Build and check

```bash
python3 scripts/build_idml.py style-system.json -o name.idml --content content.docx
python3 scripts/build_idml.py style-system.json -o name-template.idml
python3 scripts/check_idml.py name.idml name-template.idml
```

- Page setup comes from the `document` block: `page_size`, `orientation`,
  `facing_pages`, `margins_mm`, `columns` (grid), `text_frame_columns`
  (text, if different from the grid), `gutter_mm`, `bleed_mm` and `units`.
- **Pages are estimated.** The script measures the text against the styles
  (`avg_char_em`, default 0.52, about 0.56 for wide fonts like Montserrat)
  and adds `spare_pages` (default 1). Every page has a text frame at the
  margins, threaded to the next. Tell the user to delete empty pages at the
  end, or add pages if the text is overset. Nothing is lost.
- The printout lists paragraphs per style, lists, headings, tables, hashtags,
  images not placed and Word styles without a match. Pass it on.
- The template (no `--content`) has the same styles and one empty threaded
  frame. Tell the user to save it as `.indt` for the next document.
- Never deliver a file that `check_idml.py` rejects.

## Tell the user

1. Open the `.idml` in InDesign with File > Open. It opens as a new untitled
   document.
2. Fonts that aren't installed show as missing (pink highlight). Install them
   or change the font in the style.
3. Check the estimated values from the table in the Paragraph Styles panel.
4. Remove spare pages, or add pages if there is overset text.
5. Save the template as an **InDesign Template (.indt)**.

## Known limits

- No swatch folders (ColorGroups). Brand swatches sit at the top level.
- Bullets and numbering use InDesign's default bullet character and number
  format.
- Not generated: paragraph rules, borders and shading, object styles, TOC
  styles, master page items (headers, footers, page numbers), images.
- `language` is passed through as a raw InDesign id. Leave it out unless the
  exact id is known.
- With facing pages and different inside and outside margins, check the
  margins once in InDesign.
