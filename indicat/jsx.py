"""Generate the InDesign script (.jsx) from the current settings.

The script = a DATA block (book names, spellings, reading rules for the
chosen language, custom books) + the ES3 parser (js/parser.js, a port of
parser.py tested against the same cases) + the InDesign driver (js/driver.js).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from . import AUTHOR, CREDIT, REPO_URL, __version__
from . import settings as SET
from . import terms as T
from .profiles import PROFILES


def _js_dir() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    p = base / "indicat" / "js"
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
        "apocrypha": bool(cat.ap_indexed),
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
            "authorVerbs": p.get("author_verbs", []),
            "personBooks": p.get("person_books", []),
            "notBooks": p.get("not_books", []),
            "mtWords": p.get("mt_words", []),
        },
        "flags": dict(lang.flags),
        "verses": {bid: [list(v[0]), list(v[1])] for bid, v in cat.verses.items() if bid in cat.books},
        "spell": [[lang._pattern_for(k), k] for k in keys],
        "map": {k: list(v) for k, v in lang.spellings.items()},
        "books": {b.id: [b.name, b.section, b.rank, b.chapters] for b in cat.books.values()},
        "scripture": bool(settings.get("scripture", True)),
        "terms": terms_data(settings),
    }


def terms_data(settings: dict) -> dict:
    """Word-index settings, term sets and character tables for js/terms.js."""
    ws = T.words_settings(settings)
    defs = T.index_defs(settings)
    lang_names = {}
    for code, info in T.TAGGED_LANGUAGES.items():
        for nm in info[2]:
            lang_names[nm] = code
    return {
        "tables": T.js_tables(),
        "words": {k: ws[k] for k in ("group_forms", "skip_block_quotes", "max_run", "list_item_max", "min_letters")},
        "setDefaults": dict(T.TERM_SET_OPTIONS),
        "indentProseWords": T.INDENT_PROSE_WORDS,
        "defs": [{"id": d.id, "kind": d.kind, "title": d.title, "short": d.short, "letter": d.letter,
                  "opts": d.opts, "entries": d.entries} for d in defs],
        "see": list(T.SEE_WORDS.get(settings.get("language", "en"), T.SEE_WORDS["en"])),
        "langNames": lang_names,
    }


def parser_source(settings: dict) -> str:
    data = json.dumps(build_data(settings), ensure_ascii=True)
    return ("var DATA = " + data + ";\n" + (_js_dir() / "parser.js").read_text(encoding="utf-8") + "\n" +
            (_js_dir() / "terms.js").read_text(encoding="utf-8"))


def script_source(settings: dict) -> str:
    names = [d.title for d in T.index_defs(settings)]
    head = (f"// Indicat {__version__} for InDesign — Scripture index builder\n"
            f"// {CREDIT}. {REPO_URL}\n"
            "// Free software under the GNU General Public License v3; modified versions must keep the\n"
            f"// credit \"{CREDIT}\" in their interface and documentation.\n"
            f"// Generated for: {PROFILES.get(settings.get('language', 'en'), PROFILES['en'])['name']}"
            + (f"; also builds: {', '.join(names)}" if names else "") + "\n"
            "// Run from Window > Utilities > Scripts with the document open.\n"
            "#target indesign\n")
    driver = (_js_dir() / "driver.js").read_text(encoding="utf-8")
    return head + "(function () {\n" + parser_source(settings) + "\n" + driver + "\n})();\n"


def write_script(path: str | Path, settings: dict) -> None:
    Path(path).write_text("﻿" + script_source(settings), encoding="utf-8")
