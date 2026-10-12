"""Run the generated InDesign script against a fake InDesign document (Node.js).

    python tests/indesign_mock_test.py
"""
import copy
import subprocess
import sys

# Windows consoles default to a code page that has no Greek or Hebrew
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from indicat import jsx                       # noqa: E402
from indicat.settings import DEFAULTS          # noqa: E402


def run(settings, expect):
    with tempfile.TemporaryDirectory() as d:
        script = Path(d, "run.js")
        script.write_text(jsx.script_source(settings), encoding="utf-8")
        r = subprocess.run(["node", str(ROOT / "tests" / "indesign_mock.js"), str(script),
                            str(ROOT / "tests" / "fixtures" / "indesign_mockdoc.json")],
                           capture_output=True, text=True, encoding="utf-8")
        print(r.stdout)
        missing = [e for e in expect if e not in r.stdout]
        if r.returncode or missing:
            print(r.stderr)
            print("MISSING:", missing)
            sys.exit(1)


s = copy.deepcopy(DEFAULTS)
s["apocrypha"] = True
run(s, ["Scripture index markers added: 13", "Bibliography (not indexed)"])
print("OK   InDesign script (Scripture only) ran against the mock document")

s["words"] = {"scripts": {"greek": {"enabled": True}, "hebrew": {"enabled": True}}}
s["term_sets"] = [{"id": "set1", "name": "Subjects", "enabled": True, "title": "Subject Index",
                   "entries": [{"heading": "covenant", "forms": ["covenant"]},
                               {"heading": "covenant", "sub": "new", "forms": ["new covenant"]},
                               {"heading": "covenant", "sub": "Davidic", "forms": ["Davidic covenant"]},
                               {"heading": "pact", "see": "covenant"}]}]
# the Quote-style and indented paragraphs are block quotations, and the Greek of John 1:1
# is an inline quotation: none of their words are indexed
run(s, ["Index markers added: 20 (", "Scripture 13", "Greek 2", "Hebrew 2", "Subjects 3", "Cross-references added: 1",
        "Index of Hebrew and Aramaic Words [9900]", "Index of Greek Words [9901]", "λόγος [2024122427] x1",
        "Subject Index [9902]", "Davidic [davidic] x1", '[["covenant","see"]]', "<th>Index</th>"])
print("OK   InDesign script (Scripture, Greek, Hebrew, term set) ran against the mock document")

s["index_bibliography"] = True
run(s, ["Scripture 14", "Subjects 4"])
print("OK   InDesign script indexes the bibliography when asked")
