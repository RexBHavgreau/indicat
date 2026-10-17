"""Command-line interface (useful for testing and batch work).

    python -m indicat scan  "Manuscript.docx" [--csv out.csv]
    python -m indicat build "Manuscript.docx" [--out DIR] [--notes italic|bold|highlight|auto|skip]
    python -m indicat static "Book - Indexed.docx" [--mode auto|highlight]
    python -m indicat build "Book.docx" --words greek,hebrew --terms "Subjects.csv"
    python -m indicat build "Book.pdf" [--format docx|odt]      (a finished index from a PDF)
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from . import __version__
from .pipeline import (FOOTNOTE_MODES, SEPARATORS, BuildOptions, build, check_custom_separator,
                       make_static, scan)


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):      # Greek and Hebrew in a Windows console
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(prog="indicat", description=f"Indicat {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan", help="list references found")
    s.add_argument("docx")
    s.add_argument("--csv")
    b = sub.add_parser("build", help="write indexed copy and proof list")
    b.add_argument("docx")
    b.add_argument("--out")
    b.add_argument("--notes", choices=list(FOOTNOTE_MODES), default="italic")
    b.add_argument("--columns", type=int, default=2)
    b.add_argument("--sep", choices=[k for k in SEPARATORS if k != "custom"], default="comma",
                   help="page number separation")
    b.add_argument("--custom-sep", help="custom separation text (up to 5 characters), e.g. ' -- '")
    b.add_argument("--remove-existing", action="store_true")
    b.add_argument("--no-word", action="store_true")
    b.add_argument("--format", choices=["docx", "odt"], default="docx", help="index file for a PDF")
    st = sub.add_parser("static", help="make a '(static index)' copy of a checked, indexed document")
    st.add_argument("docx")
    st.add_argument("--out")
    st.add_argument("--mode", choices=["auto", "highlight"], default="auto")
    st.add_argument("--marker", choices=["auto", "Bold", "Italic", "none"], default="auto")
    st.add_argument("--update-first", action="store_true")
    for sp in (s, b):
        sp.add_argument("--words", help="original-language word indexes to build, e.g. greek,hebrew (or none)")
        sp.add_argument("--terms", action="append", default=[], help="a term list (.txt or .csv) to index; repeatable")
        sp.add_argument("--no-scripture", action="store_true", help="don't build the Scripture index")
        sp.add_argument("--pages", help="PDF only: the PDF pages to index, e.g. 9-880 or '9-14, 21-880'")
        sp.add_argument("--lang", choices=["en", "es", "pt", "fr", "de", "he"], help="language (default: saved setting)")
        sp.add_argument("--apocrypha", action="store_true", help="recognize the Apocrypha")
        sp.add_argument("--layout", choices=["single", "testaments", "sections"], help="index layout")
        sp.add_argument("--settings", help="settings file exported from the app")
        sp.add_argument("--whole-chapters", action="store_true", help="index references to whole chapters")
        sp.add_argument("--bibliography", action="store_true", help="index the bibliography")
        sp.add_argument("--mt", choices=["label", "exclude"], help="verses in Hebrew numbering: [MT] or left out")
    j = sub.add_parser("jsx", help="write the InDesign script for the current settings")
    j.add_argument("out")
    j.add_argument("--lang", choices=["en", "es", "pt", "fr", "de", "he"])
    j.add_argument("--apocrypha", action="store_true")
    j.add_argument("--settings")
    a = ap.parse_args(argv)
    from . import settings as SET
    cfg = SET.load()
    if getattr(a, "settings", None):
        cfg = SET.import_from(cfg, a.settings)
    if getattr(a, "lang", None):
        cfg["language"] = a.lang
    if getattr(a, "apocrypha", False):
        cfg["apocrypha"] = True
    if getattr(a, "layout", None):
        cfg["index_layout"] = a.layout
    if getattr(a, "no_scripture", False):
        cfg["scripture"] = False
    if getattr(a, "whole_chapters", False):
        cfg["whole_chapters"] = True
    if getattr(a, "bibliography", False):
        cfg["index_bibliography"] = True
    if getattr(a, "mt", None):
        cfg["mt_mode"] = a.mt
    if getattr(a, "words", None) is not None:
        from . import terms as T
        ws = T.words_settings(cfg)
        want = {w.strip().lower() for w in a.words.split(",") if w.strip()}
        bad = want - set(T.SCRIPT_INDEXES) - {"none"}
        if bad:
            ap.error("unknown word index: " + ", ".join(sorted(bad)) + " (use greek, hebrew, syriac)")
        for k in ws["scripts"]:
            ws["scripts"][k]["enabled"] = k in want
        cfg["words"] = ws
    for tf in getattr(a, "terms", []) or []:
        from . import terms as T
        entries, probs = T.read_term_file(tf)
        for pmsg in probs:
            print("TERMS:", pmsg)
        name = T.clean_set_name(Path(tf).stem)
        cfg.setdefault("term_sets", []).append({"id": T.new_set_id(cfg.get("term_sets", [])), "name": name,
                                                "title": name, "enabled": True, "entries": entries})
    if a.cmd == "jsx":
        from . import jsx
        jsx.write_script(a.out, cfg)
        print("InDesign script:", a.out)
        return 0
    if a.cmd == "static":
        out, msgs = make_static(a.docx, a.out, a.mode, a.marker, a.update_first)
        for m in msgs:
            print("NOTE:", m)
        print("Static copy:", out)
        return 0

    pdf = Path(a.docx).suffix.lower() == ".pdf"
    if pdf:
        from .pdf_index import scan_pdf
        try:
            res = scan_pdf(a.docx, cfg, pages=a.pages)
        except ValueError as exc:
            ap.error(str(exc))
    else:
        res, _ = scan(a.docx, cfg)
    for wmsg in res.warnings:
        print("WARNING:", wmsg)
    if a.cmd == "scan":
        print(f"{len(res.occurrences)} found; {res.counts()}")
        if a.csv:
            with open(a.csv, "w", newline="", encoding="utf-8-sig") as f:
                wr = csv.writer(f)
                wr.writerow(["include", "index", "entry", "status", "where", "context"])
                for o in res.occurrences:
                    wr.writerow([o.include, res.index_name(o.index), o.display, o.status_label, o.where, o.context])
        else:
            for o in res.occurrences:
                print(f"{'+' if o.include else '-'} {res.index_name(o.index)[:10]:10} {o.display:28} "
                      f"{o.status_label[:30]:30} {o.where:12} {o.context[:80]}")
        return 0
    out = Path(a.out) if a.out else Path(a.docx).parent
    if a.custom_sep is not None:
        err = check_custom_separator(a.custom_sep)
        if err:
            ap.error(err)
        sep_text, leader = a.custom_sep, None
    else:
        _, sep_text, leader = SEPARATORS[a.sep]
    opts = BuildOptions(out_dir=out, columns=a.columns, separator=sep_text, leader=leader,
                        footnote_mode=a.notes, remove_existing_xe=a.remove_existing,
                        use_word=not a.no_word, settings=cfg)
    if pdf:
        from .pdf_index import build_pdf
        r = build_pdf(res, opts, a.format)
    else:
        r = build(res, opts)
    for m in r.messages:
        print("NOTE:", m)
    print("Index:" if pdf else "Indexed copy:", r.indexed_docx)
    if r.final_docx:
        print("Final copy:  ", r.final_docx)
    print("Proof list:  ", r.proof_docx)
    return 0


if __name__ == "__main__":
    sys.exit(main())
