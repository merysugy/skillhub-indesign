// import_docx.jsx
// Step 3 of the indesign-layout-prep workflow.
//
// Imports a Word document (.docx) into the active InDesign document and
// leaves it styled with YOUR template styles:
//   1. Asks for the .docx and places it on page 1 (in the first empty text
//      frame, or in a new frame at the page margins).
//   2. Maps Word paragraph styles to template styles (STYLE_MAP below).
//   3. Detects hand-made structure: short all-bold paragraphs become headings,
//      "- " / "1. " paragraphs become list items, manually indented
//      paragraphs become quotes.
//   4. Turns local bold / italic / superscript into character styles BEFORE
//      clearing overrides, so emphasis survives.
//   5. Removes empty paragraphs and the Word styles that came with the file.
//   6. Adds pages and threaded frames until there is no overset text.
//
// Written in ExtendScript (ES3): no let/const, no arrow functions, no
// template literals, no Array.forEach/map, no JSON.
//
// Install: Window > Utilities > Scripts, right-click "User" > Reveal in
// Finder / Explorer, copy this file there, then double-click it in the panel.
// Everything the script does can be undone with a single Edit > Undo.

#target indesign

// ---------------------------------------------------------------------------
// CONFIG - edit this block. Style paths use "Group:Style" (or just "Style"
// when the style is not inside a group).
// ---------------------------------------------------------------------------
var CONFIG = {
    // Word style name -> template paragraph style. Matching ignores case.
    styleMap: [
        ["Title", "Headings:Headline"],
        ["Heading 1", "Headings:Headline"],
        ["Título 1", "Headings:Headline"],
        ["Heading 2", "Headings:Subhead"],
        ["Título 2", "Headings:Subhead"],
        ["Heading 3", "Headings:Section Label"],
        ["Título 3", "Headings:Section Label"],
        ["Normal", "Body:Body"],
        ["Body Text", "Body:Body"],
        ["List Bullet", "Body:Bullet"],
        ["List Paragraph", "Body:Bullet"],
        ["List Number", "Body:Numbered"],
        ["Quote", "Callouts:Pull Quote"],
        ["Cita", "Callouts:Pull Quote"],
        ["Caption", "Captions & Notes:Caption"]
    ],

    // Used for any Word style that is not in styleMap.
    bodyStyle: "Body:Body",

    // Hand-made headings: short paragraphs where every character is bold.
    detectManualHeadings: true,
    manualHeadingStyle: "Headings:Subhead",
    manualHeadingMaxChars: 90,

    // Hand-made lists: paragraphs that start with a dash/bullet or "1." / "1)".
    detectManualLists: true,
    bulletStyle: "Body:Bullet",
    numberedStyle: "Body:Numbered",
    removeListMarkers: true,

    // Hand-made quotes: body paragraphs indented by at least this many points.
    detectManualQuotes: true,
    quoteStyle: "Callouts:Pull Quote",
    quoteMinIndentPt: 18,

    // Character styles for emphasis kept from Word. Leave "" to skip one.
    boldStyle: "Text:Bold",
    italicStyle: "Text:Italic",
    boldItalicStyle: "Text:Bold Italic",
    superscriptStyle: "Text:Superscript",

    removeEmptyParagraphs: true,
    removeImportedWordStyles: true,
    maxNewPages: 400
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function trim(text) {
    return String(text).replace(/^\s+|\s+$/g, "");
}

function findStyle(doc, path, kind) {
    if (!path) {
        return null;
    }
    var parts = path.split(":");
    var container = doc;
    var i;
    for (i = 0; i < parts.length - 1; i++) {
        var groups = (kind === "paragraph") ? container.paragraphStyleGroups
                                            : container.characterStyleGroups;
        var group = groups.itemByName(parts[i]);
        if (!group.isValid) {
            return null;
        }
        container = group;
    }
    var styles = (kind === "paragraph") ? container.paragraphStyles
                                        : container.characterStyles;
    var style = styles.itemByName(parts[parts.length - 1]);
    return style.isValid ? style : null;
}

function isBold(fontStyle) {
    return /bold|black|heavy|semibold|demi/i.test(String(fontStyle));
}

function isItalic(fontStyle) {
    return /italic|oblique/i.test(String(fontStyle));
}

function mapWordStyle(name) {
    var wanted = trim(name).toLowerCase();
    var i;
    for (i = 0; i < CONFIG.styleMap.length; i++) {
        if (trim(CONFIG.styleMap[i][0]).toLowerCase() === wanted) {
            return CONFIG.styleMap[i][1];
        }
    }
    return null;
}

function styleIds(collection) {
    var ids = {};
    var i;
    for (i = 0; i < collection.length; i++) {
        ids[collection[i].id] = true;
    }
    return ids;
}

function chooseDocx() {
    var filter;
    if ($.os.indexOf("Windows") !== -1) {
        filter = "Word document:*.docx";
    } else {
        filter = function (f) {
            return (f instanceof Folder) || /\.docx$/i.test(f.name);
        };
    }
    return File.openDialog("Choose the Word document to import", filter);
}

function setWordImportPreferences() {
    var p = app.wordRTFImportPreferences;
    var settings = [
        ["useTypographersQuotes", true],
        ["removeFormatting", false],
        ["preserveGraphics", true],
        ["importFootnotes", true],
        ["importEndnotes", true],
        ["importIndex", false],
        ["importTOC", false],
        ["importUnusedStyles", false]
    ];
    var i;
    for (i = 0; i < settings.length; i++) {
        try { p[settings[i][0]] = settings[i][1]; } catch (e1) {}
    }
    try { p.convertPageBreaks = ConvertPageBreaks.NONE; } catch (e2) {}
    try { p.resolveParagraphStyleClash = ResolveStyleClash.RESOLVE_CLASH_USE_EXISTING; } catch (e3) {}
    try { p.resolveCharacterStyleClash = ResolveStyleClash.RESOLVE_CLASH_USE_EXISTING; } catch (e4) {}
}

// Frame covering the page margins, with the page's columns.
function frameAtMargins(page) {
    var b = page.bounds; // [top, left, bottom, right]
    var mp = page.marginPreferences;
    var leftMargin = mp.left;
    var rightMargin = mp.right;
    // With facing pages, "left" is the inside margin: swap it on left-hand pages.
    if (page.side === PageSideOptions.LEFT_HAND) {
        leftMargin = mp.right;
        rightMargin = mp.left;
    }
    var frame = page.textFrames.add({
        geometricBounds: [b[0] + mp.top, b[1] + leftMargin, b[2] - mp.bottom, b[3] - rightMargin]
    });
    frame.textFramePreferences.textColumnCount = mp.columnCount;
    frame.textFramePreferences.textColumnGutter = mp.columnGutter;
    return frame;
}

function firstEmptyFrame(page) {
    var i;
    for (i = 0; i < page.textFrames.length; i++) {
        var f = page.textFrames[i];
        if (f.previousTextFrame === null && f.parentStory.contents === "") {
            return f;
        }
    }
    return null;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

function run() {
    if (app.documents.length === 0) {
        alert("Open your template (.indt / .idml) first, then run this script.");
        return;
    }
    var doc = app.activeDocument;

    // Check every style named in CONFIG before touching the document.
    var missing = [];
    var needed = [CONFIG.bodyStyle, CONFIG.manualHeadingStyle, CONFIG.bulletStyle,
                  CONFIG.numberedStyle, CONFIG.quoteStyle];
    var i;
    for (i = 0; i < CONFIG.styleMap.length; i++) {
        needed.push(CONFIG.styleMap[i][1]);
    }
    for (i = 0; i < needed.length; i++) {
        if (needed[i] && !findStyle(doc, needed[i], "paragraph")) {
            missing.push("Paragraph style: " + needed[i]);
        }
    }
    var charPaths = [CONFIG.boldStyle, CONFIG.italicStyle, CONFIG.boldItalicStyle,
                     CONFIG.superscriptStyle];
    for (i = 0; i < charPaths.length; i++) {
        if (charPaths[i] && !findStyle(doc, charPaths[i], "character")) {
            missing.push("Character style: " + charPaths[i]);
        }
    }
    if (missing.length > 0) {
        alert("These styles are not in the document. Fix CONFIG or the template:\n\n" +
              missing.join("\n"));
        return;
    }

    var file = chooseDocx();
    if (!file) {
        return;
    }

    var bodyStyle = findStyle(doc, CONFIG.bodyStyle, "paragraph");
    var charBold = findStyle(doc, CONFIG.boldStyle, "character");
    var charItalic = findStyle(doc, CONFIG.italicStyle, "character");
    var charBoldItalic = findStyle(doc, CONFIG.boldItalicStyle, "character");
    var charSuper = findStyle(doc, CONFIG.superscriptStyle, "character");

    var view = doc.viewPreferences;
    var oldH = view.horizontalMeasurementUnits;
    var oldV = view.verticalMeasurementUnits;
    var oldOrigin = view.rulerOrigin;
    view.horizontalMeasurementUnits = MeasurementUnits.POINTS;
    view.verticalMeasurementUnits = MeasurementUnits.POINTS;
    view.rulerOrigin = RulerOrigin.PAGE_ORIGIN;

    var report = { mapped: {}, unmapped: {}, headings: 0, lists: 0, quotes: 0,
                   emphasis: 0, removed: 0, pages: 0, wordStyles: 0 };

    try {
        // Remember which styles existed before the import.
        var paraBefore = styleIds(doc.allParagraphStyles);
        var charBefore = styleIds(doc.allCharacterStyles);

        // 1. Place the file.
        setWordImportPreferences();
        var page = doc.pages[0];
        var frame = firstEmptyFrame(page) || frameAtMargins(page);
        frame.place(file, false);
        var story = frame.parentStory;

        // 2. Decide the target style of every paragraph (back to front, so
        //    removing list markers does not shift paragraphs still to visit).
        var paras = story.paragraphs.everyItem().getElements();
        var decisions = [];
        var p;
        for (p = paras.length - 1; p >= 0; p--) {
            var para = paras[p];
            var text = String(para.contents).replace(/[\r\n]+$/, "");
            var wordName = para.appliedParagraphStyle.name;
            var path = mapWordStyle(wordName);
            var kind = "mapped";
            if (!path) {
                path = CONFIG.bodyStyle;
                kind = "fallback";
            }
            var isBodyLike = (path === CONFIG.bodyStyle);

            if (isBodyLike && CONFIG.detectManualLists) {
                var bullet = text.match(/^\s*[\-–—•●\*]\s+/);
                var number = text.match(/^\s*\d{1,3}[\.\)]\s+/);
                if (bullet || number) {
                    path = bullet ? CONFIG.bulletStyle : CONFIG.numberedStyle;
                    kind = "list";
                    if (CONFIG.removeListMarkers) {
                        var markerLength = (bullet || number)[0].length;
                        para.characters.itemByRange(0, markerLength - 1).remove();
                    }
                }
            }
            if (kind !== "list" && isBodyLike && CONFIG.detectManualHeadings &&
                text.length > 0 && text.length <= CONFIG.manualHeadingMaxChars &&
                !/[\.:;,]$/.test(trim(text)) && allBold(para)) {
                path = CONFIG.manualHeadingStyle;
                kind = "heading";
            }
            if (kind !== "list" && kind !== "heading" && isBodyLike &&
                CONFIG.detectManualQuotes && para.leftIndent >= CONFIG.quoteMinIndentPt) {
                path = CONFIG.quoteStyle;
                kind = "quote";
            }
            decisions[p] = { path: path, kind: kind, word: wordName };
        }

        // 3. Emphasis -> character styles (skipped on detected headings).
        paras = story.paragraphs.everyItem().getElements();
        for (p = 0; p < paras.length; p++) {
            if (decisions[p] && decisions[p].kind === "heading") {
                continue;
            }
            report.emphasis += emphasisToCharacterStyles(paras[p], charBold, charItalic,
                                                         charBoldItalic, charSuper);
        }

        // 4. Apply template paragraph styles and clear local overrides.
        //    Character styles applied in step 3 are kept.
        for (p = 0; p < paras.length; p++) {
            var d = decisions[p];
            if (!d) {
                continue;
            }
            var target = findStyle(doc, d.path, "paragraph") || bodyStyle;
            paras[p].applyParagraphStyle(target, true);
            if (d.kind === "heading") { report.headings++; }
            if (d.kind === "list") { report.lists++; }
            if (d.kind === "quote") { report.quotes++; }
            if (d.kind === "fallback") {
                report.unmapped[d.word] = (report.unmapped[d.word] || 0) + 1;
            }
            report.mapped[d.path] = (report.mapped[d.path] || 0) + 1;
        }

        // 5. Remove empty paragraphs (back to front).
        if (CONFIG.removeEmptyParagraphs) {
            paras = story.paragraphs.everyItem().getElements();
            for (p = paras.length - 1; p >= 0; p--) {
                if (/^\s*$/.test(String(paras[p].contents)) &&
                    paras[p].allGraphics.length === 0 && paras[p].tables.length === 0) {
                    paras[p].remove();
                    report.removed++;
                }
            }
        }

        // 6. Remove the styles that came in with the Word file.
        if (CONFIG.removeImportedWordStyles) {
            report.wordStyles += removeNewStyles(doc.allParagraphStyles, paraBefore, bodyStyle);
            report.wordStyles += removeNewStyles(doc.allCharacterStyles, charBefore,
                                                 doc.characterStyles[0]);
        }

        // 7. Add pages and threaded frames until nothing is overset.
        while (frame.nextTextFrame) {
            frame = frame.nextTextFrame;
        }
        story.recompose();
        while (frame.overflows && report.pages < CONFIG.maxNewPages) {
            var newPage = doc.pages.add(LocationOptions.AT_END);
            var next = frameAtMargins(newPage);
            frame.nextTextFrame = next;
            frame = next;
            report.pages++;
            story.recompose();
        }
    } finally {
        view.horizontalMeasurementUnits = oldH;
        view.verticalMeasurementUnits = oldV;
        view.rulerOrigin = oldOrigin;
    }

    showReport(report);
}

function allBold(para) {
    var ranges = para.textStyleRanges.everyItem().getElements();
    var found = false;
    var r;
    for (r = 0; r < ranges.length; r++) {
        if (/^\s*$/.test(String(ranges[r].contents))) {
            continue;
        }
        if (!isBold(ranges[r].fontStyle)) {
            return false;
        }
        found = true;
    }
    return found;
}

function emphasisToCharacterStyles(para, charBold, charItalic, charBoldItalic, charSuper) {
    var baseStyle = String(para.appliedParagraphStyle.fontStyle);
    var baseBold = isBold(baseStyle);
    var baseItalic = isItalic(baseStyle);
    var ranges = para.textStyleRanges.everyItem().getElements();
    var count = 0;
    var r;
    for (r = ranges.length - 1; r >= 0; r--) {
        var range = ranges[r];
        if (/^\s*$/.test(String(range.contents))) {
            continue;
        }
        var fs = String(range.fontStyle);
        var bold = isBold(fs) && !baseBold;
        var italic = isItalic(fs) && !baseItalic;
        var style = null;
        if (bold && italic) {
            style = charBoldItalic || charBold || charItalic;
        } else if (bold) {
            style = charBold;
        } else if (italic) {
            style = charItalic;
        } else if (charSuper && range.position === Position.SUPERSCRIPT) {
            style = charSuper;
        }
        if (style) {
            range.appliedCharacterStyle = style;
            count++;
        }
    }
    return count;
}

function removeNewStyles(allStyles, before, replacement) {
    var removed = 0;
    var i;
    for (i = allStyles.length - 1; i >= 0; i--) {
        var s = allStyles[i];
        if (before[s.id] || s.name.charAt(0) === "[") {
            continue;
        }
        try {
            s.remove(replacement);
            removed++;
        } catch (e) {}
    }
    return removed;
}

function showReport(report) {
    var lines = ["Import finished.", ""];
    var key;
    lines.push("Paragraphs per style:");
    for (key in report.mapped) {
        if (report.mapped.hasOwnProperty(key)) {
            lines.push("  " + key + ": " + report.mapped[key]);
        }
    }
    lines.push("");
    lines.push("Hand-made headings detected: " + report.headings);
    lines.push("Hand-made list items detected: " + report.lists);
    lines.push("Hand-made quotes detected: " + report.quotes);
    lines.push("Emphasis runs turned into character styles: " + report.emphasis);
    lines.push("Empty paragraphs removed: " + report.removed);
    lines.push("Word styles removed: " + report.wordStyles);
    lines.push("Pages added: " + report.pages);
    var unmapped = [];
    for (key in report.unmapped) {
        if (report.unmapped.hasOwnProperty(key)) {
            unmapped.push("  " + key + " (" + report.unmapped[key] + ")");
        }
    }
    if (unmapped.length > 0) {
        lines.push("");
        lines.push("Word styles not in STYLE_MAP (set to " + CONFIG.bodyStyle + "):");
        lines.push(unmapped.join("\n"));
    }
    alert(lines.join("\n"));
}

app.doScript(run, ScriptLanguage.JAVASCRIPT, undefined, UndoModes.ENTIRE_SCRIPT,
             "Import Word document");
