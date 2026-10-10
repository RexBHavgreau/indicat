// ---------------------------------------------------------------------------
// Word and term indexes (port of terms.py for InDesign's ExtendScript, ES3).
// Reads DATA.terms: character tables, word-index settings, index definitions.
// Every rule here mirrors terms.py; tests/js_parity.py checks they agree.
// ---------------------------------------------------------------------------
var TT = DATA.terms;

function tHas(obj, k) { return Object.prototype.hasOwnProperty.call(obj, k); }
function tSet(str) { var o = {}, i; for (i = 0; i < str.length; i++) o[str.charAt(i)] = 1; return o; }
var T_SPACES = tSet(TT.tables.spaces), T_GAP = tSet(TT.tables.gap), T_LISTSEP = tSet(TT.tables.listSeps),
    T_ELISION = tSet(TT.tables.elision), T_HEBPRE = tSet(TT.tables.hebPrefixes);

function tRangeFind(rows, cp) {
    var lo = 0, hi = rows.length - 1, mid;
    while (lo <= hi) {
        mid = (lo + hi) >> 1;
        if (cp < rows[mid][0]) hi = mid - 1;
        else if (cp > rows[mid][1]) lo = mid + 1;
        else return rows[mid];
    }
    return null;
}
function isWordChar(c) { return !!tRangeFind(TT.tables.word, c.charCodeAt(0)); }
function isLetter(c) { return isWordChar(c) && !(c >= "0" && c <= "9"); }
function scriptOf(c) {
    var r = tRangeFind(TT.tables.script, c.charCodeAt(0));
    return r ? [r[2], r[3]] : [null, null];
}

function foldChar(c, cs, marks) {
    var s = (cs && tHas(TT.tables.lower, c)) ? TT.tables.lower[c] : c;
    if (marks) {
        var o = "", i, ch;
        for (i = 0; i < s.length; i++) { ch = s.charAt(i); o += tHas(TT.tables.strip, ch) ? TT.tables.strip[ch] : ch; }
        s = o;
    }
    return s;
}
// {t, starts, ends}: folded text with maps back to the original (see terms.fold)
function tFold(text, cs, marks) {
    var out = [], starts = [], ends = [], prevSpace = false, i, j, c, s;
    for (i = 0; i < text.length; i++) {
        c = text.charAt(i);
        if (T_SPACES[c]) {
            if (prevSpace) { ends[ends.length - 1] = i + 1; continue; }
            out.push(" "); starts.push(i); ends.push(i + 1); prevSpace = true; continue;
        }
        prevSpace = false;
        s = foldChar(c, cs, marks);
        if (!s.length) { if (ends.length) ends[ends.length - 1] = i + 1; continue; }
        for (j = 0; j < s.length; j++) { out.push(s.charAt(j)); starts.push(i); ends.push(i + 1); }
    }
    return {t: out.join(""), starts: starts, ends: ends};
}
function tStrip(s) { return s.replace(/^ +/, "").replace(/ +$/, ""); }
function foldStr(s, cs, marks) {
    if (cs === undefined) cs = true;
    if (marks === undefined) marks = true;
    return tStrip(tFold(s, cs, marks).t);
}

var T_GREEK = "αβγδεζηθικλμνξοπρστυφχψω", T_HEB = "אבגדהוזחטיכלמנסעפצקרשת",
    T_FINALS = {"ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ"};
function pad2(n) { return (n < 10 ? "0" : "") + n; }
function pad3(n) { return (n < 10 ? "00" : (n < 100 ? "0" : "")) + n; }
function sortCode(s) {
    var k = foldStr(s), i, c, any = false, sc;
    for (i = 0; i < k.length; i++) {
        sc = scriptOf(k.charAt(i))[0];
        if (sc === "greek" || sc === "hebrew" || sc === "syriac") { any = true; break; }
    }
    if (!any) return k;
    var out = "";
    for (i = 0; i < k.length; i++) {
        c = k.charAt(i);
        if (tHas(T_FINALS, c)) c = T_FINALS[c];
        if (T_GREEK.indexOf(c) >= 0) out += pad2(T_GREEK.indexOf(c) + 10);
        else if (T_HEB.indexOf(c) >= 0) out += pad2(T_HEB.indexOf(c) + 10);
        else if (scriptOf(c)[0] === "syriac") out += pad3(c.charCodeAt(0) - 0x700 + 100);
        else if (c === " ") out += "00";
        else out += "99";
    }
    return out;
}

// --- quotations ------------------------------------------------------------
var T_QUOTE_RE = /quot|block|extract|cita|zitat|epigra|excerpt|ציטוט/i;
function countWords(text) {
    var n = 0, inw = false, i, w;
    for (i = 0; i < text.length; i++) { w = isWordChar(text.charAt(i)); if (w && !inw) n++; inw = w; }
    return n;
}
function isBlockQuote(text, meta) {
    if (meta.table || !meta.quote) return false;
    if (meta.quote === "style") return true;
    return countWords(text) >= TT.indentProseWords;
}

function scriptTokens(text, script) {
    var toks = [], i = 0, n = text.length, j, so, s2, nxt;
    while (i < n) {
        so = scriptOf(text.charAt(i));
        if (so[0] === script && so[1] === "L") {
            j = i + 1;
            while (j < n) {
                s2 = scriptOf(text.charAt(j));
                if (s2[0] === script || (s2[0] === "*" && s2[1] === "M")) { j++; continue; }
                if (T_ELISION[text.charAt(j)] && script === "greek") {
                    nxt = j + 1 < n ? scriptOf(text.charAt(j + 1))[0] : null;
                    if (nxt !== "greek") j++;
                    break;
                }
                break;
            }
            toks.push([i, j]);
            i = j;
        } else i++;
    }
    return toks;
}
function langTokens(text, langs, lang) {
    if (!langs) return [];
    var toks = [], i = 0, n = text.length, j;
    function ok(k) {
        var t = k < langs.length ? langs[k] : null;
        return !!t && String(t).split("-")[0].toLowerCase() === lang;
    }
    while (i < n) {
        if (isLetter(text.charAt(i)) && ok(i)) {
            j = i + 1;
            while (j < n && isLetter(text.charAt(j)) && ok(j)) j++;
            var before = i > 0 && isWordChar(text.charAt(i - 1)), after = j < n && isWordChar(text.charAt(j));
            if (!before && !after) toks.push([i, j]);
            i = j;
        } else i++;
    }
    return toks;
}
function gapOk(gap) {
    if (gap.length < 1 || gap.length > 6) return false;
    for (var i = 0; i < gap.length; i++) { var c = gap.charAt(i); if (!T_SPACES[c] && !T_GAP[c]) return false; }
    return true;
}
function runsOf(text, toks) {
    var runs = [], k, last;
    for (k = 0; k < toks.length; k++) {
        if (runs.length) { last = runs[runs.length - 1]; if (gapOk(text.substring(last[last.length - 1][1], toks[k][0]))) { last.push(toks[k]); continue; } }
        runs.push([toks[k]]);
    }
    return runs;
}
function classifyRun(text, run, maxRun, itemMax) {
    if (run.length <= maxRun) return "words";
    var items = [], cur = 1, k, i, gap, sep;
    for (k = 0; k + 1 < run.length; k++) {
        gap = text.substring(run[k][1], run[k + 1][0]);
        sep = false;
        for (i = 0; i < gap.length; i++) if (T_LISTSEP[gap.charAt(i)]) sep = true;
        if (sep) { items.push(cur); cur = 1; } else cur++;
    }
    items.push(cur);
    var mx = 0;
    for (k = 0; k < items.length; k++) if (items[k] > mx) mx = items[k];
    return (items.length >= 2 && mx <= itemMax) ? "words" : "quotation";
}

// --- term sets ----------------------------------------------------------------
function TermRef(index, heading, sub, sort, subSort, key) {
    this.index = index; this.heading = heading; this.sub = sub || ""; this.sort = sort || "";
    this.subSort = subSort || ""; this.key = key || "";
}
TermRef.prototype.display = function () { return this.sub ? this.heading + ", " + this.sub : this.heading; };

function tOpt(d, k) { return tHas(d.opts, k) ? d.opts[k] : TT.setDefaults[k]; }
function compileSet(d) {
    var cs = !tOpt(d, "case_sensitive"), marks = !!tOpt(d, "ignore_marks");
    var forms = [], xrefs = [], seen = {}, e, k, h, sub, ref, fl, f, ff, key;
    for (k = 0; k < d.entries.length; k++) {
        e = d.entries[k];
        h = tStrip(String(e.heading || "").replace(/^\s+|\s+$/g, ""));
        if (!h) continue;
        sub = String(e.sub || "").replace(/^\s+|\s+$/g, "");
        ref = new TermRef(d.id, h, sub, String(e.sort || "").replace(/^\s+|\s+$/g, ""),
            String(e.sub_sort || "").replace(/^\s+|\s+$/g, ""));
        var see = String(e.see || "").replace(/^\s+|\s+$/g, ""), also = String(e.see_also || "").replace(/^\s+|\s+$/g, "");
        if (see) { xrefs.push([ref, "see", see]); continue; }
        if (also) xrefs.push([ref, "see_also", also]);
        fl = [];
        for (f = 0; f < (e.forms || []).length; f++) if (e.forms[f] && String(e.forms[f]).replace(/\s+/g, "")) fl.push(e.forms[f]);
        if (!fl.length) fl = [sub || h];
        for (f = 0; f < fl.length; f++) {
            ff = foldStr(fl[f], cs, marks);
            key = ff + "\u0001" + ref.display();
            if (ff && !tHas(seen, key)) { seen[key] = 1; forms.push([ff, ref, forms.length]); }
        }
    }
    forms.sort(function (a, b) { return (b[0].length - a[0].length) || (a[2] - b[2]); });
    return {d: d, forms: forms, xrefs: xrefs};
}
function matchSet(cs, text, meta, cache) {
    var o = cs.d, caseFold = !tOpt(o, "case_sensitive"), marks = !!tOpt(o, "ignore_marks");
    var key = (caseFold ? "1" : "0") + (marks ? "1" : "0");
    if (!cache[key]) cache[key] = tFold(text, caseFold, marks);
    var F = cache[key], ft = F.t;
    var whole = tOpt(o, "whole_words"), plurals = tOpt(o, "plurals"), prefixes = tOpt(o, "hebrew_prefixes");
    var cands = [], fi, form, ref, pos, j, s, e, okp, kk, last;
    for (fi = 0; fi < cs.forms.length; fi++) {
        form = cs.forms[fi][0]; ref = cs.forms[fi][1]; pos = 0;
        while (true) {
            j = ft.indexOf(form, pos);
            if (j < 0) break;
            pos = j + 1; s = j; e = j + form.length;
            if (whole) {
                if (s > 0 && isWordChar(ft.charAt(s - 1))) {
                    okp = false;
                    if (prefixes) {
                        kk = s;
                        while (kk > 0 && s - kk < 3 && T_HEBPRE[ft.charAt(kk - 1)]) {
                            kk--;
                            if (kk === 0 || !isWordChar(ft.charAt(kk - 1))) { okp = true; s = kk; break; }
                        }
                    }
                    if (!okp) continue;
                }
                last = form.charAt(form.length - 1);
                if (plurals && /[A-Za-z]/.test(last)) {
                    if (ft.substring(e, e + 2) === "es" && (e + 2 >= ft.length || !isWordChar(ft.charAt(e + 2)))) e += 2;
                    else if (ft.substring(e, e + 1) === "s" && (e + 1 >= ft.length || !isWordChar(ft.charAt(e + 1)))) e += 1;
                }
                if (e < ft.length && isWordChar(ft.charAt(e))) continue;
            }
            cands.push([s, e, ref, cands.length]);
        }
    }
    cands.sort(function (a, b) { return (a[0] - b[0]) || ((b[1] - b[0]) - (a[1] - a[0])) || (a[3] - b[3]); });
    var hits = [], lastEnd = -1, c, skip = tOpt(o, "skip_block_quotes") && isBlockQuote(text, meta);
    for (c = 0; c < cands.length; c++) {
        if (cands[c][0] < lastEnd) continue;
        lastEnd = cands[c][1];
        var a = F.starts[cands[c][0]], b = F.ends[cands[c][1] - 1];
        hits.push(skip ? {index: cs.d.id, start: a, end: b, status: "quotation", ref: cands[c][2], reason: "in a block quotation", words: []}
                       : {index: cs.d.id, start: a, end: b, status: "term", ref: cands[c][2], reason: "", words: []});
    }
    return hits;
}

// --- the engine --------------------------------------------------------------------
function TermEngine(defs) {
    this.ws = TT.words;
    this.defs = defs;
    this.sets = [];
    this.skip = {};
    var k, parts, i, d;
    for (k = 0; k < defs.length; k++) {
        d = defs[k];
        if (d.kind === "terms") this.sets.push(compileSet(d));
        else {
            this.skip[d.id] = {};
            parts = String(d.opts.skip || "").split(/[\s,]+/);
            for (i = 0; i < parts.length; i++) if (parts[i]) this.skip[d.id][foldStr(parts[i])] = 1;
        }
    }
}
TermEngine.prototype.wordRef = function (d, text, s, e) {
    var form = text.substring(s, e), keyFull = foldStr(form), letters = 0, i;
    for (i = 0; i < keyFull.length; i++) if (isLetter(keyFull.charAt(i))) letters++;
    if (letters < this.ws.min_letters || tHas(this.skip[d.id], keyFull)) return null;
    var key = this.ws.group_forms ? keyFull : foldStr(form, true, false);
    return new TermRef(d.id, form, "", "", "", key);
};
TermEngine.prototype.scan = function (text, meta) {
    meta = meta || {};
    var out = [], k, d, toks, runs, r, run, kind, refs, w, words, block, q;
    block = this.ws.skip_block_quotes && isBlockQuote(text, meta);
    for (k = 0; k < this.defs.length; k++) {
        d = this.defs[k];
        if (d.kind === "terms") continue;
        toks = d.kind === "script" ? scriptTokens(text, d.opts.script) : langTokens(text, meta.langs, d.opts.lang);
        if (!toks.length) continue;
        runs = block ? [toks] : runsOf(text, toks);
        for (r = 0; r < runs.length; r++) {
            run = runs[r];
            kind = block ? "quotation" : classifyRun(text, run, this.ws.max_run, this.ws.list_item_max);
            refs = [];
            for (w = 0; w < run.length; w++) refs.push([run[w][0], run[w][1], this.wordRef(d, text, run[w][0], run[w][1])]);
            if (kind === "words") {
                for (w = 0; w < refs.length; w++)
                    if (refs[w][2]) out.push({index: d.id, start: refs[w][0], end: refs[w][1], status: "word", ref: refs[w][2], reason: "", words: []});
            } else {
                words = [];
                for (w = 0; w < refs.length; w++) if (refs[w][2]) words.push(refs[w]);
                if (!words.length) continue;
                out.push({index: d.id, start: run[0][0], end: run[run.length - 1][1], status: "quotation", ref: null,
                    reason: block ? "in a block quotation" : "part of a " + run.length + "-word quotation", words: words});
            }
        }
    }
    var cache = {};
    for (k = 0; k < this.sets.length; k++) {
        var hs = matchSet(this.sets[k], text, meta, cache);
        for (q = 0; q < hs.length; q++) out.push(hs[q]);
    }
    for (k = 0; k < out.length; k++) out[k]._n = k;
    out.sort(function (a, b) { return (a.start - b.start) || (a.end - b.end) || (a._n - b._n); });
    return out;
};

function tMarks(form) {
    var n = 0, i, c;
    for (i = 0; i < form.length; i++) { c = form.charAt(i); if (tHas(TT.tables.marks, c)) n += TT.tables.marks[c]; }
    return n;
}
// one heading per group of word forms (see terms.choose_headings)
function chooseHeadings(refs) {
    var groups = {}, order = [], i, r, gk, g, st, form, best, bestScore, sc, key, full, tie, h;
    for (i = 0; i < refs.length; i++) {
        r = refs[i];
        gk = r.index + "\u0001" + r.key;
        if (!tHas(groups, gk)) { groups[gk] = []; order.push(gk); }
        groups[gk].push([i, r]);
    }
    for (g = 0; g < order.length; g++) {
        var items = groups[order[g]], stats = {}, forms = [];
        for (i = 0; i < items.length; i++) {
            form = items[i][1].heading;
            if (!tHas(stats, form)) { stats[form] = [0, items[i][0]]; forms.push(form); }
            stats[form][0]++;
        }
        best = null; bestScore = null;
        for (i = 0; i < forms.length; i++) {
            form = forms[i];
            var c0 = form.charAt(0);
            var lowerFirst = (!tHas(TT.tables.lower, c0) || c0 === "ς") ? 1 : 0;
            sc = [-tMarks(form), -lowerFirst, -stats[form][0], stats[form][1]];
            if (best === null || sc[0] < bestScore[0] || (sc[0] === bestScore[0] && (sc[1] < bestScore[1] ||
                (sc[1] === bestScore[1] && (sc[2] < bestScore[2] || (sc[2] === bestScore[2] && sc[3] < bestScore[3])))))) {
                best = form; bestScore = sc;
            }
        }
        full = foldStr(best);
        key = items[0][1].key;
        tie = "";
        if (key !== full) {
            tie = ".";
            for (i = 0; i < key.length; i++) { h = key.charCodeAt(i).toString(16); while (h.length < 4) h = "0" + h; tie += h; }
        }
        for (i = 0; i < items.length; i++) { items[i][1].heading = best; items[i][1].sort = sortCode(best) + tie; }
    }
}
