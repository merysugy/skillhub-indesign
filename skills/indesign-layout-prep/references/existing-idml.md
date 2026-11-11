# Case B - The user already has styles in InDesign

Some users already have their identity built in InDesign: a template
(.indt), a previous document (.indd), or a style package. Don't rebuild it
from a PDF. Work from their file.

## Ask for the IDML

Claude can't open .indd or .indt files. Ask the user to export one:

1. Open the template or document in InDesign.
2. **File > Save As**, format **InDesign Markup (IDML)**, then share the `.idml`.

Any document that has the styles will do. If it's full of content, that's
fine: only the styles, swatches and page setup are read.

## Extract the style system

```bash
python3 scripts/extract_idml.py their-file.idml -o style-system.json
```

The script writes the same `style-system.json` that step 1 produces, with
the page setup (size, margins, columns, bleed), named swatches, and every
paragraph and character style with its group, parent style, font, size,
leading, spacing, colour, alignment, lists and column span. It prints
warnings for anything it had to drop, such as LAB colours or references to
unnamed colours.

Show the user a short summary of what you found: style groups and styles, the
fonts in use, and the palette. Use it to confirm the names before step 3.
This replaces the step 1 table. Don't redo the analysis.

## Then

- **Template**: the user's own file *is* the template. Don't run
  `build_idml.py` unless they ask for a clean copy without content (for
  example, their IDML is a finished document). In that case, build a new
  template from the extracted JSON, then ask them to compare it with the
  original in InDesign. Paragraph rules, borders, shading, GREP and nested
  styles, tabs and object styles are not carried over.
- **Step 3**: fill `import_docx.jsx` with their exact style paths
  (`Group:Style`). Add `maps_from` to the extracted JSON, or write the
  `styleMap` by hand from the inspector output.
- **Step 4**: use their swatch names and styles in `visual_resource.jsx`.
- If the content needs a role their styles don't cover (for example, a
  bullet list with no list style), propose one that fits their identity and
  ask before adding it.
