"""Tkinter GUI for Indicat."""
from __future__ import annotations

import copy
import os
import queue
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import APP_NAME, APP_TITLE, AUTHOR, REPO_URL, SUPPORT_URL, __version__
from . import settings as SET
from . import terms as T
from . import updates
from .dialogs import AddRefDialog, EditDialog, SettingsDialog, TermEditDialog, UpdateDialog
from .parser import INDEXED_STATUSES, STATUS_LABELS
from .pipeline import (FINAL_MODES, FOOTNOTE_MODES, LIVE_MODES, SEPARATORS, TERM_LABELS, BuildOptions,
                       build, check_custom_separator, find_text, include_by_default, make_static,
                       manual_occurrence, scan)
from .profiles import LANGUAGE_ORDER, PROFILES

# rows worth a second look (yellow)
REVIEW_STATUSES = {"inferred", "inferred-weak", "check-name", "mt", "word-check", "ocr"}
LAYOUTS = {"single": "One index", "testaments": "Old and New Testament (Apocrypha with OT)",
           "sections": "By section (OT, Apocrypha, NT, Other)"}
MT_MODES = {"label": "Index them, marked [MT]", "exclude": "Leave them out"}
FONT_MODES = {"body": "Match the body text", "styles": "Use the document's index styles"}
# settings that change what the scan finds (a new scan is needed after changing them)
SCAN_KEYS = ("language", "apocrypha", "custom_books", "languages", "scripture", "words", "term_sets",
             "index_bibliography")


def asset(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    p = base / "indicat" / "assets" / name
    if not p.exists():
        p = Path(__file__).resolve().parent / "assets" / name
    return p


def set_icon(win):
    try:
        if sys.platform == "win32":
            win.iconbitmap(default=str(asset("indicat.ico")))
        else:
            img = tk.PhotoImage(file=str(asset("indicat-64.png")))
            win.iconphoto(True, img)
            win._icon_img = img
    except Exception:
        pass


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


def open_folder(folder: str):
    if sys.platform == "win32":
        os.startfile(folder)              # noqa: S606
    else:
        subprocess.Popen(["xdg-open", folder])


def elapsed_text(seconds: float) -> str:
    s = int(round(seconds))
    if s < 60:
        return f"{s} s"
    return f"{s // 60} min {s % 60} s"


# ---------------------------------------------------------------------------
class FootnoteDialog(tk.Toplevel):
    def __init__(self, master, n_refs: int, n_notes: int, current: str, word: bool, pdf: bool = False,
                 pdf_format: str = "docx"):
        super().__init__(master)
        self.title("References in notes" if n_refs else "Build the index")
        self.resizable(False, False)
        self.transient(master)
        self.result = None
        frm = ttk.Frame(self, padding=16)
        frm.pack(fill="both", expand=True)
        self.var = tk.StringVar(value=current if current in FOOTNOTE_MODES else "italic")
        self.fmt = tk.StringVar(value=pdf_format)
        if pdf:
            box = ttk.LabelFrame(frm, text="Save the index as", padding=(10, 6))
            box.pack(fill="x", pady=(0, 10))
            ttk.Radiobutton(box, text="Word document (.docx)", value="docx", variable=self.fmt).pack(anchor="w")
            ttk.Radiobutton(box, text="OpenDocument text (.odt) for LibreOffice", value="odt",
                            variable=self.fmt).pack(anchor="w")
        if n_refs:
            ttk.Label(frm, text=f"{n_refs} index entries were found in {n_notes} footnotes/endnotes.",
                      font=("Segoe UI", 10, "bold")).pack(anchor="w")
        if pdf and n_refs:
            ttk.Label(frm, wraplength=560, justify="left", text=(
                "The note numbers are read from the PDF, so they can be added to the page numbers "
                "(“33n12”).")).pack(anchor="w", pady=(4, 10))
            if self.var.get() == "highlight":
                self.var.set("auto")
            for key in ("auto", "italic", "bold", "skip"):
                ttk.Radiobutton(frm, text=FOOTNOTE_MODES[key], value=key, variable=self.var).pack(anchor="w", pady=2)
        elif n_refs:
            ttk.Label(frm, wraplength=560, justify="left", text=(
                "Word's index can't print note locators like “33n12” by itself. Choose how page numbers "
                "for references in notes should appear.")).pack(anchor="w", pady=(4, 10))
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
        self.result = (self.var.get(), self.fmt.get())
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
            "with the note page numbers completed (33n12) or highlighted, and cross-references in "
            "Chicago style. The index entry fields in the text stay where they are, and the document "
            "you choose is not changed.")).pack(anchor="w", pady=(0, 10))
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


class WelcomeDialog(tk.Toplevel):
    """First run: a guided build, or the full window."""

    def __init__(self, master):
        super().__init__(master)
        self.title(f"Welcome to {APP_NAME}")
        self.resizable(False, False)
        self.transient(master)
        self.result = "full"
        frm = ttk.Frame(self, padding=20)
        frm.pack(fill="both", expand=True)
        try:
            img = tk.PhotoImage(file=str(asset("indicat-64.png")))
            lbl = ttk.Label(frm, image=img)
            lbl.image = img
            lbl.grid(row=0, column=0, rowspan=2, sticky="n", padx=(0, 16))
        except Exception:
            pass
        ttk.Label(frm, text=f"Welcome to {APP_NAME}", font=("Georgia", 18)).grid(row=0, column=1, sticky="w")
        ttk.Label(frm, wraplength=420, justify="left", text=(
            "Indicat builds Scripture, Greek and Hebrew word, and subject indexes for books written in "
            "Word, laid out in InDesign, or finished as PDFs.\n\n"
            "New to it? The guided build takes you through the index settings one step at a time and "
            "explains each choice. You can come back to it any time from the Help menu.")).grid(
            row=1, column=1, sticky="w", pady=(8, 0))
        b = ttk.Frame(frm)
        b.grid(row=2, column=0, columnspan=2, sticky="e", pady=(18, 0))
        ttk.Button(b, text="Go to the full window", command=lambda: self._done("full")).pack(side="right")
        g = ttk.Button(b, text="Guided index build", command=lambda: self._done("guided"))
        g.pack(side="right", padx=6)
        g.focus_set()
        _center(self, master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", lambda: self._done("full"))

    def _done(self, r):
        self.result = r
        self.destroy()


# ---------------------------------------------------------------------------
class App(tk.Tk):
    SHOW = ["All", "Indexed", "To check (yellow)", "Not indexed", "Chapter only", "Open-ended (ff)",
            "Quotations (not indexed)"]
    WHERE = ["Anywhere", "Body", "Footnotes", "Endnotes"]

    def __init__(self):
        super().__init__()
        self.title(f"{APP_TITLE} {__version__}")
        set_icon(self)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{min(1280, sw - 40)}x{min(820, sh - 90)}")
        self.minsize(min(960, sw - 40), min(600, sh - 90))
        self.settings = load_settings()
        self.q: queue.Queue = queue.Queue()
        self.result = None
        self.busy = False
        self.word = word_ok()
        self.pkg = None
        self.sort_col, self.sort_rev = None, False
        self._job = None                 # (kind, start time)
        self._prog_text = ""
        self._prog_frac = 0.0
        self._out_auto = ""
        self.scan_listeners = []         # callbacks after a scan (the guided build)
        self._build_ui()
        if SET.migration_note:
            self._say(SET.migration_note)
        self.after(100, self._poll)
        self.after(500, self._tick)
        if updates.can_install():
            self.after(1000, self._offer_cleanup)
        if self.settings.get("check_updates", True) and updates.configured():
            self.after(1500, lambda: self._check_updates(True))
        if not self.settings.get("welcome_done"):
            self.after(300, self._welcome)

    # -- layout -------------------------------------------------------------------
    def _build_ui(self):
        style = ttk.Style(self)
        try:
            style.theme_use("vista" if sys.platform == "win32" else "clam")
        except tk.TclError:
            pass
        s = self.settings
        # variables shared by the main window and the Index menu
        self.apoc = tk.BooleanVar(value=s.get("apocrypha", False))
        self.whole = tk.BooleanVar(value=s.get("whole_chapters", False))
        self.bib = tk.BooleanVar(value=s.get("index_bibliography", False))
        self.mt = tk.StringVar(value=s.get("mt_mode", "label"))
        self.font_mode = tk.StringVar(value=s.get("index_font", "body"))

        menubar = tk.Menu(self)
        filem = tk.Menu(menubar, tearoff=0)
        filem.add_command(label="Open manuscript or PDF…", accelerator="Ctrl+O", command=self._pick_src)
        filem.add_command(label="Scan", accelerator="F5", command=self._scan)
        filem.add_command(label="Build index…", accelerator="Ctrl+B", command=self._build)
        filem.add_separator()
        filem.add_command(label="Exit", command=self.destroy)
        menubar.add_cascade(label="File", menu=filem)
        editm = tk.Menu(menubar, tearoff=0)
        editm.add_command(label="Preferences…", command=lambda: self._settings_dialog("general"))
        editm.add_separator()
        editm.add_command(label="Export settings…", command=self._export_settings)
        editm.add_command(label="Import settings…", command=self._import_settings)
        menubar.add_cascade(label="Edit", menu=editm)
        idxm = tk.Menu(menubar, tearoff=0)
        idxm.add_command(label="Guided build…", command=self._guided)
        idxm.add_separator()
        idxm.add_checkbutton(label="Index the Apocrypha", variable=self.apoc, command=self._scan_settings_changed)
        idxm.add_checkbutton(label="Index references to whole chapters", variable=self.whole,
                             command=self._rules_changed)
        idxm.add_checkbutton(label="Index the bibliography", variable=self.bib, command=self._scan_settings_changed)
        mtm = tk.Menu(idxm, tearoff=0)
        for k, v in MT_MODES.items():
            mtm.add_radiobutton(label=v, value=k, variable=self.mt, command=self._rules_changed)
        idxm.add_cascade(label="Verses cited in Hebrew (MT) numbering", menu=mtm)
        fm = tk.Menu(idxm, tearoff=0)
        for k, v in FONT_MODES.items():
            fm.add_radiobutton(label=v, value=k, variable=self.font_mode, command=self._store_opts)
        idxm.add_cascade(label="Index font", menu=fm)
        idxm.add_separator()
        idxm.add_command(label="Original-language word indexes…", command=lambda: self._settings_dialog("words"))
        idxm.add_command(label="Term sets…", command=lambda: self._settings_dialog("sets"))
        menubar.add_cascade(label="Index", menu=idxm)
        tools = tk.Menu(menubar, tearoff=0)
        tools.add_command(label="Export InDesign script (.jsx)…", command=self._export_jsx)
        tools.add_command(label="Make a static-index copy of a checked document…", command=self._static)
        menubar.add_cascade(label="Tools", menu=tools)
        helpm = tk.Menu(menubar, tearoff=0)
        helpm.add_command(label="Guided build…", command=self._guided)
        helpm.add_command(label="How it works", command=self._help)
        helpm.add_command(label="User guide (online)", command=lambda: self._open_url(REPO_URL + "#readme"))
        helpm.add_separator()
        helpm.add_command(label="Check for updates…", command=lambda: self._check_updates(False))
        helpm.add_command(label="Support Indicat…", command=lambda: self._open_url(SUPPORT_URL))
        helpm.add_separator()
        helpm.add_command(label=f"About {APP_NAME}", command=self._about)
        menubar.add_cascade(label="Help", menu=helpm)
        self.config(menu=menubar)
        self.bind("<Control-o>", lambda e: self._pick_src())
        self.bind("<F5>", lambda e: self._scan())
        self.bind("<Control-b>", lambda e: self._build())

        top = ttk.Frame(self, padding=(10, 10, 10, 4))
        top.pack(fill="x")
        ttk.Label(top, text="Manuscript (.docx or .pdf):").grid(row=0, column=0, sticky="w")
        self.src = tk.StringVar(value=s.get("last_file", ""))
        ttk.Entry(top, textvariable=self.src).grid(row=0, column=1, sticky="we", padx=6)
        ttk.Button(top, text="Browse…", command=self._pick_src).grid(row=0, column=2)
        ttk.Button(top, text="Scan", command=self._scan).grid(row=0, column=3, padx=(6, 0))
        ttk.Button(top, text="Guided build…", command=self._guided).grid(row=0, column=4, padx=(6, 0))
        ttk.Label(top, text="Save results to:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.out = tk.StringVar()
        ttk.Entry(top, textvariable=self.out).grid(row=1, column=1, sticky="we", padx=6, pady=(6, 0))
        ttk.Button(top, text="Browse…", command=self._pick_out).grid(row=1, column=2, pady=(6, 0))
        self.out_note = ttk.Label(top, text="", foreground="#666")
        self.out_note.grid(row=1, column=3, columnspan=2, sticky="w", padx=(6, 0), pady=(6, 0))
        top.columnconfigure(1, weight=1)
        self.src.trace_add("write", lambda *a: self._refresh_out())
        self.out.trace_add("write", lambda *a: self._out_edited())
        self._refresh_out()

        opts = ttk.LabelFrame(self, text="Index settings (for this book)", padding=(10, 6))
        opts.pack(fill="x", padx=10, pady=4)
        ttk.Label(opts, text="Scripture index title:").grid(row=0, column=0, sticky="w")
        self.heading = tk.StringVar(value=self._lang_title(s.get("language", "en")))
        ttk.Entry(opts, textvariable=self.heading, width=22).grid(row=0, column=1, sticky="w", padx=(4, 16))
        ttk.Label(opts, text="Columns:").grid(row=0, column=2, sticky="w")
        self.cols = tk.IntVar(value=s.get("columns", 2))
        ttk.Spinbox(opts, from_=1, to=4, textvariable=self.cols, width=4).grid(row=0, column=3, sticky="w", padx=(4, 16))
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
        ttk.Checkbutton(opts, text="Index the Apocrypha", variable=self.apoc,
                        command=self._scan_settings_changed).grid(row=1, column=4, columnspan=2, sticky="w", pady=(6, 0))

        ttk.Label(opts, text="Page number separation:").grid(row=2, column=0, sticky="w", pady=(6, 0))
        sep_key = s.get("separator", "comma")
        if sep_key not in SEPARATORS:
            sep_key = "comma"
        self.sep_labels = {v[0]: k for k, v in SEPARATORS.items()}
        self.sep = ttk.Combobox(opts, values=list(self.sep_labels), state="readonly", width=40)
        self.sep.set(SEPARATORS[sep_key][0])
        self.sep.grid(row=2, column=1, columnspan=3, sticky="w", padx=(4, 6), pady=(6, 0))
        self.sep.bind("<<ComboboxSelected>>", lambda e: self._sep_changed())
        self.custom_sep = tk.StringVar(value=s.get("custom_separator", " —— "))
        self.custom_entry = ttk.Entry(opts, textvariable=self.custom_sep, width=8)
        self.custom_entry.grid(row=2, column=4, sticky="w", pady=(6, 0))
        self._sep_changed()
        ttk.Checkbutton(opts, text="Index references to whole chapters (“Proverbs 5”)", variable=self.whole,
                        command=self._rules_changed).grid(row=2, column=5, sticky="w", pady=(6, 0))

        self.new_page = tk.BooleanVar(value=s.get("new_page", True))
        ttk.Checkbutton(opts, text="Start the index on a new page", variable=self.new_page).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))
        self.remove_xe = tk.BooleanVar(value=False)
        self.remove_xe_cb = ttk.Checkbutton(opts, text="Remove existing index entries (XE fields) first",
                                            variable=self.remove_xe)
        self.remove_xe_cb.grid(row=3, column=2, columnspan=3, sticky="w", pady=(6, 0))
        ttk.Checkbutton(opts, text="Index the bibliography", variable=self.bib,
                        command=self._scan_settings_changed).grid(row=3, column=5, sticky="w", pady=(6, 0))

        ttk.Label(opts, text="Verses cited in Hebrew numbering:").grid(row=4, column=0, sticky="w", pady=(6, 0))
        self.mt_box = ttk.Combobox(opts, values=list(MT_MODES.values()), state="readonly", width=26)
        self.mt_box.set(MT_MODES.get(self.mt.get(), MT_MODES["label"]))
        self.mt_box.grid(row=4, column=1, columnspan=2, sticky="w", padx=(4, 16), pady=(6, 0))
        self.mt_box.bind("<<ComboboxSelected>>", lambda e: (self.mt.set(
            {v: k for k, v in MT_MODES.items()}[self.mt_box.get()]), self._rules_changed()))
        self.mt.trace_add("write", lambda *a: self.mt_box.set(MT_MODES.get(self.mt.get(), MT_MODES["label"])))
        ttk.Label(opts, text="Index font:").grid(row=4, column=3, sticky="e", pady=(6, 0))
        self.font_box = ttk.Combobox(opts, values=list(FONT_MODES.values()), state="readonly", width=30)
        self.font_box.set(FONT_MODES.get(self.font_mode.get(), FONT_MODES["body"]))
        self.font_box.grid(row=4, column=4, columnspan=2, sticky="w", padx=(4, 16), pady=(6, 0))
        self.font_box.bind("<<ComboboxSelected>>", lambda e: (self.font_mode.set(
            {v: k for k, v in FONT_MODES.items()}[self.font_box.get()]), self._store_opts()))
        self.font_mode.trace_add("write", lambda *a: self.font_box.set(
            FONT_MODES.get(self.font_mode.get(), FONT_MODES["body"])))

        self.idx_frame = ttk.Frame(opts)
        ttk.Label(opts, text="Indexes to build:").grid(row=5, column=0, sticky="w", pady=(8, 0))
        self.idx_frame.grid(row=5, column=1, columnspan=5, sticky="w", pady=(8, 0))
        self._fill_index_toggles()

        mid = ttk.Frame(self, padding=(10, 4))
        mid.pack(fill="both", expand=True)
        bar = ttk.Frame(mid)
        bar.pack(fill="x")
        ttk.Label(bar, text="Show:").pack(side="left")
        self.filter = ttk.Combobox(bar, values=self.SHOW, state="readonly", width=20)
        self.filter.set("All")
        self.filter.pack(side="left", padx=(4, 6))
        self.how_filter = ttk.Combobox(bar, values=["Any way found"], state="readonly", width=26)
        self.how_filter.set("Any way found")
        self.how_filter.pack(side="left", padx=(0, 6))
        self.where_filter = ttk.Combobox(bar, values=self.WHERE, state="readonly", width=11)
        self.where_filter.set("Anywhere")
        self.where_filter.pack(side="left", padx=(0, 6))
        self.idx_filter = ttk.Combobox(bar, values=["All indexes"], state="readonly", width=14)
        self.idx_filter.set("All indexes")
        self.idx_filter.pack(side="left", padx=(0, 10))
        for cb in (self.filter, self.how_filter, self.where_filter, self.idx_filter):
            cb.bind("<<ComboboxSelected>>", lambda e: self._fill())
        ttk.Button(bar, text="Reading order", command=self._reading_order).pack(side="left")
        bar = ttk.Frame(mid)
        bar.pack(fill="x", pady=(6, 0))
        ttk.Button(bar, text="Include", command=lambda: self._set_include(True)).pack(side="left")
        ttk.Button(bar, text="Exclude", command=lambda: self._set_include(False)).pack(side="left", padx=4)
        ttk.Button(bar, text="Edit…", command=self._edit).pack(side="left")
        ttk.Button(bar, text="Add reference…", command=self._add_ref).pack(side="left", padx=4)
        self.pdf_btn = ttk.Button(bar, text="Open PDF at this page", command=self._open_pdf, state="disabled")
        self.pdf_btn.pack(side="left")
        self.build_btn = ttk.Button(bar, text="Build index…", command=self._build, state="disabled")
        self.build_btn.pack(side="right")
        self.summary = ttk.Label(mid, text="Choose a Word manuscript or a PDF and click Scan.", foreground="#333")
        self.summary.pack(anchor="w", pady=(4, 0))

        cols = ("inc", "index", "ref", "how", "where", "page", "context")
        self.col_titles = {"inc": "Include", "index": "Index", "ref": "Entry", "how": "How found",
                           "where": "Where", "page": "Page", "context": "Context"}
        tv = ttk.Treeview(mid, columns=cols, show="headings", selectmode="extended")
        for c, wd, st in (("inc", 60, False), ("index", 76, False), ("ref", 170, False), ("how", 230, False),
                          ("where", 100, False), ("page", 56, False), ("context", 520, True)):
            tv.heading(c, text=self.col_titles[c], command=lambda c=c: self._sort_by(c))
            tv.column(c, width=wd, stretch=st, anchor="w")
        tv.tag_configure("excluded", foreground="#888888")
        tv.tag_configure("check", background="#FFF4C2")
        tv.tag_configure("openended", background="#E3F0FF")
        tv.tag_configure("note", foreground="#1F4E8C")
        ys = ttk.Scrollbar(mid, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=ys.set)
        tv.pack(side="left", fill="both", expand=True, pady=(6, 0))
        ys.pack(side="left", fill="y", pady=(6, 0))
        tv.bind("<Double-1>", lambda e: self._toggle())
        tv.bind("<space>", lambda e: self._toggle())
        tv.bind("<<TreeviewSelect>>", lambda e: self._sel_changed())
        self.tv = tv

        status = ttk.Frame(self, padding=(10, 0))
        status.pack(fill="x")
        self.prog = ttk.Progressbar(status, mode="determinate", maximum=100, length=260)
        self.prog.pack(side="left")
        self.prog_label = ttk.Label(status, text="", foreground="#333")
        self.prog_label.pack(side="left", padx=8)

        logf = ttk.LabelFrame(self, text="Messages", padding=(6, 4))
        logf.pack(fill="x", padx=10, pady=(4, 10))
        self.log = tk.Text(logf, height=6, wrap="word", font=("Consolas", 9), state="disabled")
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

    def _src_path(self) -> Path | None:
        p = self.src.get().strip().strip('"')
        return Path(p) if p else None

    def is_pdf(self) -> bool:
        p = self._src_path()
        return bool(p and p.suffix.lower() == ".pdf")

    def _pick_src(self):
        f = filedialog.askopenfilename(filetypes=[("Word documents and PDFs", "*.docx *.pdf"),
                                                  ("Word documents", "*.docx"), ("PDF files", "*.pdf")])
        if f:
            self.src.set(f)

    # -- where results are saved -------------------------------------------------
    def default_out(self) -> str:
        """The folder the results go to under the Preferences setting ("" = ask)."""
        mode = self.settings.get("save_location", "same")
        if mode == "fixed" and self.settings.get("save_folder"):
            return self.settings["save_folder"]
        if mode == "ask":
            return ""
        p = self._src_path()
        return str(p.parent) if p else ""

    def _refresh_out(self):
        self._out_auto = self.default_out()
        self._setting_out = True
        self.out.set(self._out_auto)
        self._setting_out = False
        mode = self.settings.get("save_location", "same")
        self.out_note.configure(text={"same": "(same folder as the manuscript)", "fixed": "(your results folder)",
                                      "ask": "(you'll be asked when building)"}.get(mode, ""))

    def _out_edited(self):
        if getattr(self, "_setting_out", False):
            return
        if self.out.get().strip() != self._out_auto:
            self.out_note.configure(text="(for this build only — Preferences sets the usual folder)")

    def _pick_out(self):
        d = filedialog.askdirectory()
        if d:
            self.out.set(d)

    def out_dir(self, ask_title: str = "Save the results in") -> Path | None:
        typed = self.out.get().strip().strip('"')
        if typed and typed != self._out_auto:
            return Path(typed)                         # a one-time choice
        d = self.default_out()
        if not d:
            d = filedialog.askdirectory(title=ask_title, initialdir=str(self._src_path().parent)
                                        if self._src_path() else None)
            if not d:
                return None
        return Path(d)

    # -- background jobs and progress ---------------------------------------------
    def _run(self, fn, done, kind="work"):
        if self.busy:
            return
        self.busy = True
        self.config(cursor="watch")
        self._job = (kind, time.time())
        self._progress(0.0, "Starting")

        def worker():
            try:
                r = fn()
                self.q.put(("done", done, r))
            except Exception as exc:
                self.q.put(("error", f"{exc}\n\n{traceback.format_exc()}"))
        threading.Thread(target=worker, daemon=True).start()

    def progress_cb(self, frac, text=""):
        """Thread-safe progress callback for the engine."""
        self.q.put(("progress", frac, text))

    def _progress(self, frac, text):
        self._prog_text = text or self._prog_text
        if frac is None:                      # a step whose length can't be told (Word): keep moving
            if str(self.prog["mode"]) != "indeterminate":
                self.prog.configure(mode="indeterminate")
                self.prog.start(15)
            self._prog_frac = None
        else:
            if str(self.prog["mode"]) != "determinate":
                self.prog.stop()
                self.prog.configure(mode="determinate")
            self._prog_frac = max(0.0, min(1.0, frac))
            self.prog["value"] = 100 * self._prog_frac
        self._show_progress()

    def _show_progress(self):
        if not self._job:
            return
        el = time.time() - self._job[1]
        pct = "" if self._prog_frac is None else f" — {int(100 * self._prog_frac)}%"
        clock = f"  ·  {int(el) // 60}:{int(el) % 60:02d}"
        self.prog_label.configure(text=f"{self._prog_text}{pct}{clock}")

    def _tick(self):
        if self.busy:
            self._show_progress()
        self.after(500, self._tick)

    def _finish_job(self, ok=True):
        self.busy = False
        self.config(cursor="")
        if str(self.prog["mode"]) == "indeterminate":
            self.prog.stop()
            self.prog.configure(mode="determinate")
        kind, t0 = self._job or ("work", time.time())
        self._job = None
        el = elapsed_text(time.time() - t0)
        self.prog["value"] = 100 if ok else 0
        if not ok:
            self.prog_label.configure(text="Stopped with an error.")
        elif kind == "build":
            self.prog_label.configure(text=f"Index built in {el}.")
        elif kind == "scan":
            self.prog_label.configure(text=f"Scan finished in {el}.")
        else:
            self.prog_label.configure(text=f"Finished in {el}.")
        return el

    def _poll(self):
        try:
            while True:
                item = self.q.get_nowait()
                if item[0] == "log":
                    self._say(item[1])
                elif item[0] == "progress":
                    self._progress(item[1], item[2])
                elif item[0] == "call":
                    item[1](item[2])
                elif item[0] == "done":
                    self._finish_job(True)
                    item[1](item[2])
                elif item[0] == "error":
                    self._finish_job(False)
                    self._say("ERROR: " + item[1].splitlines()[0])
                    messagebox.showerror(APP_NAME, item[1][:2000])
        except queue.Empty:
            pass
        self.after(100, self._poll)

    # -- scan --------------------------------------------------------------------
    def _scan(self):
        p = self._src_path()
        if not p or not p.is_file() or p.suffix.lower() not in (".docx", ".pdf"):
            messagebox.showwarning(APP_NAME, "Choose a Word manuscript (.docx) or a PDF first.")
            return
        if p.name.startswith("~$"):
            messagebox.showwarning(APP_NAME, "That is Word's temporary lock file; choose the real document.")
            return
        self._say(f"Scanning {p.name}…")
        self._store_opts()
        snap = copy.deepcopy(self.settings)
        if self.is_pdf():
            from .pdf_index import scan_pdf
            self._run(lambda: (scan_pdf(p, snap, progress=self.progress_cb,
                                        log=lambda m: self.q.put(("log", m))), None),
                      self._scan_done, "scan")
        else:
            self._run(lambda: scan(p, snap, progress=self.progress_cb), self._scan_done, "scan")

    def _scan_done(self, res_pkg):
        res, self.pkg = res_pkg
        self.result = res
        pdf = getattr(res, "kind", "") == "pdf"
        for wmsg in res.warnings:
            self._say("Warning: " + wmsg)
        self.remove_xe.set(res.existing_xe > 0)
        self.remove_xe_cb.configure(state="disabled" if pdf else "normal")
        self.font_box.configure(state="disabled" if pdf else "readonly")
        self.pdf_btn.configure(state="disabled")
        c = res.counts()
        self._summarize()
        self.idx_filter.configure(values=["All indexes"] + (["Scripture"] if res.scripture else []) +
                                  [d.short for d in res.defs])
        if self.idx_filter.get() not in self.idx_filter["values"]:
            self.idx_filter.set("All indexes")
        labels = sorted({self._how_label(o) for o in res.occurrences})
        self.how_filter.configure(values=["Any way found"] + labels)
        if self.how_filter.get() not in self.how_filter["values"]:
            self.how_filter.set("Any way found")
        self._say("Scan complete: " + ", ".join(f"{STATUS_LABELS.get(k) or TERM_LABELS.get(k, k)} {v}"
                                                for k, v in c.items()))
        self.build_btn.configure(state="normal")
        self.sort_col, self.sort_rev = None, False
        self._fill()
        for cb in list(self.scan_listeners):
            cb(res)

    def _summarize(self):
        res = self.result
        inc = sum(1 for o in res.occurrences if o.include)
        chk = sum(1 for o in res.occurrences if o.include and (o.status in REVIEW_STATUSES or o.open_ended))
        text = (f"{len(res.occurrences)} found · {inc} to index · {chk} to check · "
                f"{len(res.occurrences) - inc} not indexed")
        if res.defs:
            per = {}
            for o in res.occurrences:
                if o.include:
                    per[res.index_name(o.index)] = per.get(res.index_name(o.index), 0) + 1
            text += "   (" + ", ".join(f"{k} {v}" for k, v in per.items()) + ")"
        self.summary.configure(text=text)

    @staticmethod
    def _how_label(o) -> str:
        if o.open_ended:
            return "Open-ended (ff)"
        return STATUS_LABELS.get(o.status) or TERM_LABELS.get(o.status, o.status)

    def _visible(self, o) -> bool:
        ix = self.idx_filter.get()
        if ix and ix != "All indexes" and self.result.index_name(o.index) != ix:
            return False
        hw = self.how_filter.get()
        if hw and hw != "Any way found" and self._how_label(o) != hw:
            return False
        wh = self.where_filter.get()
        if wh and wh != "Anywhere" and o.where_kind != wh:
            return False
        f = self.filter.get()
        if f == "Quotations (not indexed)":
            return o.status == "quotation"
        if f == "Indexed":
            return o.include
        if f == "To check (yellow)":
            return o.include and (o.status in REVIEW_STATUSES or o.edited or o.open_ended)
        if f == "Not indexed":
            return not o.include
        if f == "Chapter only":
            return o.status == "chapter-only"
        if f == "Open-ended (ff)":
            return o.open_ended
        return True

    # sorting: every column; Entry sorts in canonical (Bible / alphabetical) order
    def _sort_key(self, col):
        res = self.result

        def entry(o):
            r = o.ref
            if r is None:
                return (2, "", o.hit.raw)
            if o.is_scripture:
                return (0, r.book_key(), r.sort_key())
            return (1, res.index_name(o.index), r.yomi())

        def where(o):
            kind = {"Body": 0, "Footnotes": 1, "Endnotes": 2}.get(o.where_kind, 3)
            num = o.note_number or ""
            return (kind, int(num) if num.isdigit() else 0, num, o.seq)

        def page(o):
            if getattr(o, "pdf_page", None) is not None:
                return (0, o.pdf_page, o.seq)
            from .proof import page_sort_key
            return page_sort_key(o)
        return {"inc": lambda o: (not o.include, o.seq), "index": lambda o: (res.index_name(o.index), o.seq),
                "ref": entry, "how": lambda o: (self._how_label(o), o.seq), "where": where, "page": page,
                "context": lambda o: o.context.lstrip("…").lower()}.get(col, lambda o: o.seq)

    def _sort_by(self, col):
        if self.sort_col == col:
            self.sort_rev = not self.sort_rev
        else:
            self.sort_col, self.sort_rev = col, False
        self._fill()

    def _reading_order(self):
        self.sort_col, self.sort_rev = None, False
        self._fill()

    def _fill(self):
        self.tv.delete(*self.tv.get_children())
        for c, t in self.col_titles.items():
            arrow = (" ▼" if self.sort_rev else " ▲") if c == self.sort_col else ""
            self.tv.heading(c, text=t + arrow)
        if not self.result:
            return
        rows = [(i, o) for i, o in enumerate(self.result.occurrences) if self._visible(o)]
        if self.sort_col:
            key = self._sort_key(self.sort_col)
            rows.sort(key=lambda x: key(x[1]), reverse=self.sort_rev)
        for i, o in rows:
            tags = []
            if not o.include:
                tags.append("excluded")
            elif o.open_ended:
                tags.append("openended")
            elif o.status in REVIEW_STATUSES or o.edited:
                tags.append("check")
            if o.in_note:
                tags.append("note")
            self.tv.insert("", "end", iid=str(i), tags=tags, values=(
                "✔" if o.include else "", self.result.index_name(o.index), o.display, o.status_label,
                o.where, o.page or "", o.context.replace("⟦", "[").replace("⟧", "]")))
        self._summarize()

    def _selected(self):
        return [self.result.occurrences[int(i)] for i in self.tv.selection()] if self.result else []

    def _sel_changed(self):
        sel = self._selected()
        ok = len(sel) == 1 and getattr(sel[0], "pdf_page", None) is not None
        self.pdf_btn.configure(state="normal" if ok else "disabled")

    def _set_include(self, val: bool):
        sel = self._selected()
        bad = [o for o in sel if val and not o.indexable]
        for o in sel:
            if val and not o.indexable:
                continue
            o.include = val
            o.user_set = True
        if bad:
            messagebox.showinfo(APP_NAME, "Some selected rows have no book yet. Use “Edit…” "
                                          "to give them a book, then include them.")
        keep = self.tv.selection()
        self._fill()
        self.tv.selection_set([k for k in keep if self.tv.exists(k)])

    def _toggle(self):
        sel = self._selected()
        if len(sel) == 1:
            o = sel[0]
            if not o.indexable:
                self._edit()
                return
            self._set_include(not o.include)

    def _edit(self):
        sel = self._selected()
        if len(sel) != 1:
            messagebox.showinfo(APP_NAME, "Select one row to edit.")
            return
        o = sel[0]
        if not o.is_scripture:
            d = TermEditDialog(self, o)
            self.wait_window(d)
            if d.result is None:
                return
            o.ref = d.result
            o.edited = True
            o.include = True
            if o.status == "quotation":
                o.words = None
                o.status = "term"
            self._fill()
            return
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

    def _open_pdf(self):
        sel = self._selected()
        if len(sel) != 1 or getattr(sel[0], "pdf_page", None) is None:
            return
        from .pdf_viewer import open_at
        o = sel[0]
        msg = open_at(self.result.path, o.pdf_page + 1, self.settings)
        if msg:
            self._say(msg + f" (printed page {o.page})")

    def _rules_changed(self):
        """Whole chapters / [MT]: re-decide the rows the user hasn't touched, without a new scan."""
        self._store_opts()
        if not self.result:
            return
        for o in self.result.occurrences:
            if o.is_scripture and o.ref is not None and not o.edited and not getattr(o, "user_set", False) \
                    and o.status in ("chapter-only", "mt"):
                o.include = include_by_default(o.status, self.settings)
        self._fill()

    # -- build -------------------------------------------------------------------
    def _build(self):
        if not self.result or self.busy:
            return
        self._store_opts()
        if any(self.result.settings.get(k) != self.settings.get(k) for k in SCAN_KEYS):
            if messagebox.askyesno(APP_NAME, "The language, book, bibliography, word-index or term-set settings "
                                   "changed since the last scan. Scan again now? (Your include/exclude choices "
                                   "will be reset.)"):
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
        pdf = getattr(self.result, "kind", "") == "pdf"
        note_refs = [o for o in self.result.occurrences if o.in_note and o.include and o.indexable]
        mode = self.settings.get("pdf_notes_mode", "auto") if pdf else self.settings.get("footnote_mode", "italic")
        use_word = bool(self.settings.get("use_word", True)) and self.word
        fmt = self.settings.get("pdf_format", "docx")
        if note_refs or pdf:
            notes = {(o.note_kind, o.note_ordinal) for o in note_refs}
            d = FootnoteDialog(self, len(note_refs), len(notes), mode, use_word, pdf=pdf, pdf_format=fmt)
            self.wait_window(d)
            if d.result is None:
                return
            mode, fmt = d.result
        out = self.out_dir()
        if out is None:
            return
        src = self._src_path()
        opts = BuildOptions(out_dir=out, heading=self.heading.get().strip(),
                            settings=copy.deepcopy(self.settings),
                            columns=max(1, min(4, int(self.cols.get() or 2))),
                            separator=sep_text, leader=leader,
                            new_page=bool(self.new_page.get()), footnote_mode=mode,
                            remove_existing_xe=bool(self.remove_xe.get()) and not pdf, use_word=use_word)
        upd = dict(last_file=str(src), columns=opts.columns, separator=key, custom_separator=self.custom_sep.get(),
                   new_page=opts.new_page)
        if pdf:
            upd.update(pdf_format=fmt, pdf_notes_mode=mode)
        else:
            upd.update(footnote_mode=mode)
        self.settings.update(upd)
        save_settings(self.settings)
        self._say("Building…")
        res = self.result
        log = lambda m: self.q.put(("log", m))           # noqa: E731
        if pdf:
            from .pdf_index import build_pdf
            self._run(lambda: build_pdf(res, opts, fmt, log=log, progress=self.progress_cb), self._build_done, "build")
        else:
            self._run(lambda: build(res, opts, log=log, progress=self.progress_cb), self._build_done, "build")

    def _build_done(self, r):
        took = self.prog_label.cget("text")
        pdf = getattr(self.result, "kind", "") == "pdf"
        if not pdf:
            self.settings["last_indexed"] = str(r.indexed_docx)
            save_settings(self.settings)
        for m in r.messages:
            self._say("Note: " + m)
        if pdf:
            self._say(f"Done. Index: {r.indexed_docx.name}")
        else:
            self._say(f"Done. Indexed copy (live index): {r.indexed_docx.name}")
            if r.final_docx:
                self._say(f"Finalized copy (plain-text index): {r.final_docx.name}")
        self._say(f"Proofreading list: {r.proof_docx.name}")
        self._say(took)
        if messagebox.askyesno(APP_NAME, f"{took}\n\nOpen the folder with the results?"):
            open_folder(str(r.indexed_docx.parent))

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
        self.settings["whole_chapters"] = bool(self.whole.get())
        self.settings["index_bibliography"] = bool(self.bib.get())
        self.settings["mt_mode"] = self.mt.get() or "label"
        self.settings["index_font"] = self.font_mode.get() or "body"
        self.settings["index_layout"] = self.layout_labels.get(self.layout.get(), "single")
        title = self.heading.get().strip()
        ls = SET.lang_settings(self.settings, code)
        if title and title != PROFILES[code]["index_title"]:
            ls["index_title"] = title
        else:
            ls.pop("index_title", None)
        save_settings(self.settings)

    def sync_from_settings(self):
        """Show self.settings in the window (after Preferences, an import, or the guided build)."""
        s = self.settings
        self.lang.set(PROFILES.get(s.get("language", "en"), PROFILES["en"])["name"])
        self.apoc.set(s.get("apocrypha", False))
        self.whole.set(s.get("whole_chapters", False))
        self.bib.set(s.get("index_bibliography", False))
        self.mt.set(s.get("mt_mode", "label"))
        self.font_mode.set(s.get("index_font", "body"))
        self.layout.set(LAYOUTS.get(s.get("index_layout", "single"), LAYOUTS["single"]))
        self.heading.set(self._lang_title(s.get("language", "en")))
        self.cols.set(s.get("columns", 2))
        sk = s.get("separator", "comma")
        self.sep.set(SEPARATORS.get(sk, SEPARATORS["comma"])[0])
        self.custom_sep.set(s.get("custom_separator", self.custom_sep.get()))
        self._sep_changed()
        self.new_page.set(s.get("new_page", True))
        self._fill_index_toggles()
        self._refresh_out()

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

    def _settings_dialog(self, tab: str = "general"):
        self._store_opts()
        d = SettingsDialog(self, self.settings, tab)
        self.wait_window(d)
        if d.result is not None:
            self.settings = d.result
            save_settings(self.settings)
            self.sync_from_settings()
            self._scan_settings_changed()

    # -- which indexes ------------------------------------------------------------------
    def _fill_index_toggles(self):
        for w_ in self.idx_frame.winfo_children():
            w_.destroy()
        self.idx_vars = []
        v = tk.BooleanVar(value=self.settings.get("scripture", True))
        ttk.Checkbutton(self.idx_frame, text="Scripture", variable=v,
                        command=lambda: self._toggle_index("scripture", v)).pack(side="left", padx=(0, 10))
        self.idx_vars.append(v)
        for d in T.index_defs(self.settings, include_disabled=True):
            on = self._index_enabled(d.id)
            var = tk.BooleanVar(value=on)
            ttk.Checkbutton(self.idx_frame, text=d.short + (" words" if d.kind in ("script", "lang") else ""),
                            variable=var, command=lambda i=d.id, vv=var: self._toggle_index(i, vv)).pack(
                side="left", padx=(0, 10))
            self.idx_vars.append(var)
        ttk.Button(self.idx_frame, text="Word & term indexes…",
                   command=lambda: self._settings_dialog("words")).pack(side="left", padx=(6, 0))

    def _index_enabled(self, index_id: str) -> bool:
        kind, _, key = index_id.partition(":")
        if kind == "script":
            return bool(T.words_settings(self.settings)["scripts"].get(key, {}).get("enabled"))
        if kind == "lang":
            return any(t.get("lang") == key and t.get("enabled") for t in
                       T.words_settings(self.settings).get("tagged", []))
        if kind == "set":
            return any(t.get("id") == key and t.get("enabled") for t in self.settings.get("term_sets", []))
        return bool(self.settings.get("scripture", True))

    def set_index(self, index_id: str, val: bool):
        kind, _, key = index_id.partition(":")
        if kind == "scripture":
            self.settings["scripture"] = val
        elif kind in ("script", "lang"):
            ws = T.words_settings(self.settings)
            if kind == "script":
                ws["scripts"][key]["enabled"] = val
            else:
                for t in ws.get("tagged", []):
                    if t.get("lang") == key:
                        t["enabled"] = val
            self.settings["words"] = ws
        elif kind == "set":
            for t in self.settings.get("term_sets", []):
                if t.get("id") == key:
                    t["enabled"] = val
        save_settings(self.settings)

    def _toggle_index(self, index_id: str, var):
        self.set_index(index_id, bool(var.get()))
        if self.result is not None:
            self._say("Indexes changed: scan again to apply.")

    def _open_url(self, url: str):
        import webbrowser
        webbrowser.open(url)

    def _export_settings(self):
        self._store_opts()
        f = filedialog.asksaveasfilename(defaultextension=".json",
                                         initialfile="Indicat settings.json",
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
        self.sync_from_settings()
        self._say(f"Settings imported from {f}")
        self._scan_settings_changed()

    def _export_jsx(self):
        from . import jsx
        self._store_opts()
        f = filedialog.asksaveasfilename(defaultextension=".jsx", initialfile="Indicat for InDesign.jsx",
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
                            "open. Your current language, abbreviation and custom-book settings, and the word "
                            "indexes and term sets that are switched on, are built into the script. Export it "
                            "again after changing them.")

    # -- add reference ------------------------------------------------------------
    def _add_ref(self):
        if not self.result or getattr(self, "pkg", None) is None:
            messagebox.showinfo(APP_NAME, "Scan a Word manuscript first." if not self.result else
                                "Adding references by hand works with Word manuscripts. For a PDF, note the "
                                "missing reference and add it to the finished index.")
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
                can = updates.can_install() and bool(r.get("asset"))
                d = UpdateDialog(self, r["latest"], __version__, r.get("notes", ""), can)
                self.wait_window(d)
                if d.result == "install":
                    self._install_update(r)
                elif d.result == "page":
                    import webbrowser
                    webbrowser.open(r.get("url") or "")
            elif not quiet:
                msg = {"current": f"You have the latest version ({__version__}).",
                       "unconfigured": "Update checking will start working once the project is published "
                                       "on GitHub.",
                       "norelease": "No release has been published yet, so there is nothing newer.",
                       "error": f"Couldn't check for updates: {r.get('error', '')}"}.get(st, str(r))
                messagebox.showinfo(APP_NAME, msg)
        if quiet:
            threading.Thread(target=lambda: self.q.put(("call", done, work())), daemon=True).start()
        else:
            self._run(work, done)

    def _install_update(self, r):
        if self.busy:
            messagebox.showinfo(APP_NAME, "Indicat is busy. When it has finished, choose Help > Check for "
                                "updates to install the new version.")
            return
        latest = r["latest"]
        self._say(f"Downloading Indicat {latest}…")

        def work():
            try:
                path, moved = updates.install(r["asset"], latest, progress=self.progress_cb)
                return {"path": path, "moved": moved}
            except updates.UpdateError as exc:
                return {"error": str(exc)}

        def done(res):
            if res.get("error"):
                self._say(res["error"])
                messagebox.showwarning(APP_NAME, res["error"])
                return
            path = res["path"]
            if res["moved"]:
                here = updates.running_exe().parent
                self._say(f"Saved {path}")
                messagebox.showinfo(APP_NAME, (
                    f"Indicat can't save files in {here}, so Indicat {latest} was saved in your Downloads "
                    f"folder instead:\n\n{path}\n\nMove it to where you keep Indicat, then start it."))
                open_folder(str(path.parent))
                return
            self._say(f"Indicat {latest} is installed: {path}")
            if messagebox.askyesno(APP_NAME, f"Indicat {latest} is installed in {path.parent}.\n\n"
                                   "Start it now and close this version?"):
                try:
                    updates.launch(path)
                except OSError as exc:
                    messagebox.showwarning(APP_NAME, f"Couldn't start {path.name} ({exc}). Start it from "
                                           f"{path.parent}.")
                    return
                self.destroy()
        self._run(work, done, "update")

    def _offer_cleanup(self):
        """At the start of a new version: offer to delete older copies in this folder and to point
        shortcuts to this one.  A copy the user chose to keep isn't asked about again."""
        exe = updates.running_exe()
        kept = set(self.settings.get("kept_old_versions") or [])
        olds = [p for p in updates.older_copies(exe.parent, exe) if p.name not in kept]
        if not olds:
            return
        names = ", ".join(p.name for p in olds)
        one = len(olds) == 1
        if not messagebox.askyesno(APP_NAME, (
                f"This is Indicat {__version__}. The older version{'' if one else 's'} in this folder "
                f"({names}) can be deleted now, and shortcuts that open {'it' if one else 'them'} changed to "
                f"open this version. Your settings are kept.\n\nDelete the old version{'' if one else 's'} "
                "and update the shortcuts?")):
            self.settings["kept_old_versions"] = sorted(kept | {p.name for p in olds})
            save_settings(self.settings)
            return

        def work():
            n = updates.retarget_shortcuts(olds, exe)
            deleted, left = updates.delete_old(olds)
            return n, deleted, left

        def done(r):
            n, deleted, left = r
            if deleted:
                self._say("Deleted " + ", ".join(p.name for p in deleted) + ".")
            self._say(f"Shortcuts changed to open this version: {n}.")
            if left:
                messagebox.showwarning(APP_NAME, "Couldn't delete " + ", ".join(p.name for p in left) +
                                       " (it may still be open). Close it and delete it by hand.")
        threading.Thread(target=lambda: self.q.put(("call", done, work())), daemon=True).start()

    def _static(self):
        d = StaticDialog(self, self.settings.get("last_indexed", ""), self.word)
        self.wait_window(d)
        if not d.result:
            return
        path, mode, marker, upd = d.result
        typed = self.out.get().strip()
        mode_s = self.settings.get("save_location", "same")
        if typed and typed != self._out_auto:
            out = typed
        elif mode_s == "fixed" and self.settings.get("save_folder"):
            out = self.settings["save_folder"]
        elif mode_s == "ask":
            out = filedialog.askdirectory(title="Save the static copy in", initialdir=str(Path(path).parent))
            if not out:
                return
        else:
            out = None                                    # next to the indexed document
        self._say(f"Making a static-index copy of {Path(path).name}…")
        self._run(lambda: make_static(path, out, mode, marker, upd, log=lambda m: self.q.put(("log", m))),
                  self._static_done)

    def _static_done(self, res):
        out, msgs = res
        for m in msgs:
            self._say("Note: " + m)
        self._say(f"Done. Static copy: {out.name}")
        if messagebox.askyesno(APP_NAME, "Finished. Open the folder with the static copy?"):
            open_folder(str(out.parent))

    # -- guided build ------------------------------------------------------------------
    def _welcome(self):
        d = WelcomeDialog(self)
        self.wait_window(d)
        self.settings["welcome_done"] = True
        save_settings(self.settings)
        if d.result == "guided":
            self._guided()

    def _guided(self):
        from .guided import GuidedBuild
        if self.busy:
            return
        GuidedBuild(self)

    # -- help --------------------------------------------------------------------
    def _help(self):
        messagebox.showinfo("How it works", (
            "0. Choose a Word manuscript or a PDF, the language, the index layout, and which indexes to "
            "build: Scripture, Greek or Hebrew words, and any term sets. New to Indicat? Try Help > Guided "
            "build.\n\n"
            "1. Scan finds every Scripture reference (including bare references like “(5:17)” whose book "
            "comes from earlier text), every Greek or Hebrew word outside quotations (filed under its "
            "dictionary form), and every term from your sets.\n\n"
            "2. Review the list. Yellow rows are worth checking (book from context, Vulgate names, "
            "Hebrew numbering, OCR slips); blue rows are open-ended (34ff.). Grey rows will not be indexed. "
            "Click a column heading to sort by it; the filters combine. Double-click a row to include or "
            "exclude it, use Edit to correct it, or Add reference for one the scan missed.\n\n"
            "3. Build. For Word: a COPY of the manuscript with an index entry field after each entry and the "
            "indexes at the end, laid out by Word to read every page number. For a PDF: a finished index "
            "(.docx or .odt) using the printed page numbers.\n\n"
            "4. The proofreading list (.docx and .csv) shows every indexed entry sorted by page, with its "
            "context, for checking against the finished pages.\n\n"
            "For InDesign, use Tools > Export InDesign script (.jsx).\n\n"
            "Your original manuscript is never changed."))

    def _about(self):
        win = tk.Toplevel(self)
        win.title(f"About {APP_NAME}")
        win.resizable(False, False)
        win.transient(self)
        frm = ttk.Frame(win, padding=18)
        frm.pack(fill="both", expand=True)
        try:
            img = tk.PhotoImage(file=str(asset("indicat-64.png")))
            lbl = ttk.Label(frm, image=img)
            lbl.image = img
            lbl.grid(row=0, column=0, rowspan=4, sticky="n", padx=(0, 16))
        except Exception:
            pass
        ttk.Label(frm, text=APP_NAME, font=("Georgia", 20)).grid(row=0, column=1, sticky="w")
        ttk.Label(frm, text=f"Scripture Index Builder · version {__version__}").grid(row=1, column=1, sticky="w")
        ttk.Label(frm, text=f"Created by {AUTHOR}", font=("Segoe UI", 10, "bold")).grid(
            row=2, column=1, sticky="w", pady=(8, 0))
        ttk.Label(frm, wraplength=380, justify="left", text=(
            "Indicat (Latin, “it points out”) builds Scripture, original-language word and term "
            "indexes for Word, InDesign and PDF.\n\nGreek and Hebrew dictionary forms from the Open "
            "Scriptures Hebrew Bible (CC BY 4.0) and MorphGNT (CC BY-SA).\n\nFree software under the GNU "
            "General Public License, version 3. Modified versions must keep the credit “Indicat, created by "
            f"{AUTHOR}”.")).grid(row=3, column=1, sticky="w", pady=(6, 0))
        b = ttk.Frame(frm)
        b.grid(row=4, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(b, text="Close", command=win.destroy).pack(side="right")
        ttk.Button(b, text="Support Indicat…", command=lambda: self._open_url(SUPPORT_URL)).pack(side="right", padx=6)
        ttk.Button(b, text="Website", command=lambda: self._open_url(REPO_URL)).pack(side="right")
        _center(win, self)
        win.grab_set()


def main():
    app = App()
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
