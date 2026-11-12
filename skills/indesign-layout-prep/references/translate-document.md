# Step 4 - Translate a laid-out InDesign document

The last step of the workflow, and usable on its own. Use this when the user wants a document already laid out in InDesign (or a
PDF exported from InDesign) in another language, keeping the layout. The
result is a copy of their `.indd` with every paragraph replaced in place:
same frames, styles, master pages and formatting runs. Nothing is rebuilt.

## Inputs

Ask in one message only for what is missing:

1. **The PDF of the source document.** Claude reads the text, the formatting
   runs and the layout from it.
2. **Whether they have the `.indd` (or IDML).** Without it this route does not
   apply: offer route A of step 1 to rebuild the layout from the PDF, or a
   conversion with their own tools, and say what each one loses.
3. **Replace in a copy or create a new document.** Recommend the copy: it keeps
   the layout and styles. The rest of this file assumes it.
4. **Target language and variant** if not obvious (US or UK English). Match
   what the brand already publishes in that language: check their website or
   recent documents and keep their vocabulary.

## Step 1 - Translate and review (no script yet)

1. Read the text layer and render the pages (pdf-reading skill). Translate
   page by page, in document order, labelling each element: title, lead,
   body, quote, box, diagram labels, captions, table cells.
2. Mark with `**...**` the runs whose formatting differs from the rest of the
   paragraph (bold, a coloured label). The script copies that formatting.
3. Report the problems found in the source, because they carry over:
   repeated subtitles, typos, missing full stops, hidden objects in the text
   layer, screenshots or images with text in the source language (no script
   translates images).
4. Wait for the user to review the translation and decide on any text Claude
   had to invent (for example, a subtitle that was duplicated by mistake).

## Step 2 - Build and check the script

1. Write `translations.json`, one entry per paragraph in document order:
   ```json
   [
     {"es": "Texto con **tramo en negrita** del original", "en": "Text with a **bold run** from the original"},
     {"es": "Subtitulo repetido", "en": ["For the first page it appears on", "For the second page"]},
     {"es": "Marca  \u00b7   Cabecera", "en": "Brand  \u00b7   Header"}
   ]
   ```
   - `es` is the source text as it appears in the layout. Case, line breaks
     and special spaces do not matter for matching.
   - `en` is the target text, written exactly as it must appear. Keep
     intentional multiple spaces (running headers often have them: measure
     the gaps between characters in the PDF if in doubt).
   - A list in `en` assigns translations by page order to a source text that
     appears more than once.
   - Diagram labels, table cells and captions are separate entries.
   - Leave out what does not change: names, e-mails, numbers, words that are
     the same in both languages.
   - Write the typographic apostrophe ’ in `en` if the brand uses it,
     rather than relying on InDesign settings.
2. Check the JSON against the source PDF. It must report 0 problems:
   ```bash
   python3 scripts/check_translation_pdf.py source translations.json source.pdf
   ```
   It confirms that every source text exists and that every marked run has a
   uniform font or colour different from the rest. It found real mistakes in
   testing: a bold run that started one word later than it looked, and a
   coloured label whose colon was not coloured. It also lists the PDF text no
   entry covers: only page numbers, e-mails, names and invariable words should
   remain.
3. Build the script, then check it:
   ```bash
   python3 scripts/build_translation_jsx.py translations.json -o Translate-EN.jsx
   python3 scripts/check_es3.py Translate-EN.jsx
   node scripts/test_translate_mock.js Translate-EN.jsx    # if Node is available
   ```
   The builder rejects unbalanced `**` and duplicate source texts, and writes
   every non-ASCII character as a `\uXXXX` escape. The mock runs the script
   against a simulated document with every entry plus the hard cases below.
   It tests the script's logic, not InDesign: say so when delivering.
   The template is `assets/translate_document.jsx`; `CONFIG` at the top holds
   the target locale and the file-name tags (`[ES]` becomes `[EN]` in the copy).

## Step 3 - Deliver and run

Tell the user:
1. Install the `.jsx` (steps in `extendscript-rules.md`).
2. Open the **source-language `.indd`**, not an earlier translated copy. The
   column check compares where paragraphs start before and after the
   translation in the same run; on a copy that is already translated there is
   nothing to compare.
3. Run it. It saves a copy (the original is not touched), replaces the text,
   sets it to the target language and leaves the changes unsaved. One Edit >
   Undo reverts everything.
4. Read the `.txt` report saved next to the document, then save.

## Step 4 - Review the result

Ask for the translated PDF and the report, then:
```bash
python3 scripts/check_translation_pdf.py result translations.json translated.pdf
```
It lists source texts still present. "Target not found in one piece" usually
means a paragraph split across columns or pages: check those by eye, they
are often the lost column starts below.

Then review the pages visually and give the user a short list of manual
fixes, page by page, with the exact keystroke.

## What the report means

| Section | Cause | Fix |
| --- | --- | --- |
| Not found | The text is split across separate frames, contains an anchored object, or the entry does not match the layout | Fix the entry, or replace by hand |
| Partial replacements | A label shared a short paragraph (up to 120 characters) with other text | Check the page |
| Merged paragraphs | The source had lines cut with Enter: 2 to 4 paragraphs became one, which takes the attributes of the last one | Check line breaks; re-add a forced break (Shift+Enter) if a word is left alone |
| Lost column or frame starts | The target text is shorter, so the text moved up | Cursor at the start of the paragraph: Enter on the numeric keypad (column) or Shift+Enter on the numeric keypad (frame) |
| Overset text | The target text is longer | Adjust frames or copy |

## Lessons from real runs

- **Lines cut with Enter.** In the source PDF, lines of a quote, a caption or a
  diagram label that end without a trailing space are usually separate
  paragraphs. The first version of the script only matched whole paragraphs
  and missed four texts; it now joins up to 4 consecutive paragraphs.
- **Shorter text reflows.** Spanish to English shrinks the text, so paragraphs
  that started a column or a frame move up and long paragraphs split across
  columns. The script reports them; it does not insert breaks, because a
  forced break is sometimes wrong. Name each one for the user with the page.
- **Multiple spaces are collapsed for matching** but written as given in `en`:
  a running header lost its spacing until `en` copied it.
- **Repeated texts get their translation by page order**, which also fixes
  subtitles duplicated by mistake in the source.
- **Running the script on a translated copy** appends the suffix again to the
  file name (`-EN-EN`). Run it on the source file and rename the final copy.
- **Images keep the source language**: screenshots of software interfaces need
  new captures in the target language.

## Verification status

Verified in InDesign 2026 (21.5, Windows) on a 12-page document: whole and
multi-paragraph replacement, formatting runs (bold and colour), master-page
text, translations by page order, multiple spaces, the target-language
setting and the detection of lost column and frame starts (it reported the
three paragraphs found in the visual review plus a fourth that was also
right and easy to miss).
