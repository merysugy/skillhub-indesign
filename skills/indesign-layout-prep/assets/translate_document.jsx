#target indesign
// ===========================================================================
// Translate an InDesign document paragraph by paragraph (source -> target)
// Built by scripts/build_translation_jsx.py from a translations JSON file.
// Do not edit TRANSLATIONS by hand: edit the JSON and build again.
//
// What it does (all undoable in one step, Edit > Undo):
//   1. Saves a COPY of the open document; the original is never modified.
//   2. Finds each paragraph by its source text (ignores case, line breaks,
//      special spaces) and replaces it with the target text, keeping the
//      paragraph style and the formatting of the **marked** runs.
//      Also matches a sentence split over 2-4 paragraphs (lines cut with Enter).
//   3. Sets the replaced text to the target language (hyphenation, spelling).
//   4. Writes a .txt report next to the document: not found, partial
//      replacements, merged paragraphs, column/frame starts lost, overset text.
// It does not translate images.
// ===========================================================================
var CONFIG = {
    targetLocale: "en_US",      // ICU locale of the target language
    sourceTag: "[ES]",          // tag in the file name, replaced in the copy...
    targetTag: "[EN]",          // ...by this one (if absent, "-EN" is appended)
    copySuffix: "-EN"
};

// @@TRANSLATIONS@@

// ---------------------------------------------------------------------------
// LOGIC (nothing to change below this line)
// ---------------------------------------------------------------------------
var MAX_PARTIAL_LEN = 120;   // partial matches are only searched in short paragraphs (labels)
var FMT_PROPS = ["appliedCharacterStyle", "appliedFont", "fontStyle", "pointSize",
                 "fillColor", "fillTint", "capitalization", "underline"];

function isIgnorable(ch) {
    return ch == "\u00AD" || ch == "\uFEFF" || ch == "\u200B" || ch == "\u200C" ||
           ch == "\u200D" || ch == "\u0003" || ch == "\u0007" || ch == "\u0008";
}
function isSpace(ch) {
    if (ch == " " || ch == "\t" || ch == "\r" || ch == "\n" || ch == "\u00A0" ||
        ch == "\u202F" || ch == "\u2028" || ch == "\u2029") { return true; }
    return ch >= "\u2000" && ch <= "\u200A";   // em, en, third, quarter, sixth, thin, hair, figure, punctuation, flush
}
function canon(ch) {
    if (ch == "\u2019" || ch == "\u2018" || ch == "\u00B4") { return "'"; }
    if (ch == "\u201C" || ch == "\u201D") { return "\""; }
    if (ch == "\u2013" || ch == "\u2014" || ch == "\u2011") { return "-"; }
    return ch.toLowerCase();
}
function isWordChar(ch) { return /[0-9a-z\u00C0-\u024F]/.test(ch); }

// Normalised text (lower case, spaces and breaks collapsed) + map to the original index.
function normalize(raw) {
    var out = [], map = [], pending = false, pendingIdx = -1, i, ch;
    for (i = 0; i < raw.length; i++) {
        ch = raw.charAt(i);
        if (isIgnorable(ch)) { continue; }
        if (isSpace(ch)) {
            if (!pending) { pending = true; pendingIdx = i; }
            continue;
        }
        if (pending && out.length > 0) { out.push(" "); map.push(pendingIdx); }
        pending = false;
        out.push(canon(ch));
        map.push(i);
    }
    return { s: out.join(""), map: map };
}

// Splits the **...** marks -> plain text + runs [start, end) over the plain text.
function parseMarked(str) {
    var plain = "", runs = [], open = -1, i = 0;
    while (i < str.length) {
        if (str.substr(i, 2) == "**") {
            if (open < 0) { open = plain.length; } else { runs.push([open, plain.length]); open = -1; }
            i += 2;
            continue;
        }
        plain += str.charAt(i);
        i++;
    }
    if (open >= 0) { throw new Error("Unclosed ** marks in: " + str); }
    return { plain: plain, runs: runs };
}

function inRuns(idx, runs) {
    for (var r = 0; r < runs.length; r++) {
        if (idx >= runs[r][0] && idx < runs[r][1]) { return true; }
    }
    return false;
}

function prepareEntries(list) {
    var entries = [], index = {}, i, e, es, n, k, enList, j;
    for (i = 0; i < list.length; i++) {
        e = list[i];
        es = parseMarked(e.es);
        n = normalize(es.plain);
        enList = (e.en instanceof Array) ? e.en : [e.en];
        for (j = 0; j < enList.length; j++) { enList[j] = parseMarked(enList[j]); }
        var entry = { es: es, norm: n.s, en: enList, isList: (e.en instanceof Array),
                      markK: -1, normalK: -1, hits: [] };
        // index (in the normalised text) of the first marked and the first unmarked character
        for (k = 0; k < n.s.length; k++) {
            if (n.s.charAt(k) == " ") { continue; }
            if (inRuns(n.map[k], es.runs)) { if (entry.markK < 0) { entry.markK = k; } }
            else if (entry.normalK < 0) { entry.normalK = k; }
        }
        if (index["k_" + n.s]) { throw new Error("Duplicate source text in the data: " + es.plain); }
        index["k_" + n.s] = entry;
        entries.push(entry);
    }
    return { entries: entries, index: index };
}

function paraText(p) {
    var c = p.contents;
    return (typeof c == "string") ? c : "";
}

// Prefix that is kept: typed bullets, anchored objects and leading spaces.
function prefixLength(raw) {
    var i = 0, ch;
    while (i < raw.length) {
        ch = raw.charAt(i);
        if (ch == "\u2022" || ch == "\uFFFC" || isSpace(ch) || isIgnorable(ch)) { i++; } else { break; }
    }
    return i;
}

function normalizePara(raw) {
    var pre = prefixLength(raw);
    var n = normalize(raw.substring(pre));
    for (var i = 0; i < n.map.length; i++) { n.map[i] += pre; }
    return n;
}

function textRange(p, a, b) { return p.characters.itemByRange(a, b).texts[0]; }

function readFmt(ch) {
    var f = {}, i;
    for (i = 0; i < FMT_PROPS.length; i++) {
        try { f[FMT_PROPS[i]] = ch[FMT_PROPS[i]]; } catch (e) {}
    }
    return f;
}
function applyFmt(t, f) {
    var i;
    for (i = 0; i < FMT_PROPS.length; i++) {
        if (f.hasOwnProperty(FMT_PROPS[i])) {
            try { t[FMT_PROPS[i]] = f[FMT_PROPS[i]]; } catch (e) {}
        }
    }
}

function sortKey(p) {
    var page = 999999, y = 0, x = 0;
    try {
        var fr = p.parentTextFrames[0];
        var pg = fr.parentPage;
        if (pg && pg.parent && pg.parent.constructor.name == "Spread") { page = pg.documentOffset; }
        else if (pg) { page = 100000; }   // master page
        var gb = fr.geometricBounds;
        y = gb[0]; x = gb[1];
    } catch (e) {}
    try { y = p.baseline; x = p.horizontalOffset; } catch (e2) {}
    return [page, y, x];
}
function cmpKeys(a, b) {
    for (var i = 0; i < 3; i++) { if (a.key[i] != b.key[i]) { return a.key[i] - b.key[i]; } }
    return 0;
}

function pageLabel(p) {
    try {
        var pg = p.parentTextFrames[0].parentPage;
        if (!pg) { return "pasteboard"; }
        if (pg.parent.constructor.name == "MasterSpread") { return "master " + pg.parent.name; }
        return "p. " + pg.name;
    } catch (e) { return "?"; }
}

function shortText(s) {
    s = s.replace(/[\r\n]+/g, " ");
    return s.length > 70 ? s.substring(0, 70) + "\u2026" : s;
}

// Does the paragraph start a column or a frame? (the previous one ends in another frame, or lower in the same one)
function frameId(ch) {
    try { var f = ch.parentTextFrames; return (f && f.length) ? String(f[0].id) : null; } catch (e) { return null; }
}
function startsColumn(container, idx) {
    if (idx == 0) { return false; }
    try {
        var p = container.paragraphs[idx], prev = container.paragraphs[idx - 1];
        if (!p.characters.length || !prev.characters.length) { return false; }
        var a = prev.characters[prev.characters.length - 1], b = p.characters[0];
        var fa = frameId(a), fb = frameId(b);
        if (!fa || !fb) { return false; }
        if (fa != fb) { return true; }
        return b.baseline < a.baseline - 1;
    } catch (e) { return false; }
}

function collectContainers(doc) {
    var out = [], stories = doc.stories, i, t, c, tables, cells;
    for (i = 0; i < stories.length; i++) {
        out.push({ obj: stories[i], isStory: true });
        tables = stories[i].tables;
        for (t = 0; t < tables.length; t++) {
            cells = tables[t].cells;
            for (c = 0; c < cells.length; c++) { out.push({ obj: cells[c], isStory: false }); }
        }
    }
    return out;
}

function findLanguage(app) {
    try {
        var langs = app.languagesWithVendors, i;
        for (i = 0; i < langs.length; i++) {
            try { if (langs[i].icuLocaleName == CONFIG.targetLocale) { return langs[i]; } } catch (e) {}
        }
    } catch (e2) {}
    return null;
}

// Replaces the whole paragraph, keeping the prefix, paragraph style and formatting.
function replaceWhole(target, entry, en, lang, report) {
    var p = target.container.paragraphs[target.idx];
    var raw = paraText(p);
    var pn = normalizePara(raw);
    if (pn.s != entry.norm) {
        report.skipped.push(target.where + ": the text changed before it could be replaced: " + shortText(raw));
        return;
    }
    var a = pn.map[0], b = pn.map[pn.map.length - 1];
    var inner = raw.substring(a, b + 1);
    if (inner.indexOf("\uFFFC") >= 0 || inner.indexOf("\u0016") >= 0) {
        report.skipped.push(target.where + ": holds an anchored object or a table, replace by hand: " + shortText(raw));
        return;
    }
    var normalFmt = entry.normalK >= 0 ? readFmt(p.characters[pn.map[entry.normalK]]) : null;
    var markFmt = entry.markK >= 0 ? readFmt(p.characters[pn.map[entry.markK]]) : null;

    textRange(p, a, b).contents = en.plain;

    p = target.container.paragraphs[target.idx];
    var all = textRange(p, a, a + en.plain.length - 1);
    if (normalFmt) { applyFmt(all, normalFmt); }
    if (markFmt) {
        for (var r = 0; r < en.runs.length; r++) {
            if (en.runs[r][1] > en.runs[r][0]) {
                applyFmt(textRange(p, a + en.runs[r][0], a + en.runs[r][1] - 1), markFmt);
            }
        }
    } else if (en.runs.length) {
        report.notes.push(target.where + ": the target has marked runs but the source does not; check the formatting: " + shortText(en.plain));
    }
    if (lang) { try { all.appliedLanguage = lang; } catch (e) {} }
    report.replaced++;
}

// Partial replacement (labels that share a paragraph with others). Keeps the formatting of the first character.
function replacePartial(target, entry, lang, report) {
    var count = 0, guard = 0;
    while (guard++ < 20) {
        var p = target.container.paragraphs[target.idx];
        var raw = paraText(p);
        var pn = normalizePara(raw);
        var pos = pn.s.indexOf(entry.norm), found = false;
        while (pos >= 0) {
            var before = pos > 0 ? pn.s.charAt(pos - 1) : " ";
            var after = pos + entry.norm.length < pn.s.length ? pn.s.charAt(pos + entry.norm.length) : " ";
            if (!isWordChar(before) && !isWordChar(after)) { found = true; break; }
            pos = pn.s.indexOf(entry.norm, pos + 1);
        }
        if (!found) { break; }
        var a = pn.map[pos], b = pn.map[pos + entry.norm.length - 1];
        textRange(p, a, b).contents = entry.en[0].plain;
        if (lang) {
            p = target.container.paragraphs[target.idx];
            try { textRange(p, a, a + entry.en[0].plain.length - 1).appliedLanguage = lang; } catch (e) {}
        }
        count++;
    }
    if (count) {
        report.partial.push(target.where + ": \u00AB" + entry.es.plain + "\u00BB \u2192 \u00AB" + entry.en[0].plain + "\u00BB");
        report.replaced += count;
    }
    return count;
}

// Merges paragraphs idx..idx+span-1 into one (their returns become spaces, from last to first).
function mergeParagraphs(container, idx, span) {
    for (var k = idx + span - 2; k >= idx; k--) {
        var pk = container.paragraphs[k];
        var last = pk.characters.length - 1;
        if (paraText(pk).charAt(last) == "\r") { textRange(pk, last, last).contents = " "; }
    }
}

function inventory(containers) {
    var list = [], c, j, ps, raw, pn;
    for (c = 0; c < containers.length; c++) {
        ps = containers[c].obj.paragraphs;
        var row = [];
        for (j = 0; j < ps.length; j++) {
            raw = paraText(ps[j]);
            pn = normalizePara(raw);
            row.push({ container: containers[c].obj, isStory: containers[c].isStory, cNo: c, idx: j,
                       span: 1, norm: pn.s, used: false, p: ps[j] });
        }
        list.push(row);
    }
    return list;
}

function runTranslation(doc, appRef) {
    var prep = prepareEntries(TRANSLATIONS);
    var report = { replaced: 0, notFound: [], skipped: [], partial: [], merged: [], breaks: [],
                   notes: [], overset: [], lang: true };
    var lang = findLanguage(appRef);
    if (!lang) { report.lang = false; }
    var containers = collectContainers(doc);
    var rows = inventory(containers), r, j, n, t, entry, i, h;

    // 1) Whole paragraph
    for (r = 0; r < rows.length; r++) {
        for (j = 0; j < rows[r].length; j++) {
            t = rows[r][j];
            if (!t.norm.length) { continue; }
            entry = prep.index["k_" + t.norm];
            if (entry) { t.used = true; entry.hits.push(t); }
        }
    }
    // 2) Several consecutive paragraphs (lines cut with Enter): 2 to 4 paragraphs
    for (r = 0; r < rows.length; r++) {
        for (j = 0; j < rows[r].length; j++) {
            for (n = 2; n <= 4 && j + n <= rows[r].length; n++) {
                var parts = [], ok = true;
                for (i = j; i < j + n; i++) {
                    if (rows[r][i].used || !rows[r][i].norm.length) { ok = false; break; }
                    parts.push(rows[r][i].norm);
                }
                if (!ok) { break; }
                entry = prep.index["k_" + parts.join(" ")];
                if (entry) {
                    t = rows[r][j];
                    t.span = n;
                    for (i = j; i < j + n; i++) { rows[r][i].used = true; }
                    entry.hits.push(t);
                    break;
                }
            }
        }
    }

    // 3) Assign translations (repeated texts by page order) and prepare the operations
    var ops = [];
    for (i = 0; i < prep.entries.length; i++) {
        entry = prep.entries[i];
        if (!entry.hits.length) { continue; }
        for (h = 0; h < entry.hits.length; h++) {
            entry.hits[h].key = sortKey(entry.hits[h].p);
            entry.hits[h].where = pageLabel(entry.hits[h].p);
        }
        entry.hits.sort(cmpKeys);
        if (entry.isList && entry.hits.length != entry.en.length) {
            report.notes.push("\u00AB" + entry.es.plain + "\u00BB appears " + entry.hits.length +
                              " times and there are " + entry.en.length + " translations; check the order.");
        }
        for (h = 0; h < entry.hits.length; h++) {
            t = entry.hits[h];
            t.entry = entry;
            t.en = entry.en[Math.min(h, entry.en.length - 1)];
            ops.push(t);
        }
    }

    // 4) Paragraphs that start a column or frame in the source: noted with the text they will have
    var colStarts = [];
    for (r = 0; r < rows.length; r++) {
        if (!rows[r].length || !rows[r][0].isStory) { continue; }
        for (j = 1; j < rows[r].length; j++) {
            t = rows[r][j];
            if (!t.norm.length || !startsColumn(t.container, j)) { continue; }
            var expected = t.en ? normalize(t.en.plain).s : (t.used ? null : t.norm);
            if (expected) { colStarts.push({ cNo: r, norm: expected, where: pageLabel(t.p) }); }
        }
    }

    // 5) Run: per container and bottom to top, so indexes stay valid
    ops.sort(function (x, y) { return (x.cNo != y.cNo) ? x.cNo - y.cNo : y.idx - x.idx; });
    for (i = 0; i < ops.length; i++) {
        t = ops[i];
        if (t.span > 1) {
            mergeParagraphs(t.container, t.idx, t.span);
            report.merged.push(t.where + ": " + t.span + " paragraphs merged into one: \u00AB" + shortText(t.en.plain) + "\u00BB");
        }
        replaceWhole(t, t.entry, t.en, lang, report);
    }

    // 6) Partial matches in short paragraphs (fresh inventory, after the changes)
    var fresh = inventory(containers), pending = [];
    for (i = 0; i < prep.entries.length; i++) {
        if (!prep.entries[i].hits.length) { pending.push(prep.entries[i]); }
    }
    pending.sort(function (x, y) { return y.norm.length - x.norm.length; });
    for (i = 0; i < pending.length; i++) {
        entry = pending[i];
        var done = 0;
        if (!entry.es.runs.length && !entry.isList) {
            for (r = 0; r < fresh.length; r++) {
                for (j = 0; j < fresh[r].length; j++) {
                    t = fresh[r][j];
                    if (!t.norm.length || t.norm.length > MAX_PARTIAL_LEN) { continue; }
                    t.where = pageLabel(t.p);
                    done += replacePartial(t, entry, lang, report);
                }
            }
        }
        if (!done) { report.notFound.push(entry.es.plain); }
    }

    // 7) Do the paragraphs that started a column or frame in the source still do?
    for (i = 0; i < colStarts.length; i++) {
        var cs = colStarts[i], cont = containers[cs.cNo].obj, ps = cont.paragraphs, found = false;
        for (j = 1; j < ps.length; j++) {
            if (normalizePara(paraText(ps[j])).s == cs.norm) {
                found = true;
                if (!startsColumn(cont, j)) {
                    report.breaks.push(pageLabel(ps[j]) + ": \u00AB" + shortText(paraText(ps[j])) + "\u00BB");
                }
                break;
            }
        }
    }

    // 8) Overset text
    var st = doc.stories;
    for (i = 0; i < st.length; i++) {
        try {
            if (st[i].overflows) {
                var tc = st[i].textContainers;
                var last = tc[tc.length - 1];
                var where = "?";
                try { where = last.parentPage ? "p. " + last.parentPage.name : "pasteboard"; } catch (e) {}
                report.overset.push(where + ": " + shortText(paraText(st[i])));
            }
        } catch (e2) {}
    }
    return report;
}

function reportText(r, docName) {
    var L = [], i;
    L.push("Translation " + CONFIG.sourceTag + " \u2192 " + CONFIG.targetTag + " \u00B7 " + docName);
    L.push("Paragraphs replaced: " + r.replaced);
    if (!r.lang) { L.push("WARNING: language " + CONFIG.targetLocale + " not found; the text keeps the source language (affects hyphenation and spelling)."); }
    function block(title, arr) {
        L.push("");
        L.push(title + " (" + arr.length + ")");
        for (i = 0; i < arr.length; i++) { L.push("  - " + arr[i]); }
    }
    block("NOT FOUND: source texts that are not in the document as a paragraph", r.notFound);
    block("PARTIAL REPLACEMENTS: check on the page", r.partial);
    block("MERGED PARAGRAPHS: the source had lines cut with Enter; check the line breaks", r.merged);
    block("LOST COLUMN OR FRAME STARTS: these paragraphs started a column or frame in the source. " +
          "Put the cursor at the start and press Enter on the numeric keypad (column) or Shift + Enter on the numeric keypad (frame)", r.breaks);
    block("SKIPPED: replace by hand", r.skipped);
    block("NOTES", r.notes);
    block("OVERSET TEXT", r.overset);
    return L.join("\n");
}

function main() {
    if (app.documents.length == 0) { alert("Open the source-language .indd first."); return; }
    var doc = app.activeDocument;
    if (!doc.saved) { alert("Save the document before running the script."); return; }
    var src = doc.fullName;
    var base = src.name.replace(/\.indd$/i, "");
    var enBase = base.indexOf(CONFIG.sourceTag) >= 0 ? base.replace(CONFIG.sourceTag, CONFIG.targetTag) : base + CONFIG.copySuffix;
    var dst = new File(src.parent.fsName + "/" + enBase + ".indd");
    if (dst.exists && !confirm("\u00AB" + dst.name + "\u00BB already exists. Overwrite it?")) { return; }

    // Copy: the original is not modified. From here on the script works on the copy.
    doc = doc.save(dst);

    var report = null;
    app.doScript(function () { report = runTranslation(doc, app); },
                 ScriptLanguage.JAVASCRIPT, undefined, UndoModes.ENTIRE_SCRIPT, "Translate document");

    var txt = reportText(report, doc.name);
    var log = new File(src.parent.fsName + "/" + enBase + " - translation report.txt");
    log.encoding = "UTF-8";
    if (log.open("w")) { log.write(txt); log.close(); }

    alert("Copy created: " + doc.name + "\n" +
          "Replaced: " + report.replaced + "\n" +
          "Not found: " + report.notFound.length + " \u00B7 Partial: " + report.partial.length +
          " \u00B7 Skipped: " + report.skipped.length + " \u00B7 Overset: " + report.overset.length + "\n" +
          "Merged paragraphs: " + report.merged.length + " \u00B7 Column/frame starts to check: " + report.breaks.length + "\n\n" +
          "Details in: " + log.name + "\n" +
          "The changes are not saved: check them and save (or Edit > Undo to revert).");
}

if (typeof app != "undefined" && typeof app.documents != "undefined") { main(); }
