// ---------------------------------------------------------------------------
// InDesign driver: finds references in the active document, adds index
// topics and page references (markers), marks references whose book came
// from context, and writes a proofreading list (HTML and/or CSV).
// ---------------------------------------------------------------------------
var PREF_FILE = File(Folder.userData + "/Indicat-InDesign.txt");
var OLD_PREF_FILES = [File(Folder.userData + "/ScriptureIndexBuilder-InDesign.txt")];   // earlier versions
var CREDIT = "Indicat, created by Beaux Hargrove";
var TERM_LABELS = {word: "Word", term: "Term set match", quotation: "Quotation (not indexed)"};
var QUOTE_PT = 28.35;            // an indent this large (0.4 in / 1 cm) reads as a block quotation
var COND_NAME = "Scripture Index: check book";
var NOTE_STYLE = "Scripture Index: note page";

function loadPrefs() {
    var p = {notes: "italic", mark: "1", layout: DATA.layout || "single", proof: "html", clear: "1"};
    // the preferences of an earlier version are used until this version saves its own
    var files = [PREF_FILE].concat(OLD_PREF_FILES), f, k;
    for (k = 0; k < files.length; k++) {
        f = files[k];
        try {
            if (f.exists && f.open("r")) {
                while (!f.eof) {
                    var line = f.readln(), i = line.indexOf("=");
                    if (i > 0) p[line.substring(0, i)] = line.substring(i + 1);
                }
                f.close();
                break;
            }
        } catch (e) {}
    }
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
    var w = new Window("dialog", "Indicat " + DATA.version + " — Scripture Index Builder");
    w.alignChildren = "fill";
    w.add("statictext", undefined, "Language: " + DATA.langName + "   ·   Apocrypha: " + (DATA.apocrypha ? "on" : "off") +
        "   ·   Custom books: " + DATA.customCount);
    var gi = w.add("panel", undefined, "Indexes to build");
    var idxBoxes = [], k;
    var sBox = gi.add("checkbox", undefined, "Scripture");
    sBox.value = DATA.scripture !== false;
    for (k = 0; k < TT.defs.length; k++) {
        var cb = gi.add("checkbox", undefined, TT.defs[k].title);
        cb.value = true;
        idxBoxes.push(cb);
    }
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
    w.add("statictext", undefined, CREDIT + " · GNU GPL v3");
    if (w.show() !== 1) return null;
    prefs.scripture = sBox.value;
    prefs.defs = [];
    for (k = 0; k < TT.defs.length; k++) if (idxBoxes[k].value) prefs.defs.push(TT.defs[k]);
    prefs.notes = ["skip", "italic", "bold", "plain"][notes.selection.index];
    prefs.layout = ["single", "testaments", "sections"][layout.selection.index];
    prefs.mark = mark.value ? "1" : "0";
    prefs.clear = clear.value ? "1" : "0";
    prefs.proof = ["html", "csv", "both"][proof.selection.index];
    var keep = {notes: prefs.notes, layout: prefs.layout, mark: prefs.mark, clear: prefs.clear, proof: prefs.proof};
    savePrefs(keep);
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
function langFlags(para) {
    var flags = [], ranges, i, j, name, code, key;
    try { ranges = para.textStyleRanges.everyItem().getElements(); } catch (e) { return null; }
    for (i = 0; i < ranges.length; i++) {
        code = null;
        try { name = String(ranges[i].appliedLanguage.name); } catch (e2) { name = ""; }
        for (key in TT.langNames) if (tHas(TT.langNames, key) && name.indexOf(key) === 0) { code = TT.langNames[key]; break; }
        var len = ranges[i].characters.length;
        for (j = 0; j < len; j++) flags.push(code);
    }
    return flags;
}
function paraMeta(para, inTable, isHead, needLangs) {
    var m = {quote: null, table: !!inTable, langs: null}, sname = "";
    try { sname = String(para.appliedParagraphStyle.name); } catch (e) {}
    if (!isHead) {
        if (T_QUOTE_RE.test(sname)) m.quote = "style";
        else if (!/^(list|bibliograph|toc|index|caption|footnote|endnote)/i.test(sname)) {
            try {
                var li = Number(para.leftIndent), fi = Number(para.firstLineIndent), listed = false;
                try { listed = para.bulletsAndNumberingListType !== ListType.NO_LIST; } catch (e3) {}
                if (!listed && li >= QUOTE_PT && li + Math.min(0, fi) >= QUOTE_PT) m.quote = "indent";
            } catch (e2) {}
        }
    }
    if (needLangs) m.langs = langFlags(para);
    return m;
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
    var units = null;
    try {        // read indents in points
        units = doc.viewPreferences.horizontalMeasurementUnits;
        doc.viewPreferences.horizontalMeasurementUnits = MeasurementUnits.POINTS;
    } catch (e) { units = null; }
    try { run(doc, prefs); }
    finally {
        if (units !== null) { try { doc.viewPreferences.horizontalMeasurementUnits = units; } catch (e) {} }
    }
}

function run(doc, prefs) {
    var scanner = new Scanner(15);
    var defs = prefs.defs, defById = {}, needLangs = false, k;
    for (k = 0; k < defs.length; k++) { defById[defs[k].id] = defs[k]; defs[k].order = k; if (defs[k].kind === "lang") needLangs = true; }
    var engine = defs.length ? new TermEngine(defs) : null;
    var doScripture = prefs.scripture;
    var occs = [], segNo = 0, si, pi;

    function addTerms(para, text, note, meta) {
        if (!engine) return;
        var ths = engine.scan(text, meta), t;
        for (t = 0; t < ths.length; t++) {
            var th = ths[t];
            occs.push({para: para, text: text, th: th, def: defById[th.index], note: note, seq: occs.length,
                hit: {start: th.start, end: th.end, status: th.status, reason: th.reason, ref: null,
                      raw: text.substring(th.start, th.end)}});
        }
    }
    // Scripture hits and word/term hits of one paragraph, in text order
    function addAll(para, text, hits, note, meta) {
        var before = occs.length, h;
        if (doScripture) for (h = 0; h < hits.length; h++) occs.push({para: para, text: text, hit: hits[h], note: note, seq: occs.length});
        addTerms(para, text, note, meta);
        var mine = occs.splice(before, occs.length - before);
        for (h = 0; h < mine.length; h++) mine[h]._n = h;
        mine.sort(function (x, y) { return (x.hit.start - y.hit.start) || (x.hit.end - y.hit.end) || (x._n - y._n); });
        for (h = 0; h < mine.length; h++) { mine[h].seq = occs.length; occs.push(mine[h]); }
    }

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
            addAll(para, text, res.hits, null, paraMeta(para, false, isHead, needLangs));
            for (k = 0; k < here.length; k++) {
                var ctx = res.snaps[here[k].idx - pstart] || copyCtx(scanner.ctx);
                var fparas = here[k].fn.texts[0].paragraphs.everyItem().getElements(), fp;
                for (fp = 0; fp < fparas.length; fp++) {
                    var ftext = String(fparas[fp].contents);
                    var fres = scanner.scan(ftext, italicFlags(fparas[fp]), segNo, [], ctx);
                    addAll(fparas[fp], ftext, fres.hits, here[k].n, paraMeta(fparas[fp], false, false, needLangs));
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
                    addAll(cps[cp], ctext, cres.hits, null, paraMeta(cps[cp], true, false, needLangs));
                    segNo++;
                }
            }
        } catch (e) {}
    }
    // one heading per group of word forms
    var wrefs = [], w;
    for (k = 0; k < occs.length; k++) {
        var o0 = occs[k];
        if (!o0.th || o0.def.kind === "terms") continue;
        if (o0.th.ref) wrefs.push(o0.th.ref);
        for (w = 0; w < o0.th.words.length; w++) wrefs.push(o0.th.words[w][2]);
    }
    chooseHeadings(wrefs);

    // --- index topics --------------------------------------------------------
    var index = doc.indexes.length ? doc.indexes[0] : doc.indexes.add();
    var topicCache = {};
    if (prefs.clear === "1") {
        var tops = index.topics.everyItem().getElements(), t;
        var known = {};
        for (var bid in DATA.books) if (DATA.books.hasOwnProperty(bid)) known[DATA.books[bid][0]] = 1;
        for (var sk in DATA.sectionTitles) if (DATA.sectionTitles.hasOwnProperty(sk)) known[DATA.sectionTitles[sk]] = 1;
        for (k = 0; k < TT.defs.length; k++) known[TT.defs[k].title] = 1;
        for (t = 0; t < tops.length; t++) if (known[tops[t].name]) { try { tops[t].remove(); } catch (e) {} }
    }
    // topics are handled through wrappers {t: Topic, k: full path}, so that the same
    // heading under two different parents never gets mixed up
    var ROOT = {t: index, k: ""};
    function topic(parent, name, sortKey) {
        var key = parent.k + "\u0001" + name;
        if (tHas(topicCache, key)) return topicCache[key];
        var tp = parent.t.topics.itemByName(name);
        if (!tp.isValid) tp = parent.t.topics.add(name, sortKey);
        else { try { tp.sortOrder = sortKey; } catch (e) {} }
        topicCache[key] = {t: tp, k: key};
        return topicCache[key];
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

    function setTopic(d) { return topic(ROOT, d.title, "99" + (d.order < 10 ? "0" : "") + d.order); }
    function termTopic(d, ref) {
        var t = topic(setTopic(d), ref.heading, ref.sort || sortCode(ref.heading));
        if (ref.sub) t = topic(t, ref.sub, ref.subSort || sortCode(ref.sub));
        return t;
    }
    // place markers paragraph by paragraph, last hit first
    var byPara = {}, order = [], o, counts = {};
    for (k = 0; k < occs.length; k++) {
        o = occs[k];
        if (o.th) o.indexed = (o.th.status === "word" || o.th.status === "term") && !!o.th.ref && !(o.note && prefs.notes === "skip");
        else o.indexed = !!INDEXED[o.hit.status] && o.hit.ref && !(o.note && prefs.notes === "skip");
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
            var r = o.hit.ref, lt;
            try {
                if (o.th) {
                    lt = termTopic(o.def, o.th.ref);
                } else {
                    if (cond && (o.hit.status === "inferred" || o.hit.status === "inferred-weak") && o.hit.end > o.hit.start) {
                        o.para.characters.itemByRange(o.hit.start, o.hit.end - 1).applyConditions([cond], false);
                    }
                    var grp = sectionGroup(r.book, prefs.layout), parent = ROOT;
                    if (grp) parent = topic(ROOT, DATA.sectionTitles[grp] || grp, String(sectionRank(grp)));
                    var bt = topic(parent, bookName(r.book), refBookKey(r));
                    lt = topic(bt, refLabel(r), refSortKey(r));
                }
                var ip = o.para.insertionPoints[o.hit.end];
                var pr = lt.t.pageReferences.add(ip, PageReferenceType.CURRENT_PAGE);
                if (o.note && noteStyle) { try { pr.pageNumberStyleOverride = noteStyle; } catch (e) {} }
                o.marker = ip;
                placed++;
                var cname = o.th ? o.def.short : "Scripture";
                counts[cname] = (counts[cname] || 0) + 1;
            } catch (err) {
                o.error = String(err);
                failed++;
            }
        }
    }

    // See / See also cross-references of term sets
    var xr = 0;
    for (k = 0; k < defs.length; k++) {
        if (defs[k].kind !== "terms") continue;
        var cs = compileSet(defs[k]), x;
        for (x = 0; x < cs.xrefs.length; x++) {
            try {
                var from = termTopic(defs[k], cs.xrefs[x][0]);
                var to = topic(setTopic(defs[k]), cs.xrefs[x][2], sortCode(cs.xrefs[x][2]));
                from.t.crossReferences.add(to.t, cs.xrefs[x][1] === "see" ? CrossReferenceType.SEE : CrossReferenceType.SEE_ALSO);
                xr++;
            } catch (e) {}
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
    var parts = [];
    for (var cn in counts) if (counts.hasOwnProperty(cn)) parts.push(cn + " " + counts[cn]);
    alert((defs.length ? "Index markers added: " : "Scripture index markers added: ") + placed +
        (defs.length && parts.length ? " (" + parts.join(", ") + ")" : "") +
        (xr ? "\nCross-references added: " + xr : "") +
        (failed ? "\n" + failed + " could not be placed (see the proofreading list)." : "") +
        "\n\nGenerate the index with Window > Type & Tables > Index > Generate Index." +
        (defs.length ? "\nEach word or term index is a top-level entry of the generated index (" +
            setTitles(defs) + "); move each into its own section and style it as needed." : "") +
        (cond ? "\nReferences whose book came from context are highlighted with the condition “" + COND_NAME +
            "” (non-printing). Delete the condition when you're done checking." : ""));
}

// --- proofreading list ----------------------------------------------------------
function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
function csvq(s) { return "\"" + String(s).replace(/"/g, "\"\"") + "\""; }

function setTitles(defs) {
    var t = [], k;
    for (k = 0; k < defs.length; k++) t.push(defs[k].title);
    return t.join("; ");
}
function writeProof(doc, occs, prefs) {
    var folder, name = doc.name.replace(/\.indd$/i, ""), multi = prefs.defs.length > 0;
    var title = multi ? "Index" : "Scripture Index";
    try { folder = doc.filePath; } catch (e) { folder = Folder.desktop; }
    var idx = [], rest = [], k, o;
    for (k = 0; k < occs.length; k++) (occs[k].indexed && !occs[k].error ? idx : rest).push(occs[k]);
    idx.sort(function (a, b) { return a.pageKey - b.pageKey; });
    function how(o) {
        var s = STATUS_LABELS[o.hit.status] || TERM_LABELS[o.hit.status] || o.hit.status;
        if (o.error) s = "Could not be indexed: " + o.error;
        else if (!o.indexed && INDEXED[o.hit.status] && o.note) s = "In a footnote (footnotes not indexed)";
        if (o.hit.reason) s += " (" + o.hit.reason + ")";
        return s;
    }
    function where(o) { return o.note ? "Footnote " + o.note : "Body"; }
    function disp(o) {
        if (o.th) { var t = o.th.ref ? o.th.ref.display() : o.hit.raw; return t.length > 60 ? t.substring(0, 57) + "…" : t; }
        return o.hit.ref ? refDisplay(o.hit.ref) : o.hit.raw;
    }
    function iname(o) { return o.th ? o.def.short : "Scripture"; }
    function icell(o) { return multi ? "<td>" + esc(iname(o)) + "</td>" : ""; }
    var ihead = multi ? "<th>Index</th>" : "";
    if (prefs.proof === "html" || prefs.proof === "both") {
        var f = File(folder + "/" + name + " - Index Proof List.html");
        f.encoding = "UTF-8";
        f.open("w");
        f.writeln("<!doctype html><html><head><meta charset='utf-8'><title>" + esc(name) + " — " + title + " Proof List</title>");
        f.writeln("<style>body{font:14px/1.4 Calibri,Segoe UI,sans-serif;margin:24px;color:#222}h1{font-size:20px}h2{font-size:16px;margin-top:28px}" +
            "table{border-collapse:collapse;width:100%}th,td{border:1px solid #bbb;padding:4px 6px;vertical-align:top}th{background:#e5e5e5;text-align:left}" +
            "td.ctx{font-size:12px;color:#444}td.ctx b{color:#000}.chk{background:#fff4c2}@media print{th{background:#ddd}}</style></head><body>");
        f.writeln("<h1>" + title + " — Proofreading List</h1><p><b>Document:</b> " + esc(doc.name) +
            "<br><b>Built:</b> " + esc(new Date().toString()) + " with Indicat " + DATA.version +
            " (" + esc(DATA.langName) + ")<br><b>Page numbers:</b> from InDesign's current layout.</p>");
        f.writeln("<p>Work through the pages in order, find each reference, confirm book, chapter and verse, and tick the box. " +
            "Rows highlighted in yellow took their book from context.</p>");
        f.writeln("<h2>Indexed " + (multi ? "entries" : "references") + " (" + idx.length + ")</h2><table><tr><th>✓</th><th>Page</th>" + ihead +
            "<th>Index entry</th><th>Where</th><th>" + (multi ? "How found" : "How the book was found") + "</th><th>Context</th></tr>");
        for (k = 0; k < idx.length; k++) {
            o = idx[k];
            var sn = snippet(o.text, o.hit.start, o.hit.end);
            var chk = (o.hit.status === "inferred" || o.hit.status === "inferred-weak") ? " class='chk'" : "";
            f.writeln("<tr><td>☐</td><td>" + esc(o.page) + "</td>" + icell(o) + "<td>" + esc(disp(o)) + "</td><td>" + where(o) +
                "</td><td" + chk + ">" + esc(how(o)) + "</td><td class='ctx'>" + esc(sn.pre) + "<b>" + esc(sn.ref) + "</b>" + esc(sn.post) + "</td></tr>");
        }
        f.writeln("</table><h2>Not indexed — review (" + rest.length + ")</h2><table><tr><th>Page</th>" + ihead + "<th>Found</th><th>Where</th><th>Reason</th><th>Context</th></tr>");
        for (k = 0; k < rest.length; k++) {
            o = rest[k];
            var sn2 = snippet(o.text, o.hit.start, o.hit.end);
            f.writeln("<tr><td>" + esc(o.page) + "</td>" + icell(o) + "<td>" + esc(disp(o)) + "</td><td>" + where(o) + "</td><td>" + esc(how(o)) +
                "</td><td class='ctx'>" + esc(sn2.pre) + "<b>" + esc(sn2.ref) + "</b>" + esc(sn2.post) + "</td></tr>");
        }
        f.writeln("</table><p style='color:#777;font-size:12px'>" + esc(CREDIT) + "</p></body></html>");
        f.close();
    }
    if (prefs.proof === "csv" || prefs.proof === "both") {
        var c = File(folder + "/" + name + " - Index Proof List.csv");
        c.encoding = "UTF-8";
        c.open("w");
        c.write("﻿");
        c.writeln("indexed,page,index,book_or_heading,entry_or_subentry,where,status,context");
        var all = idx.concat(rest);
        for (k = 0; k < all.length; k++) {
            o = all[k];
            var sn3 = snippet(o.text, o.hit.start, o.hit.end);
            var bh = o.th ? (o.th.ref ? o.th.ref.heading : "") : (o.hit.ref ? bookName(o.hit.ref.book) : "");
            var es = o.th ? (o.th.ref ? o.th.ref.sub : o.hit.raw) : (o.hit.ref ? refLabel(o.hit.ref) : o.hit.raw);
            c.writeln([o.indexed && !o.error ? "yes" : "no", csvq(o.page), csvq(iname(o)), csvq(bh),
                csvq(es), csvq(where(o)), csvq(how(o)),
                csvq(sn3.pre + "[" + sn3.ref + "]" + sn3.post)].join(","));
        }
        c.close();
    }
}

app.doScript(main, ScriptLanguage.JAVASCRIPT, undefined, UndoModes.ENTIRE_SCRIPT, "Indicat");
