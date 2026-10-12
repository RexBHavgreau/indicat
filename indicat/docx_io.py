"""Reading and writing .docx packages at the XML level (lxml).

Reading turns the main story, footnotes and endnotes into *segments*
(paragraph text plus a map back to the <w:t> nodes) so the parser can work on
plain strings.  Writing inserts XE fields and hidden bookmarks at exact
character offsets without touching any of the manuscript's own text.
"""
from __future__ import annotations

import copy
import re
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
XML_NS = "http://www.w3.org/XML/1998/namespace"


def w(tag: str) -> str:
    return f"{{{W}}}{tag}"


WVAL = w("val")
SKIP_FIELD_RESULTS = {"INDEX", "TOC", "TOA", "PAGEREF", "NOTEREF", "SEQ", "PAGE", "NUMPAGES"}
PARTS = {"document": "word/document.xml", "footnotes": "word/footnotes.xml",
         "endnotes": "word/endnotes.xml"}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class TNode:
    el: etree._Element
    start: int
    length: int


@dataclass
class Anchor:
    offset: int
    kind: str          # "footnote" | "endnote"
    note_id: str


@dataclass
class Segment:
    part: str                      # "document" | "footnotes" | "endnotes"
    idx: int                       # running number within its part
    text: str = ""
    italic: list = field(default_factory=list)
    tnodes: list = field(default_factory=list)
    anchors: list = field(default_factory=list)
    heading: bool = False
    level: int | None = None       # heading level (0 = top) when heading
    biblio: bool = False           # in the bibliography
    style_names: tuple = ()        # paragraph style and the styles it is based on
    style_id: str | None = None    # paragraph style
    note_kind: str | None = None   # for note segments
    note_id: str | None = None
    in_simple_field: list = field(default_factory=list)   # spans inside w:fldSimple (not writable)
    langs: list = field(default_factory=list)     # language tag of each character (or None)
    quote: str | None = None                      # "style" | "indent" | None (block quotation?)
    in_table: bool = False

    def add(self, s: str, ital: bool, node=None, simple=False, lang=None):
        if node is not None:
            self.tnodes.append(TNode(node, len(self.text), len(s)))
        if simple:
            self.in_simple_field.append((len(self.text), len(self.text) + len(s)))
        self.text += s
        self.italic.extend([ital] * len(s))
        self.langs.extend([lang] * len(s))

    def meta(self):
        from .terms import SegMeta
        return SegMeta(self.quote, self.in_table, self.langs if any(self.langs) else None)

    def locate(self, offset: int):
        """Return (TNode, local offset) for an insertion point *after* char offset-1."""
        for tn in self.tnodes:
            if tn.start < offset <= tn.start + tn.length:
                return tn, offset - tn.start
        return None, None


# ---------------------------------------------------------------------------
# Style resolution (italic + headings)
# ---------------------------------------------------------------------------
class Styles:
    def __init__(self, root):
        self.root = root
        self.by_id = {}
        self.name_to_id = {}
        if root is not None:
            for st in root.iter(w("style")):
                sid = st.get(w("styleId"))
                self.by_id[sid] = st
                nm = st.find(w("name"))
                if nm is not None:
                    self.name_to_id[nm.get(WVAL, "").lower()] = sid
        self._ital = {}
        self._outline = {}
        self._lang = {}
        self.default_lang = None
        if root is not None:
            d = root.find(f"{w('docDefaults')}/{w('rPrDefault')}/{w('rPr')}/{w('lang')}")
            if d is not None:
                self.default_lang = d.get(WVAL)

    def _based(self, sid):
        st = self.by_id.get(sid)
        if st is None:
            return None
        b = st.find(w("basedOn"))
        return b.get(WVAL) if b is not None else None

    def italic(self, sid) -> bool | None:
        if sid is None:
            return None
        if sid in self._ital:
            return self._ital[sid]
        res = None
        seen = set()
        cur = sid
        while cur and cur not in seen:
            seen.add(cur)
            st = self.by_id.get(cur)
            if st is None:
                break
            i = st.find(f"{w('rPr')}/{w('i')}")
            if i is not None:
                res = _onoff(i)
                break
            cur = self._based(cur)
        self._ital[sid] = res
        return res

    def outline(self, sid) -> int | None:
        if sid is None:
            return None
        if sid in self._outline:
            return self._outline[sid]
        res = None
        seen = set()
        cur = sid
        while cur and cur not in seen:
            seen.add(cur)
            st = self.by_id.get(cur)
            if st is None:
                break
            o = st.find(f"{w('pPr')}/{w('outlineLvl')}")
            if o is not None:
                res = int(o.get(WVAL, "9"))
                break
            nm = st.find(w("name"))
            name = nm.get(WVAL, "").lower() if nm is not None else ""
            if name in ("heading 1", "title"):
                res = 0
                break
            hm = re.fullmatch(r"heading ([1-9])", name)
            if hm:
                res = int(hm.group(1)) - 1
                break
            cur = self._based(cur)
        self._outline[sid] = res
        return res

    def _chain(self, sid):
        seen = set()
        cur = sid
        while cur and cur not in seen:
            seen.add(cur)
            st = self.by_id.get(cur)
            if st is None:
                break
            yield st
            cur = self._based(cur)

    def lang(self, sid) -> str | None:
        """Language (w:lang/@w:val) set by a style or the styles it is based on."""
        if sid is None:
            return None
        if sid not in self._lang:
            res = None
            for st in self._chain(sid):
                lg = st.find(f"{w('rPr')}/{w('lang')}")
                if lg is not None and lg.get(WVAL):
                    res = lg.get(WVAL)
                    break
            self._lang[sid] = res
        return self._lang[sid]

    def names(self, sid) -> list[str]:
        out = []
        for st in self._chain(sid):
            nm = st.find(w("name"))
            if nm is not None:
                out.append(nm.get(WVAL, ""))
        return out

    def ppr_child(self, sid, tag):
        for st in self._chain(sid):
            e = st.find(f"{w('pPr')}/{w(tag)}")
            if e is not None:
                return e
        return None

    def id_for_name(self, name: str):
        return self.name_to_id.get(name.lower())

    # -- fonts -------------------------------------------------------------------
    theme_fonts: dict = {}

    def _font_of(self, rfonts) -> str | None:
        if rfonts is None:
            return None
        f = rfonts.get(w("ascii")) or rfonts.get(w("hAnsi"))
        if f:
            return f
        th = rfonts.get(w("asciiTheme")) or rfonts.get(w("hAnsiTheme"))
        if th:
            return self.theme_fonts.get("major" if th.startswith("major") else "minor")
        return None

    def default_para_style(self):
        if self.root is not None:
            for st in self.root.iter(w("style")):
                if st.get(w("type")) == "paragraph" and st.get(w("default")) in ("1", "true", "on"):
                    return st.get(w("styleId"))
        return self.id_for_name("normal")

    def own_font(self, sid) -> str | None:
        """The font a style names itself (not inherited)."""
        st = self.by_id.get(sid)
        return self._font_of(st.find(f"{w('rPr')}/{w('rFonts')}")) if st is not None else None

    def font(self, sid) -> str | None:
        """The font text in this paragraph style is set in: the style, the styles it is based
        on, then the document defaults (and the theme's body font)."""
        if sid is None or sid not in self.by_id:
            sid = self.default_para_style()
        for st in self._chain(sid) if sid else ():
            f = self._font_of(st.find(f"{w('rPr')}/{w('rFonts')}"))
            if f:
                return f
        if self.root is not None:
            f = self._font_of(self.root.find(f"{w('docDefaults')}/{w('rPrDefault')}/{w('rPr')}/{w('rFonts')}"))
            if f:
                return f
        return self.theme_fonts.get("minor")


def _onoff(el) -> bool:
    v = el.get(WVAL)
    return v is None or v.lower() not in ("0", "false", "off", "none")


# ---------------------------------------------------------------------------
# Package
# ---------------------------------------------------------------------------
class DocxPackage:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.trees: dict[str, etree._ElementTree] = {}
        with zipfile.ZipFile(self.path) as z:
            names = set(z.namelist())
            for key, name in PARTS.items():
                if name in names:
                    self.trees[key] = etree.fromstring(z.read(name)).getroottree()
            self.styles_tree = (etree.fromstring(z.read("word/styles.xml")).getroottree()
                                if "word/styles.xml" in names else None)
        self.styles = Styles(self.styles_tree.getroot() if self.styles_tree is not None else None)
        self.styles.theme_fonts = self._theme_fonts()
        self.body_segments: list[Segment] = []
        self.note_segments: dict[tuple[str, str], list[Segment]] = {}
        self.note_ordinals: dict[tuple[str, str], int] = {}
        self.warnings: list[str] = []
        self.existing_xe = 0
        self.existing_index = 0
        self.tracked_changes = 0
        self._read()

    def _theme_fonts(self) -> dict:
        try:
            with zipfile.ZipFile(self.path) as z:
                data = z.read("word/theme/theme1.xml")
        except Exception:
            return {}
        out = {}
        try:
            root = etree.fromstring(data)
            A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
            for kind in ("major", "minor"):
                lat = root.find(f".//{A}{kind}Font/{A}latin")
                if lat is not None and lat.get("typeface"):
                    out[kind] = lat.get("typeface")
        except Exception:
            pass
        return out

    def body_font(self) -> str | None:
        """The font of the body text: that of the paragraph style holding the most text
        (headings, notes, tables and the bibliography left out)."""
        count: dict = {}
        for seg in self.body_segments:
            if seg.heading or seg.in_table or seg.biblio:
                continue
            count[seg.style_id] = count.get(seg.style_id, 0) + len(seg.text)
        if not count:
            return self.styles.font(None)
        sid = max(count, key=count.get)
        return self.styles.font(sid)

    # -- reading ---------------------------------------------------------------
    def _read(self):
        doc = self.trees["document"].getroot()
        self.body_segments = _walk_part(doc.find(w("body")), "document", self.styles, self)
        for kind, part in (("footnote", "footnotes"), ("endnote", "endnotes")):
            if part not in self.trees:
                continue
            nxt = 0
            for note in self.trees[part].getroot().findall(w(kind)):
                if note.get(w("type")) in ("separator", "continuationSeparator", "continuationNotice"):
                    continue
                nid = note.get(w("id"))
                segs = _walk_part(note, part, self.styles, self, nxt)
                nxt += len(segs)
                for s in segs:
                    s.note_kind, s.note_id = kind, nid
                self.note_segments[(kind, nid)] = segs
        mark_bibliography(self.body_segments)
        counters = {"footnote": 0, "endnote": 0}
        for seg in self.body_segments:
            for a in seg.anchors:
                key = (a.kind, a.note_id)
                if key not in self.note_ordinals:
                    counters[a.kind] += 1
                    self.note_ordinals[key] = counters[a.kind]
        root = self.trees["document"].getroot()
        self.tracked_changes = len(root.findall(f".//{w('ins')}")) + len(root.findall(f".//{w('del')}"))
        if self.tracked_changes:
            self.warnings.append(
                f"The document has {self.tracked_changes} tracked changes. Accept or reject them "
                "first; index fields placed inside tracked insertions are tracked too.")

    # -- writing ---------------------------------------------------------------
    def max_bookmark_id(self) -> int:
        m = 0
        for t in self.trees.values():
            for b in t.getroot().iter(w("bookmarkStart")):
                try:
                    m = max(m, int(b.get(w("id"), "0")))
                except ValueError:
                    pass
        return m

    def save(self, out_path: str | Path):
        out_path = Path(out_path)
        tmp = out_path.with_suffix(".tmp")
        repl = {PARTS[k]: _ser(t) for k, t in self.trees.items()}
        if self.styles_tree is not None:
            repl["word/styles.xml"] = _ser(self.styles_tree)
        with zipfile.ZipFile(self.path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = repl.get(item.filename)
                if data is None:
                    data = zin.read(item.filename)
                zout.writestr(item, data)
        shutil.move(str(tmp), str(out_path))


def _ser(tree) -> bytes:
    return etree.tostring(tree, xml_declaration=True, encoding="UTF-8", standalone=True)


def _field_type(instr: str) -> str:
    m = re.match(r"\s*([A-Za-z]+)", instr or "")
    return m.group(1).upper() if m else ""


def _twips(el, *names) -> int:
    if el is None:
        return 0
    for n in names:
        v = el.get(w(n))
        if v is not None:
            try:
                return int(float(v))
            except ValueError:
                return 0
    return 0


QUOTE_INDENT = 567     # twips (about 0.4 in): an indented prose paragraph reads as a block quotation


BIB_HEADING_RE = re.compile(r"^\s*(?:\d+[.)]?\s*)?(?:select(?:ed)?\s+)?(?:bibliography|works\s+cited|"
                            r"sources\s+consulted|bibliographie|bibliografía|bibliografia|literaturverzeichnis)"
                            r"\s*[.:]?\s*$", re.I)
BIB_STYLE_RE = re.compile(r"bibliograph|bibliograf", re.I)


def mark_bibliography(segs: list) -> int:
    """Mark the paragraphs of the bibliography: everything under a heading such as
    "Bibliography" or "Works Cited" (until the next heading at the same or a higher
    level), and any paragraph in a bibliography style.  Returns how many were marked."""
    inside, level, n = False, 0, 0
    for seg in segs:
        if seg.heading:
            lvl = seg.level if seg.level is not None else 0
            if BIB_HEADING_RE.match(seg.text or ""):
                inside, level = True, lvl
                continue
            if inside and lvl <= level:
                inside = False
        if inside or any(BIB_STYLE_RE.search(nm or "") for nm in seg.style_names):
            seg.biblio = True
            n += 1
    return n


def _quote_kind(ppr, pstyle, styles: Styles, heading: bool) -> str | None:
    """"style" for a paragraph in a quotation style, "indent" for one indented
    like a block quotation (left indent, no hanging indent, not numbered)."""
    from .terms import QUOTE_STYLE_RE
    if heading:
        return None
    if any(QUOTE_STYLE_RE.search(n or "") for n in styles.names(pstyle)):
        return "style"
    ind = ppr.find(w("ind")) if ppr is not None else None
    if ind is None:
        ind = styles.ppr_child(pstyle, "ind")
    num = ppr.find(w("numPr")) if ppr is not None else None
    if num is None:
        num = styles.ppr_child(pstyle, "numPr")
    if num is not None or ind is None:
        return None
    if any(re.match(r"(list|bibliograph|toc|index|caption|footnote|endnote)", n or "", re.I)
           for n in styles.names(pstyle)):
        return None
    left = _twips(ind, "left", "start")
    hanging = _twips(ind, "hanging")
    if left >= QUOTE_INDENT and left - hanging >= QUOTE_INDENT:
        return "indent"
    return None


def _walk_part(root, part: str, styles: Styles, pkg: DocxPackage, start: int = 0) -> list[Segment]:
    """Walk a story in document order and return its paragraph segments."""
    segs: list[Segment] = []
    stack: list[Segment] = []
    fields: list[dict] = []           # complex-field stack
    counter = [start]

    def skipping() -> bool:
        for f in fields:
            if f["phase"] == "code":
                return True
            if f["phase"] == "result" and _field_type(f["instr"]) in SKIP_FIELD_RESULTS:
                return True
        return False

    def in_simple() -> bool:
        return any(f.get("simple") for f in fields)

    table_depth = [0]

    def run_lang(run, pstyle):
        rpr = run.find(w("rPr"))
        if rpr is not None:
            lg = rpr.find(w("lang"))
            if lg is not None and lg.get(WVAL):
                return lg.get(WVAL)
            rs = rpr.find(w("rStyle"))
            if rs is not None:
                v = styles.lang(rs.get(WVAL))
                if v:
                    return v
        return styles.lang(pstyle) or styles.default_lang

    def run_italic(run, pstyle) -> bool:
        rpr = run.find(w("rPr"))
        if rpr is not None:
            i = rpr.find(w("i"))
            if i is not None:
                return _onoff(i)
            rs = rpr.find(w("rStyle"))
            if rs is not None:
                v = styles.italic(rs.get(WVAL))
                if v is not None:
                    return v
        v = styles.italic(pstyle)
        return bool(v)

    def visit(el, run=None, pstyle=None):
        tag = el.tag
        if not isinstance(tag, str):
            return
        if tag == f"{{{MC}}}Fallback" or tag in (w("del"), w("moveFrom"), w("delText")):
            return
        if tag == w("p"):
            seg = Segment(part, counter[0])
            counter[0] += 1
            ppr = el.find(w("pPr"))
            ps = None
            if ppr is not None:
                s = ppr.find(w("pStyle"))
                ps = s.get(WVAL) if s is not None else None
                ol = ppr.find(w("outlineLvl"))
                if ol is not None and ol.get(WVAL, "9").isdigit() and int(ol.get(WVAL)) < 9:
                    seg.heading, seg.level = True, int(ol.get(WVAL))
            lvl = styles.outline(ps)
            if not seg.heading and lvl is not None and lvl < 9:
                seg.heading, seg.level = True, lvl
            seg.style_names = tuple(styles.names(ps)) if ps else ()
            seg.style_id = ps
            seg.in_table = table_depth[0] > 0
            seg.quote = _quote_kind(ppr, ps, styles, seg.heading)
            stack.append(seg)
            for ch in el:
                visit(ch, None, ps)
            stack.pop()
            segs.append(seg)
            return
        if tag == w("tbl"):
            table_depth[0] += 1
            for ch in el:
                visit(ch, run, pstyle)
            table_depth[0] -= 1
            return
        if tag == w("fldSimple"):
            fields.append({"instr": el.get(w("instr"), ""), "phase": "result", "simple": True})
            for ch in el:
                visit(ch, run, pstyle)
            fields.pop()
            return
        if tag == w("r"):
            for ch in el:
                visit(ch, el, pstyle)
            return
        if tag == w("fldChar"):
            t = el.get(w("fldCharType"))
            if t == "begin":
                fields.append({"instr": "", "phase": "code"})
            elif t == "separate" and fields:
                fields[-1]["phase"] = "result"
            elif t == "end" and fields:
                f = fields.pop()
                ft = _field_type(f["instr"])
                if ft == "XE" and part is not None:
                    pkg.existing_xe += 1
                elif ft == "INDEX":
                    pkg.existing_index += 1
            return
        if tag == w("instrText"):
            if fields:
                fields[-1]["instr"] += el.text or ""
            return
        seg = stack[-1] if stack else None
        if tag == w("t"):
            if seg is not None and not skipping():
                seg.add(el.text or "", run_italic(run, pstyle) if run is not None else False,
                        el, simple=in_simple(), lang=run_lang(run, pstyle) if run is not None else None)
            return
        if tag in (w("tab"), w("ptab")) and run is not None:
            if seg is not None and not skipping():
                seg.add("\t", False)
            return
        if tag in (w("br"), w("cr")) and run is not None:
            if seg is not None and not skipping():
                seg.add(" ", False)
            return
        if tag == w("noBreakHyphen"):
            if seg is not None and not skipping():
                seg.add("‑", False)
            return
        if tag in (w("footnoteReference"), w("endnoteReference")):
            if seg is not None:
                kind = "footnote" if tag == w("footnoteReference") else "endnote"
                seg.anchors.append(Anchor(len(seg.text), kind, el.get(w("id"))))
            return
        for ch in el:
            visit(ch, run, pstyle)

    visit(root)
    return segs


# ---------------------------------------------------------------------------
# Writing helpers
# ---------------------------------------------------------------------------
def _el(tag, attrib=None, text=None):
    e = etree.Element(w(tag))
    for k, v in (attrib or {}).items():
        e.set(w(k), str(v))
    if text is not None:
        e.text = text
        if text != text.strip():
            e.set(f"{{{XML_NS}}}space", "preserve")
    return e


def _hidden_run(child):
    # XE fields have no visible result, so no hidden formatting is needed (and
    # LibreOffice ignores hidden XE fields).
    r = _el("r")
    r.append(child)
    return r


def xe_elements(entry_text: str, yomi: str, switch: str | None, bm_name: str | None, bm_id: int | None,
                group: str | None = None, see: str | None = None, see_italic: int = 0):
    """Bookmark (zero-length) + XE field runs.  `see` makes a cross-reference
    (\\t "See …") instead of a page reference."""
    out = []
    if bm_name:
        out.append(_el("bookmarkStart", {"id": bm_id, "name": bm_name}))
        out.append(_el("bookmarkEnd", {"id": bm_id}))
    tail = (f" \\{switch}" if switch else "") + " "
    head = f' XE "{entry_text}" \\y "{yomi}"' + (f' \\f "{group}"' if group else "")
    out.append(_hidden_run(_el("fldChar", {"fldCharType": "begin"})))
    if see and see_italic:
        # "See" / "See also" in italics: Word carries the formatting of the XE text into the index
        out.append(_hidden_run(_el("instrText", text=head + ' \\t "')))
        r = _hidden_run(_el("instrText", text=see[:see_italic]))
        rpr = _el("rPr")
        rpr.append(_el("i"))
        r.insert(0, rpr)
        out.append(r)
        out.append(_hidden_run(_el("instrText", text=see[see_italic:] + '"' + tail)))
    else:
        out.append(_hidden_run(_el("instrText", text=head + (f' \\t "{see}"' if see else "") + tail)))
    out.append(_hidden_run(_el("fldChar", {"fldCharType": "end"})))
    return out


def insert_after_offset(seg: Segment, offset: int, elements: list) -> bool:
    """Insert `elements` (runs / bookmarks) right after character offset-1 of seg."""
    tn, local = seg.locate(offset)
    if tn is None:
        return False
    t = tn.el
    run = t.getparent()
    if run is None or run.tag != w("r"):
        return False
    text = t.text or ""
    if local < len(text):
        t2 = _el("t", text=text[local:])
        t.text = text[:local]
        if t.text != t.text.strip():
            t.set(f"{{{XML_NS}}}space", "preserve")
        r2 = etree.Element(run.tag, attrib=dict(run.attrib))
        rpr = run.find(w("rPr"))
        if rpr is not None:
            r2.append(copy.deepcopy(rpr))
        r2.append(t2)
        kids = list(run)
        for ch in kids[kids.index(t) + 1:]:
            r2.append(ch)
        run.addnext(r2)
    else:
        kids = list(run)
        after = kids[kids.index(t) + 1:]
        if after:
            r2 = etree.Element(run.tag, attrib=dict(run.attrib))
            rpr = run.find(w("rPr"))
            if rpr is not None:
                r2.append(copy.deepcopy(rpr))
            for ch in after:
                r2.append(ch)
            run.addnext(r2)
    anchor = run
    for el in elements:
        anchor.addnext(el)
        anchor = el
    return True


def remove_xe_fields(pkg: DocxPackage) -> int:
    """Delete every existing XE field (index entry) from all stories."""
    removed = 0
    for tree in pkg.trees.values():
        runs = list(tree.getroot().iter(w("r")))
        state = None         # list of runs of the current top-level field
        depth = 0
        instr = ""
        for r in runs:
            fc = r.find(w("fldChar"))
            it = r.find(w("instrText"))
            if fc is not None and fc.get(w("fldCharType")) == "begin":
                depth += 1
                if depth == 1:
                    state, instr = [r], ""
                    continue
            if state is not None:
                state.append(r)
                if it is not None and depth == 1:
                    instr += it.text or ""
            if fc is not None and fc.get(w("fldCharType")) == "end":
                depth -= 1
                if depth == 0 and state is not None:
                    if _field_type(instr) == "XE":
                        for rr in state:
                            par = rr.getparent()
                            if par is not None:
                                par.remove(rr)
                        removed += 1
                    state = None
    return removed


def ensure_index_styles(pkg: DocxPackage, leader: str | None, cols: int, font: str | None = None):
    """Make sure 'index 1'/'index 2' paragraph styles exist.  For right-aligned
    page numbers (`leader` = "dot" or "none") give 'index 2' a right tab at
    the column edge."""
    st = pkg.styles_tree
    if st is None:
        return
    root = st.getroot()
    # text width of the last section
    body = pkg.trees["document"].getroot().find(w("body"))
    sect = body.find(w("sectPr"))
    width = 9360
    if sect is not None:
        pg, mar = sect.find(w("pgSz")), sect.find(w("pgMar"))
        try:
            width = int(pg.get(w("w"))) - int(mar.get(w("left"))) - int(mar.get(w("right")))
            g = mar.get(w("gutter"))
            if g:
                width -= int(g)
        except Exception:
            pass
    colw = int((width - (cols - 1) * 720) / max(cols, 1))
    for lvl, left, bold in ((1, 220, True), (2, 440, False)):
        sid = pkg.styles.id_for_name(f"index {lvl}")
        if sid is None:
            sid = f"Index{lvl}"
            s = etree.SubElement(root, w("style"))
            s.set(w("type"), "paragraph")
            s.set(w("styleId"), sid)
            s.append(_el("name", {"val": f"index {lvl}"}))
            s.append(_el("basedOn", {"val": pkg.styles.id_for_name("normal") or "Normal"}))
            s.append(_el("next", {"val": pkg.styles.id_for_name("normal") or "Normal"}))
            s.append(_el("uiPriority", {"val": "99"}))
            s.append(_el("unhideWhenUsed"))
            ppr = _el("pPr")
            ppr.append(_el("spacing", {"after": "0"}))
            ppr.append(_el("ind", {"left": left, "hanging": 220}))
            s.append(ppr)
            if bold:
                rpr = _el("rPr")
                rpr.append(_el("b"))
                s.append(rpr)
            pkg.styles.by_id[sid] = s
            pkg.styles.name_to_id[f"index {lvl}"] = sid
        if font and not pkg.styles.own_font(sid):
            _set_style_font(pkg.styles.by_id[sid], font)
        if leader:
            s = pkg.styles.by_id[sid]
            ppr = s.find(w("pPr"))
            if ppr is None:
                ppr = _el("pPr")
                nm = s.find(w("rPr"))
                if nm is not None:
                    nm.addprevious(ppr)
                else:
                    s.append(ppr)
            old = ppr.find(w("tabs"))
            if old is not None:
                ppr.remove(old)
            tabs = _el("tabs")
            tabs.append(_el("tab", {"val": "right", "leader": leader, "pos": max(colw - 10, 1440)}))
            # tabs must come early in pPr (after keepNext..., before spacing); insert first
            ppr.insert(0, tabs)


def _set_style_font(style_el, font: str) -> None:
    """Name a font in a style's run properties (rFonts goes first in rPr)."""
    rpr = style_el.find(w("rPr"))
    if rpr is None:
        rpr = _el("rPr")
        style_el.append(rpr)
    old = rpr.find(w("rFonts"))
    if old is not None:
        rpr.remove(old)
    rpr.insert(0, _el("rFonts", {"ascii": font, "hAnsi": font, "cs": font, "eastAsia": font}))


def set_index_heading_font(pkg: DocxPackage, font: str) -> None:
    """The "index heading" style (group letters), if the document has one without a font."""
    sid = pkg.styles.id_for_name("index heading")
    if sid and not pkg.styles.own_font(sid):
        _set_style_font(pkg.styles.by_id[sid], font)


def _heading_para(pkg, text, level, page_break=False):
    p = _el("p")
    ppr = _el("pPr")
    hid = pkg.styles.id_for_name(f"heading {level}")
    if hid:
        ppr.append(_el("pStyle", {"val": hid}))
    if page_break:
        ppr.append(_el("pageBreakBefore"))
    if len(ppr):
        p.append(ppr)
    r = _el("r")
    r.append(_el("t", text=text))
    p.append(r)
    return p


def _index_field_para(cols: int, separator: str, group: str | None):
    p = _el("p")
    p.append(_run_with(_el("fldChar", {"fldCharType": "begin"})))
    p.append(_run_with(_el("instrText", text=f' INDEX \\y \\c "{cols}" \\e "')))
    if separator == "\t":
        p.append(_run_with(_el("tab")))
    else:
        p.append(_run_with(_el("instrText", text=separator)))
    p.append(_run_with(_el("instrText", text='"' + (f' \\f "{group}"' if group else "") + " ")))
    p.append(_run_with(_el("fldChar", {"fldCharType": "separate"})))
    p.append(_run_with(_el("t", text="Index not built yet: select this line and press F9 "
                                      "(or Ctrl+A, then F9) to update it.")))
    p.append(_run_with(_el("fldChar", {"fldCharType": "end"})))
    return p


def append_index(pkg: DocxPackage, heading: str, cols: int, separator: str, new_page: bool,
                 groups: list | None = None, letter: str | None = None, extra: list | None = None,
                 scripture: bool = True):
    """Append the index (or indexes) at the end of the document in its own section.

    `groups`: [(letter, section title)] for a split Scripture index (one INDEX
    field per section, using the XE \\f switch); empty/None for one index,
    which then uses `letter` (None = no \\f switch).
    `extra`: further indexes, [(title, letter, [cross-reference XE runs])],
    each starting with its own level-1 heading.
    """
    body = pkg.trees["document"].getroot().find(w("body"))
    sect = body.find(w("sectPr"))
    paras = []
    if sect is not None:
        # End the manuscript's last section here and give the index its own
        # section, so special formatting of the closing page (vertical
        # centring, a numbering restart, ...) does not carry over.
        brk = _el("p")
        bppr = _el("pPr")
        bppr.append(copy.deepcopy(sect))
        brk.append(bppr)
        paras.append(brk)
        e = sect.find(w("vAlign"))
        if e is not None:
            sect.remove(e)
        pn = sect.find(w("pgNumType"))
        if pn is not None and pn.get(w("start")) is not None:
            del pn.attrib[w("start")]
        typ = sect.find(w("type"))
        if typ is None:
            typ = _el("type")
            sect.insert(0, typ)
        typ.set(WVAL, "nextPage" if new_page else "continuous")
        refs = [c for c in sect if c.tag in (w("headerReference"), w("footerReference"),
                                             w("footnotePr"), w("endnotePr"))]
        if refs:
            refs[-1].addnext(typ)
        first_break = False
    else:
        first_break = new_page

    def start(title, page_break):
        if title:
            paras.append(_heading_para(pkg, title, 1, page_break))
        elif page_break:
            p = _el("p")
            r = _el("r")
            r.append(_el("br", {"type": "page"}))
            p.append(r)
            paras.append(p)
        return paras[-1] if paras and title else None

    if scripture:
        start(heading, first_break)
        if groups:
            for gl, title in groups:
                paras.append(_heading_para(pkg, title, 2))
                paras.append(_index_field_para(cols, separator, gl))
        else:
            paras.append(_index_field_para(cols, separator, letter))
        first_break = new_page
    for title, xl, xrefs in extra or []:
        hp = start(title, first_break)
        if xrefs:
            holder = hp if hp is not None else _el("p")
            for el in xrefs:
                holder.append(el)
            if hp is None:
                paras.append(holder)
        paras.append(_index_field_para(cols, separator, xl))
        first_break = new_page
    for para in paras:
        if sect is not None:
            sect.addprevious(para)
        else:
            body.append(para)


def _run_with(child):
    r = _el("r")
    r.append(child)
    return r


def escape_entry(s: str) -> str:
    return s.replace("\\", "\\\\").replace(":", "\\:").replace('"', "'")
