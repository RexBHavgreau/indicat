"""Check that the InDesign (JavaScript) word and term engine gives exactly the
same results as the Python one.  Needs Node.js.

    python tests/terms_parity.py [manuscript.docx ...]

Runs built-in sentences plus any manuscripts given, with Greek, Hebrew and
Latin indexes and a term set switched on.  The JavaScript is run with ES5+
helpers removed, to mimic InDesign's ES3."""
import copy
import json
import subprocess
import sys

# Windows consoles default to a code page that has no Greek or Hebrew
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from indicat import docx_io as D            # noqa: E402
from indicat import jsx                     # noqa: E402
from indicat import terms as T              # noqa: E402
from indicat.settings import DEFAULTS       # noqa: E402

SENTENCES = [
    ("The verbs ἀγαπάω, φιλέω, στέργω, ἐράω, and ποθέω differ; so do λόγος and λόγου.", None, False, None),
    ("Ἐν ἀρχῇ ἦν ὁ λόγος, καὶ ὁ λόγος ἦν πρὸς τὸν θεόν, καὶ θεὸς ἦν ὁ λόγος.", None, False, None),
    ("The forms λόγος, λόγου, λόγῳ, λόγον, λόγε, λόγοι are listed; δι’ αὐτοῦ and ἀλλ’ ἐγώ.", None, False, None),
    ("The word חֶסֶד (and חסד, חַסְדּוֹ) in כָּל־הָאָרֶץ; also וְהָאָרֶץ and בְּרֵאשִׁית בָּרָא אֱלֹהִים אֵת הַשָּׁמַיִם וְאֵת הָאָרֶץ׃", None, False, None),
    ("A block quotation that mentions λόγος and חֶסֶד among many other words in a long paragraph of quoted prose here.", "indent", False, None),
    ("Short indented λόγος line", "indent", False, None),
    ("Quoted in a Quote style: λόγος.", "style", False, None),
    ("ἀγαπάω φιλέω στέργω ἐράω ποθέω", "style", True, None),
    ("Covenant and covenants; the new covenant, the Davidic covenant. Justified by grace; GRACE alone; graces.", None, False, None),
    ("The Latin sola gratia and sola fide (soli Deo gloria) are mottos.", None, False, "latin"),
    ("ܡܠܬܐ and ܐܠܗܐ in Syriac; Λόγος vs λόγος vs ΛΟΓΟΣ.", None, False, None),
]

SETTINGS = copy.deepcopy(DEFAULTS)
SETTINGS["words"] = {"scripts": {"greek": {"enabled": True}, "hebrew": {"enabled": True},
                                 "syriac": {"enabled": True}},
                     "tagged": [{"lang": "la", "enabled": True, "title": "Index of Latin Words",
                                 "skip": T.TAGGED_LANGUAGES["la"][3]}]}
SETTINGS["term_sets"] = [
    {"id": "set1", "name": "Subjects", "enabled": True, "title": "Subject Index",
     "options": {"plurals": True},
     "entries": [{"heading": "covenant", "forms": ["covenant"]},
                 {"heading": "covenant", "sub": "new", "forms": ["new covenant"]},
                 {"heading": "covenant", "sub": "Davidic", "forms": ["Davidic covenant"]},
                 {"heading": "grace", "forms": ["grace"]},
                 {"heading": "justification", "forms": ["justified", "justification"]},
                 {"heading": "marriage", "forms": ["marriage", "married"]},
                 {"heading": "exile", "forms": ["exile", "exilic"]},
                 {"heading": "favor", "see": "grace"}]},
    {"id": "set2", "name": "Hebrew terms", "enabled": True, "title": "Hebrew Terms",
     "options": {"hebrew_prefixes": True, "whole_words": True},
     "entries": [{"heading": "חֶסֶד", "forms": ["חֶסֶד", "חַסְדּוֹ"]}, {"heading": "אֶרֶץ", "forms": ["ארץ", "הארץ"]},
                 {"heading": "λόγος", "forms": ["λόγος", "λόγου", "λόγῳ"]}]},
]

NODE_MAIN = r"""
var fs = require('fs');
var input = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
['forEach','map','filter','indexOf','some','every','reduce','lastIndexOf'].forEach(function(k){ delete Array.prototype[k]; });
delete String.prototype.trim; delete Object.keys;
var eng = new TermEngine(TT.defs);
var out = [], refs = [], all = [];
for (var i = 0; i < input.length; i++) {
  var hs = eng.scan(input[i].text, input[i].meta);
  for (var k = 0; k < hs.length; k++) {
    all.push([i, hs[k]]);
    if (hs[k].index.indexOf('set:') !== 0) {
      if (hs[k].ref) refs.push(hs[k].ref);
      for (var w = 0; w < hs[k].words.length; w++) refs.push(hs[k].words[w][2]);
    }
  }
}
chooseHeadings(refs);
for (var a = 0; a < all.length; a++) {
  var h = all[a][1];
  var ws = []; for (var w2 = 0; w2 < h.words.length; w2++) ws.push([h.words[w2][0], h.words[w2][1], h.words[w2][2].heading, h.words[w2][2].sort]);
  out.push([all[a][0], h.index, h.start, h.end, h.status, h.ref ? h.ref.heading : null, h.ref ? h.ref.sub : null,
            h.ref ? (h.ref.sort || sortCode(h.ref.heading)) : null, ws]);
}
process.stdout.write(JSON.stringify(out));
"""


def python_out(segs):
    eng = T.TermEngine(SETTINGS)
    allh, refs = [], []
    for i, s in enumerate(segs):
        meta = T.SegMeta(s["meta"]["quote"], s["meta"]["table"], s["meta"]["langs"])
        for h in eng.scan(s["text"], meta):
            allh.append((i, h))
            if not h.index.startswith("set:"):
                if h.ref is not None:
                    refs.append(h.ref)
                refs.extend(r for _, _, r in h.words)
    T.choose_headings(refs)
    out = []
    for i, h in allh:
        out.append([i, h.index, h.start, h.end, h.status, h.ref.heading if h.ref else None,
                    h.ref.sub if h.ref else None, (h.ref.sort or T.sort_code(h.ref.heading)) if h.ref else None,
                    [[a, b, r.heading, r.sort] for a, b, r in h.words]])
    return out


def node_out(segs):
    with tempfile.TemporaryDirectory() as d:
        src = Path(d, "t.js")
        src.write_text("var DATA = " + json.dumps(jsx.build_data(SETTINGS)) + ";\n" +
                       (jsx._js_dir() / "terms.js").read_text(encoding="utf-8") + NODE_MAIN, encoding="utf-8")
        inp = Path(d, "in.json")
        inp.write_text(json.dumps(segs, ensure_ascii=False), encoding="utf-8")
        r = subprocess.run(["node", str(src), str(inp)], capture_output=True, text=True, encoding="utf-8")
        if r.returncode:
            print(r.stderr)
            sys.exit(1)
        return json.loads(r.stdout)


def segs_from_sentences():
    out = []
    for text, quote, table, lang in SENTENCES:
        langs = None
        if lang == "latin":
            langs = [None] * len(text)
            for w in ("sola gratia", "sola fide", "soli Deo gloria"):
                i = text.find(w)
                for k in range(i, i + len(w)):
                    langs[k] = "la-Latn"
        out.append({"text": text, "meta": {"quote": quote, "table": table, "langs": langs}})
    return out


def segs_from_docx(path):
    pkg = D.DocxPackage(path)
    out = []
    for s in pkg.body_segments + [x for lst in pkg.note_segments.values() for x in lst]:
        m = s.meta()
        out.append({"text": s.text, "meta": {"quote": m.quote, "table": m.table, "langs": m.langs}})
    return out


def compare(name, segs):
    a, b = python_out(segs), node_out(segs)
    if a == b:
        print(f"OK   {name}: {len(a)} hits identical")
        return True
    print(f"DIFF {name}: python {len(a)} / js {len(b)}")
    for x, y in zip(a, b):
        if x != y:
            print("  py:", x)
            print("  js:", y)
            break
    return False


def main():
    ok = compare("sentences", segs_from_sentences())
    for p in sys.argv[1:]:
        ok &= compare(Path(p).name, segs_from_docx(p))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
