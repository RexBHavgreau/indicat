"""User settings: stored in %APPDATA%\\ScriptureIndexBuilder\\settings.json and
exportable to a file so a new version (or a colleague) can pick them up."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

from . import __version__
from .catalog import DEFAULT_SECTION_ORDER, build_catalog
from .lang import get_language
from .profiles import PROFILES

DEFAULTS = {
    "language": "en",
    "apocrypha": False,
    "index_layout": "single",            # single | testaments | sections
    "section_order": list(DEFAULT_SECTION_ORDER),
    "ot_order": None,                    # None = the language's default
    "custom_books": [],
    "languages": {},                     # per-language overrides
    "columns": 2,
    "separator": "comma",
    "custom_separator": " —— ",
    "new_page": True,
    "use_word": True,
    "footnote_mode": "italic",
    "check_updates": True,
}
# keys that are personal/machine-specific and are not exported
LOCAL_KEYS = {"last_file", "out_dir", "last_indexed", "use_word"}


def settings_path() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    p = Path(base) / "ScriptureIndexBuilder"
    p.mkdir(parents=True, exist_ok=True)
    return p / "settings.json"


def load() -> dict:
    s = copy.deepcopy(DEFAULTS)
    try:
        s.update(json.loads(settings_path().read_text(encoding="utf-8")))
    except Exception:
        pass
    return s


def save(s: dict) -> None:
    try:
        settings_path().write_text(json.dumps(s, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def export_to(s: dict, path: str | Path) -> None:
    data = {k: v for k, v in s.items() if k not in LOCAL_KEYS}
    data["_exported_by"] = f"Scripture Index Builder {__version__}"
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def import_from(s: dict, path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    data.pop("_exported_by", None)
    out = copy.deepcopy(s)
    for k, v in data.items():
        if k in LOCAL_KEYS:
            continue
        out[k] = v
    return out


def lang_settings(s: dict, code: str) -> dict:
    return s.setdefault("languages", {}).setdefault(code, {})


def make_context(s: dict):
    """(catalog, language) for the current settings."""
    code = s.get("language", "en")
    profile = PROFILES.get(code, PROFILES["en"])
    cat = build_catalog(profile, s)
    return cat, get_language(code, s, cat)
