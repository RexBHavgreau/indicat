"""The PDF route: reading a PDF's text layer and writing a static index.

    python tests/test_pdf.py

Builds a small book with reportlab (pip install reportlab) and checks the
paragraphs, running heads, folios, footnotes, hyphenation, old-style
citations and the index written from it."""
import copy
import sys
import tempfile
import zipfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from indicat import pdf_index as X           # noqa: E402
from indicat import pipeline as P            # noqa: E402
from indicat.pdf_io import font_family, ocr_fix   # noqa: E402
from indicat.settings import DEFAULTS        # noqa: E402

BODY = 11
LEAD = 15


def make_book(path):
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(path), pagesize=letter)
    W, H = letter
    left = 72

    def page(head, folio, lines, notes=(), first=False):
        c.setFont("Times-Roman", 9)
        if head:
            c.drawCentredString(W / 2, H - 50, head)
        y = H - 90
        for ln in lines:
            if isinstance(ln, tuple):              # (text, superscript, rest)
                t, sup, rest = ln
                c.setFont("Times-Roman", BODY)
                c.drawString(left, y, t)
                x = left + c.stringWidth(t, "Times-Roman", BODY)
                c.setFont("Times-Roman", 7)
                c.drawString(x, y + 4, sup)
                x += c.stringWidth(sup, "Times-Roman", 7)
                c.setFont("Times-Roman", BODY)
                c.drawString(x, y, rest)
            elif ln.startswith("#"):
                c.setFont("Times-Bold", 16)
                c.drawString(left, y, ln[1:])
                y -= 8
            else:
                indent = 18 if ln.startswith(">") else 0
                c.setFont("Times-Roman", BODY)
                c.drawString(left + indent, y, ln.lstrip(">"))
            y -= LEAD
        if notes:
            ny = 120
            c.line(left, ny + 14, left + 120, ny + 14)
            for num, text in notes:
                c.setFont("Times-Roman", 6)
                c.drawString(left, ny + 3, num)
                c.setFont("Times-Roman", 8.5)
                c.drawString(left + 6, ny, text)
                ny -= 11
        c.setFont("Times-Roman", 9)
        c.drawCentredString(W / 2, 40, folio)
        c.showPage()

    page("", "1", ["#Chapter One",
                   ">In the beginning God created the heavens (Gen. 1:1). Later the",
                   "Psalmist sings of it (Ps. 19:1). The Song of Solo-",
                   "mon 2:7 repeats a refrain, and the law in Deu-"], first=True)
    page("The Book of Beginnings", "2",
         ["teronomy 6:4 is the Shema. Old writers cite Matt. v. 3 and ch. vi. ver. 9.",
          ("The covenant is renewed", "1", " (Josh. 24:25)."),
          ">Afterwards the people served the Lord (Judg. 2:7)."],
         notes=[("1", "Compare Exod. 24:8 and Heb. 9:20.")])
    c.save()


def test_read_and_index():
    with tempfile.TemporaryDirectory() as d:
        pdf = Path(d, "Book.pdf")
        make_book(pdf)
        s = copy.deepcopy(DEFAULTS)
        s["term_sets"] = [{"id": "set1", "name": "Subjects", "enabled": True, "title": "Subject Index",
                           "entries": [{"heading": "covenant", "forms": ["covenant"]},
                                       {"heading": "pact", "see": "covenant"}]}]
        res = X.scan_pdf(pdf, s, log=lambda *a: None)
        book = res.pdf
        assert [p.label for p in book.pages] == ["1", "2"], [p.label for p in book.pages]
        texts = [seg.text for seg in book.body_segments]
        assert not any("Beginnings" in t for t in texts), texts          # running head left out
        got = {(o.ref.display() if o.ref else o.hit.raw, o.status, o.page, o.note_number if o.in_note else None)
               for o in res.occurrences}
        want = {("Genesis 1:1", "explicit", "1", None), ("Psalms 19:1", "explicit", "1", None),
                ("Song of Solomon 2:7", "explicit", "1", None),
                ("Deuteronomy 6:4", "interrupted", "2", None),
                ("Matthew 5:3", "explicit", "2", None), ("Matthew 6:9", "inferred", "2", None),
                ("Joshua 24:25", "explicit", "2", None), ("Judges 2:7", "explicit", "2", None),
                ("Exodus 24:8", "explicit", "2", "1"), ("Hebrews 9:20", "explicit", "2", "1"),
                ("covenant", "term", "2", None)}
        assert want <= got, sorted(got - want) + ["--missing--"] + sorted(want - got)
        inter = [o for o in res.occurrences if o.status == "interrupted"][0]
        assert "Deu-‖2‖teronomy" in inter.hit.reason and "Deuteronomy?" in inter.hit.reason
        # the note mark "1" was taken out of the text, not read as part of a reference
        assert "renewed (Josh" in " ".join(texts)
        out = Path(d, "out")
        r = X.build_pdf(res, P.BuildOptions(out_dir=out, footnote_mode="auto", settings=s, columns=2), "docx",
                        log=lambda *a: None)
        from docx import Document
        txt = "\n".join(p.text for p in Document(r.indexed_docx).paragraphs)
        for line in ("Genesis", "1:1, 1", "Exodus", "24:8, 2n1", "Subject Index", "covenant, 2", "pact. See covenant"):
            assert line in txt, (line, txt)
        assert "Deuteronomy" not in txt                       # an interrupted term is not indexed
        r = X.build_pdf(res, P.BuildOptions(out_dir=out, footnote_mode="auto", settings=s, columns=2), "odt",
                        log=lambda *a: None)
        with zipfile.ZipFile(r.indexed_docx) as z:
            assert z.namelist()[0] == "mimetype" and z.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
            content = z.read("content.xml").decode()
        assert "24:8, 2n1" in content and 'style-name="Ti">See</text:span> covenant' in content


def make_two_columns(path):
    """A page set in two columns, like page 880 of the book where this went wrong: a reference
    that starts at the end of a line in the left column ("(Ps" / "85:4–7)") sits beside a line of
    the right column that ends with another book ("cf. Rom"). There are printer's marks too:
    a slug line outside the bleed box, under the running foot."""
    from reportlab.pdfgen import canvas
    W, H = 621, 747
    c = canvas.Canvas(str(path), pagesize=(W, H))
    L, R = 99, 316
    left = ["The Lord seeks shalom for His people by",
            "graciously forgiving the sins of the rebel-",
            "lious. In His steadfast loyal love and",
            "mercy, He delights to save and restore",
            "objects of His wrath (Ps",
            "85:4–7). He speaks shalom to His people,",
            "and His glory dwells among them (vv.",
            "8–9). When the Lord’s righteousness and",
            "shalom kiss each other, His people know",
            "the fullest truth (vv. 10–13). Indeed, the"]
    right = ["Messiah bears the title Sar Shalom, or",
             "“Prince of Peace” (Isa 9:6). He paid the",
             "full sacrificial price for the shalom",
             "of His people (Isa 53:5; cf. John 14:27;",
             "Rom",
             "5:1). Indeed, He Himself is that shalom",
             "for aliens and strangers whom He now",
             "brings into one household (Eph 2:14–22).",
             "He sends preachers of the gospel (Isa",
             "52:7) and guides us (Luke 1:74–79)."]
    for t in left + right:
        assert c.stringWidth(t, "Times-Roman", BODY) < R - L - 12, t
    for folio in (880, 881, 882):
        c.setBleedBox((27, 27, 594, 720))
        y = H - 110
        for a, b in zip(left, right):
            c.setFont("Times-Roman", BODY)
            c.drawString(L, y, a)
            c.drawString(R, y, b)
            y -= LEAD
        c.setFont("Times-Bold", 14)
        c.drawString(L + 30, y - 8, "Living Shalom Wisely")
        y -= 30
        for a, b in (("Living wisely according to God’s instruc-", "God-given, Word-driven wisdom. Jesus"),
                     ("tions brings shalom (Prov 3:13–18).", "instructed His disciples (Luke 10:5–6).")):
            c.setFont("Times-Roman", BODY)
            c.drawString(L, y, a)
            c.drawString(R, y, b)
            y -= LEAD
        c.setFont("Times-Roman", 8)
        c.drawString(L + 12, 150, "1. On shalom see also Num 6:24–26, a blessing quoted often in the letters of the church fathers.")
        c.setFont("Times-Roman", 10)
        c.drawString(L, 85, f"{folio} | Part 3: Practices")
        c.setFont("Times-Roman", 6)
        c.drawString(55, 6, f"Biblical_Missions_int.indd {folio}")
        c.drawString(520, 6, "11/21/24 9:53 AM")
        c.showPage()
    c.save()


def test_two_columns():
    with tempfile.TemporaryDirectory() as d:
        pdf = Path(d, "Columns.pdf")
        make_two_columns(pdf)
        res = X.scan_pdf(pdf, copy.deepcopy(DEFAULTS), log=lambda *a: None)
        got = {(o.ref.display() if o.ref else o.hit.raw, o.status, o.page, o.note_number if o.in_note else None)
               for o in res.occurrences}
        want = {("Psalms 85:4–7", "explicit", "880", None), ("Romans 5:1", "explicit", "880", None),
                ("Isaiah 53:5", "explicit", "880", None), ("Ephesians 2:14–22", "explicit", "880", None),
                ("Luke 1:74–79", "explicit", "880", None), ("Proverbs 3:13–18", "explicit", "880", None),
                ("Luke 10:5–6", "explicit", "880", None), ("Numbers 6:24–26", "explicit", "880", "1"),
                ("Psalms 85:4–7", "explicit", "882", None)}
        assert want <= got, sorted(got - want) + ["--missing--"] + sorted(want - got)
        assert not any(o.status == "invalid" for o in res.occurrences), sorted(got)
        texts = " ".join(seg.text for seg in res.pdf.body_segments)
        assert "objects of His wrath (Ps 85:4–7)" in texts, texts
        assert "indd" not in texts and "Part 3" not in texts, texts       # slug and running foot left out
        assert [res.pdf.label(i) for i in range(3)] == ["880", "881", "882"]
        notes = " ".join(seg.text for segs in res.pdf.note_segments.values() for seg in segs)
        assert "Part 3" not in notes and "indd" not in notes, notes


def test_ocr_fixes_and_fonts():
    t, changed = ocr_fix("Gen. l:l and John 3;16 but not Chapter I: and 1; 2 or I;l")
    assert t.startswith("Gen. 1:1 and John 3:16 but not Chapter I: and 1; 2"), t
    assert len(changed) == 3
    assert font_family("BCDEEE+EBGaramond-Regular") == "EB Garamond"
    assert font_family("TimesNewRomanPSMT") == "Times New Roman"


if __name__ == "__main__":
    bad = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print("ok", name)
            except AssertionError as e:
                bad += 1
                print("FAIL", name, e)
    sys.exit(1 if bad else 0)
