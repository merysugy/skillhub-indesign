# Route B: the user already has styles in InDesign

Some users already have their identity built in InDesign, as a template
(.indt), a previous document (.indd) or a style package. Don't rebuild it
from a PDF. Lay the Word content out inside their own file.

## Ask for the IDML

Claude can't open .indd or .indt files. Ask the user to export one:

1. Open the template or document in InDesign.
2. Choose **File > Save As**, set the format to **InDesign Markup (IDML)**,
   and share the `.idml`.

A template with no content works best. A document that already has content
works too: the new pages go after the existing ones.

If they also share a **PDF of a finished piece** in that identity, use it to
choose which of their styles go to each role (which heading level, which
style for the lead, the callouts, the tables) and which master page to use.

## 1. Read their style system

```bash
python3 scripts/extract_idml.py their.idml -o style-system.json
```

This writes the page setup, named swatches, and every paragraph and
character style with its group, parent, font, size, leading, spacing,
colour, alignment and lists. It prints warnings for anything it dropped.

Show the user a short summary: style groups and styles, fonts in use, and the
palette. Don't redo a full analysis.

## 2. Add roles (and tables)

Add a `roles` block naming **their** styles (see
`02-idml-document.md` for what each role does). Style names can be
`"Style"` or `"Group:Style"` when the same name exists in two groups. Add
`maps_from` to their styles for the Word styles in the content (from
`scripts/inspect_docx.py`).

- If one of their table styles should be used, set `tables.style_name` to its
  name. Its cell styles are used if they are named `<style_name> header` and
  `<style_name> body`, or are set in `header_cell_style` and
  `body_cell_style`.
- If they have no table style and the content has tables, a `tables` block
  with swatch names adds one to their file, built from their palette.
- If the content needs a role their styles don't cover (for example, a list
  with no list style), tell the user. Either map it to the closest style or
  ask them to add one to their template.

Show the role mapping to the user (one line per role) before or with the
result.

## 3. Lay out the content

```bash
python3 scripts/fill_idml.py their.idml style-system.json content.docx -o laid-out.idml
python3 scripts/fill_idml.py their.idml style-system.json content.docx -o laid-out.idml --master "B-Content"
python3 scripts/check_idml.py laid-out.idml
```

- Their styles, swatches, master pages and resources stay as they are. The
  content goes in as a new threaded story on new pages that use the first
  master page, or the one passed with `--master`.
- Page geometry comes from that master page.
- **Existing pages:**
  - If they are all empty (a template), they are replaced.
  - If they have text, they are kept and the new pages are added after
    them. Tell the user so they can delete the old pages.
  - `--replace-pages` forces replacement, but only when nothing else in the
    document (XML structure, hyperlinks, TOC) refers to their stories.
    Otherwise the script keeps them and says why.
- The original IDML is never modified. Always write a new file.
- Never deliver a file that `check_idml.py` rejects.

## Then

- **What is not placed:** covers, captions, sidebars and images. The script
  doesn't know where those go. They stay with the designer, or go to step 2
  as visual resources.
- **Step 2:** use their swatch names and styles in `visual_resource.jsx`.
- **New text later:** run `fill_idml.py` again with the new Word file, or use
  the ExtendScript import script inside InDesign (`import-script.md`).
