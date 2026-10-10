"""Check that the InDesign (JavaScript) parser gives exactly the same results
as the Python parser.  Needs Node.js.

    python tests/js_parity.py [manuscript.docx ...]

Runs built-in sentences in every language, plus any manuscripts given.
The JavaScript is run with ES5+ helpers removed, to mimic InDesign's ES3."""
import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from indicat import docx_io as D            # noqa: E402
from indicat import jsx                     # noqa: E402
from indicat.parser import Scanner          # noqa: E402
from indicat.settings import DEFAULTS, make_context  # noqa: E402

SENTENCES = {
    "en": ["Saul gave David wives (1 Sam. 25:43; 27:3). Later (2 Sam. 11:1–27; 12:9–10).",
           "In Proverbs, Solomon says (10:12; 5:4) and (5:1, 7). If you",
           "refrain of Song of Solomon 2:7, 3:5, and 8:4: “Do not", "First Kings 11:1–8 says. First John 3:4.",
           "Gn 1:1 and Jo 3:16 and Is 5 and Is 53:5 and Ps. 23 and 1 Chron. 16:1, 37–40) and Song of Sol. 7:11–8:7",
           "(Brill, 2000), 1:279. HALOT, 1:43–44. Peter said (3:16).", "Jude 5, Sir 24:3, Tob 1:1, Deuteronomy 1–21:9",
           "Starting in Ephesians 5. Starting in verse 21, he says (v. 23) and vv. 1–3. At 10:30 a.m.",
           "Gen 1:28 and 2 Kings 5:1; Prov 5:18, 19, and 2 Cor 3:1."],
    "es": ["Como dice Juan 3:16 y Gn 1:1; 2:3. Primera de Corintios 13:4 y 1 Co 13:7, Ap 21:4.",
           "En Romanos (8:28) y Sal 23:1-3. Hch 2:38. Genesis 1:1 y vv. 4-5."],
    "pt": ["João 3:16 e Jo 3:16; Jn 1:2 (Jonas). 1Co 13:4, Gn 1:1-3."],
    "fr": ["Jn 3,16 et Gn 1,1-3 ; 2,4.7. Voir 1 Co 13,4s. Es 53,5. Il a 3,5 ans (3,5)."],
    "de": ["Joh 3,16; 1. Mose 1,1; 1 Kor 13,4ff.; Röm 8,28.30. Es kostet 3,5 Euro. Ps 23,1-3",
           "vgl. Sir 24,3 und 1. Mose 1,1. Mt 5,3 und 7."],
    "he": ["כתוב בבראשית א, א ובשמות ג:יד. ראו תה׳ כג, א-ג; ישעיהו נג, ה. גם שמ״א טז, ז. בראשית 1:1"],
}

NODE_MAIN = r"""
var fs = require('fs');
var J = JSON;
var input = J.parse(fs.readFileSync(process.argv[2], 'utf8'));
// remove ES5+ helpers to mimic ExtendScript (ES3)
['forEach','map','filter','indexOf','some','every','reduce','lastIndexOf'].forEach(function(k){ delete Array.prototype[k]; });
delete String.prototype.trim; delete Object.keys;
var out = [];
var sc = new Scanner(15);
function put(h, seg){ out.push([seg, h.start, h.end, h.status, h.ref ? refDisplay(h.ref) : null]); }
for (var i = 0; i < input.length; i++) {
  var s = input[i];
  if (s.heading) sc.heading();
  var anchors = []; for (var a = 0; a < s.notes.length; a++) anchors.push(s.notes[a].offset);
  var res = sc.scan(s.text, s.italic, s.idx, anchors);
  // interleave like the Python pipeline
  var hits = res.hits, hi = 0, ns = s.notes.slice(0);
  ns.sort(function(x,y){return x.offset-y.offset;});
  for (var k = 0; k < ns.length; k++) {
    while (hi < hits.length && hits[hi].start < ns[k].offset) { put(hits[hi], s.id); hi++; }
    var ctx = res.snaps[ns[k].offset] ? copyCtx(res.snaps[ns[k].offset]) : copyCtx(sc.ctx);
    for (var p = 0; p < ns[k].segs.length; p++) {
      var r2 = sc.scan(ns[k].segs[p].text, ns[k].segs[p].italic, s.idx, [], ctx);
      for (var q = 0; q < r2.hits.length; q++) put(r2.hits[q], ns[k].segs[p].id);
    }
  }
  while (hi < hits.length) { put(hits[hi], s.id); hi++; }
}
process.stdout.write(J.stringify(out));
"""


def python_hits(settings, segs):
    cat, lang = make_context(settings)
    sc = Scanner(lang)
    out = []

    def put(h, sid):
        out.append([sid, h.start, h.end, h.status, h.ref.display() if h.ref else None])
    for s in segs:
        if s["heading"]:
            sc.heading()
        hits, snaps = sc.scan_segment(s["text"], s["italic"], s["idx"], anchors=[n["offset"] for n in s["notes"]])
        hi = 0
        for n in sorted(s["notes"], key=lambda x: x["offset"]):
            while hi < len(hits) and hits[hi].start < n["offset"]:
                put(hits[hi], s["id"])
                hi += 1
            ctx = snaps.get(n["offset"], sc.ctx).copy()
            for ns in n["segs"]:
                nh, _ = sc.scan_segment(ns["text"], ns["italic"], s["idx"], ctx=ctx)
                for h in nh:
                    put(h, ns["id"])
        while hi < len(hits):
            put(hits[hi], s["id"])
            hi += 1
    return out


def js_hits(settings, segs):
    src = jsx.parser_source(settings) + NODE_MAIN
    with tempfile.TemporaryDirectory() as d:
        Path(d, "p.js").write_text(src, encoding="utf-8")
        Path(d, "in.json").write_text(json.dumps(segs), encoding="utf-8")
        r = subprocess.run(["node", str(Path(d, "p.js")), str(Path(d, "in.json"))],
                           capture_output=True, text=True, encoding="utf-8")
        if r.returncode:
            raise RuntimeError(r.stderr[-3000:])
        return json.loads(r.stdout)


def segs_from_docx(path):
    pkg = D.DocxPackage(path)
    out = []
    for s in pkg.body_segments:
        notes = []
        for a in s.anchors:
            ns = pkg.note_segments.get((a.kind, a.note_id), [])
            notes.append({"offset": a.offset, "segs": [{"id": f"{n.part}:{n.idx}", "text": n.text,
                                                        "italic": n.italic} for n in ns]})
        out.append({"id": f"{s.part}:{s.idx}", "idx": s.idx, "text": s.text, "italic": s.italic,
                    "heading": s.heading, "notes": notes})
    return out


def compare(name, settings, segs):
    a, b = python_hits(settings, segs), js_hits(settings, segs)
    if a == b:
        print(f"OK   {name}: {len(a)} hits identical")
        return True
    print(f"DIFF {name}: python {len(a)} vs js {len(b)}")
    sa, sb = [tuple(x) for x in a], [tuple(x) for x in b]
    for x in [x for x in sa if x not in sb][:15]:
        print("   only python:", x)
    for x in [x for x in sb if x not in sa][:15]:
        print("   only js:    ", x)
    return False


def main(paths):
    ok = True
    for code, sents in SENTENCES.items():
        s = copy.deepcopy(DEFAULTS)
        s["language"] = code
        s["apocrypha"] = True
        segs = [{"id": f"s{i}", "idx": i, "text": t, "italic": [False] * len(t), "heading": False, "notes": []}
                for i, t in enumerate(sents)]
        ok &= compare(f"sentences [{code}]", s, segs)
    for p in paths:
        s = copy.deepcopy(DEFAULTS)
        ok &= compare(Path(p).name[:60], s, segs_from_docx(p))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
