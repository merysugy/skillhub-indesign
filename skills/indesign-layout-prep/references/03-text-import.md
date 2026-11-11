# Step 3 - Import the text in one go

Goal: all the Word content inside the template, every paragraph in its
template style, emphasis kept, pages and threaded frames added as needed.

## Inspect the Word file first

```bash
python3 scripts/inspect_docx.py content.docx --style-system style-system.json
```

It reports the Word styles used, hand-made headings (short all-bold
paragraphs), typed lists (`- ` / `1. `), manually indented paragraphs, tables
and images, gives a verdict, and prints a `styleMap` for the script.

## Case 1 - Well-styled Word (no script)

The Word file uses real styles ("Heading 1", "Heading 2", "Normal"). Tell the
user:

1. Open the template, select the frame on page 1 (or nothing).
2. File > Place, choose the .docx, tick **Show Import Options**.
3. Choose **Preserve Styles and Formatting from Text and Tables**, then
   **Customize Style Import** > **Style Mapping**: map each Word style to the
   template style (give them the list from the inspector).
4. Shift-click in the frame to autoflow: InDesign adds pages and frames.

Emphasis (bold/italic) applied by hand in Word arrives as local overrides.
If they plan to clear overrides, recommend the script instead (case 2),
which turns emphasis into character styles first.

## Case 2 - Hand-made Word (script)

Bold lines used as headings, typed dashes, quotes indented by hand. Use
`assets/import_docx.jsx`:

1. Copy it and fill the `CONFIG` block (it ships empty: every value comes
   from this project's style system):
   - `styleMap`: paste the inspector's map. Paths are `Group:Style` exactly
     as in the template. Matching ignores case.
   - `bodyStyle` (required): style for any unmapped Word style.
   - `leadStyle`: optional style for the first body paragraph (standfirst).
   - `manualHeadingStyle`: style for short all-bold paragraphs;
     `firstHeadingStyle`: optional style for the first one (the title).
   - `bulletStyle`, `numberedStyle`: for real Word lists and typed lists.
   - `quoteStyle`: for manually indented paragraphs.
   - `boldStyle`, `italicStyle`, `boldItalicStyle`, `superscriptStyle`:
     character styles that keep Word emphasis.
   - Leave any style `""` to switch that detection off.
   - **Write every non-ASCII character as a `\uXXXX` escape**
     (`"T\u00EDtulos:T\u00EDtulo 1"` for "Títulos:Título 1"): ExtendScript may
     read the file in the system encoding and break accented names.
2. Run `python3 scripts/check_es3.py import_docx.jsx` and fix every error and
   every non-ASCII warning.
3. Deliver the file with the install steps below.

What it does, in order (all undoable in one step):
1. Asks for the .docx, places it in the first empty frame on page 1 (or a new
   frame at the margins with the page's columns).
2. Decides each paragraph's style: Word style map; real Word lists (which
   would otherwise lose their bullets when overrides are cleared) and typed
   lists (removes the typed marker; the style adds a real bullet/number);
   short all-bold headings (the first one as title); the first body paragraph
   as lead; indented quotes.
3. Turns local bold, italic, bold italic and superscript into character
   styles. **This must happen before clearing overrides**, otherwise
   emphasis is lost.
4. Applies the template paragraph styles, clearing local overrides
   (character styles stay).
5. Removes empty paragraphs and the styles that came in with the Word file.
6. Adds pages and threaded frames (with the same columns as the first
   frame) until there is no overset text.
7. Shows a report: paragraphs per style, detections, Word styles not mapped.

Options for common Word problems (ask the user before turning them on,
since they change the text):
- `titleSeparator` + `subtitleStyle`: a title and subtitle typed in one
  paragraph ("Title - Subtitle") become two paragraphs.
- `hashtags: "remove"` deletes the `#` of #hashtags; `"style"` applies
  `hashtagStyle` to them instead.
- A lead typed entirely in bold gets `leadStyle` without the bold (it is
  paragraph formatting, not emphasis).

Flag what no option covers, e.g. social-media phrases ("link in the
comments") or other text that needs editing for print.

If the user's prompt asks for something different (e.g. "place it from
page 3", "one column on the first page", "keep Word tables as they are"),
adapt the script and keep the structure and the ES3 rules.

## Install and run a script (tell the user)

1. In InDesign: **Window > Utilities > Scripts**.
2. In the Scripts panel, right-click **User** > **Reveal in Finder** (macOS)
   or **Reveal in Explorer** (Windows).
3. Copy the `.jsx` into that folder.
4. Back in InDesign, open the template and double-click the script in the
   panel.
5. If something looks wrong, **Edit > Undo** reverts the whole import.

## After the import

Ask the user to check the report and look at: headings detected by hand
(false positives are short bold sentences), lists, quotes, tables and images.
Offer to adjust `CONFIG` and run again on a fresh copy of the template.
