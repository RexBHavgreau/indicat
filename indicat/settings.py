"""User settings.

Stored in %APPDATA%\\Indicat\\settings.json.  A new version picks up the
settings of the version before it automatically: every version of Indicat
reads the same file, and the first run of Indicat also brings over the
settings of its predecessor, Scripture Index Builder 0.2
(%APPDATA%\\ScriptureIndexBuilder\\settings.json).  Settings can still be
exported to a file, to move them to another computer or share them.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

from . import __version__
from .catalog import DEFAULT_SECTION_ORDER, build_catalog
from .lang import get_language
from .profiles import PROFILES

SETTINGS_VERSION = 4          # bump when the layout of the file changes; see migrate()

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
    "scripture": True,                   # build the Scripture index
    "words": {},                         # original-language word indexes (see terms.DEFAULT_WORDS)
    "term_sets": [],                     # user term sets (see terms.py)
    # 0.4.0
    "whole_chapters": False,             # index references to whole chapters ("Proverbs 5")
    "index_bibliography": False,         # index references and words in the bibliography
    "mt_mode": "label",                  # Hebrew (MT) verse numbers: "label" with [MT] | "exclude"
    "index_font": "body",                # "body" = match the body text | "styles" = the document's index styles
    "save_location": "same",             # "same" folder as the manuscript | "fixed" folder | "ask"
    "save_folder": "",                   # the fixed folder
    "pdf_viewer": "auto",                # auto | acrobat | sumatra | foxit | edge | chrome | firefox | default
    "pdf_viewer_path": "",
    "welcome_done": False,               # the first-run welcome (guided build or full window) was shown
}
# keys that are personal/machine-specific and are not exported
LOCAL_KEYS = {"last_file", "out_dir", "last_indexed", "use_word", "_migrated_from", "_settings_version",
              "save_folder", "pdf_viewer_path", "welcome_done"}

APP_FOLDER = "Indicat"
# folders of earlier versions, newest first
PREVIOUS_FOLDERS = ["ScriptureIndexBuilder"]

# set by load() when settings were brought over from an earlier version this run
migration_note: str | None = None


def _base() -> Path:
    return Path(os.environ.get("APPDATA") or str(Path.home() / ".config"))


def settings_path() -> Path:
    p = _base() / APP_FOLDER
    p.mkdir(parents=True, exist_ok=True)
    return p / "settings.json"


def previous_settings() -> Path | None:
    """The settings file of an earlier version, if there is one."""
    for name in PREVIOUS_FOLDERS:
        p = _base() / name / "settings.json"
        if p.is_file():
            return p
    return None


def migrate(data: dict) -> dict:
    """Bring settings written by any earlier version up to date."""
    ver = data.get("_settings_version", 2)
    if ver < 3:
        # 0.2: no word or term indexes yet; nothing to convert
        pass
    if ver < 4:
        # 0.4: the Greek skip list gained pronouns, τίς, εἰμί and elided forms; add them to a saved list
        from .terms import GREEK_SKIP
        g = (data.get("words") or {}).get("scripts", {}).get("greek")
        if isinstance(g, dict) and isinstance(g.get("skip"), str):
            have = set(g["skip"].split())
            extra = [w for w in GREEK_SKIP.split() if w not in have]
            if extra:
                g["skip"] = (g["skip"].rstrip() + " " + " ".join(extra)).strip()
    data["_settings_version"] = SETTINGS_VERSION
    return data


def load() -> dict:
    global migration_note
    s = copy.deepcopy(DEFAULTS)
    path = settings_path()
    data = None
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = None
    else:
        old = previous_settings()
        if old is not None:
            try:
                data = json.loads(old.read_text(encoding="utf-8"))
                data["_migrated_from"] = str(old)
                migration_note = (f"Your settings from Scripture Index Builder were brought over "
                                  f"automatically ({old}).")
                data = migrate(data)
                path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception:
                data = None
    if data:
        s.update(migrate(data))
    return s


def save(s: dict) -> None:
    try:
        s["_settings_version"] = SETTINGS_VERSION
        settings_path().write_text(json.dumps(s, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def export_to(s: dict, path: str | Path) -> None:
    data = {k: v for k, v in s.items() if k not in LOCAL_KEYS}
    data["_exported_by"] = f"Indicat {__version__}"
    data["_settings_version"] = SETTINGS_VERSION
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def import_from(s: dict, path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    data.pop("_exported_by", None)
    data = migrate(data)
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
