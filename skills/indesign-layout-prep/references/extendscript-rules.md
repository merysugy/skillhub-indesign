# ExtendScript rules for InDesign

InDesign scripts run in **ExtendScript**, Adobe's JavaScript from 1999
(ECMAScript 3). Modern JavaScript fails, often with a vague error. Unless told
otherwise, Claude tends to write modern JavaScript: these rules prevent it.

## Language: ES3 only

| Don't | Do |
| --- | --- |
| `let`, `const` | `var` |
| `(a) => a * 2` | `function (a) { return a * 2; }` |
| `` `Hi ${name}` `` | `"Hi " + name` |
| `arr.forEach`, `map`, `filter`, `reduce`, `find`, `includes` | `for (var i = 0; i < arr.length; i++)` |
| `arr.indexOf(x)` on arrays | a loop (string `indexOf` is fine) |
| `str.trim()`, `startsWith`, `endsWith`, `repeat` | regex: `str.replace(/^\s+\|\s+$/g, "")` |
| `JSON.parse/stringify` | avoid, or `#include "json2.js"` |
| `Object.keys/assign` | `for (var k in o) { if (o.hasOwnProperty(k)) ... }` |
| `class`, destructuring, spread, default params, `for...of` | constructor functions, explicit code |
| `Map`, `Set`, `Promise`, `async/await` | plain objects, synchronous code |
| trailing commas `[1, 2,]` | none |
| accented letters or symbols in code/strings (`"Título"`) | `\uXXXX` escapes (`"T\u00EDtulo"`) |

Always run `python3 scripts/check_es3.py file.jsx` before delivering.

## Structure

- Start with `#target indesign`.
- Put settings in a `CONFIG` object at the top with comments, so the user can
  edit names without reading the code.
- Run everything through `app.doScript(run, ScriptLanguage.JAVASCRIPT,
  undefined, UndoModes.ENTIRE_SCRIPT, "Name")`: one Undo reverts all.
- Check `app.documents.length` and every style/swatch the script needs
  **before** changing anything; list what is missing in one `alert`.
- Set measurement units and ruler origin explicitly
  (`doc.viewPreferences.horizontalMeasurementUnits = MeasurementUnits.POINTS`,
  `rulerOrigin = RulerOrigin.PAGE_ORIGIN`) and restore them in `finally`.
- End with an `alert` report of what was done.

## InDesign object model pitfalls

- **Styles in groups**: `doc.paragraphStyles.itemByName("Headline")` does not
  find a style inside a group. Walk the groups
  (`doc.paragraphStyleGroups.itemByName("Headings").paragraphStyles.itemByName("Headline")`)
  or use the `findStyle(doc, "Headings:Headline", "paragraph")` helper in the
  templates. Check `.isValid` before using a result.
- **Emphasis survives only as character styles**: clearing overrides
  (`applyParagraphStyle(style, true)`, `clearOverrides()`) removes local
  bold/italic. Convert them to character styles first.
- **Iterate backwards** when removing text or paragraphs, and take a
  snapshot first: `story.paragraphs.everyItem().getElements()`.
- `geometricBounds` is `[top, left, bottom, right]`, not x/y/width/height.
- With facing pages, `marginPreferences.left` is the **inside** margin; on
  left-hand pages (`page.side === PageSideOptions.LEFT_HAND`) the inside is on
  the right.
- Threading: `frame.nextTextFrame = newFrame`; check `frame.overflows` after
  `story.recompose()`.
- Placing a Word file: `frame.place(file, false)`; import options live in
  `app.wordRTFImportPreferences` (wrap each setting in `try`, names vary
  across versions).
- File dialogs: on macOS `File.openDialog` takes a filter **function**, on
  Windows a filter **string** (`"Word:*.docx"`).
- Swatches by name: `doc.swatches.itemByName("Brand Blue")`; built-ins are
  `"None"`, `"Paper"`, `"Black"`, `"Registration"`.

## Installing (repeat to the user)

Window > Utilities > Scripts > right-click **User** > Reveal in Finder /
Explorer > copy the `.jsx` there > double-click it in the panel.
