"""Philosopher Mode: a guided, step-by-step index build.

It walks through the index settings one at a time (the document, what to
index, language and abbreviations, how the index looks, notes), runs the scan
with a word on what to check in the review list, and ends with a summary
before building.  Everything it sets is an ordinary setting: the main window
shows the same choices, and the next build starts from them.
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import APP_NAME
from . import settings as SET
from . import terms as T
from .pipeline import FOOTNOTE_MODES, SEPARATORS
from .profiles import LANGUAGE_ORDER, PROFILES

STEPS = ["Your document", "What to index", "Language and abbreviations", "How the index looks", "Notes",
         "Scan and review", "Build"]
LAYOUTS = {"single": "One index", "testaments": "Old and New Testament (Apocrypha with OT)",
           "sections": "By section (OT, Apocrypha, NT, Other)"}
SAMPLE = [("OT", "Genesis", [("1:1", ["3", "17"]), ("3:15", ["22", "45n3"])]),
          ("OT", "Psalms", [("23:1–6", ["104"]), ("119:105", ["12", "88"])]),
          ("AP", "Sirach", [("24:3", ["61"])]),
          ("NT", "John", [("1:1", ["2", "9", "130"]), ("3:16", ["7"])]),
          ("NT", "Romans", [("8:28–30", ["54n2", "77"])])]


class GuidedBuild(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.s = app.settings
        self.title("Philosopher Mode — guided index build")
        self.geometry("880x640")
        self.minsize(760, 560)
        self.transient(app)
        self.step = 0
        self.info = {}                       # what the document check found
        self.scanned = False
        head = ttk.Frame(self, padding=(16, 12, 16, 0))
        head.pack(fill="x")
        self.crumbs = ttk.Label(head, text="", foreground="#666")
        self.crumbs.pack(anchor="w")
        self.h1 = ttk.Label(head, text="", font=("Georgia", 17))
        self.h1.pack(anchor="w", pady=(4, 0))
        self.body = ttk.Frame(self, padding=(16, 8, 16, 8))
        self.body.pack(fill="both", expand=True)
        nav = ttk.Frame(self, padding=(16, 0, 16, 14))
        nav.pack(fill="x")
        ttk.Button(nav, text="Close", command=self._close).pack(side="left")
        self.next_btn = ttk.Button(nav, text="Next ›", command=self._next)
        self.next_btn.pack(side="right")
        self.back_btn = ttk.Button(nav, text="‹ Back", command=self._back)
        self.back_btn.pack(side="right", padx=6)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.app.scan_listeners.append(self._scanned)
        self._show()

    # -- navigation -------------------------------------------------------------------
    def _close(self):
        if self._scanned in self.app.scan_listeners:
            self.app.scan_listeners.remove(self._scanned)
        self._apply()
        self.destroy()

    def _show(self):
        for w in self.body.winfo_children():
            w.destroy()
        nxt = f"   Next: {STEPS[self.step + 1]}" if self.step + 1 < len(STEPS) else ""
        self.crumbs.configure(text=f"Step {self.step + 1} of {len(STEPS)}{nxt}")
        self.h1.configure(text=f"{self.step + 1}. {STEPS[self.step]}")
        getattr(self, f"_step{self.step}")(self.body)
        self.back_btn.configure(state="normal" if self.step else "disabled")
        if self.step == len(STEPS) - 1:
            self.next_btn.configure(text="Build now", command=self._build)
        else:
            self.next_btn.configure(text="Next ›", command=self._next)
        self._update_next()

    def _update_next(self):
        ok = True
        if self.step == 0:
            p = self._path()
            ok = bool(p and p.is_file() and p.suffix.lower() in (".docx", ".pdf"))
        if self.step == 5:
            ok = self.scanned and not self.app.busy
        self.next_btn.configure(state="normal" if ok else "disabled")

    def _next(self):
        self._apply()
        if self.step < len(STEPS) - 1:
            self.step += 1
            self._show()

    def _back(self):
        self._apply()
        if self.step:
            self.step -= 1
            self._show()

    def _apply(self):
        """Store this step's choices and show them in the main window."""
        fn = getattr(self, f"_apply{self.step}", None)
        if fn:
            fn()
        SET.save(self.s)
        self.app.sync_from_settings()

    @staticmethod
    def _para(parent, text, fg="#222", pady=(0, 8), wrap=820):
        lbl = ttk.Label(parent, text=text, wraplength=wrap, justify="left", foreground=fg)
        lbl.pack(anchor="w", pady=pady)
        return lbl

    def _path(self) -> Path | None:
        p = self.app.src.get().strip().strip('"')
        return Path(p) if p else None

    # -- 1. the document ------------------------------------------------------------------
    def _step0(self, f):
        self._para(f, "Start with the book. A Word manuscript (.docx) gets an index built into a copy of it, "
                      "with the page numbers read from Word's own layout. A finished PDF gets an index "
                      "written from its printed page numbers. Your file itself is never changed.")
        row = ttk.Frame(f)
        row.pack(fill="x", pady=(4, 10))
        ttk.Entry(row, textvariable=self.app.src).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Choose…", command=self._choose).pack(side="left", padx=6)
        self.check_box = ttk.LabelFrame(f, text="What Indicat sees in it", padding=(10, 6))
        self.check_box.pack(fill="both", expand=True)
        self._check()

    def _choose(self):
        self.app._pick_src()
        self._check()
        self._update_next()

    def _check(self):
        for w in self.check_box.winfo_children():
            w.destroy()
        p = self._path()
        if not p or not p.is_file():
            self._para(self.check_box, "No document chosen yet.", fg="#666")
            return
        self.config(cursor="watch")
        self.update_idletasks()
        try:
            lines = self._doc_facts(p)
        except Exception as exc:                      # a damaged or unusual file: say so, don't stop
            lines = [f"Indicat couldn't read this file: {exc}"]
        finally:
            self.config(cursor="")
        for t in lines:
            self._para(self.check_box, "•  " + t, pady=(0, 3))

    def _doc_facts(self, p: Path) -> list[str]:
        out = []
        if p.suffix.lower() == ".pdf":
            import pdfplumber
            with pdfplumber.open(str(p)) as pdf:
                n = len(pdf.pages)
                sample = [pdf.pages[i] for i in range(0, n, max(1, n // 12))][:12]
                chars = [len(pg.chars) for pg in sample]
                imgs = sum(1 for pg in sample if pg.images and len(pg.chars) > 0 and
                           sum((im["x1"] - im["x0"]) * (im["bottom"] - im["top"]) for im in pg.images)
                           > 0.7 * pg.width * pg.height)
            self.info = {"pdf": True, "pages": n, "ocr": imgs >= len(sample) / 2, "notes": None}
            out.append(f"A PDF of {n} pages.")
            if not any(chars):
                out.append("No text layer was found in the pages sampled. Indicat reads a PDF's text, not its "
                           "images: run the PDF through OCR first (Acrobat: Scan & OCR).")
            elif self.info["ocr"]:
                out.append("It was OCR'd (its text lies over page images). Indicat builds the Scripture index "
                           "and term sets from it, reads common OCR slips (l for 1, ; for :) and flags them, "
                           "and lists pages whose text looks thin or garbled.")
            else:
                out.append("It has a text layer (born digital). Footnotes, running heads and page numbers are "
                           "worked out from the layout when it is scanned.")
            return out
        from . import docx_io as D
        pkg = D.DocxPackage(p)
        words = sum(len(s.text.split()) for s in pkg.body_segments)
        nf = sum(1 for k in pkg.note_segments if k[0] == "footnote")
        ne = sum(1 for k in pkg.note_segments if k[0] == "endnote")
        heads = sum(1 for s in pkg.body_segments if s.heading)
        bib = sum(1 for s in pkg.body_segments if s.biblio)
        self.info = {"pdf": False, "notes": nf + ne, "bib": bib, "xe": pkg.existing_xe}
        out.append(f"A Word document of about {words:,} words, with {heads} headings.")
        out.append(f"{nf} footnotes and {ne} endnotes." if nf or ne else "No footnotes or endnotes.")
        if bib:
            out.append(f"A bibliography ({bib} paragraphs). It is left out of the index unless you choose "
                       "otherwise in the next step.")
        font = pkg.body_font()
        if font:
            out.append(f"The body text is set in {font}; the index will match it.")
        if pkg.existing_xe:
            out.append(f"It already has {pkg.existing_xe} index entries (XE fields). Indicat will remove "
                       "them before adding its own, so nothing is doubled.")
        if pkg.existing_index:
            out.append("It already has an index (INDEX field): delete it before building, or it will be "
                       "rebuilt from the new entries too.")
        out.extend(pkg.warnings[:3])
        return out

    # -- 2. what to index -------------------------------------------------------------------
    def _step1(self, f):
        self._para(f, "Choose the indexes to build. Each becomes its own index at the end of the book.")
        box = ttk.Frame(f)
        box.pack(fill="x")
        self.v_idx = {}
        ocr = self.info.get("ocr")
        v = tk.BooleanVar(value=self.s.get("scripture", True))
        ttk.Checkbutton(box, text="Scripture index", variable=v).grid(row=0, column=0, sticky="w")
        self.v_idx["scripture"] = v
        r = 1
        for d in T.index_defs(self.s, include_disabled=True):
            on = tk.BooleanVar(value=self.app._index_enabled(d.id) and not (ocr and d.kind != "terms"))
            text = d.title + ("" if d.kind == "terms" else "  (every word in that alphabet)")
            cb = ttk.Checkbutton(box, text=text, variable=on)
            if ocr and d.kind != "terms":
                cb.configure(state="disabled", text=text + " — not for OCR'd PDFs")
            cb.grid(row=r, column=0, sticky="w")
            self.v_idx[d.id] = on
            r += 1
        ttk.Button(box, text="Add a term set from a file…", command=self._add_set).grid(row=r, column=0, sticky="w",
                                                                                      pady=(6, 0))
        self._para(f, "A term set is a list of subjects, names or words to index, one per line (or a "
                      "spreadsheet saved as “CSV UTF-8” with headings, subentries and See also). Greek and "
                      "Hebrew words are filed under their dictionary form: λόγου and λόγοις under λόγος.",
                   fg="#555", pady=(6, 10))
        opt = ttk.LabelFrame(f, text="Special cases", padding=(10, 6))
        opt.pack(fill="x")
        self.v_whole = tk.BooleanVar(value=self.s.get("whole_chapters", False))
        ttk.Checkbutton(opt, text="Index references to whole chapters (“Proverbs 5”, “1 Kings 1–11”)",
                        variable=self.v_whole).pack(anchor="w")
        self._para(opt, "Many indexes leave these out because they point to no particular verse.", fg="#555",
                   pady=(0, 6))
        self.v_bib = tk.BooleanVar(value=self.s.get("index_bibliography", False))
        ttk.Checkbutton(opt, text="Index the bibliography", variable=self.v_bib).pack(anchor="w")
        self._para(opt, "Usually off: a commentary title like “Luke 1:1–9:50” is not a reference to Luke. "
                        "Skipped entries still show, in grey, in the review list.", fg="#555", pady=(0, 6))
        self.v_mt = tk.StringVar(value=self.s.get("mt_mode", "label"))
        ttk.Label(opt, text="When a verse is cited in both English and Hebrew numbering (Joel 2:28 [3:1 MT]):").pack(
            anchor="w")
        ttk.Radiobutton(opt, text="Index the Hebrew number too, marked [MT]", value="label",
                        variable=self.v_mt).pack(anchor="w", padx=(16, 0))
        ttk.Radiobutton(opt, text="Index the English number only", value="exclude",
                        variable=self.v_mt).pack(anchor="w", padx=(16, 0))

    def _add_set(self):
        f = filedialog.askopenfilename(parent=self, filetypes=[("Term lists", "*.txt *.csv *.tsv"),
                                                               ("All files", "*.*")])
        if not f:
            return
        entries, problems = T.read_term_file(f)
        if not entries:
            messagebox.showwarning(APP_NAME, "\n".join(problems) or "No terms found.", parent=self)
            return
        if problems:
            messagebox.showinfo(APP_NAME, f"{len(entries)} entries read.\n\n" + "\n".join(problems[:8]), parent=self)
        name = T.clean_set_name(Path(f).stem)
        sets = self.s.setdefault("term_sets", [])
        sets.append({"id": T.new_set_id(sets), "name": name,
                     "title": name if name.lower().startswith("index") else f"Index of {name}", "enabled": True,
                     "options": dict(T.TERM_SET_OPTIONS), "entries": entries, "source": Path(f).name})
        self._apply1()
        self._show()

    def _apply1(self):
        if not hasattr(self, "v_idx"):
            return
        for k, v in self.v_idx.items():
            try:
                self.app.set_index(k, bool(v.get()))
            except tk.TclError:
                pass
        self.s["whole_chapters"] = bool(self.v_whole.get())
        self.s["index_bibliography"] = bool(self.v_bib.get())
        self.s["mt_mode"] = self.v_mt.get()

    # -- 3. language and abbreviations ----------------------------------------------------
    def _step2(self, f):
        self._para(f, "Which language is the book written in? This decides the book names and abbreviations "
                      "Indicat looks for, and the names printed in the index.")
        row = ttk.Frame(f)
        row.pack(fill="x")
        self.lang_names = {PROFILES[c]["name"]: c for c in LANGUAGE_ORDER}
        self.v_lang = ttk.Combobox(row, values=list(self.lang_names), state="readonly", width=30)
        self.v_lang.set(PROFILES.get(self.s.get("language", "en"), PROFILES["en"])["name"])
        self.v_lang.pack(side="left")
        self.v_lang.bind("<<ComboboxSelected>>", lambda e: (self._apply2(), self._show()))
        code = self.s.get("language", "en")
        sets = PROFILES[code].get("sets", {})
        if sets:
            box = ttk.LabelFrame(f, text="Abbreviation styles to recognize", padding=(10, 6))
            box.pack(fill="x", pady=(10, 0))
            disabled = set(self.s.get("languages", {}).get(code, {}).get("disabled_sets", []))
            self.v_sets = {}
            for name in sets:
                v = tk.BooleanVar(value=name not in disabled)
                ttk.Checkbutton(box, text=name, variable=v).pack(anchor="w")
                self.v_sets[name] = v
            self._para(box, "Keep the styles the author uses. An abbreviation from a style that is switched off "
                            "is never guessed from context: it shows in grey with a suggestion (“Ex. → Exodus?”).",
                       fg="#555", pady=(4, 0))
        self.v_ap = tk.BooleanVar(value=self.s.get("apocrypha", False))
        ap = ttk.LabelFrame(f, text="The Apocrypha", padding=(10, 6))
        ap.pack(fill="x", pady=(10, 0))
        ttk.Checkbutton(ap, text="Index the Apocrypha (Tobit, Sirach, 1–2 Maccabees, Wisdom…)",
                        variable=self.v_ap).pack(anchor="w")
        self._para(ap, "Apocrypha references are always recognized, so they are never mistaken for another "
                       "book. With this off they are listed in grey and left out of the index.", fg="#555",
                   pady=(4, 0))
        self._para(f, "Custom books, renamed books and section order are in Edit > Preferences.", fg="#555",
                   pady=(10, 0))

    def _apply2(self):
        if not hasattr(self, "v_lang"):
            return
        try:
            code = self.lang_names[self.v_lang.get()]
        except (KeyError, tk.TclError):
            return
        old = self.s.get("language", "en")
        if hasattr(self, "v_sets") and old == code:
            ls = SET.lang_settings(self.s, code)
            ls["disabled_sets"] = [n for n, v in self.v_sets.items() if not v.get()]
        self.s["language"] = code
        self.s["apocrypha"] = bool(self.v_ap.get())

    # -- 4. look ----------------------------------------------------------------------------
    def _step3(self, f):
        left = ttk.Frame(f)
        left.pack(side="left", fill="y")
        right = ttk.LabelFrame(f, text="Preview", padding=6)
        right.pack(side="left", fill="both", expand=True, padx=(14, 0))
        code = self.s.get("language", "en")
        ttk.Label(left, text="Title:").grid(row=0, column=0, sticky="w")
        self.v_title = tk.StringVar(value=self.app._lang_title(code))
        ttk.Entry(left, textvariable=self.v_title, width=28).grid(row=0, column=1, sticky="w", pady=2)
        ttk.Label(left, text="Layout:").grid(row=1, column=0, sticky="w")
        self.layout_labels = {v: k for k, v in LAYOUTS.items()}
        self.v_layout = ttk.Combobox(left, values=list(self.layout_labels), state="readonly", width=36)
        self.v_layout.set(LAYOUTS.get(self.s.get("index_layout", "single")))
        self.v_layout.grid(row=1, column=1, sticky="w", pady=2)
        ttk.Label(left, text="Columns:").grid(row=2, column=0, sticky="w")
        self.v_cols = tk.IntVar(value=self.s.get("columns", 2))
        ttk.Spinbox(left, from_=1, to=4, textvariable=self.v_cols, width=4,
                    command=self._preview).grid(row=2, column=1, sticky="w", pady=2)
        ttk.Label(left, text="Page numbers:").grid(row=3, column=0, sticky="w")
        self.sep_labels = {v[0]: k for k, v in SEPARATORS.items() if k != "custom"}
        self.v_sep = ttk.Combobox(left, values=list(self.sep_labels), state="readonly", width=36)
        sk = self.s.get("separator", "comma")
        self.v_sep.set(SEPARATORS.get(sk if sk in self.sep_labels.values() else "comma")[0])
        self.v_sep.grid(row=3, column=1, sticky="w", pady=2)
        self.v_newpage = tk.BooleanVar(value=self.s.get("new_page", True))
        ttk.Checkbutton(left, text="Start the index on a new page", variable=self.v_newpage).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(6, 0))
        if not self.info.get("pdf"):
            self.v_font = tk.StringVar(value=self.s.get("index_font", "body"))
            ttk.Label(left, text="Font:").grid(row=5, column=0, sticky="w", pady=(6, 0))
            fr = ttk.Frame(left)
            fr.grid(row=5, column=1, sticky="w", pady=(6, 0))
            ttk.Radiobutton(fr, text="Match the body text", value="body", variable=self.v_font).pack(anchor="w")
            ttk.Radiobutton(fr, text="Use the document's index styles", value="styles",
                            variable=self.v_font).pack(anchor="w")
        ttk.Label(left, text="The preview shows sample entries. Book names follow the language you chose; "
                             "notes are shown as “45n3”.", foreground="#555", wraplength=330,
                  justify="left").grid(row=6, column=0, columnspan=2, sticky="w", pady=(12, 0))
        self.canvas = tk.Canvas(right, background="white", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        for w in (self.v_layout, self.v_sep):
            w.bind("<<ComboboxSelected>>", lambda e: self._preview())
        self.v_title.trace_add("write", lambda *a: self._preview())
        self.v_cols.trace_add("write", lambda *a: self._preview())
        self.canvas.bind("<Configure>", lambda e: self._preview())

    def _preview(self):
        c = getattr(self, "canvas", None)
        if c is None or not c.winfo_exists():
            return
        c.delete("all")
        W = max(200, c.winfo_width())
        try:
            cols = max(1, min(4, int(self.v_cols.get())))
        except (tk.TclError, ValueError):
            cols = 2
        layout = self.layout_labels.get(self.v_layout.get(), "single")
        sep = SEPARATORS[self.sep_labels.get(self.v_sep.get(), "comma")]
        lines = []
        groups = {"single": [("", ("OT", "AP", "NT"))],
                  "testaments": [("Old Testament", ("OT", "AP")), ("New Testament", ("NT",))],
                  "sections": [("Old Testament", ("OT",)), ("Apocrypha", ("AP",)), ("New Testament", ("NT",))]}[layout]
        from .catalog import build_catalog
        cat = build_catalog(PROFILES.get(self.s.get("language", "en"), PROFILES["en"]), self.s)
        ids = {"Genesis": "Gen", "Psalms": "Ps", "Sirach": "Sir", "John": "John", "Romans": "Rom"}
        for gtitle, secs in groups:
            if gtitle:
                lines.append(("group", gtitle))
            for sec, book, refs in SAMPLE:
                if sec not in secs:
                    continue
                if sec == "AP" and not self.s.get("apocrypha"):
                    continue
                try:
                    name = cat.name(ids[book])
                except Exception:
                    name = book
                lines.append(("book", name))
                for lab, pages in refs:
                    lines.append(("entry", (lab, ", ".join(pages))))
        y0 = 12
        c.create_text(12, y0, text=self.v_title.get(), anchor="nw", font=("Georgia", 14, "bold"))
        y0 += 30
        colw = (W - 24 - (cols - 1) * 16) / cols
        per = max(1, -(-len(lines) // cols))
        for k, (kind, val) in enumerate(lines):
            col, row = divmod(k, per)
            x = 12 + col * (colw + 16)
            y = y0 + row * 18
            if kind == "group":
                c.create_text(x, y, text=val, anchor="nw", font=("Georgia", 10, "bold italic"))
            elif kind == "book":
                c.create_text(x, y, text=val, anchor="nw", font=("Georgia", 10, "bold"))
            else:
                lab, pages = val
                if sep[1] == "\t":
                    c.create_text(x + 14, y, text=lab, anchor="nw", font=("Georgia", 10))
                    c.create_text(x + colw - 4, y, text=pages, anchor="ne", font=("Georgia", 10))
                    if sep[2] == "dot":
                        c.create_text(x + 14 + 9 * len(lab), y, text="." * int(max(0, (colw - 30 - 9 * len(lab)
                                                                                       - 7 * len(pages)) / 4)),
                                      anchor="nw", font=("Georgia", 10), fill="#777")
                else:
                    c.create_text(x + 14, y, text=f"{lab}{sep[1]}{pages}", anchor="nw", font=("Georgia", 10))

    def _apply3(self):
        if not hasattr(self, "v_title"):
            return
        try:
            code = self.s.get("language", "en")
            ls = SET.lang_settings(self.s, code)
            t = self.v_title.get().strip()
            if t and t != PROFILES[code]["index_title"]:
                ls["index_title"] = t
            else:
                ls.pop("index_title", None)
            self.s["index_layout"] = self.layout_labels.get(self.v_layout.get(), "single")
            self.s["columns"] = max(1, min(4, int(self.v_cols.get())))
            self.s["separator"] = self.sep_labels.get(self.v_sep.get(), "comma")
            self.s["new_page"] = bool(self.v_newpage.get())
            if hasattr(self, "v_font"):
                self.s["index_font"] = self.v_font.get()
        except (tk.TclError, ValueError):
            pass

    # -- 5. notes ------------------------------------------------------------------------------
    def _step4(self, f):
        pdf = self.info.get("pdf")
        n = self.info.get("notes")
        if pdf:
            self._para(f, "In a PDF, Indicat reads the footnote numbers from the page, so the index can give "
                          "“143n12” for a reference in note 12 on page 143 (Chicago style). A reference that "
                          "is also in the text on the same page gets the page number alone.")
            keys = ("auto", "italic", "bold", "skip")
            cur = self.s.get("pdf_notes_mode", "auto")
        else:
            self._para(f, ("This document has notes. " if n else "This document has no notes, so this choice "
                           "won't matter for it. ") +
                       "Word's own index can't print “143n12” for a reference in a note. Indicat can mark those "
                       "page numbers in italics or bold, which keeps the index live (it updates with F9), or "
                       "finish the index as plain text with the note numbers added or highlighted.")
            keys = ("italic", "bold", "auto", "highlight", "skip")
            cur = self.s.get("footnote_mode", "italic")
        self.v_notes = tk.StringVar(value=cur if cur in keys else keys[0])
        for k in keys:
            extra = ""
            if not pdf and k in ("auto", "highlight"):
                extra = "  — a second, plain-text copy" + ("" if self.app.word else " (needs Microsoft Word)")
            ttk.Radiobutton(f, text=FOOTNOTE_MODES[k] + extra, value=k, variable=self.v_notes).pack(anchor="w",
                                                                                                   pady=2)
        if not pdf:
            self._para(f, "Tip: build with italics while the book is still changing; choose “add the note number” "
                          "for the final pass, once the page layout is settled.", fg="#555", pady=(10, 0))

    def _apply4(self):
        if not hasattr(self, "v_notes"):
            return
        if self.info.get("pdf"):
            self.s["pdf_notes_mode"] = self.v_notes.get()
        else:
            self.s["footnote_mode"] = self.v_notes.get()

    # -- 6. scan and review ---------------------------------------------------------------------
    def _step5(self, f):
        self._para(f, "Indicat now reads the book and lists everything it found. Nothing is built yet: you "
                      "check the list first.")
        ttk.Button(f, text="Scan now", command=self._scan).pack(anchor="w", pady=(0, 10))
        self.scan_box = ttk.Frame(f)
        self.scan_box.pack(fill="both", expand=True)
        if self.scanned and self.app.result is not None:
            self._coach(self.app.result)

    def _scan(self):
        self.scanned = False
        self._update_next()
        for w in self.scan_box.winfo_children():
            w.destroy()
        self._para(self.scan_box, "Scanning… the progress bar at the foot of the main window shows how far it "
                                  "has got.", fg="#555")
        self.app._scan()

    def _scanned(self, res):
        if not self.winfo_exists():
            return
        self.scanned = True
        if self.step == 5:
            for w in self.scan_box.winfo_children():
                w.destroy()
            self._coach(res)
            self._update_next()

    def _coach(self, res):
        from .gui import REVIEW_STATUSES
        occ = res.occurrences
        inc = sum(1 for o in occ if o.include)
        yellow = sum(1 for o in occ if o.include and o.status in REVIEW_STATUSES)
        grey = len(occ) - inc
        sug = sum(1 for o in occ if o.status == "unknown-book")
        pages = [p for p in getattr(getattr(res, "pdf", None), "pages", []) if p.flag]
        f = self.scan_box
        self._para(f, f"Found {len(occ):,}: {inc:,} will be indexed and {grey:,} are left out.",
                   pady=(0, 6)).configure(font=("Segoe UI", 10, "bold"))
        tips = [f"Yellow rows ({yellow}) are indexed but worth a look: the book came from earlier in the text, "
                "or a name needs checking (“3 Kings” = 1 Kings), or a verse is in Hebrew numbering. Sort by "
                "“How found” to take them in batches.",
                "Grey rows are left out: verses with no chapter, whole chapters, titles in italics, "
                "volume:page citations, quotations, the bibliography. Double-click one to include it."]
        if sug:
            tips.append(f"{sug} reference(s) follow a word that isn't a book name Indicat knows. These are never "
                        "guessed: look for a suggestion such as “Ex. → Exodus?” and use Edit to fix them.")
        if pages:
            tips.append(f"{len(pages)} page(s) of the PDF have missing, thin or garbled text. They are listed in "
                        "the Messages box: check those pages by eye.")
        tips.append("Click a column heading to sort by it (Entry sorts in Bible order); the filters above the "
                    "list combine.")
        for t in tips:
            self._para(f, "•  " + t, pady=(0, 4))

    # -- 7. build ---------------------------------------------------------------------------------
    def _step6(self, f):
        s = self.s
        code = s.get("language", "en")
        idx = ["Scripture"] if s.get("scripture", True) else []
        idx += [d.title for d in T.index_defs(s)]
        sep = SEPARATORS.get(s.get("separator", "comma"), SEPARATORS["comma"])[0].split("  ")[0]
        notes = (s.get("pdf_notes_mode", "auto") if self.info.get("pdf") else s.get("footnote_mode", "italic"))
        out = self.app.default_out() or "(you'll be asked)"
        rows = [("Document", str(self._path() or "")),
                ("Indexes", ", ".join(idx) or "none"),
                ("Language", PROFILES[code]["name"]),
                ("Apocrypha", "indexed" if s.get("apocrypha") else "recognized, not indexed"),
                ("Whole chapters", "indexed" if s.get("whole_chapters") else "left out"),
                ("Bibliography", "indexed" if s.get("index_bibliography") else "left out"),
                ("Hebrew numbering", "indexed, marked [MT]" if s.get("mt_mode", "label") == "label" else "left out"),
                ("Look", f"{self.app._lang_title(code)}; {LAYOUTS[s.get('index_layout', 'single')].lower()}; "
                         f"{s.get('columns', 2)} column(s); {sep}"),
                ("Notes", FOOTNOTE_MODES.get(notes, notes)),
                ("Saved to", out)]
        g = ttk.Frame(f)
        g.pack(fill="x")
        for i, (k, v) in enumerate(rows):
            ttk.Label(g, text=k + ":", font=("Segoe UI", 9, "bold")).grid(row=i, column=0, sticky="nw", pady=2)
            ttk.Label(g, text=v, wraplength=640, justify="left").grid(row=i, column=1, sticky="w", padx=(10, 0),
                                                                      pady=2)
        self._para(f, "Build now, or close this window to go through the list in the main window first and "
                      "click Build index when you're ready. These settings stay as they are for next time.",
                   fg="#555", pady=(14, 0))

    def _build(self):
        self._close()
        self.app._build()
