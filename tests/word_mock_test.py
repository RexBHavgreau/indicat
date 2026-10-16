"""Exercise the Word automation (word_com.py) against a fake Word object model.

    python tests/word_mock_test.py

Checks that note page numbers in the finished indexes are completed (33n2)
or highlighted, for a Scripture index and for a word index with subentries,
and that updating the index keeps the tab leader of the index styles.
"""
import copy
import sys

# Windows consoles default to a code page that has no Greek or Hebrew
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class Obj:
    pass


class Doc:
    def __init__(self, text, ital, lefts):
        self.chars, self.ital, self.hl = list(text), list(ital), [0] * len(text)
        self.lefts = lefts          # paragraph start -> left indent (points)

    def Range(self, a, b):
        return Rng(self, a, b)


class Font:
    Bold = 0

    def __init__(self, r):
        object.__setattr__(self, "r", r)

    @property
    def Italic(self):
        v = self.r.d.ital[self.r.Start:self.r.End]
        return -1 if v and all(v) else (0 if not any(v) else 9999999)

    @Italic.setter
    def Italic(self, val):
        for i in range(self.r.Start, self.r.End):
            self.r.d.ital[i] = bool(val)


class Rng:
    def __init__(self, d, a, b):
        self.d, self.Start, self.End = d, a, b

    @property
    def Text(self):
        return "".join(self.d.chars[self.Start:self.End])

    @property
    def Font(self):
        return Font(self)

    @property
    def ParagraphFormat(self):
        return types.SimpleNamespace(LeftIndent=self.d.lefts.get(self.Start, 0))

    @property
    def HighlightColorIndex(self):
        return 0

    @HighlightColorIndex.setter
    def HighlightColorIndex(self, v):
        for i in range(self.Start, self.End):
            self.d.hl[i] = v

    def InsertAfter(self, t):
        d = self.d
        d.chars[self.End:self.End] = list(t)
        d.ital[self.End:self.End] = [False] * len(t)
        d.hl[self.End:self.End] = [0] * len(t)
        # paragraphs after this point move
        d.lefts = {(k + len(t) if k > self.End else k): v for k, v in d.lefts.items()}

    @property
    def Paragraphs(self):
        d, parts, st = self.d, [], self.Start
        for i, ch in enumerate(self.Text):
            if ch == "\r":
                parts.append((st, self.Start + i + 1))
                st = self.Start + i + 1

        class P:
            Count = len(parts)

            def Item(self, i):
                o = Obj()
                o.Range = Rng(d, *parts[i - 1])
                return o
        return P()


class Coll:
    def __init__(self, items):
        self.items, self.Count = items, len(items)

    def Item(self, i):
        return self.items[i - 1]

    def Update(self):
        pass


def fake_word(text, ital, lefts, fields_spec, pages, note_pages):
    """fields_spec: [(code, start, end)] INDEX fields over parts of `text`."""
    d = Doc(text, ital, lefts)
    flds = []
    for code, a, b in fields_spec:
        f = Obj()
        f.Type = 8
        f.Code = types.SimpleNamespace(Text=code)
        f.Result = Rng(d, a, b)
        f.Unlink = (lambda: setattr(d, "unlinked", getattr(d, "unlinked", 0) + 1))
        flds.append(f)

    class BRng(Rng):
        def __init__(self, p):
            self.p = p

        def Information(self, n):
            return self.p

        @property
        def Sections(self):
            return Coll([types.SimpleNamespace(Footers=Coll([types.SimpleNamespace(
                PageNumbers=types.SimpleNamespace(NumberStyle=0))]))])

    class BM:
        ShowHidden = False

        def Exists(self, n):
            return n in pages

        def Item(self, n):
            o = Obj()
            o.Range = BRng(pages[n])
            return o
    fns = Coll([types.SimpleNamespace(Reference=BRng(p)) for p in note_pages])
    fns.NumberingRule, fns.StartingNumber, fns.NumberStyle = 0, 1, 0
    ens = Coll([])
    ens.NumberingRule, ens.StartingNumber, ens.NumberStyle = 0, 1, 0
    d.Bookmarks = BM()
    d.Fields = Coll(flds)
    d.Fields.Update = lambda: 0
    d.TablesOfContents = Coll([])
    d.Indexes = Coll([])
    d.Footnotes, d.Endnotes = fns, ens
    d.Repaginate = lambda: None
    d.Save = lambda: None
    d.Close = lambda x: None
    d.ActiveWindow = types.SimpleNamespace(View=Obj())
    d.SaveAs2 = lambda p, f: None
    word = Obj()
    word.Options = Obj()
    word.Documents = types.SimpleNamespace(Open=lambda *a: d)
    word.Quit = lambda: None
    pc = types.ModuleType("pythoncom")
    pc.CoInitialize = pc.CoUninitialize = lambda: None
    wc = types.ModuleType("win32com")
    wcc = types.ModuleType("win32com.client")
    wcc.DispatchEx = lambda n: word
    wc.client = wcc
    sys.modules.update({"pythoncom": pc, "win32com": wc, "win32com.client": wcc})
    return d


def main():
    from indicat import word_com
    from indicat.parser import Hit, Ref
    from indicat.pipeline import BuildOptions, Occurrence
    from indicat.settings import DEFAULTS, make_context
    from indicat.terms import TermRef

    cat, _ = make_context(copy.deepcopy(DEFAULTS))
    scripture = "Genesis\r1:28, 54\r2:24, 49, 95\r"
    words = "λόγος, 12, 33\rδιαθήκη\rκαινή, 40, 41\rπαλαιά, 41\r"
    text = scripture + words
    ital = [False] * len(text)

    def mark(sub, start=0):
        i = text.index(sub, start)
        for k in range(i, i + len(sub)):
            ital[k] = True
    mark("95")
    mark("33", len(scripture))
    mark("41", text.index("κα"))
    s0 = len(scripture)
    lefts = {}
    pos = s0
    for line in words.split("\r")[:-1]:
        lefts[pos] = 22 if line.startswith(("καινή", "παλαιά")) else 11
        pos += len(line) + 1
    fields = [(' INDEX \\y \\c "2" \\e ", " ', 0, s0),
              (' INDEX \\y \\c "2" \\e ", " \\f "G" ', s0, len(text))]
    pages = {"_SIB1": 54, "_SIB2": 95, "_SIB3": 12, "_SIB4": 33, "_SIB5": 41}
    d = fake_word(text, ital, lefts, fields, pages, note_pages=[95, 33, 41])

    def socc(i, c, v, bm, note=None):
        r = Ref("Gen", c, v, cat=cat)
        o = Occurrence(str(i), i, "document", i, 0, 1, Hit(0, 1, r, "explicit"), r, "explicit", True, "ctx",
                       note, None, bookmark=bm)
        return o

    def wocc(i, h, sub, bm, note=None):
        r = TermRef("script:greek", h, sub)
        o = Occurrence(f"w{i}", i, "document", i, 0, 1, Hit(0, 1, None, "word"), r, "word", True, "ctx",
                       note, None, bookmark=bm, index="script:greek", letter="G")
        return o
    o1 = socc(1, 1, 28, "_SIB1")
    o2 = socc(2, 2, 24, "_SIB2", "footnote")
    o2.note_ordinal = 1
    o3 = wocc(3, "λόγος", "", "_SIB3")
    o4 = wocc(4, "λόγος", "", "_SIB4", "footnote")
    o4.note_ordinal = 2
    o5 = wocc(5, "διαθήκη", "καινή", "_SIB5", "footnote")
    o5.note_ordinal = 3
    msgs = word_com.paginate("x.docx", [o1, o2, o3, o4, o5], BuildOptions(out_dir=None, footnote_mode="auto"),
                             lambda m: None, "final.docx")
    out = "".join(d.chars)
    expect = "Genesis\r1:28, 54\r2:24, 49, 95n1\rλόγος, 12, 33n2\rδιαθήκη\rκαινή, 40, 41n3\rπαλαιά, 41\r"
    if out != expect or msgs:
        print("FAIL")
        print(repr(out))
        print(repr(expect))
        print(msgs)
        sys.exit(1)
    print("OK   note page numbers completed in a Scripture index and a word index with subentries")


def leader_test():
    """Word gives a rebuilt index its own leader (dots); Indicat must keep the styles' leader."""
    from indicat import word_com
    order = []

    def stop(align, leader):
        return types.SimpleNamespace(Alignment=align, Leader=leader)
    styles = {-11: [stop(0, 0), stop(word_com.WD_ALIGN_TAB_RIGHT, 0)],      # index 1: no leader
              -12: [stop(word_com.WD_ALIGN_TAB_RIGHT, 0)],
              -13: []}
    ix_right = types.SimpleNamespace(RightAlignPageNumbers=True, TabLeader=1)
    ix_comma = types.SimpleNamespace(RightAlignPageNumbers=False, TabLeader=1)

    def upd(ix):
        def f():
            order.append(("update", ix.TabLeader))
            if ix.RightAlignPageNumbers:      # what Word does: the index's leader goes into the styles
                for sid in (-11, -12):
                    for t in styles[sid]:
                        if t.Alignment == word_com.WD_ALIGN_TAB_RIGHT:
                            t.Leader = ix.TabLeader
        return f
    ix_right.Update, ix_comma.Update = upd(ix_right), upd(ix_comma)
    d = Obj()
    d.Indexes = Coll([ix_right, ix_comma])
    d.Fields = Coll([])
    d.Fields.Update = lambda: order.append(("fields", None))
    d.Styles = lambda sid: types.SimpleNamespace(ParagraphFormat=types.SimpleNamespace(TabStops=Coll(styles[sid])))
    word_com._update_indexes(d)
    ok = (ix_right.TabLeader == 0 and ix_comma.TabLeader == 1 and order[0] == ("fields", None)
          and all(t.Leader == 0 for sid in (-11, -12) for t in styles[sid]))
    # 'dot' chosen: the style's dot leader is kept
    styles[-11][1].Leader = styles[-12][0].Leader = 1
    ix_right.TabLeader = 0
    word_com._update_indexes(d)
    ok = ok and ix_right.TabLeader == 1 and styles[-11][1].Leader == 1
    if not ok:
        print("FAIL leader", order, ix_right.TabLeader, [(t.Alignment, t.Leader) for t in styles[-11]])
        sys.exit(1)
    print("OK   updating the index keeps the leader of the index styles (none or dots)")


if __name__ == "__main__":
    main()
    leader_test()
