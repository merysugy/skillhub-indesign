# Step 1 - Analyse identity and styles

Goal: a style system the designer can validate in one read, and the same
system as `style-system.json` for the generator.

## Prompt this step answers

> Analyse this PDF as the design and identity base, and the Word document as
> the content to lay out. Give me the style system in a table, with every
> element classified: paragraph and character styles with font and weight,
> size, leading, space before and after, colour and based-on style. Organise
> the styles in a hierarchy and include repeated resources (callouts, quotes,
> captions, tables). Mark anything you cannot measure reliably as estimated.

## How to read the reference

From the PDF (or InDesign export):

1. **Grid**: page size, margins, number of columns and gutter, facing pages,
   bleed if visible. Measure in mm. Run a PDF tool if available (e.g.
   `pdfplumber`, `pypdf`, `pdftotext -bbox`) to get page size, text positions,
   font names and sizes; otherwise estimate from the rendered pages.
2. **Type**: for each distinct text role (headline, subhead, body, lists,
   quotes, captions, notes, table text, labels, page numbers) note font
   family, weight/style, size, leading, alignment, case, tracking, colour,
   indents and space before/after. Font names embedded in a PDF often carry a
   subset prefix (`ABCDEF+MinionPro-Regular`): report the family as InDesign
   shows it (`Minion Pro`, style `Regular`).
3. **Colour**: brand colours with CMYK (print) or RGB/hex (screen). Name them
   as the brand does (its own colour names), not "Blue 1". Values sampled
   from a PDF render are estimates unless the PDF states them.
4. **Repeated resources**: callout boxes, key figures, pull quotes, captions,
   sources, tables, icons, rules. Each becomes a style (or a set of styles)
   and is noted for step 4.

From the Word document: which roles the content actually needs (how many
heading levels, lists, quotes, tables, footnotes, captions). Do not add styles
the content will never use; do flag roles the content needs but the
reference lacks, and propose a style in the same identity.

## PDFs exported from design tools

Figma, Canva and similar tools often export text as **Type3 fonts**: the
text is extractable and the sizes are real, but font names are gone and the
text colour may read as black. Then:

- **Scale**: if the page is not in points at real size (Figma exports A4 as
  1249 x 1769 "pt", i.e. pixels), convert: `real_pt = size * 595.28 / page_width`.
- **Fonts**: identify them visually from zoomed renders (letter shapes:
  `a`, `g`, `Q`, `R`, italics) and mark them **estimated**.
- **Colours**: sample the darkest pixel inside each text box of a render;
  read fills of vector shapes for the palette. Boxes may be a colour at
  reduced opacity: report the colour as rendered.
- **Leading and spacing**: from baseline-to-baseline distances between
  lines of the same style and between consecutive styles.

`pymupdf` (pip) does all of this: `page.get_text("dict")` for spans with
size and position, `page.get_drawings()` for fills, `page.get_pixmap()` for
renders and pixel sampling.

## Hierarchy

- Base styles first, children based on them (`Subhead` based on `Headline`,
  `Body First` based on `Body`). Children only list what changes.
- Group styles in folders by role: `Headings`, `Body`, `Callouts`,
  `Captions & Notes`, `Tables`; character styles in `Text` (Bold, Italic...)
  and `Brand` (accent, link).
- Always include character styles for **Bold**, **Italic** and **Bold
  Italic**: the import script needs them to keep Word emphasis.
- Set `next_style` where it helps typing (Headline -> Body First -> Body).
- Use `span_columns` for headlines in multi-column layouts.

## Table format

One table for paragraph styles, one for character styles, one for colours.
Mark estimated values with `~` and an "Estimated" column.

Paragraph styles, in hierarchy order, with these columns:

`Group | Style | Based on | Font / weight | Size / leading (pt) | Before / after (pt) | Colour | Align | Notes | Estimated`

Children only fill in what changes ("(inherits)" elsewhere). Character
styles use the same columns without spacing and alignment. Colours:

`Colour | CMYK | RGB / hex | Use | Estimated`

Name styles in the user's language and the brand's vocabulary.

Then list the grid: `A4, margins 20 mm, 2 columns, 6 mm gutter, 3 mm bleed`.

## The JSON

Write `style-system.json` following `../assets/style-system.schema.json`,
using only what this reference shows (no styles, fonts or colours from other
projects). Notes:

- Sizes in points, geometry in millimetres.
- `group` is the folder; `based_on` and `next_style` use style **names**.
- `estimated` is `true` or a list of fields; the generator prints them so the
  designer checks them in InDesign.
- `maps_from` lists the Word style names that become this style (`Heading 1`,
  `Título 1`...). The step-3 inspector uses it to write the import map.
- Only `Black`, `Paper`, `Registration` and `None` exist without being defined.

After writing it, validate by running the generator once (step 2 command) and
fix any error before showing the table to the user.

## Checkpoint

Show the tables and the grid, list the estimated values, and ask the user to
confirm or correct. Do not move to step 2 until they do.
