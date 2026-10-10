"""Generate the InDesign script (.jsx) from the current settings.

The script = a DATA block (book names, spellings, reading rules for the
chosen language, custom books) + the ES3 parser (js/parser.js, a port of
parser.py tested against the same cases) + the InDesign driver (js/driver.js).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from . import __version__
from . import settings as SET
from .profiles import PROFILES


def _js_dir() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    p = base / "scripture_index" / "js"
    if not p.exists():
        p = Path(__file__).resolve().parent / "js"
    return p


def build_data(settings: dict) -> dict:
    cat, lang = SET.make_context(settings)
    p = lang.p
    keys = sorted(lang.spellings, key=len, reverse=True)
    return {
        "version": __version__,
        "lang": lang.code,
        "langName": p["name"],
        "apocrypha": bool(settings.get("apocrypha")),
        "customCount": len(settings.get("custom_books", [])),
        "layout": settings.get("index_layout", "single"),
        "numerals": p.get("numerals", "arabic"),
        "labelSep": p.get("label_sep", ":"),
        "indexTitle": cat.index_title,
        "sectionOrder": cat.section_order,
        "sectionTitles": cat.section_titles,
        "rules": {
            "cvSeps": p.get("cv_seps", [":"]),
            "suffixes": [list(x) for x in p.get("suffixes", [])],
            "verseWords": p.get("verse_words", []),
            "andWords": p.get("and_words", []),
            "cfWords": p.get("cf_words", []),
            "intro": p.get("intro", []),
            "spaced": p.get("verse_list_spaced", []),
            "tight": p.get("verse_list_tight", []),
            "bareParens": bool(p.get("bare_requires_parens")),
            "prefixLetters": p.get("prefix_letters", ""),
        },
        "spell": [[lang._pattern_for(k), k] for k in keys],
        "map": {k: list(v) for k, v in lang.spellings.items()},
        "books": {b.id: [b.name, b.section, b.rank, b.chapters] for b in cat.books.values()},
    }


def parser_source(settings: dict) -> str:
    data = json.dumps(build_data(settings), ensure_ascii=True)
    return "var DATA = " + data + ";\n" + (_js_dir() / "parser.js").read_text(encoding="utf-8")


def script_source(settings: dict) -> str:
    head = (f"// Scripture Index Builder {__version__} — InDesign script\n"
            f"// Generated for: {PROFILES.get(settings.get('language', 'en'), PROFILES['en'])['name']}\n"
            "// Run from Window > Utilities > Scripts with the document open.\n"
            "#target indesign\n")
    driver = (_js_dir() / "driver.js").read_text(encoding="utf-8")
    return head + "(function () {\n" + parser_source(settings) + "\n" + driver + "\n})();\n"


def write_script(path: str | Path, settings: dict) -> None:
    Path(path).write_text("﻿" + script_source(settings), encoding="utf-8")
