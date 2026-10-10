// ---------------------------------------------------------------------------
// InDesign driver: finds references in the active document, adds index
// topics and page references (markers), marks references whose book came
// from context, and writes a proofreading list (HTML and/or CSV).
// ---------------------------------------------------------------------------
var PREF_FILE = File(Folder.userData + "/ScriptureIndexBuilder-InDesign.txt");
var COND_NAME = "Scripture Index: check book";
var NOTE_STYLE = "Scripture Index: note page";

function loadPrefs() {
    var p = {notes: "italic", mark: "1", layout: DATA.layout || "single", proof: "html", clear: "1"};
    try {
        if (PREF_FILE.exists && PREF_FILE.open("r")) {
            while (!PREF_FILE.eof) {
                var line = PREF_FILE.readln(), i = line.indexOf("=");
                if (i > 0) p[line.substring(0, i)] = line.substring(i + 1);
            }
            PREF_FILE.close();
        }
    } catch (e) {}
    return p;
}
function savePrefs(p) {
    try {
        PREF_FILE.encoding = "UTF-8";
        if (PREF_FILE.open("w")) {
            for (var k in p) if (p.hasOwnProperty(k)) PREF_FILE.writeln(k + "=" + p[k]);
            PREF_FILE.close();
        }
    } catch (e) {}
}

function showDialog(prefs) {
    var w = new Window("dialog", "Scripture Index Builder " + DATA.version);
    w.alignChildren = "fill";
    w.add("statictext", undefined, "Language: " + DATA.langName + "   ·   Apocrypha: " + (DATA.apocrypha ? "on" : "off") +
        "   ·   Custom books: " + DATA.customCount);
    var g1 = w.add("panel", undefined, "References in footnotes");
    var notes = g1.add("dropdownlist", undefined, ["Don't index them", "Index them, page numbers in italics",
        "Index them, page numbers in bold", "Index them, no special formatting"]);
    var NOTE_IDX = {skip: 0, italic: 1, bold: 2, plain: 3};
    notes.selection = NOTE_IDX.hasOwnProperty(prefs.notes) ? NOTE_IDX[prefs.notes] : 1;
    var g2 = w.add("panel", undefined, "Index layout");
    var layout = g2.add("dropdownlist", undefined, ["One index", "Old and New Testament (Apocrypha with OT)",
        "By section (OT, Apocrypha, NT, Other)"]);
    var LAY_IDX = {single: 0, testaments: 1, sections: 2};
    layout.selection = LAY_IDX.hasOwnProperty(prefs.layout) ? LAY_IDX[prefs.layout] : 0;
    var mark = w.add("checkbox", undefined, "Highlight references whose book came from context (non-printing condition)");
    mark.value = prefs.mark === "1";
    var clear = w.add("checkbox", undefined, "First remove Scripture topics added by an earlier run");
    clear.value = prefs.clear === "1";
    var g3 = w.add("panel", undefined, "Proofreading list");
    var proof = g3.add("dropdownlist", undefined, ["HTML (opens in a browser)", "CSV (opens in Excel)", "Both"]);
    var PRF_IDX = {html: 0, csv: 1, both: 2};
    proof.selection = PRF_IDX.hasOwnProperty(prefs.proof) ? PRF_IDX[prefs.proof] : 0;
    var b = w.add("group");
    b.alignment = "right";
    b.add("button", undefined, "Cancel", {name: "cancel"});
    b.add("button", undefined, "Index", {name: "ok"});
    if (w.show() !== 1) return null;
    prefs.notes = ["skip", "italic", "bold", "plain"][notes.selection.index];
    prefs.layout = ["single", "testaments", "sections"][layout.selection.index];
    prefs.mark = mark.value ? "1" : "0";
    prefs.clear = clear.value ? "1" : "0";
    prefs.proof = ["html", "csv", "both"][proof.selection.index];
    savePrefs(prefs);
    return prefs;
}

// --- text helpers ------------------------------------------------------------
function italicFlags(para) {
    var flags = [], ranges, i, j;
    try { ranges = para.textStyleRanges.everyItem().getElements(); } catch (e) { return flags; }
    for (i = 0; i < ranges.length; i++) {
        var fs = "";
        try { fs = String(ranges[i].fontStyle || ""); } catch (e2) {}
        var it = /italic|oblique|kursiv/i.test(fs);
        var len = ranges[i].characters.length;
        for (j = 0; j < len; j++) flags.push(it);
    }
    return flags;
}
function snippet(text, s, e) {
    var a = Math.max(0, s - 70), b = Math.min(text.length, e + 50);
    return {pre: (a > 0 ? "…" : "") + text.substring(a, s), ref: text.substring(s, e),
        post: text.substring(e, b) + (b < text.length ? "…" : "")};
}
function sectionGroup(bookId, layout) {
    var sec = bookOf(bookId)[1];
    if (layout === "single") return null;
    if (layout === "testaments") return sec === "NT" ? "NT" : (sec === "OTHER" ? "OTHER" : "OT");
    return sec;
}

// --- collect segments: [{para, text, italic, note: footnoteIndex|null, story}] --
function collectStories(doc) {
    var stories = doc.stories.everyItem().getElements(), out = [], i;
    for (i = 0; i < stories.length; i++) {
        var st = stories[i], key = 1e9;
        try {
            var tc = st.textContainers;
            if (tc.length && tc[0].parentPage) key = tc[0].parentPage.documentOffset * 10000 + tc[0].geometricBounds[0];
        } catch (e) {}
        out.push({story: st, key: key});
    }
    out.sort(function (a, b) { return a.key - b.key; });
    return out;
}

function main() {
    if (!app.documents.length) { alert("Open the document to index first."); return; }
    var doc = app.activeDocument;
    var prefs = showDialog(loadPrefs());
    if (!prefs) return;
    var scanner = new Scanner(15);
    var occs = [], segNo = 0, si, pi, k;

    var stories = collectStories(doc);
    for (si = 0; si < stories.length; si++) {
        var story = stories[si].story;
        var paras = story.paragraphs.everyItem().getElements();
        var fns = [];
        try { fns = story.footnotes.everyItem().getElements(); } catch (e) {}
        var fnPos = [];
        for (k = 0; k < fns.length; k++) {
            try { fnPos.push({idx: fns[k].storyOffset.index, fn: fns[k], n: k + 1}); } catch (e) {}
        }
        for (pi = 0; pi < paras.length; pi++) {
            var para = paras[pi], text;
            try { text = String(para.contents); } catch (e) { continue; }
            var pstart = para.index, pend = pstart + text.length;
            var isHead = false;
            try { isHead = /heading 1|title|chapter/i.test(para.appliedParagraphStyle.name); } catch (e) {}
            if (isHead) scanner.heading();
            var anchors = [], here = [];
            for (k = 0; k < fnPos.length; k++) {
                if (fnPos[k].idx >= pstart && fnPos[k].idx < pend) { anchors.push(fnPos[k].idx - pstart); here.push(fnPos[k]); }
            }
            var res = scanner.scan(text, italicFlags(para), segNo, anchors);
            var h;
            for (h = 0; h < res.hits.length; h++) occs.push({para: para, text: text, hit: res.hits[h], note: null, seq: occs.length});
            for (k = 0; k < here.length; k++) {
                var ctx = res.snaps[here[k].idx - pstart] || copyCtx(scanner.ctx);
                var fparas = here[k].fn.texts[0].paragraphs.everyItem().getElements(), fp;
                for (fp = 0; fp < fparas.length; fp++) {
                    var ftext = String(fparas[fp].contents);
                    var fres = scanner.scan(ftext, italicFlags(fparas[fp]), segNo, [], ctx);
                    for (h = 0; h < fres.hits.length; h++)
                        occs.push({para: fparas[fp], text: ftext, hit: fres.hits[h], note: here[k].n, seq: occs.length});
                }
            }
            segNo++;
        }
        // table cells
        try {
            var cells = story.tables.everyItem().cells.everyItem().getElements(), c;
            for (c = 0; c < cells.length; c++) {
                var cps = cells[c].paragraphs.everyItem().getElements(), cp;
                for (cp = 0; cp < cps.length; cp++) {
                    var ctext = String(cps[cp].contents);
                    var cres = scanner.scan(ctext, italicFlags(cps[cp]), segNo, []);
                    for (h = 0; h < cres.hits.length; h++) occs.push({para: cps[cp], text: ctext, hit: cres.hits[h], note: null, seq: occs.length});
                    segNo++;
                }
            }
        } catch (e) {}
    }

    // --- index topics --------------------------------------------------------
    var index = doc.indexes.length ? doc.indexes[0] : doc.indexes.add();
    var topicCache = {};
    if (prefs.clear === "1") {
        var tops = index.topics.everyItem().getElements(), t;
        var known = {};
        for (var bid in DATA.books) if (DATA.books.hasOwnProperty(bid)) known[DATA.books[bid][0]] = 1;
        for (var sk in DATA.sectionTitles) if (DATA.sectionTitles.hasOwnProperty(sk)) known[DATA.sectionTitles[sk]] = 1;
        for (t = 0; t < tops.length; t++) if (known[tops[t].name]) { try { tops[t].remove(); } catch (e) {} }
    }
    function topic(parent, name, sortKey) {
        var key = (parent === index ? "" : parent.name + "\u0001") + name;
        if (topicCache[key]) return topicCache[key];
        var tp = parent.topics.itemByName(name);
        if (!tp.isValid) tp = parent.topics.add(name, sortKey);
        else { try { tp.sortOrder = sortKey; } catch (e) {} }
        topicCache[key] = tp;
        return tp;
    }
    var noteStyle = null;
    if (prefs.notes === "italic" || prefs.notes === "bold") {
        noteStyle = doc.characterStyles.itemByName(NOTE_STYLE);
        if (!noteStyle.isValid) noteStyle = doc.characterStyles.add({name: NOTE_STYLE});
        try { noteStyle.fontStyle = prefs.notes === "bold" ? "Bold" : "Italic"; } catch (e) {}
    }
    var cond = null;
    if (prefs.mark === "1") {
        cond = doc.conditions.itemByName(COND_NAME);
        if (!cond.isValid) {
            cond = doc.conditions.add({name: COND_NAME});
            try { cond.indicatorMethod = ConditionIndicatorMethod.USE_HIGHLIGHT; cond.indicatorColor = UIColors.YELLOW; } catch (e) {}
        }
    }

    // place markers paragraph by paragraph, last hit first
    var byPara = {}, order = [], o;
    for (k = 0; k < occs.length; k++) {
        o = occs[k];
        o.indexed = !!INDEXED[o.hit.status] && o.hit.ref && !(o.note && prefs.notes === "skip");
        var pid = o.para.toSpecifier();
        if (!byPara[pid]) { byPara[pid] = []; order.push(pid); }
        byPara[pid].push(o);
    }
    var placed = 0, failed = 0;
    for (k = 0; k < order.length; k++) {
        var list = byPara[order[k]];
        list.sort(function (a, b) { return b.hit.end - a.hit.end; });
        for (var q = 0; q < list.length; q++) {
            o = list[q];
            if (!o.indexed) continue;
            var r = o.hit.ref;
            try {
                if (cond && (o.hit.status === "inferred" || o.hit.status === "inferred-weak") && o.hit.end > o.hit.start) {
                    o.para.characters.itemByRange(o.hit.start, o.hit.end - 1).applyConditions([cond], false);
                }
                var grp = sectionGroup(r.book, prefs.layout), parent = index;
                if (grp) parent = topic(index, DATA.sectionTitles[grp] || grp, String(sectionRank(grp)));
                var bt = topic(parent, bookName(r.book), refBookKey(r));
                var lt = topic(bt, refLabel(r), refSortKey(r));
                var ip = o.para.insertionPoints[o.hit.end];
                var pr = lt.pageReferences.add(ip, PageReferenceType.CURRENT_PAGE);
                if (o.note && noteStyle) { try { pr.pageNumberStyleOverride = noteStyle; } catch (e) {} }
                o.marker = ip;
                placed++;
            } catch (err) {
                o.error = String(err);
                failed++;
            }
        }
    }

    // pages
    for (k = 0; k < occs.length; k++) {
        o = occs[k];
        o.page = "";
        o.pageKey = 1e9 + o.seq;
        try {
            var ip2 = o.para.insertionPoints[Math.min(o.hit.end, o.para.insertionPoints.length - 1)];
            var tf = ip2.parentTextFrames;
            if (tf.length && tf[0].parentPage) { o.page = tf[0].parentPage.name; o.pageKey = tf[0].parentPage.documentOffset * 100000 + o.seq; }
            else o.page = "overset";
        } catch (e) {}
    }
    writeProof(doc, occs, prefs);
    alert("Scripture index markers added: " + placed + (failed ? "\n" + failed + " could not be placed (see the proofreading list)." : "") +
        "\n\nGenerate the index with Window > Type & Tables > Index > Generate Index." +
        (cond ? "\nReferences whose book came from context are highlighted with the condition “" + COND_NAME +
            "” (non-printing). Delete the condition when you're done checking." : ""));
}

// --- proofreading list ----------------------------------------------------------
function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
function csvq(s) { return "\"" + String(s).replace(/"/g, "\"\"") + "\""; }

function writeProof(doc, occs, prefs) {
    var folder, name = doc.name.replace(/\.indd$/i, "");
    try { folder = doc.filePath; } catch (e) { folder = Folder.desktop; }
    var idx = [], rest = [], k, o;
    for (k = 0; k < occs.length; k++) (occs[k].indexed && !occs[k].error ? idx : rest).push(occs[k]);
    idx.sort(function (a, b) { return a.pageKey - b.pageKey; });
    function how(o) {
        var s = STATUS_LABELS[o.hit.status] || o.hit.status;
        if (o.error) s = "Could not be indexed: " + o.error;
        else if (!o.indexed && INDEXED[o.hit.status] && o.note) s = "In a footnote (footnotes not indexed)";
        if (o.hit.reason) s += " (" + o.hit.reason + ")";
        return s;
    }
    function where(o) { return o.note ? "Footnote " + o.note : "Body"; }
    function disp(o) { return o.hit.ref ? refDisplay(o.hit.ref) : o.hit.raw; }
    if (prefs.proof === "html" || prefs.proof === "both") {
        var f = File(folder + "/" + name + " - Scripture Index Proof List.html");
        f.encoding = "UTF-8";
        f.open("w");
        f.writeln("<!doctype html><html><head><meta charset='utf-8'><title>" + esc(name) + " — Scripture Index Proof List</title>");
        f.writeln("<style>body{font:14px/1.4 Calibri,Segoe UI,sans-serif;margin:24px;color:#222}h1{font-size:20px}h2{font-size:16px;margin-top:28px}" +
            "table{border-collapse:collapse;width:100%}th,td{border:1px solid #bbb;padding:4px 6px;vertical-align:top}th{background:#e5e5e5;text-align:left}" +
            "td.ctx{font-size:12px;color:#444}td.ctx b{color:#000}.chk{background:#fff4c2}@media print{th{background:#ddd}}</style></head><body>");
        f.writeln("<h1>Scripture Index — Proofreading List</h1><p><b>Document:</b> " + esc(doc.name) +
            "<br><b>Built:</b> " + esc(new Date().toString()) + " with Scripture Index Builder " + DATA.version +
            " (" + esc(DATA.langName) + ")<br><b>Page numbers:</b> from InDesign's current layout.</p>");
        f.writeln("<p>Work through the pages in order, find each reference, confirm book, chapter and verse, and tick the box. " +
            "Rows highlighted in yellow took their book from context.</p>");
        f.writeln("<h2>Indexed references (" + idx.length + ")</h2><table><tr><th>✓</th><th>Page</th><th>Index entry</th><th>Where</th><th>How the book was found</th><th>Context</th></tr>");
        for (k = 0; k < idx.length; k++) {
            o = idx[k];
            var sn = snippet(o.text, o.hit.start, o.hit.end);
            var chk = (o.hit.status === "inferred" || o.hit.status === "inferred-weak") ? " class='chk'" : "";
            f.writeln("<tr><td>☐</td><td>" + esc(o.page) + "</td><td>" + esc(disp(o)) + "</td><td>" + where(o) +
                "</td><td" + chk + ">" + esc(how(o)) + "</td><td class='ctx'>" + esc(sn.pre) + "<b>" + esc(sn.ref) + "</b>" + esc(sn.post) + "</td></tr>");
        }
        f.writeln("</table><h2>Not indexed — review (" + rest.length + ")</h2><table><tr><th>Page</th><th>Found</th><th>Where</th><th>Reason</th><th>Context</th></tr>");
        for (k = 0; k < rest.length; k++) {
            o = rest[k];
            var sn2 = snippet(o.text, o.hit.start, o.hit.end);
            f.writeln("<tr><td>" + esc(o.page) + "</td><td>" + esc(disp(o)) + "</td><td>" + where(o) + "</td><td>" + esc(how(o)) +
                "</td><td class='ctx'>" + esc(sn2.pre) + "<b>" + esc(sn2.ref) + "</b>" + esc(sn2.post) + "</td></tr>");
        }
        f.writeln("</table></body></html>");
        f.close();
    }
    if (prefs.proof === "csv" || prefs.proof === "both") {
        var c = File(folder + "/" + name + " - Scripture Index Proof List.csv");
        c.encoding = "UTF-8";
        c.open("w");
        c.write("﻿");
        c.writeln("indexed,page,book,entry,where,status,context");
        var all = idx.concat(rest);
        for (k = 0; k < all.length; k++) {
            o = all[k];
            var sn3 = snippet(o.text, o.hit.start, o.hit.end);
            c.writeln([o.indexed && !o.error ? "yes" : "no", csvq(o.page), csvq(o.hit.ref ? bookName(o.hit.ref.book) : ""),
                csvq(o.hit.ref ? refLabel(o.hit.ref) : o.hit.raw), csvq(where(o)), csvq(how(o)),
                csvq(sn3.pre + "[" + sn3.ref + "]" + sn3.post)].join(","));
        }
        c.close();
    }
}

app.doScript(main, ScriptLanguage.JAVASCRIPT, undefined, UndoModes.ENTIRE_SCRIPT, "Scripture Index");
