"""Run the generated InDesign script against a fake InDesign document (Node.js).

    python tests/indesign_mock_test.py
"""
import copy
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripture_index import jsx                       # noqa: E402
from scripture_index.settings import DEFAULTS          # noqa: E402

s = copy.deepcopy(DEFAULTS)
s["apocrypha"] = True
with tempfile.TemporaryDirectory() as d:
    script = Path(d, "run.js")
    script.write_text(jsx.script_source(s), encoding="utf-8")
    r = subprocess.run(["node", str(ROOT / "tests" / "indesign_mock.js"), str(script),
                        str(ROOT / "tests" / "fixtures" / "indesign_mockdoc.json")],
                       capture_output=True, text=True, encoding="utf-8")
    print(r.stdout)
    if r.returncode or "Scripture index markers added: 12" not in r.stdout:
        print(r.stderr)
        sys.exit(1)
print("OK   InDesign script ran against the mock document")
