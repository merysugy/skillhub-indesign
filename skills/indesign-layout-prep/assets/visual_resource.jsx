// visual_resource.jsx
// Step 4 of the indesign-layout-prep workflow.
//
// Builds one visual resource (here: a "key figure" box) on the current page,
// using the swatches and styles that already exist in the document, and
// groups it so you can move it, resize it, or take it apart.
//
// Claude adapts this file for each resource it proposes (key figure, process
// diagram, comparison, mind map, quote box...). The helpers at the top
// (box, textBox, line, ellipse) are the building blocks; build() composes them.
//
// ExtendScript (ES3): no let/const, no arrow functions, no template literals.
// Install: Window > Utilities > Scripts, right-click "User" > Reveal in
// Finder / Explorer, copy the file there, double-click it in the panel.
// One Edit > Undo removes everything it created.

#target indesign

// ---------------------------------------------------------------------------
// CONFIG - all positions and sizes in millimetres, from the page's top-left.
// ---------------------------------------------------------------------------
var CONFIG = {
    name: "Key figure - 68% adoption",
    origin: [20, 20],          // [x, y] of the top-left corner
    width: 80,
    padding: 6,

    figure: "68%",
    label: "of teams already use AI in their daily workflow",
    source: "Source: Northwind Survey 2026",

    // Swatch names and style paths ("Group:Style") from your template.
    backgroundSwatch: "Northwind Sand",
    accentSwatch: "Northwind Teal",
    figureStyle: "Callouts:Key Figure",
    labelStyle: "Callouts:Box Text",
    sourceStyle: "Captions & Notes:Source"
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function findStyle(doc, path, kind) {
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

function swatch(doc, name) {
    var s = doc.swatches.itemByName(name);
    return s.isValid ? s : null;
}

// Rectangle. bounds = [x, y, width, height] in mm.
function box(page, bounds, fill, stroke, strokeWeightPt) {
    var r = page.rectangles.add({
        geometricBounds: [bounds[1], bounds[0], bounds[1] + bounds[3], bounds[0] + bounds[2]]
    });
    r.fillColor = fill || page.parent.parent.swatches.itemByName("None");
    if (stroke) {
        r.strokeColor = stroke;
        r.strokeWeight = strokeWeightPt || 0.5;
    } else {
        r.strokeWeight = 0;
    }
    return r;
}

// Text frame. paragraphs = [[text, paragraphStyle], ...]
function textBox(page, bounds, paragraphs) {
    var tf = page.textFrames.add({
        geometricBounds: [bounds[1], bounds[0], bounds[1] + bounds[3], bounds[0] + bounds[2]]
    });
    var texts = [];
    var i;
    for (i = 0; i < paragraphs.length; i++) {
        texts.push(paragraphs[i][0]);
    }
    tf.contents = texts.join("\r");
    for (i = 0; i < paragraphs.length; i++) {
        if (paragraphs[i][1]) {
            tf.paragraphs[i].applyParagraphStyle(paragraphs[i][1], true);
        }
    }
    return tf;
}

// Straight line from [x1, y1] to [x2, y2] in mm.
function line(page, from, to, stroke, weightPt) {
    var l = page.graphicLines.add();
    l.paths[0].pathPoints[0].anchor = [from[0], from[1]];
    l.paths[0].pathPoints[1].anchor = [to[0], to[1]];
    if (stroke) {
        l.strokeColor = stroke;
    }
    l.strokeWeight = weightPt || 0.75;
    return l;
}

// Ellipse. bounds = [x, y, width, height] in mm.
function ellipse(page, bounds, fill) {
    var o = page.ovals.add({
        geometricBounds: [bounds[1], bounds[0], bounds[1] + bounds[3], bounds[0] + bounds[2]]
    });
    if (fill) {
        o.fillColor = fill;
    }
    o.strokeWeight = 0;
    return o;
}

// ---------------------------------------------------------------------------
// The resource
// ---------------------------------------------------------------------------

function build(doc, page) {
    var c = CONFIG;
    var x = c.origin[0];
    var y = c.origin[1];
    var inner = c.width - 2 * c.padding;
    var items = [];

    var textFrame = textBox(page, [x + c.padding + 2, y + c.padding, inner - 2, 60], [
        [c.figure, findStyle(doc, c.figureStyle, "paragraph")],
        [c.label, findStyle(doc, c.labelStyle, "paragraph")],
        [c.source, findStyle(doc, c.sourceStyle, "paragraph")]
    ]);
    // Shrink the frame to its text, then size the background to match.
    textFrame.fit(FitOptions.FRAME_TO_CONTENT);
    var tb = textFrame.geometricBounds; // [top, left, bottom, right]
    var height = (tb[2] - y) + c.padding;

    var background = box(page, [x, y, c.width, height], swatch(doc, c.backgroundSwatch));
    var accent = box(page, [x, y, 1.5, height], swatch(doc, c.accentSwatch));
    background.sendToBack();

    items.push(background, accent, textFrame);
    var group = page.groups.add(items);
    group.name = c.name;
    return group;
}

function run() {
    if (app.documents.length === 0) {
        alert("Open the document first.");
        return;
    }
    var doc = app.activeDocument;
    var page = (app.layoutWindows.length > 0) ? app.activeWindow.activePage : doc.pages[0];

    var missing = [];
    var styles = [CONFIG.figureStyle, CONFIG.labelStyle, CONFIG.sourceStyle];
    var swatches = [CONFIG.backgroundSwatch, CONFIG.accentSwatch];
    var i;
    for (i = 0; i < styles.length; i++) {
        if (!findStyle(doc, styles[i], "paragraph")) {
            missing.push("Paragraph style: " + styles[i]);
        }
    }
    for (i = 0; i < swatches.length; i++) {
        if (!swatch(doc, swatches[i])) {
            missing.push("Swatch: " + swatches[i]);
        }
    }
    if (missing.length > 0) {
        alert("Missing in this document (edit CONFIG or the template):\n\n" +
              missing.join("\n"));
        return;
    }

    var view = doc.viewPreferences;
    var oldH = view.horizontalMeasurementUnits;
    var oldV = view.verticalMeasurementUnits;
    var oldOrigin = view.rulerOrigin;
    view.horizontalMeasurementUnits = MeasurementUnits.MILLIMETERS;
    view.verticalMeasurementUnits = MeasurementUnits.MILLIMETERS;
    view.rulerOrigin = RulerOrigin.PAGE_ORIGIN;
    try {
        build(doc, page);
    } finally {
        view.horizontalMeasurementUnits = oldH;
        view.verticalMeasurementUnits = oldV;
        view.rulerOrigin = oldOrigin;
    }
}

app.doScript(run, ScriptLanguage.JAVASCRIPT, undefined, UndoModes.ENTIRE_SCRIPT,
             "Add visual resource");
