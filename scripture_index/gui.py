"""Tkinter GUI for Scripture Index Builder."""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import APP_NAME, __version__
from . import settings as SET
from . import updates
from .dialogs import AddRefDialog, EditDialog, SettingsDialog
from .parser import INDEXED_STATUSES, STATUS_LABELS
from .pipeline import (FINAL_MODES, FOOTNOTE_MODES, LIVE_MODES, SEPARATORS, BuildOptions,
                       build, check_custom_separator, find_text, make_static, manual_occurrence, scan)
from .profiles import LANGUAGE_ORDER, PROFILES

REVIEW_STATUSES = {"inferred", "inferred-weak"}
LAYOUTS = {"single": "One index", "testaments": "Old and New Testament (Apocrypha with OT)",
           "sections": "By section (OT, Apocrypha, NT, Other)"}
# settings that change what the scan finds (a new scan is needed after changing them)
SCAN_KEYS = ("language", "apocrypha", "custom_books", "languages")


def load_settings() -> dict:
    return SET.load()


def save_settings(d: dict) -> None:
    SET.save(d)


def word_ok() -> bool:
    from . import word_com
    return word_com.available()


def _center(win, master):
    win.update_idletasks()
    x = master.winfo_rootx() + (master.winfo_width() - win.winfo_width()) // 2
    y = master.winfo_rooty() + (master.winfo_height() - win.winfo_height()) // 3
    win.geometry(f"+{max(x, 0)}+{max(y, 0)}")


# ---------------------------------------------------------------------------
class FootnoteDialog(tk.Toplevel):
    def __init__(self, master, n_refs: int, n_notes: int, current: str, word: bool):
        super().__init__(master)
        self.title("References in notes")
        self.resizable(False, False)
        self.transient(master)
        self.result = None
        frm = ttk.Frame(self, padding=16)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=f"{n_refs} Scripture references were found in {n_notes} footnotes/endnotes.",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(frm, wraplength=560, justify="left", text=(
            "Word's index can't print note locators like “33n12” by itself. Choose how page numbers "
            "for references in notes should appear.")).pack(anchor="w", pady=(4, 10))
        self.var = tk.StringVar(value=current if current in FOOTNOTE_MODES else "italic")
        live = ttk.LabelFrame(frm, text="Index stays live", padding=(10, 6))
        live.pack(fill="x")
        ttk.Label(live, wraplength=540, justify="left", foreground="#444", text=(
            "The index is a Word field: after later edits, select it and press F9 and it rebuilds "
            "with the new page numbers.")).pack(anchor="w", pady=(0, 4))
        for key in LIVE_MODES:
            ttk.Radiobutton(live, text=FOOTNOTE_MODES[key], value=key,
                            variable=self.var).pack(anchor="w", pady=2)
        final = ttk.LabelFrame(frm, text="Final step: index becomes plain text", padding=(10, 6))
        final.pack(fill="x", pady=(10, 0))
        ttk.Label(final, wraplength=540, justify="left", foreground="#444", text=(
            "You get two copies: one with a live index, and a “(final)” copy whose index is plain "
            "text with the note page numbers marked or completed. The final copy won't update, so "
            "choose these once the layout is settled.")).pack(anchor="w", pady=(0, 4))
        for key in FINAL_MODES:
            state = "normal" if word else "disabled"
            text = FOOTNOTE_MODES[key] + ("" if word else "  (needs Microsoft Word)")
            ttk.Radiobutton(final, text=text, value=key, variable=self.var,
                            state=state).pack(anchor="w", pady=2)
        btns = ttk.Frame(frm)
        btns.pack(fill="x", pady=(14, 0))
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(btns, text="Build", command=self._ok).pack(side="right", padx=6)
        _center(self, master)
        self.grab_set()
        self.wait_visibility()
        self.focus_set()

    def _ok(self):
        self.result = self.var.get()
        self.destroy()


class StaticDialog(tk.Toplevel):
    """Options for turning a checked, live index into a plain-text one."""

    def __init__(self, master, initial: str, word: bool):
        super().__init__(master)
        self.title("Make a static-index copy")
        self.resizable(False, False)
        self.transient(master)
        self.result = None
        frm = ttk.Frame(self, padding=16)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, wraplength=560, justify="left", text=(
            "Use this once you've checked the live index. The tool opens the indexed document "
            "read-only and saves a new copy, “… (static index).docx”, whose index is plain text "
            "with the note page numbers completed (33n12) or highlighted. The index entry fields "
            "in the text stay where they are, and the document you choose is not changed.")).pack(
            anchor="w", pady=(0, 10))
        row = ttk.Frame(frm)
        row.pack(fill="x")
        ttk.Label(row, text="Indexed document:").pack(side="left")
        self.path = tk.StringVar(value=initial)
        ttk.Entry(row, textvariable=self.path, width=52).pack(side="left", padx=6, fill="x", expand=True)
        ttk.Button(row, text="Browse…", command=self._browse).pack(side="left")
        box = ttk.LabelFrame(frm, text="Note page numbers", padding=(10, 6))
        box.pack(fill="x", pady=(10, 0))
        self.mode = tk.StringVar(value="auto")
        ttk.Radiobutton(box, text="Add the note number (e.g. 33n12)", value="auto",
                        variable=self.mode).pack(anchor="w")
        ttk.Radiobutton(box, text="Highlight them, so n# can be added by hand", value="highlight",
                        variable=self.mode).pack(anchor="w")
        mrow = ttk.Frame(box)
        mrow.pack(fill="x", pady=(6, 0))
        ttk.Label(mrow, text="In the live index they are marked with:").pack(side="left")
        self.marker_labels = {"Detect automatically": "auto", "Bold": "Bold", "Italics": "Italic",
                              "Nothing (match by page)": "none"}
        self.marker = ttk.Combobox(mrow, values=list(self.marker_labels), state="readonly", width=24)
        self.marker.set("Detect automatically")
        self.marker.pack(side="left", padx=6)
        self.update_first = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm, text="Update the index from the document first", variable=self.update_first).pack(
            anchor="w", pady=(10, 0))
        ttk.Label(frm, wraplength=560, justify="left", foreground="#444", text=(
            "Leave this off if you've corrected the index by hand: updating rebuilds it from the "
            "entry fields and would undo those corrections.")).pack(anchor="w")
        btns = ttk.Frame(frm)
        btns.pack(fill="x", pady=(14, 0))
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right")
        ok = ttk.Button(btns, text="Make static copy", command=self._ok,
                        state="normal" if word else "disabled")
        ok.pack(side="right", padx=6)
        if not word:
            ttk.Label(btns, text="Needs Microsoft Word.", foreground="#a00").pack(side="left")
        _center(self, master)
        self.grab_set()

    def _browse(self):
        f = filedialog.askopenfilename(parent=self, filetypes=[("Word documents", "*.docx")])
        if f:
            self.path.set(f)

    def _ok(self):
        p = self.path.get().strip().strip('"')
        if not p or not Path(p).is_file():
            messagebox.showwarning("Make a static-index copy", "Choose the indexed .docx file.", parent=self)
            return
        self.result = (p, self.mode.get(), self.marker_labels[self.marker.get()], bool(self.update_first.get()))
        self.destroy()


# ---------------------------------------------------------------------------
class App(tk.Tk):
    FILTERS = ["All", "Indexed", "Check: book from context", "Not indexed", "In notes"]

    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} {__version__}")
        self.geometry("1180x760")
        self.minsize(900, 600)
        self.settings = load_settings()
        self.q: queue.Queue = queue.Queue()
        self.result = None
        self.busy = False
        self.word = word_ok()
        self._build_ui()
        self.pkg = None
        self.after(100, self._poll)
        if self.settings.get("check_updates", True) and updates.configured():
            self.after(1500, lambda: self._check_updates(True))

    # -- layout -------------------------------------------------------------------
    def _build_ui(self):
        style = ttk.Style(self)
        try:
            style.theme_use("vista" if sys.platform == "win32" else "clam")
        except tk.TclError:
            pass
        menubar = tk.Menu(self)
        tools = tk.Menu(menubar, tearoff=0)
        tools.add_command(label="Settings (languages, abbreviations, sections, custom books)…",
                          command=self._settings_dialog)
        tools.add_command(label="Export settings…", command=self._export_settings)
        tools.add_command(label="Import settings…", command=self._import_settings)
        tools.add_separator()
        tools.add_command(label="Export InDesign script (.jsx)…", command=self._export_jsx)
        tools.add_command(label="Make a static-index copy of a checked document…", command=self._static)
        menubar.add_cascade(label="Tools", menu=tools)
        helpm = tk.Menu(menubar, tearoff=0)
        helpm.add_command(label="Check for updates…", command=lambda: self._check_updates(False))
        helpm.add_command(label="How it works", command=self._help)
        helpm.add_command(label=f"About {APP_NAME}", command=self._about)
        menubar.add_cascade(label="Help", menu=helpm)
        self.config(menu=menubar)

        top = ttk.Frame(self, padding=(10, 10, 10, 4))
        top.pack(fill="x")
        ttk.Label(top, text="Manuscript (.docx):").grid(row=0, column=0, sticky="w")
        self.src = tk.StringVar(value=self.settings.get("last_file", ""))
        ttk.Entry(top, textvariable=self.src).grid(row=0, column=1, sticky="we", padx=6)
        ttk.Button(top, text="Browse…", command=self._pick_src).grid(row=0, column=2)
        ttk.Button(top, text="Scan", command=self._scan).grid(row=0, column=3, padx=(6, 0))
        ttk.Label(top, text="Save results to:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.out = tk.StringVar(value=self.settings.get("out_dir", ""))
        ttk.Entry(top, textvariable=self.out).grid(row=1, column=1, sticky="we", padx=6, pady=(6, 0))
        ttk.Button(top, text="Browse…", command=self._pick_out).grid(row=1, column=2, pady=(6, 0))
        ttk.Label(top, text="(blank = same folder as the manuscript)", foreground="#666").grid(
            row=1, column=3, sticky="w", padx=(6, 0), pady=(6, 0))
        top.columnconfigure(1, weight=1)

        opts = ttk.LabelFrame(self, text="Index options", padding=(10, 6))
        opts.pack(fill="x", padx=10, pady=4)
        s = self.settings
        ttk.Label(opts, text="Heading:").grid(row=0, column=0, sticky="w")
        self.heading = tk.StringVar(value=self._lang_title(s.get("language", "en")))
        ttk.Entry(opts, textvariable=self.heading, width=22).grid(row=0, column=1, sticky="w", padx=(4, 16))
        ttk.Label(opts, text="Columns:").grid(row=0, column=2, sticky="w")
        self.cols = tk.IntVar(value=s.get("columns", 2))
        ttk.Spinbox(opts, from_=1, to=4, textvariable=self.cols, width=4).grid(row=0, column=3, sticky="w", padx=(4, 16))
        ttk.Label(opts, text="Page Number Separation:").grid(row=2, column=0, sticky="w", pady=(6, 0))
        sep_key = s.get("separator", "comma")
        if sep_key not in SEPARATORS:
            sep_key = "comma"
        self.sep_labels = {v[0]: k for k, v in SEPARATORS.items()}
        self.sep = ttk.Combobox(opts, values=list(self.sep_labels), state="readonly", width=40)
        self.sep.set(SEPARATORS[sep_key][0])
        self.sep.grid(row=2, column=1, columnspan=3, sticky="w", padx=(4, 6), pady=(6, 0))
        self.sep.bind("<<ComboboxSelected>>", lambda e: self._sep_changed())
        self.custom_sep = tk.StringVar(value=s.get("custom_separator", " \u2014\u2014 "))
        self.custom_entry = ttk.Entry(opts, textvariable=self.custom_sep, width=8)
        self.custom_entry.grid(row=2, column=4, sticky="w", pady=(6, 0))
        self._sep_changed()
        self.new_page = tk.BooleanVar(value=s.get("new_page", True))
        ttk.Checkbutton(opts, text="Start the index on a new page", variable=self.new_page).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))
        self.remove_xe = tk.BooleanVar(value=False)
        self.remove_xe_cb = ttk.Checkbutton(opts, text="Remove existing index entries (XE fields) first",
                                            variable=self.remove_xe)
        self.remove_xe_cb.grid(row=3, column=2, columnspan=3, sticky="w", pady=(6, 0))
        ttk.Label(opts, text="Language:").grid(row=0, column=4, sticky="w")
        self.lang_names = {PROFILES[c]["name"]: c for c in LANGUAGE_ORDER}
        self.lang = ttk.Combobox(opts, values=list(self.lang_names), state="readonly", width=24)
        self.lang.set(PROFILES.get(s.get("language", "en"), PROFILES["en"])["name"])
        self.lang.grid(row=0, column=5, sticky="w", padx=(4, 16))
        self.lang.bind("<<ComboboxSelected>>", lambda e: self._lang_changed())
        ttk.Label(opts, text="Index layout:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.layout_labels = {v: k for k, v in LAYOUTS.items()}
        self.layout = ttk.Combobox(opts, values=list(self.layout_labels), state="readonly", width=40)
        self.layout.set(LAYOUTS.get(s.get("index_layout", "single"), LAYOUTS["single"]))
        self.layout.grid(row=1, column=1, columnspan=3, sticky="w", padx=(4, 16), pady=(6, 0))
        self.layout.bind("<<ComboboxSelected>>", lambda e: self._store_opts())
        self.apoc = tk.BooleanVar(value=s.get("apocrypha", False))
        ttk.Checkbutton(opts, text="Recognize the Apocrypha", variable=self.apoc,
                        command=self._scan_settings_changed).grid(row=1, column=4, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Button(opts, text="Settings…", command=self._settings_dialog).grid(row=1, column=5, sticky="e",
                                                                              pady=(6, 0))
        self.use_word = tk.BooleanVar(value=self.word and s.get("use_word", True))
        ttk.Checkbutton(opts, text="Open the copy in Word to build the index and read page numbers" +
                        ("" if self.word else " (Word not found)"), variable=self.use_word,
                        state="normal" if self.word else "disabled").grid(row=4, column=0, columnspan=6,
                                                                          sticky="w", pady=(6, 0))

        mid = ttk.Frame(self, padding=(10, 4))
        mid.pack(fill="both", expand=True)
        bar = ttk.Frame(mid)
        bar.pack(fill="x")
        ttk.Label(bar, text="Show:").pack(side="left")
        self.filter = ttk.Combobox(bar, values=self.FILTERS, state="readonly", width=26)
        self.filter.set("All")
        self.filter.pack(side="left", padx=(4, 12))
        self.filter.bind("<<ComboboxSelected>>", lambda e: self._fill())
        ttk.Button(bar, text="Include", command=lambda: self._set_include(True)).pack(side="left")
        ttk.Button(bar, text="Exclude", command=lambda: self._set_include(False)).pack(side="left", padx=4)
        ttk.Button(bar, text="Edit reference…", command=self._edit).pack(side="left")
        ttk.Button(bar, text="Add reference…", command=self._add_ref).pack(side="left", padx=4)

        self.build_btn = ttk.Button(bar, text="Build index…", command=self._build, state="disabled")
        self.build_btn.pack(side="right")
        ttk.Button(bar, text="Make static copy…", command=self._static).pack(side="right", padx=6)
        self.summary = ttk.Label(mid, text="Choose a manuscript and click Scan.", foreground="#333")
        self.summary.pack(anchor="w", pady=(4, 0))

        cols = ("inc", "ref", "how", "where", "context")
        tv = ttk.Treeview(mid, columns=cols, show="headings", selectmode="extended")
        for c, t, wd, st in (("inc", "Index", 50, False), ("ref", "Reference", 170, False),
                             ("how", "How the book was found", 190, False), ("where", "Where", 100, False),
                             ("context", "Context", 600, True)):
            tv.heading(c, text=t)
            tv.column(c, width=wd, stretch=st, anchor="w")
        tv.tag_configure("excluded", foreground="#888888")
        tv.tag_configure("check", background="#FFF4C2")
        tv.tag_configure("note", foreground="#1F4E8C")
        ys = ttk.Scrollbar(mid, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=ys.set)
        tv.pack(side="left", fill="both", expand=True, pady=(6, 0))
        ys.pack(side="left", fill="y", pady=(6, 0))
        tv.bind("<Double-1>", lambda e: self._toggle())
        tv.bind("<space>", lambda e: self._toggle())
        self.tv = tv

        logf = ttk.LabelFrame(self, text="Messages", padding=(6, 4))
        logf.pack(fill="x", padx=10, pady=(4, 10))
        self.log = tk.Text(logf, height=7, wrap="word", font=("Consolas", 9), state="disabled")
        self.log.pack(fill="x")

    # -- helpers -----------------------------------------------------------------
    def _say(self, msg: str):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _sep_key(self) -> str:
        return self.sep_labels.get(self.sep.get(), "comma")

    def _sep_changed(self):
        if self._sep_key() == "custom":
            self.custom_entry.configure(state="normal")
            self.custom_entry.focus_set()
        else:
            self.custom_entry.configure(state="disabled")

    def _pick_src(self):
        f = filedialog.askopenfilename(filetypes=[("Word documents", "*.docx")])
        if f:
            self.src.set(f)

    def _pick_out(self):
        d = filedialog.askdirectory()
        if d:
            self.out.set(d)

    def _run(self, fn, done):
        if self.busy:
            return
        self.busy = True
        self.config(cursor="watch")

        def worker():
            try:
                r = fn()
                self.q.put(("done", done, r))
            except Exception as exc:
                self.q.put(("error", f"{exc}\n\n{traceback.format_exc()}"))
        threading.Thread(target=worker, daemon=True).start()

    def _poll(self):
        try:
            while True:
                item = self.q.get_nowait()
                if item[0] == "log":
                    self._say(item[1])
                elif item[0] == "call":
                    item[1](item[2])
                elif item[0] == "done":
                    self.busy = False
                    self.config(cursor="")
                    item[1](item[2])
                elif item[0] == "error":
                    self.busy = False
                    self.config(cursor="")
                    self._say("ERROR: " + item[1].splitlines()[0])
                    messagebox.showerror(APP_NAME, item[1][:2000])
        except queue.Empty:
            pass
        self.after(100, self._poll)

    # -- scan --------------------------------------------------------------------
    def _scan(self):
        p = self.src.get().strip().strip('"')
        if not p or not Path(p).is_file():
            messagebox.showwarning(APP_NAME, "Choose a .docx manuscript first.")
            return
        if Path(p).name.startswith("~$"):
            messagebox.showwarning(APP_NAME, "That is Word's temporary lock file; choose the real document.")
            return
        self._say(f"Scanning {Path(p).name}…")
        self._store_opts()
        snap = __import__("copy").deepcopy(self.settings)
        self._run(lambda: scan(p, snap), self._scan_done)

    def _scan_done(self, res_pkg):
        res, self.pkg = res_pkg
        self.result = res
        for wmsg in res.warnings:
            self._say("Warning: " + wmsg)
        self.remove_xe.set(res.existing_xe > 0)
        c = res.counts()
        inc = sum(1 for o in res.occurrences if o.include)
        chk = sum(1 for o in res.occurrences if o.include and o.status in REVIEW_STATUSES)
        self.summary.configure(text=f"{len(res.occurrences)} found · {inc} to index · "
                                    f"{chk} with book from context · {len(res.occurrences) - inc} not indexed")
        self._say("Scan complete: " + ", ".join(f"{STATUS_LABELS.get(k, k)} {v}" for k, v in c.items()))
        self.build_btn.configure(state="normal")
        self._fill()

    def _visible(self, o) -> bool:
        f = self.filter.get()
        if f == "Indexed":
            return o.include
        if f == "Check: book from context":
            return o.include and o.status in REVIEW_STATUSES
        if f == "Not indexed":
            return not o.include
        if f == "In notes":
            return o.in_note
        return True

    def _fill(self):
        self.tv.delete(*self.tv.get_children())
        if not self.result:
            return
        for i, o in enumerate(self.result.occurrences):
            if not self._visible(o):
                continue
            tags = []
            if not o.include:
                tags.append("excluded")
            elif o.status in REVIEW_STATUSES or o.edited:
                tags.append("check")
            if o.in_note:
                tags.append("note")
            self.tv.insert("", "end", iid=str(i), tags=tags, values=(
                "✔" if o.include else "", o.display, o.status_label, o.where,
                o.context.replace("⟦", "[").replace("⟧", "]")))

    def _selected(self):
        return [self.result.occurrences[int(i)] for i in self.tv.selection()] if self.result else []

    def _set_include(self, val: bool):
        sel = self._selected()
        bad = [o for o in sel if val and o.ref is None]
        for o in sel:
            if val and o.ref is None:
                continue
            o.include = val
        if bad:
            messagebox.showinfo(APP_NAME, "Some selected rows have no book yet. Use “Edit reference…” "
                                          "to give them a book, then include them.")
        keep = self.tv.selection()
        self._fill()
        self.tv.selection_set([k for k in keep if self.tv.exists(k)])

    def _toggle(self):
        sel = self._selected()
        if len(sel) == 1:
            o = sel[0]
            if o.ref is None:
                self._edit()
                return
            self._set_include(not o.include)

    def _edit(self):
        sel = self._selected()
        if len(sel) != 1:
            messagebox.showinfo(APP_NAME, "Select one row to edit.")
            return
        o = sel[0]
        d = EditDialog(self, o, self.result.catalog)
        self.wait_window(d)
        if d.result is not None:
            o.ref = d.result
            o.edited = True
            o.include = True
            if o.status not in INDEXED_STATUSES:
                o.status = "explicit"
            self._fill()
            if self.tv.exists(str(self.result.occurrences.index(o))):
                self.tv.selection_set(str(self.result.occurrences.index(o)))

    # -- build -------------------------------------------------------------------
    def _build(self):
        if not self.result:
            return
        self._store_opts()
        if any(self.result.settings.get(k) != self.settings.get(k) for k in SCAN_KEYS):
            if messagebox.askyesno(APP_NAME, "The language, Apocrypha or book settings changed since the "
                                   "last scan. Scan again now? (Your include/exclude choices will be reset.)"):
                self._scan()
            return
        key = self._sep_key()
        if key == "custom":
            sep_text, leader = self.custom_sep.get(), None
            err = check_custom_separator(sep_text)
            if err:
                messagebox.showwarning(APP_NAME, f"Custom page number separation: {err}")
                return
        else:
            _, sep_text, leader = SEPARATORS[key]
        note_refs = [o for o in self.result.occurrences if o.in_note and o.include]
        mode = self.settings.get("footnote_mode", "italic")
        use_word = bool(self.use_word.get())
        if note_refs:
            notes = {(o.note_kind, o.note_ordinal) for o in note_refs}
            d = FootnoteDialog(self, len(note_refs), len(notes), mode, use_word)
            self.wait_window(d)
            if d.result is None:
                return
            mode = d.result
        src = Path(self.src.get().strip().strip('"'))
        out = Path(self.out.get().strip()) if self.out.get().strip() else src.parent
        opts = BuildOptions(out_dir=out, heading=self.heading.get().strip(),
                            settings=__import__("copy").deepcopy(self.settings),
                            columns=max(1, min(4, int(self.cols.get() or 2))),
                            separator=sep_text, leader=leader,
                            new_page=bool(self.new_page.get()), footnote_mode=mode,
                            remove_existing_xe=bool(self.remove_xe.get()), use_word=use_word)
        self.settings.update(last_file=str(src), out_dir=self.out.get().strip(),
                             columns=opts.columns, separator=key, custom_separator=self.custom_sep.get(),
                             new_page=opts.new_page,
                             footnote_mode=mode, use_word=use_word)
        save_settings(self.settings)
        self._say("Building…")
        res = self.result
        self._run(lambda: build(res, opts, log=lambda m: self.q.put(("log", m))), self._build_done)

    # -- language / settings -------------------------------------------------------
    def _lang_code(self) -> str:
        return self.lang_names.get(self.lang.get(), "en")

    def _lang_title(self, code: str) -> str:
        ls = self.settings.get("languages", {}).get(code, {})
        return ls.get("index_title") or PROFILES.get(code, PROFILES["en"])["index_title"]

    def _store_opts(self):
        code = self._lang_code()
        self.settings["language"] = code
        self.settings["apocrypha"] = bool(self.apoc.get())
        self.settings["index_layout"] = self.layout_labels.get(self.layout.get(), "single")
        title = self.heading.get().strip()
        ls = SET.lang_settings(self.settings, code)
        if title and title != PROFILES[code]["index_title"]:
            ls["index_title"] = title
        else:
            ls.pop("index_title", None)
        save_settings(self.settings)

    def _lang_changed(self):
        old = self.settings.get("language", "en")
        # keep the heading the user typed for the old language
        t = self.heading.get().strip()
        ls = SET.lang_settings(self.settings, old)
        if t and t != PROFILES[old]["index_title"]:
            ls["index_title"] = t
        code = self._lang_code()
        self.settings["language"] = code
        self.heading.set(self._lang_title(code))
        self._scan_settings_changed()

    def _scan_settings_changed(self):
        self._store_opts()
        if self.result is not None:
            self._say("Settings changed: scan again to apply them.")

    def _settings_dialog(self):
        self._store_opts()
        d = SettingsDialog(self, self.settings)
        self.wait_window(d)
        if d.result is not None:
            self.settings = d.result
            save_settings(self.settings)
            self.lang.set(PROFILES.get(self.settings.get("language", "en"), PROFILES["en"])["name"])
            self.apoc.set(self.settings.get("apocrypha", False))
            self.layout.set(LAYOUTS.get(self.settings.get("index_layout", "single"), LAYOUTS["single"]))
            self.heading.set(self._lang_title(self.settings.get("language", "en")))
            self._scan_settings_changed()

    def _export_settings(self):
        self._store_opts()
        f = filedialog.asksaveasfilename(defaultextension=".json",
                                         initialfile="Scripture Index Builder settings.json",
                                         filetypes=[("Settings", "*.json")])
        if f:
            SET.export_to(self.settings, f)
            self._say(f"Settings exported to {f}")

    def _import_settings(self):
        f = filedialog.askopenfilename(filetypes=[("Settings", "*.json")])
        if not f:
            return
        try:
            self.settings = SET.import_from(self.settings, f)
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Could not read that file: {exc}")
            return
        save_settings(self.settings)
        self.lang.set(PROFILES.get(self.settings.get("language", "en"), PROFILES["en"])["name"])
        self.apoc.set(self.settings.get("apocrypha", False))
        self.layout.set(LAYOUTS.get(self.settings.get("index_layout", "single"), LAYOUTS["single"]))
        self.heading.set(self._lang_title(self.settings.get("language", "en")))
        self._say(f"Settings imported from {f}")
        self._scan_settings_changed()

    def _export_jsx(self):
        from . import jsx
        self._store_opts()
        f = filedialog.asksaveasfilename(defaultextension=".jsx", initialfile="Scripture Index Builder.jsx",
                                         filetypes=[("InDesign script", "*.jsx")])
        if not f:
            return
        try:
            jsx.write_script(f, self.settings)
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Could not write the script: {exc}")
            return
        self._say(f"InDesign script saved: {f}")
        messagebox.showinfo(APP_NAME, "InDesign script saved.\n\nIn InDesign, open Window > Utilities > "
                            "Scripts, right-click the User folder and choose Reveal in Explorer, copy the "
                            ".jsx file there, then double-click it in the Scripts panel with your document "
                            "open. Your current language, abbreviation and custom-book settings are built "
                            "into the script.")

    # -- add reference ------------------------------------------------------------
    def _add_ref(self):
        if not self.result or getattr(self, "pkg", None) is None:
            messagebox.showinfo(APP_NAME, "Scan a manuscript first.")
            return
        d = AddRefDialog(self, self.pkg, self.result.catalog, find_text)
        self.wait_window(d)
        if d.result:
            place, ref = d.result
            occ = manual_occurrence(self.result, place, ref)
            self.result.occurrences.append(occ)
            self.result.occurrences.sort(key=lambda o: (o.seq if not o.uid.startswith("manual:") else
                                                        self._manual_seq(o)))
            self._fill()
            self._say(f"Added {ref.display()} by hand.")

    def _manual_seq(self, o):
        # place a manual entry next to the nearest scanned reference in the same paragraph
        near = [x.seq for x in self.result.occurrences
                if not x.uid.startswith("manual:") and x.part == o.part and x.seg_idx == o.seg_idx
                and x.start <= o.start]
        return (max(near) + 0.5) if near else o.seq

    # -- updates ---------------------------------------------------------------------
    def _check_updates(self, quiet: bool):
        def work():
            return updates.check()

        def done(r):
            st = r.get("status")
            if st == "newer":
                if messagebox.askyesno(APP_NAME, f"Version {r['latest']} is available (you have "
                                       f"{__version__}). Open the download page?"):
                    import webbrowser
                    webbrowser.open(r.get("url") or "")
            elif not quiet:
                msg = {"current": f"You have the latest version ({__version__}).",
                       "unconfigured": "Update checking will start working once the project is published "
                                       "on GitHub.",
                       "error": f"Couldn't check for updates: {r.get('error', '')}"}.get(st, str(r))
                messagebox.showinfo(APP_NAME, msg)
        if quiet:
            threading.Thread(target=lambda: self.q.put(("call", done, work())), daemon=True).start()
        else:
            self._run(work, done)

    def _static(self):
        d = StaticDialog(self, self.settings.get("last_indexed", ""), self.word)
        self.wait_window(d)
        if not d.result:
            return
        path, mode, marker, upd = d.result
        out = self.out.get().strip() or None
        self._say(f"Making a static-index copy of {Path(path).name}…")
        self._run(lambda: make_static(path, out, mode, marker, upd, log=lambda m: self.q.put(("log", m))),
                  self._static_done)

    def _static_done(self, res):
        out, msgs = res
        for m in msgs:
            self._say("Note: " + m)
        self._say(f"Done. Static copy: {out.name}")
        if messagebox.askyesno(APP_NAME, "Finished. Open the folder with the static copy?"):
            folder = str(out.parent)
            if sys.platform == "win32":
                os.startfile(folder)
            else:
                subprocess.Popen(["xdg-open", folder])

    def _build_done(self, r):
        self.settings["last_indexed"] = str(r.indexed_docx)
        save_settings(self.settings)
        for m in r.messages:
            self._say("Note: " + m)
        self._say(f"Done. Indexed copy (live index): {r.indexed_docx.name}")
        if r.final_docx:
            self._say(f"Finalized copy (plain-text index): {r.final_docx.name}")
        self._say(f"Proofreading list: {r.proof_docx.name}")
        if messagebox.askyesno(APP_NAME, "Finished. Open the folder with the results?"):
            folder = str(r.indexed_docx.parent)
            if sys.platform == "win32":
                os.startfile(folder)
            else:
                subprocess.Popen(["xdg-open", folder])

    # -- help --------------------------------------------------------------------
    def _help(self):
        messagebox.showinfo("How it works", (
            "0. Choose the language, the index layout and whether to recognize the Apocrypha. "
            "Tools > Settings holds abbreviations, section order and headings, and custom books.\n\n"
            "1. Scan finds every Scripture reference, including bare references like “(5:17)” whose "
            "book comes from earlier text.\n\n"
            "2. Review the list. Yellow rows took their book from context. Grey rows will not be "
            "indexed (verse-only, chapter-only, possible titles, volume:page citations). Double-click "
            "a row to include or exclude it, use Edit to correct it, or Add reference for one the "
            "scan missed.\n\n"
            "3. Build writes a COPY of the manuscript with an index entry field after each reference "
            "and the index at the end, then (if Word is available) lets Word lay it out and reads the "
            "page number of every reference.\n\n"
            "4. The proofreading list (.docx and .csv) shows every indexed reference sorted by page, "
            "with its context, for checking against the finished pages.\n\n"
            "For InDesign, use Tools > Export InDesign script (.jsx).\n\n"
            "Your original manuscript is never changed."))

    def _about(self):
        messagebox.showinfo(f"About {APP_NAME}", f"{APP_NAME}\nVersion {__version__}\n\n"
                                                 "Builds canonically ordered Scripture indexes for Word and InDesign documents.")


def main():
    app = App()
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
