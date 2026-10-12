"""Dialogs for settings (languages, abbreviations, sections, custom books),
adding a reference by hand, and editing a reference."""
from __future__ import annotations

import copy
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from pathlib import Path

from . import settings as SET
from . import terms as T
from .catalog import OT_ORDER_LABELS, PLACEHOLDER_SECTIONS, SECTION_KEYS
from .parser import parse_label
from .profiles import LANGUAGE_ORDER, PROFILES

SECTION_NAMES = {"OT": "Old Testament", "AP": "Apocrypha", "NT": "New Testament",
                 "OTHER": "Other (custom books)"}


def center(win, master):
    win.update_idletasks()
    x = master.winfo_rootx() + (master.winfo_width() - win.winfo_width()) // 2
    y = master.winfo_rooty() + (master.winfo_height() - win.winfo_height()) // 3
    win.geometry(f"+{max(x, 0)}+{max(y, 0)}")


def _split(s: str) -> list[str]:
    return [x.strip() for x in s.replace(";", ",").split(",") if x.strip()]


def book_choices(cat) -> list:
    """[(display name, id)] in index order."""
    items = sorted(cat.books.values(), key=lambda b: (cat.section_rank(b.section), b.rank, b.name))
    return [(b.name, b.id) for b in items]


# ---------------------------------------------------------------------------
class EditDialog(tk.Toplevel):
    def __init__(self, master, occ, cat, title="Edit reference"):
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self.transient(master)
        self.result = None
        self.cat = cat
        frm = ttk.Frame(self, padding=16)
        frm.pack(fill="both", expand=True)
        if occ is not None:
            ttk.Label(frm, text="Context:").grid(row=0, column=0, sticky="nw")
            ctx = tk.Text(frm, width=70, height=4, wrap="word", font=("Segoe UI", 9))
            ctx.insert("1.0", occ.context)
            ctx.configure(state="disabled")
            ctx.grid(row=0, column=1, columnspan=2, sticky="we", pady=(0, 8))
        self.choices = book_choices(cat)
        ttk.Label(frm, text="Book:").grid(row=1, column=0, sticky="w")
        self.book = ttk.Combobox(frm, values=[n for n, _ in self.choices], state="readonly", width=30)
        self.book.grid(row=1, column=1, sticky="w")
        ttk.Label(frm, text="Chapter:verse:").grid(row=2, column=0, sticky="w", pady=6)
        self.ref = ttk.Entry(frm, width=26)
        self.ref.grid(row=2, column=1, sticky="w", pady=6)
        ttk.Label(frm, text="e.g. 5:9–6:1, 3,16, 3:16a, 5:9–16", foreground="#666").grid(row=2, column=2, sticky="w")
        if occ is not None and occ.ref:
            self.book.set(occ.ref.book_name)
            self.ref.insert(0, occ.ref.label())
        btns = ttk.Frame(frm)
        btns.grid(row=3, column=0, columnspan=3, sticky="e", pady=(10, 0))
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(btns, text="OK", command=self._ok).pack(side="right", padx=6)
        center(self, master)
        self.grab_set()
        self.ref.focus_set()

    def _ok(self):
        name = self.book.get()
        if not name:
            messagebox.showwarning(self.title(), "Choose a book.", parent=self)
            return
        bid = dict(self.choices)[name]
        r = parse_label(self.cat, bid, self.ref.get())
        if r is None:
            messagebox.showwarning(self.title(), f"“{self.ref.get()}” is not a valid reference for {name}.",
                                   parent=self)
            return
        self.result = r
        self.destroy()


# ---------------------------------------------------------------------------
class AddRefDialog(tk.Toplevel):
    """Find a spot in the text, then type the reference to index there."""

    def __init__(self, master, pkg, cat, finder):
        super().__init__(master)
        self.title("Add reference")
        self.geometry("820x520")
        self.transient(master)
        self.result = None
        self.pkg, self.cat, self.finder = pkg, cat, finder
        self.places = []
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, wraplength=780, justify="left", text=(
            "1. Type a few words from the text where the reference should be indexed (for example, "
            "the reference as written, or the words just before it) and click Find. "
            "2. Choose the right spot. 3. Enter the reference. The index entry is placed right "
            "after the text you searched for.")).pack(anchor="w")
        row = ttk.Frame(frm)
        row.pack(fill="x", pady=8)
        self.q = tk.StringVar()
        e = ttk.Entry(row, textvariable=self.q, width=50)
        e.pack(side="left", fill="x", expand=True)
        e.bind("<Return>", lambda ev: self._find())
        ttk.Button(row, text="Find", command=self._find).pack(side="left", padx=6)
        self.lb = tk.Listbox(frm, height=12, font=("Segoe UI", 9))
        self.lb.pack(fill="both", expand=True)
        form = ttk.Frame(frm)
        form.pack(fill="x", pady=8)
        self.choices = book_choices(cat)
        ttk.Label(form, text="Book:").pack(side="left")
        self.book = ttk.Combobox(form, values=[n for n, _ in self.choices], state="readonly", width=28)
        self.book.pack(side="left", padx=6)
        ttk.Label(form, text="Chapter:verse:").pack(side="left", padx=(12, 0))
        self.ref = ttk.Entry(form, width=16)
        self.ref.pack(side="left", padx=6)
        btns = ttk.Frame(frm)
        btns.pack(fill="x")
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(btns, text="Add", command=self._ok).pack(side="right", padx=6)
        center(self, master)
        self.grab_set()
        e.focus_set()

    def _find(self):
        self.places = self.finder(self.pkg, self.q.get())
        self.lb.delete(0, "end")
        for p in self.places:
            where = "Body" if not p["note_kind"] else f"{p['note_kind'].title()} #{p['note_ordinal']}"
            self.lb.insert("end", f"[{where}]  " + p["context"].replace("⟦", "[").replace("⟧", "]"))
        if not self.places:
            self.lb.insert("end", "(not found — check spelling, or search for fewer words)")

    def _ok(self):
        sel = self.lb.curselection()
        if not sel or not self.places or sel[0] >= len(self.places):
            messagebox.showwarning("Add reference", "Choose where the reference is.", parent=self)
            return
        name = self.book.get()
        if not name:
            messagebox.showwarning("Add reference", "Choose a book.", parent=self)
            return
        bid = dict(self.choices)[name]
        r = parse_label(self.cat, bid, self.ref.get())
        if r is None:
            messagebox.showwarning("Add reference", f"“{self.ref.get()}” is not a valid reference for {name}.",
                                   parent=self)
            return
        self.result = (self.places[sel[0]], r)
        self.destroy()


# ---------------------------------------------------------------------------
class CustomBookDialog(tk.Toplevel):
    def __init__(self, master, book: dict | None):
        super().__init__(master)
        self.title("Custom book")
        self.resizable(False, False)
        self.transient(master)
        self.result = None
        b = book or {}
        frm = ttk.Frame(self, padding=14)
        frm.pack(fill="both", expand=True)
        self.v = {}
        rows = [("name", "Name in the index:", b.get("name", "")),
                ("spellings", "Other full spellings (comma-separated):", ", ".join(b.get("spellings", []))),
                ("abbreviations", "Abbreviations (comma-separated):", ", ".join(b.get("abbreviations", []))),
                ("position", "Position in its section (0 = first, 999 = last):", str(b.get("position", 999))),
                ("chapters", "Highest chapter number (for checking):", str(b.get("chapters", 150)))]
        for i, (k, label, val) in enumerate(rows):
            ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w", pady=3)
            var = tk.StringVar(value=val)
            ttk.Entry(frm, textvariable=var, width=40).grid(row=i, column=1, sticky="w", padx=6)
            self.v[k] = var
        ttk.Label(frm, text="Section:").grid(row=len(rows), column=0, sticky="w", pady=3)
        self.section = ttk.Combobox(frm, values=[SECTION_NAMES[s] for s in SECTION_KEYS], state="readonly",
                                    width=28)
        self.section.set(SECTION_NAMES.get(b.get("section", "OTHER"), SECTION_NAMES["OTHER"]))
        self.section.grid(row=len(rows), column=1, sticky="w", padx=6)
        ttk.Label(frm, foreground="#555", wraplength=520, justify="left", text=(
            "Planned sets (not available yet): " + ", ".join(PLACEHOLDER_SECTIONS.values()) +
            ". Until then, add the works you need here, in “Other”.")).grid(
            row=len(rows) + 1, column=0, columnspan=2, sticky="w", pady=(8, 0))
        btns = ttk.Frame(frm)
        btns.grid(row=len(rows) + 2, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(btns, text="OK", command=self._ok).pack(side="right", padx=6)
        self.book_id = b.get("id")
        center(self, master)
        self.grab_set()

    def _ok(self):
        name = self.v["name"].get().strip()
        if not name:
            messagebox.showwarning("Custom book", "Enter the name.", parent=self)
            return
        try:
            pos = int(self.v["position"].get() or 999)
            ch = int(self.v["chapters"].get() or 150)
        except ValueError:
            messagebox.showwarning("Custom book", "Position and chapters must be numbers.", parent=self)
            return
        sec = {v: k for k, v in SECTION_NAMES.items()}[self.section.get()]
        self.result = {"id": self.book_id or ("X_" + "".join(c for c in name if c.isalnum())[:24]),
                       "name": name, "spellings": _split(self.v["spellings"].get()),
                       "abbreviations": _split(self.v["abbreviations"].get()),
                       "section": sec, "position": pos, "chapters": ch}
        self.destroy()


# ---------------------------------------------------------------------------
class SettingsDialog(tk.Toplevel):
    """Languages & abbreviations, index sections, custom books, import/export."""

    TABS = ["abbr", "sections", "custom", "words", "tagged", "sets"]

    def __init__(self, master, settings: dict, tab: str = "abbr"):
        super().__init__(master)
        self.title("Settings")
        self.geometry("1040x700")
        self.transient(master)
        self.s = copy.deepcopy(settings)
        self.result = None
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        self._tab_abbr(nb)
        self._tab_sections(nb)
        self._tab_custom(nb)
        self._tab_words(nb)
        self._tab_sets(nb)
        if tab in self.TABS:
            nb.select(self.TABS.index(tab))
        btns = ttk.Frame(self, padding=(8, 0, 8, 8))
        btns.pack(fill="x")
        ttk.Button(btns, text="Export settings…", command=self._export).pack(side="left")
        ttk.Button(btns, text="Import settings…", command=self._import).pack(side="left", padx=6)
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(btns, text="Save", command=self._ok).pack(side="right", padx=6)
        center(self, master)
        self.grab_set()

    # -- abbreviations ------------------------------------------------------------
    def _tab_abbr(self, nb):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text="Languages & abbreviations")
        top = ttk.Frame(f)
        top.pack(fill="x")
        ttk.Label(top, text="Language:").pack(side="left")
        self.lang_names = {PROFILES[c]["name"]: c for c in LANGUAGE_ORDER}
        self.abbr_lang = ttk.Combobox(top, values=list(self.lang_names), state="readonly", width=26)
        self.abbr_lang.set(PROFILES[self.s.get("language", "en")]["name"])
        self.abbr_lang.pack(side="left", padx=6)
        self.abbr_lang.bind("<<ComboboxSelected>>", lambda e: self._load_lang())
        self.sets_frame = ttk.LabelFrame(f, text="Abbreviation sets to recognize", padding=(8, 4))
        self.sets_frame.pack(fill="x", pady=8)
        body = ttk.Frame(f)
        body.pack(fill="both", expand=True)
        self.book_tv = ttk.Treeview(body, columns=("name", "spellings"), show="headings", height=16)
        self.book_tv.heading("name", text="Book")
        self.book_tv.heading("spellings", text="Recognized spellings")
        self.book_tv.column("name", width=180, stretch=False)
        self.book_tv.column("spellings", width=420)
        ys = ttk.Scrollbar(body, orient="vertical", command=self.book_tv.yview)
        self.book_tv.configure(yscrollcommand=ys.set)
        self.book_tv.pack(side="left", fill="both", expand=True)
        ys.pack(side="left", fill="y")
        self.book_tv.bind("<<TreeviewSelect>>", lambda e: self._show_book())
        ed = ttk.Frame(body, padding=(10, 0))
        ed.pack(side="left", fill="y")
        self.ed_title = ttk.Label(ed, text="Select a book", font=("Segoe UI", 10, "bold"))
        self.ed_title.pack(anchor="w")
        ttk.Label(ed, text="Name printed in the index:").pack(anchor="w", pady=(8, 0))
        self.ed_name = tk.StringVar()
        ttk.Entry(ed, textvariable=self.ed_name, width=34).pack(anchor="w")
        ttk.Label(ed, text="Add abbreviations / spellings (comma-separated):").pack(anchor="w", pady=(8, 0))
        self.ed_add = tk.StringVar()
        ttk.Entry(ed, textvariable=self.ed_add, width=34).pack(anchor="w")
        ttk.Label(ed, text="Don't recognize (comma-separated):").pack(anchor="w", pady=(8, 0))
        self.ed_remove = tk.StringVar()
        ttk.Entry(ed, textvariable=self.ed_remove, width=34).pack(anchor="w")
        ttk.Button(ed, text="Apply to this book", command=self._apply_book).pack(anchor="w", pady=10)
        self.note = ttk.Label(ed, wraplength=260, justify="left", foreground="#7a4b00")
        self.note.pack(anchor="w")
        self.cur_book = None
        self._load_lang()

    def _code(self):
        return self.lang_names[self.abbr_lang.get()]

    def _load_lang(self):
        code = self._code()
        p = PROFILES[code]
        ls = SET.lang_settings(self.s, code)
        for w in self.sets_frame.winfo_children():
            w.destroy()
        self.set_vars = {}
        disabled = set(ls.get("disabled_sets", []))
        for name in p["sets"]:
            v = tk.BooleanVar(value=name not in disabled)
            unconf = " (unconfirmed — please review)" if name in p.get("unconfirmed_sets", []) else ""
            ttk.Checkbutton(self.sets_frame, text=name + unconf, variable=v,
                            command=self._sets_changed).pack(side="left", padx=(0, 16))
            self.set_vars[name] = v
        self._fill_books()

    def _sets_changed(self):
        ls = SET.lang_settings(self.s, self._code())
        ls["disabled_sets"] = [n for n, v in self.set_vars.items() if not v.get()]
        self._fill_books()

    def _fill_books(self):
        code = self._code()
        s2 = copy.deepcopy(self.s)
        s2["language"] = code
        s2["apocrypha"] = True
        cat, lang = SET.make_context(s2)
        by_book: dict[str, list] = {}
        for key, (bid, kind, short, bare) in lang.spellings.items():
            by_book.setdefault(bid, []).append(key)
        self.book_tv.delete(*self.book_tv.get_children())
        for name, bid in book_choices(cat):
            sp = sorted(by_book.get(bid, []), key=lambda k: (len(k), k))
            self.book_tv.insert("", "end", iid=bid, values=(name, ", ".join(sp)))
        self._cat = cat
        p = PROFILES[code]
        note = ""
        if p.get("unconfirmed_names"):
            note = ("Names for the " + ", ".join(SECTION_NAMES[x] for x in p["unconfirmed_names"]) +
                    " in this language are starter forms — please check them. ")
        if code != "en":
            note += ("Apocrypha abbreviations are included only where a published standard confirmed "
                     "them; add the ones your style uses.")
        self.note.configure(text=note)

    def _show_book(self):
        sel = self.book_tv.selection()
        if not sel:
            return
        bid = sel[0]
        self.cur_book = bid
        ls = SET.lang_settings(self.s, self._code())
        o = ls.get("books", {}).get(bid, {})
        self.ed_title.configure(text=self._cat.name(bid))
        self.ed_name.set(ls.get("names", {}).get(bid, self._cat.name(bid)))
        self.ed_add.set(", ".join(o.get("add", [])))
        self.ed_remove.set(", ".join(o.get("remove", [])))

    def _apply_book(self):
        if not self.cur_book:
            return
        ls = SET.lang_settings(self.s, self._code())
        bid = self.cur_book
        books = ls.setdefault("books", {})
        books[bid] = {"add": _split(self.ed_add.get()), "remove": _split(self.ed_remove.get())}
        default_name = PROFILES[self._code()].get("names", {}).get(bid)
        nm = self.ed_name.get().strip()
        names = ls.setdefault("names", {})
        if nm and nm != default_name:
            names[bid] = nm
        else:
            names.pop(bid, None)
        self._fill_books()
        if self.book_tv.exists(bid):
            self.book_tv.selection_set(bid)
            self.book_tv.see(bid)

    # -- sections -------------------------------------------------------------------
    def _tab_sections(self, nb):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text="Index sections")
        ttk.Label(f, text="Order of sections (used for one index and for split indexes):").grid(
            row=0, column=0, columnspan=3, sticky="w")
        self.sec_lb = tk.Listbox(f, height=6, width=34, exportselection=False)
        self.sec_lb.grid(row=1, column=0, rowspan=4, sticky="nw", pady=4)
        self.sec_order = list(self.s.get("section_order", ["OT", "AP", "NT", "OTHER"]))
        for k in SECTION_KEYS:
            if k not in self.sec_order:
                self.sec_order.append(k)
        self._fill_sections()
        ttk.Button(f, text="Move up", command=lambda: self._move(-1)).grid(row=1, column=1, sticky="w", padx=6)
        ttk.Button(f, text="Move down", command=lambda: self._move(1)).grid(row=2, column=1, sticky="w", padx=6)
        ttk.Label(f, foreground="#555", text="Planned (not available yet): " +
                  ", ".join(PLACEHOLDER_SECTIONS.values())).grid(row=5, column=0, columnspan=3, sticky="w", pady=(6, 12))
        ttk.Label(f, text="Old Testament order:").grid(row=6, column=0, sticky="w")
        self.ot_labels = {"Language default": None}
        self.ot_labels.update({v: k for k, v in OT_ORDER_LABELS.items()})
        self.ot_order = ttk.Combobox(f, values=list(self.ot_labels), state="readonly", width=34)
        cur = self.s.get("ot_order")
        self.ot_order.set(OT_ORDER_LABELS.get(cur, "Language default") if cur else "Language default")
        self.ot_order.grid(row=6, column=1, sticky="w", padx=6)
        ttk.Label(f, foreground="#555", text="Hebrew defaults to Tanakh order (JPS/Koren); other languages "
                  "to English Bible order.").grid(row=7, column=0, columnspan=3, sticky="w")
        ttk.Label(f, text="Section headings for the current language (blank = default):").grid(
            row=8, column=0, columnspan=3, sticky="w", pady=(14, 4))
        code = self.s.get("language", "en")
        ls = SET.lang_settings(self.s, code)
        p = PROFILES[code]
        self.title_vars = {}
        ttk.Label(f, text="Index title:").grid(row=9, column=0, sticky="w")
        v = tk.StringVar(value=ls.get("index_title", ""))
        ttk.Entry(f, textvariable=v, width=40).grid(row=9, column=1, sticky="w", padx=6)
        ttk.Label(f, foreground="#777", text=p["index_title"]).grid(row=9, column=2, sticky="w")
        self.title_vars["__index__"] = v
        for i, k in enumerate(SECTION_KEYS):
            ttk.Label(f, text=SECTION_NAMES[k] + ":").grid(row=10 + i, column=0, sticky="w")
            v = tk.StringVar(value=ls.get("section_titles", {}).get(k, ""))
            ttk.Entry(f, textvariable=v, width=40).grid(row=10 + i, column=1, sticky="w", padx=6, pady=2)
            ttk.Label(f, foreground="#777", text=p["section_titles"].get(k, "")).grid(row=10 + i, column=2, sticky="w")
            self.title_vars[k] = v

    def _fill_sections(self):
        self.sec_lb.delete(0, "end")
        for k in self.sec_order:
            self.sec_lb.insert("end", SECTION_NAMES[k])

    def _move(self, d):
        sel = self.sec_lb.curselection()
        if not sel:
            return
        i = sel[0]
        j = i + d
        if 0 <= j < len(self.sec_order):
            self.sec_order[i], self.sec_order[j] = self.sec_order[j], self.sec_order[i]
            self._fill_sections()
            self.sec_lb.selection_set(j)

    # -- custom books ---------------------------------------------------------------
    def _tab_custom(self, nb):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text="Custom books")
        ttk.Label(f, wraplength=900, justify="left", text=(
            "Add any work a book or dissertation cites — for example a pseudepigraphal book or a "
            "church father — with its spellings, abbreviations and place in the index. Custom books "
            "work in every language and are included when you export your settings.")).pack(anchor="w")
        self.cb_tv = ttk.Treeview(f, columns=("name", "section", "pos", "abbr"), show="headings", height=14)
        for c, t, wd in (("name", "Name", 220), ("section", "Section", 160), ("pos", "Position", 80),
                         ("abbr", "Spellings and abbreviations", 420)):
            self.cb_tv.heading(c, text=t)
            self.cb_tv.column(c, width=wd)
        self.cb_tv.pack(fill="both", expand=True, pady=8)
        b = ttk.Frame(f)
        b.pack(fill="x")
        ttk.Button(b, text="Add…", command=self._cb_add).pack(side="left")
        ttk.Button(b, text="Edit…", command=self._cb_edit).pack(side="left", padx=6)
        ttk.Button(b, text="Remove", command=self._cb_remove).pack(side="left")
        self._cb_fill()

    def _cb_fill(self):
        self.cb_tv.delete(*self.cb_tv.get_children())
        for i, cb in enumerate(self.s.get("custom_books", [])):
            self.cb_tv.insert("", "end", iid=str(i), values=(
                cb.get("name"), SECTION_NAMES.get(cb.get("section", "OTHER")), cb.get("position", 999),
                ", ".join(cb.get("spellings", []) + cb.get("abbreviations", []))))

    def _cb_add(self):
        d = CustomBookDialog(self, None)
        self.wait_window(d)
        if d.result:
            self.s.setdefault("custom_books", []).append(d.result)
            self._cb_fill()

    def _cb_edit(self):
        sel = self.cb_tv.selection()
        if not sel:
            return
        i = int(sel[0])
        d = CustomBookDialog(self, self.s["custom_books"][i])
        self.wait_window(d)
        if d.result:
            self.s["custom_books"][i] = d.result
            self._cb_fill()

    def _cb_remove(self):
        sel = self.cb_tv.selection()
        if sel and messagebox.askyesno("Custom books", "Remove the selected book?", parent=self):
            del self.s["custom_books"][int(sel[0])]
            self._cb_fill()

    # -- original-language words ------------------------------------------------------
    def _tab_words(self, nb):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text="Original-language words")
        ws = T.words_settings(self.s)
        self.ws = ws
        ttk.Label(f, wraplength=940, justify="left", text=(
            "Index every Greek, Hebrew or Syriac word in the manuscript, each in its own index. "
            "These alphabets are found by their letters alone. Each index can be switched on and "
            "off here or in the main window.")).grid(row=0, column=0, columnspan=4, sticky="w")
        self.script_vars = {}
        for i, key in enumerate(T.SCRIPT_ORDER):
            info, cur = T.SCRIPT_INDEXES[key], ws["scripts"][key]
            on = tk.BooleanVar(value=bool(cur.get("enabled")))
            title = tk.StringVar(value=cur.get("title") or info["title"])
            ttk.Checkbutton(f, text=info["label"], variable=on).grid(row=1 + i, column=0, sticky="w", pady=2)
            ttk.Label(f, text="Index title:").grid(row=1 + i, column=1, sticky="e", padx=(12, 4))
            ttk.Entry(f, textvariable=title, width=40).grid(row=1 + i, column=2, sticky="w")
            ttk.Button(f, text="Words to skip…", command=lambda k=key: self._edit_skip_script(k)).grid(
                row=1 + i, column=3, sticky="w", padx=6)
            self.script_vars[key] = (on, title)
        opts = ttk.LabelFrame(f, text="How words are found", padding=(10, 6))
        opts.grid(row=5, column=0, columnspan=4, sticky="we", pady=(12, 0))
        self.w_group = tk.BooleanVar(value=ws["group_forms"])
        ttk.Checkbutton(opts, variable=self.w_group, text=(
            "Group forms that differ only in accents, breathings, vowel points or cantillation marks "
            "(λόγος = λογος; דָּבָר = דבר)")).grid(row=0, column=0, columnspan=6, sticky="w")
        self.w_block = tk.BooleanVar(value=ws["skip_block_quotes"])
        ttk.Checkbutton(opts, variable=self.w_block, text=(
            "Skip block quotations: paragraphs in a quotation style, and indented paragraphs of prose")).grid(
            row=1, column=0, columnspan=6, sticky="w", pady=(4, 0))
        self.w_run = tk.IntVar(value=int(ws["max_run"]))
        self.w_item = tk.IntVar(value=int(ws["list_item_max"]))
        self.w_min = tk.IntVar(value=int(ws["min_letters"]))
        r = ttk.Frame(opts)
        r.grid(row=2, column=0, columnspan=6, sticky="w", pady=(6, 0))
        ttk.Label(r, text="Within a paragraph, more than").pack(side="left")
        ttk.Spinbox(r, from_=1, to=50, width=4, textvariable=self.w_run).pack(side="left", padx=4)
        ttk.Label(r, text="words in a row are a quotation and are skipped,").pack(side="left")
        r2 = ttk.Frame(opts)
        r2.grid(row=3, column=0, columnspan=6, sticky="w")
        ttk.Label(r2, text="unless they form a list (separated by commas, semicolons or slashes) of items no longer "
                           "than").pack(side="left")
        ttk.Spinbox(r2, from_=1, to=10, width=4, textvariable=self.w_item).pack(side="left", padx=4)
        ttk.Label(r2, text="words each.").pack(side="left")
        r3 = ttk.Frame(opts)
        r3.grid(row=4, column=0, columnspan=6, sticky="w", pady=(4, 0))
        ttk.Label(r3, text="Ignore words shorter than").pack(side="left")
        ttk.Spinbox(r3, from_=1, to=6, width=4, textvariable=self.w_min).pack(side="left", padx=4)
        ttk.Label(r3, text="letters.").pack(side="left")
        ttk.Label(opts, foreground="#555", wraplength=900, justify="left", text=(
            "Skipped quotations are listed in the review table (grey) and the proofreading list, so you "
            "can include one if the author discusses its words. Words in tables are counted cell by cell.")).grid(
            row=5, column=0, columnspan=6, sticky="w", pady=(6, 0))

        f.columnconfigure(2, weight=1)
        tgf = ttk.Frame(nb, padding=10)
        nb.add(tgf, text="Other languages")
        tg = ttk.LabelFrame(tgf, text="Words tagged in another language (Latin, German, …)", padding=(10, 6))
        tg.pack(fill="both", expand=True)
        ttk.Label(tg, wraplength=900, justify="left", text=(
            "Latin and other languages written in the same alphabet as the book can't be told apart by "
            "their letters. These indexes take the words the manuscript marks as that language (in Word: "
            "select the text, then Review > Language > Set Proofing Language). For untagged words, use a "
            "term set.")).pack(anchor="w")
        row = ttk.Frame(tg)
        row.pack(fill="both", expand=True, pady=(6, 0))
        self.tag_tv = ttk.Treeview(row, columns=("on", "lang", "title"), show="headings", height=8)
        for c, t, wd in (("on", "On", 40), ("lang", "Language", 120), ("title", "Index title", 360)):
            self.tag_tv.heading(c, text=t)
            self.tag_tv.column(c, width=wd, stretch=c == "title")
        self.tag_tv.pack(side="left", fill="both", expand=True)
        self.tag_tv.bind("<Double-1>", lambda e: self._tag_toggle())
        b = ttk.Frame(tg)
        b.pack(fill="x", pady=(6, 0))
        self.tag_new = ttk.Combobox(b, values=[v[0] for v in T.TAGGED_LANGUAGES.values()], state="readonly",
                                    width=14)
        self.tag_new.set("Latin")
        self.tag_new.pack(side="left")
        ttk.Button(b, text="Add", command=self._tag_add).pack(side="left", padx=(4, 16))
        ttk.Button(b, text="On / off", command=self._tag_toggle).pack(side="left")
        ttk.Button(b, text="Rename index…", command=self._tag_rename).pack(side="left", padx=4)
        ttk.Button(b, text="Words to skip…", command=self._tag_skip).pack(side="left")
        ttk.Button(b, text="Remove", command=self._tag_remove).pack(side="left", padx=4)
        self.tagged = [dict(t) for t in ws.get("tagged", [])]
        self._tag_fill()
        ttk.Label(f, foreground="#7a4b00", wraplength=940, justify="left", text=(
            "When the book itself is written in Hebrew, the Hebrew word index stays off (it would list "
            "every word). Build a term set with the words you want indexed instead.")).grid(
            row=6, column=0, columnspan=4, sticky="w", pady=(10, 0))

    def _edit_skip_script(self, key):
        cur = self.ws["scripts"][key].get("skip", T.SCRIPT_INDEXES[key]["skip"])
        d = TextListDialog(self, f"Words to skip — {T.SCRIPT_INDEXES[key]['label']}", cur,
                           "Words listed here are never indexed. Accents, breathings and vowel points are "
                           "ignored when comparing. Separate words with spaces or new lines.",
                           T.SCRIPT_INDEXES[key]["skip"])
        self.wait_window(d)
        if d.result is not None:
            self.ws["scripts"][key]["skip"] = d.result

    def _tag_fill(self):
        self.tag_tv.delete(*self.tag_tv.get_children())
        for i, t in enumerate(self.tagged):
            name = T.TAGGED_LANGUAGES.get(t["lang"], (t["lang"],))[0]
            self.tag_tv.insert("", "end", iid=str(i), values=("✔" if t.get("enabled") else "", name,
                                                              t.get("title", "")))

    def _tag_sel(self):
        sel = self.tag_tv.selection()
        return int(sel[0]) if sel else None

    def _tag_add(self):
        name = self.tag_new.get()
        code = next((k for k, v in T.TAGGED_LANGUAGES.items() if v[0] == name), None)
        if not code or any(t["lang"] == code for t in self.tagged):
            return
        info = T.TAGGED_LANGUAGES[code]
        self.tagged.append({"lang": code, "enabled": True, "title": info[1], "skip": info[3]})
        self._tag_fill()

    def _tag_toggle(self):
        i = self._tag_sel()
        if i is not None:
            self.tagged[i]["enabled"] = not self.tagged[i].get("enabled")
            self._tag_fill()
            self.tag_tv.selection_set(str(i))

    def _tag_rename(self):
        i = self._tag_sel()
        if i is None:
            return
        d = TextListDialog(self, "Index title", self.tagged[i].get("title", ""), "Title printed above this index.",
                           None, single=True)
        self.wait_window(d)
        if d.result:
            self.tagged[i]["title"] = d.result
            self._tag_fill()

    def _tag_skip(self):
        i = self._tag_sel()
        if i is None:
            return
        t = self.tagged[i]
        default = T.TAGGED_LANGUAGES.get(t["lang"], ("", "", [], ""))[3]
        d = TextListDialog(self, "Words to skip", t.get("skip", default),
                           "Words listed here are never indexed.", default)
        self.wait_window(d)
        if d.result is not None:
            t["skip"] = d.result

    def _tag_remove(self):
        i = self._tag_sel()
        if i is not None:
            del self.tagged[i]
            self._tag_fill()

    def _collect_words(self):
        ws = self.ws
        for key, (on, title) in self.script_vars.items():
            ws["scripts"][key]["enabled"] = bool(on.get())
            ws["scripts"][key]["title"] = title.get().strip() or T.SCRIPT_INDEXES[key]["title"]
        ws["group_forms"] = bool(self.w_group.get())
        ws["skip_block_quotes"] = bool(self.w_block.get())
        for k, var, lo in (("max_run", self.w_run, 1), ("list_item_max", self.w_item, 1), ("min_letters", self.w_min, 1)):
            try:
                ws[k] = max(lo, int(var.get()))
            except (tk.TclError, ValueError):
                pass
        ws["tagged"] = self.tagged
        self.s["words"] = ws
        self.s["term_sets"] = self.sets

    # -- term sets ------------------------------------------------------------------------
    def _tab_sets(self, nb):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text="Term sets")
        ttk.Label(f, wraplength=940, justify="left", text=(
            "A term set is a list of words or names to index, each set in its own index (for example a "
            "subject index, or the Hebrew words a Hebrew-language book discusses). Build one from a plain "
            "text file — one term per line, with other forms after a vertical bar (λόγος | λόγου | λόγῳ) — "
            "or from a CSV file with the columns heading, subentry, match forms, sort as, see, see also. "
            "Sets are saved with your settings and exported with them.")).pack(anchor="w")
        ttk.Label(f, foreground="#7a4b00", wraplength=940, justify="left", text=(
            "A term set works like a concordance: it finds every place a listed form appears, but it can't "
            "tell whether a passage is really about the term. Review the rows before building, and exclude "
            "passing mentions.")).pack(anchor="w", pady=(6, 0))
        row = ttk.Frame(f)
        row.pack(fill="both", expand=True, pady=8)
        self.set_tv = ttk.Treeview(row, columns=("on", "name", "title", "n", "opts"), show="headings", height=12)
        for c, t, wd in (("on", "On", 40), ("name", "Set", 180), ("title", "Index title", 220),
                         ("n", "Entries", 70), ("opts", "Matching", 380)):
            self.set_tv.heading(c, text=t)
            self.set_tv.column(c, width=wd, stretch=c in ("opts", "title"))
        self.set_tv.bind("<Double-1>", lambda e: self._set_edit())
        b = ttk.Frame(row, padding=(8, 0))
        b.pack(side="right", fill="y")
        self.set_tv.pack(side="left", fill="both", expand=True)
        ttk.Button(b, text="Build a new set…", command=self._set_new, width=22).pack(anchor="w", fill="x")
        ttk.Button(b, text="Edit…", command=self._set_edit).pack(anchor="w", fill="x", pady=(4, 0))
        ttk.Button(b, text="On / off", command=self._set_toggle).pack(anchor="w", fill="x", pady=(4, 0))
        ttk.Button(b, text="Replace terms from a file…", command=self._set_replace).pack(anchor="w", fill="x",
                                                                                        pady=(4, 0))
        ttk.Button(b, text="Export set as CSV…", command=self._set_export).pack(anchor="w", fill="x", pady=(4, 0))
        ttk.Button(b, text="Remove", command=self._set_remove).pack(anchor="w", fill="x", pady=(4, 0))
        ttk.Separator(b).pack(fill="x", pady=10)
        ttk.Button(b, text="Save a sample CSV…", command=self._set_sample).pack(anchor="w", fill="x")
        self.sets = copy.deepcopy(self.s.get("term_sets", []))
        self._set_fill()

    def _set_fill(self):
        self.set_tv.delete(*self.set_tv.get_children())
        for i, ts in enumerate(self.sets):
            o = dict(T.TERM_SET_OPTIONS)
            o.update(ts.get("options", {}))
            bits = ["case-sensitive" if o["case_sensitive"] else "any case",
                    "accents ignored" if o["ignore_marks"] else "exact accents",
                    "whole words" if o["whole_words"] else "parts of words too"]
            if o["plurals"]:
                bits.append("+ plurals")
            if o["hebrew_prefixes"]:
                bits.append("+ Hebrew prefixes")
            if o["skip_block_quotes"]:
                bits.append("block quotations skipped")
            self.set_tv.insert("", "end", iid=str(i), values=(
                "✔" if ts.get("enabled") else "", ts.get("name", ""), ts.get("title", ""),
                len(ts.get("entries", [])), ", ".join(bits)))

    def _set_sel(self):
        sel = self.set_tv.selection()
        return int(sel[0]) if sel else None

    def _ask_file(self):
        return filedialog.askopenfilename(parent=self, title="Choose a term list", filetypes=[
            ("Term lists", "*.txt *.csv *.tsv"), ("Text", "*.txt"), ("CSV", "*.csv"), ("All files", "*.*")])

    def _load_file(self, path):
        try:
            entries, problems = T.read_term_file(path)
        except Exception as exc:
            messagebox.showerror("Term set", f"Could not read the file: {exc}", parent=self)
            return None
        if not entries:
            messagebox.showwarning("Term set", "\n".join(problems) or "No terms found.", parent=self)
            return None
        if problems:
            messagebox.showinfo("Term set", f"{len(entries)} entries read.\n\n" + "\n".join(problems[:15]),
                                parent=self)
        return entries

    def _set_new(self):
        path = self._ask_file()
        if not path:
            return
        entries = self._load_file(path)
        if entries is None:
            return
        name = T.clean_set_name(Path(path).stem)
        ts = {"id": T.new_set_id(self.sets), "name": name, "title": name if name.lower().startswith("index")
              else f"Index of {name}", "enabled": True, "options": dict(T.TERM_SET_OPTIONS),
              "entries": entries, "source": Path(path).name}
        d = TermSetDialog(self, ts)
        self.wait_window(d)
        if d.result:
            self.sets.append(d.result)
            self._set_fill()
            self.set_tv.selection_set(str(len(self.sets) - 1))

    def _set_edit(self):
        i = self._set_sel()
        if i is None:
            return
        d = TermSetDialog(self, self.sets[i])
        self.wait_window(d)
        if d.result:
            self.sets[i] = d.result
            self._set_fill()
            self.set_tv.selection_set(str(i))

    def _set_toggle(self):
        i = self._set_sel()
        if i is not None:
            self.sets[i]["enabled"] = not self.sets[i].get("enabled")
            self._set_fill()
            self.set_tv.selection_set(str(i))

    def _set_replace(self):
        i = self._set_sel()
        if i is None:
            messagebox.showinfo("Term sets", "Select a set first.", parent=self)
            return
        path = self._ask_file()
        if not path:
            return
        entries = self._load_file(path)
        if entries is not None:
            self.sets[i]["entries"] = entries
            self.sets[i]["source"] = Path(path).name
            self._set_fill()

    def _set_export(self):
        i = self._set_sel()
        if i is None:
            return
        f = filedialog.asksaveasfilename(parent=self, defaultextension=".csv",
                                         initialfile=f"{self.sets[i].get('name', 'terms')}.csv",
                                         filetypes=[("CSV", "*.csv")])
        if f:
            T.write_term_csv(f, self.sets[i].get("entries", []))

    def _set_remove(self):
        i = self._set_sel()
        if i is not None and messagebox.askyesno("Term sets", f"Remove the set “{self.sets[i].get('name')}”?",
                                                 parent=self):
            del self.sets[i]
            self._set_fill()

    def _set_sample(self):
        f = filedialog.asksaveasfilename(parent=self, defaultextension=".csv", initialfile="Sample term set.csv",
                                         filetypes=[("CSV", "*.csv")])
        if f:
            Path(f).write_text(T.sample_csv(), encoding="utf-8-sig")

    # -- import / export / save --------------------------------------------------------
    def _collect(self):
        self._collect_words()
        self.s["section_order"] = list(self.sec_order)
        self.s["ot_order"] = self.ot_labels.get(self.ot_order.get())
        ls = SET.lang_settings(self.s, self.s.get("language", "en"))
        it = self.title_vars["__index__"].get().strip()
        if it:
            ls["index_title"] = it
        else:
            ls.pop("index_title", None)
        st = {k: v.get().strip() for k, v in self.title_vars.items() if k != "__index__" and v.get().strip()}
        ls["section_titles"] = st

    def _export(self):
        self._collect()
        f = filedialog.asksaveasfilename(parent=self, defaultextension=".json",
                                         initialfile="Indicat settings.json",
                                         filetypes=[("Settings", "*.json")])
        if f:
            SET.export_to(self.s, f)
            messagebox.showinfo("Export settings", "Settings exported. Import this file in any version of "
                                "the app to restore them.", parent=self)

    def _import(self):
        f = filedialog.askopenfilename(parent=self, filetypes=[("Settings", "*.json")])
        if not f:
            return
        try:
            self.s = SET.import_from(self.s, f)
        except Exception as exc:
            messagebox.showerror("Import settings", f"Could not read that file: {exc}", parent=self)
            return
        self.result = self.s
        messagebox.showinfo("Import settings", "Settings imported.", parent=self)
        self.destroy()

    def _ok(self):
        self._collect()
        self.result = self.s
        self.destroy()


# ---------------------------------------------------------------------------
class TextListDialog(tk.Toplevel):
    """Edit a list of words (or one line of text)."""

    def __init__(self, master, title, text, note, default=None, single=False):
        super().__init__(master)
        self.title(title)
        self.transient(master)
        self.result = None
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=note, wraplength=520, justify="left").pack(anchor="w")
        if single:
            self.var = tk.StringVar(value=text)
            e = ttk.Entry(frm, textvariable=self.var, width=60)
            e.pack(fill="x", pady=8)
            self.txt = None
        else:
            self.txt = tk.Text(frm, width=64, height=12, wrap="word", font=("Segoe UI", 11))
            self.txt.insert("1.0", text)
            self.txt.pack(fill="both", expand=True, pady=8)
        b = ttk.Frame(frm)
        b.pack(fill="x")
        if default is not None:
            ttk.Button(b, text="Restore the default list", command=lambda: self._set(default)).pack(side="left")
        ttk.Button(b, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(b, text="OK", command=self._ok).pack(side="right", padx=6)
        center(self, master)
        self.grab_set()

    def _set(self, text):
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", text)

    def _ok(self):
        if self.txt is None:
            self.result = self.var.get().strip()
        else:
            self.result = " ".join(self.txt.get("1.0", "end").split())
        self.destroy()


class TermSetDialog(tk.Toplevel):
    """Name, index title and matching options of a term set."""

    LABELS = [("case_sensitive", "Match capital letters exactly (Grace ≠ grace)"),
              ("ignore_marks", "Ignore accents, breathings and vowel points (λόγος = λογος)"),
              ("whole_words", "Whole words only (off: also inside longer words)"),
              ("plurals", "Also match simple English plurals (-s, -es)"),
              ("hebrew_prefixes", "Also match Hebrew words with prefixes (ו ה ב כ ל מ ש)"),
              ("skip_block_quotes", "Skip block quotations (quotation styles and indented prose)")]

    def __init__(self, master, ts: dict):
        super().__init__(master)
        self.title("Term set")
        self.resizable(False, False)
        self.transient(master)
        self.result = None
        self.ts = copy.deepcopy(ts)
        frm = ttk.Frame(self, padding=14)
        frm.pack(fill="both", expand=True)
        self.name = tk.StringVar(value=ts.get("name", ""))
        self.title_v = tk.StringVar(value=ts.get("title", ""))
        ttk.Label(frm, text="Name of the set:").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.name, width=44).grid(row=0, column=1, sticky="w", padx=6, pady=2)
        ttk.Label(frm, text="Index title:").grid(row=1, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.title_v, width=44).grid(row=1, column=1, sticky="w", padx=6, pady=2)
        o = dict(T.TERM_SET_OPTIONS)
        o.update(ts.get("options", {}))
        self.vars = {}
        box = ttk.LabelFrame(frm, text="Matching", padding=(10, 6))
        box.grid(row=2, column=0, columnspan=2, sticky="we", pady=(10, 0))
        for k, label in self.LABELS:
            v = tk.BooleanVar(value=bool(o.get(k)))
            ttk.Checkbutton(box, text=label, variable=v).pack(anchor="w")
            self.vars[k] = v
        entries = ts.get("entries", [])
        subs = sum(1 for e in entries if e.get("sub"))
        xr = sum(1 for e in entries if e.get("see") or e.get("see_also"))
        info = f"{len(entries)} entries"
        if subs:
            info += f", {subs} subentries"
        if xr:
            info += f", {xr} cross-references"
        if ts.get("source"):
            info += f" (from {ts['source']})"
        ttk.Label(frm, text=info, foreground="#555").grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))
        prev = tk.Listbox(frm, height=8, width=70, font=("Segoe UI", 10))
        for e in entries[:200]:
            line = e.get("heading", "") + (f" › {e['sub']}" if e.get("sub") else "")
            if e.get("see"):
                line += f"   (see {e['see']})"
            elif e.get("forms"):
                line += "   ← " + " | ".join(e["forms"][:6]) + (" …" if len(e["forms"]) > 6 else "")
            prev.insert("end", line)
        prev.grid(row=4, column=0, columnspan=2, sticky="we", pady=(4, 0))
        b = ttk.Frame(frm)
        b.grid(row=5, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(b, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(b, text="OK", command=self._ok).pack(side="right", padx=6)
        center(self, master)
        self.grab_set()

    def _ok(self):
        name = self.name.get().strip()
        if not name:
            messagebox.showwarning("Term set", "Give the set a name.", parent=self)
            return
        self.ts["name"] = name
        self.ts["title"] = self.title_v.get().strip() or name
        self.ts["options"] = {k: bool(v.get()) for k, v in self.vars.items()}
        self.result = self.ts
        self.destroy()


class TermEditDialog(tk.Toplevel):
    """Change the heading (and subentry) a word or term is filed under."""

    def __init__(self, master, occ):
        super().__init__(master)
        self.title("Edit entry")
        self.resizable(False, False)
        self.transient(master)
        self.result = None
        frm = ttk.Frame(self, padding=16)
        frm.pack(fill="both", expand=True)
        ctx = tk.Text(frm, width=70, height=4, wrap="word", font=("Segoe UI", 10))
        ctx.insert("1.0", occ.context)
        ctx.configure(state="disabled")
        ctx.grid(row=0, column=0, columnspan=2, sticky="we", pady=(0, 8))
        r = occ.ref
        self.h = tk.StringVar(value=r.heading if r else occ.hit.raw)
        self.sub = tk.StringVar(value=r.sub if r else "")
        ttk.Label(frm, text="Heading:").grid(row=1, column=0, sticky="w")
        e = ttk.Entry(frm, textvariable=self.h, width=40, font=("Segoe UI", 11))
        e.grid(row=1, column=1, sticky="w", pady=3)
        ttk.Label(frm, text="Subentry (optional):").grid(row=2, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.sub, width=40, font=("Segoe UI", 11)).grid(row=2, column=1, sticky="w")
        ttk.Label(frm, foreground="#555", wraplength=480, justify="left", text=(
            "Use this to file a word under its dictionary form (λόγου under λόγος), or to correct a "
            "heading. Only this occurrence changes; for a lasting rule, add the form to a term set.")).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))
        b = ttk.Frame(frm)
        b.grid(row=4, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(b, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(b, text="OK", command=self._ok).pack(side="right", padx=6)
        self.occ = occ
        center(self, master)
        self.grab_set()
        e.focus_set()

    def _ok(self):
        h = self.h.get().strip()
        if not h:
            messagebox.showwarning("Edit entry", "Enter a heading.", parent=self)
            return
        old = self.occ.ref
        self.result = T.TermRef(self.occ.index, h, self.sub.get().strip(), "", "",
                                old.key if old is not None else T.fold_str(h))
        if old is not None and h == old.heading:
            self.result.sort = old.sort
        self.destroy()
