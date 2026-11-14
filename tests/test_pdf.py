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


def test_page_range():
    """Index only some PDF pages (PDF page numbers, 1 = the first page)."""
    assert X.parse_pages("") == [] and X.parse_pages("  ") == []
    assert X.parse_pages("9–14, 21-880", 900) == [(9, 14), (21, 880)]
    assert X.parse_pages("45; 3 to 5", 900) == [(3, 5), (45, 45)]
    assert X.parse_pages("21–", 900) == [(21, 900)]
    for bad, why in (("9–x", "isn't a page"), ("14–9", "not after the last"), ("0–3", "1 or more"),
                     ("5–901", "has 900 pages")):
        try:
            X.parse_pages(bad, 900)
            raise AssertionError(bad)
        except ValueError as exc:
            assert why in str(exc), (bad, str(exc))
    labels = ["", "", "i", "ii"] + [str(i) for i in range(1, 897)]
    assert X.describe_pages("3–4, 5–10", 900, labels) == "8 of 900 pages = printed pages i–ii, 1–6."
    assert X.describe_pages("", 900, None) == "Blank: all 900 pages."
    assert "shown in the log after the scan" in X.describe_pages("5", 900, None)
    with tempfile.TemporaryDirectory() as d:
        pdf = Path(d, "Book.pdf")
        make_book(pdf)
        s = copy.deepcopy(DEFAULTS)
        res = X.scan_pdf(pdf, s, log=lambda *a: None, pages="2")
        got = {(o.ref.display() if o.ref else o.hit.raw, o.page) for o in res.occurrences}
        assert all(pg == "2" for _, pg in got), got
        # a word that runs on from page 1 is still caught where it ends, and so are page 2's notes
        assert {("Deuteronomy 6:4", "2"), ("Exodus 24:8", "2"), ("Joshua 24:25", "2")} <= got, got
        assert not any(name == "Genesis 1:1" for name, _ in got)
        assert any("Only PDF pages 2 were indexed (printed pages 2; 1 of 2 pages)" in w for w in res.warnings), \
            res.warnings
        # the range kept for this PDF in the settings is used when none is given
        s["pdf_pages"] = {X.page_key(pdf): "1"}
        res = X.scan_pdf(pdf, s, log=lambda *a: None)
        assert {o.page for o in res.occurrences} == {"1"}, {o.page for o in res.occurrences}
        cols = Path(d, "Columns.pdf")
        make_two_columns(cols)
        res = X.scan_pdf(cols, copy.deepcopy(DEFAULTS), log=lambda *a: None, pages="2–3")
        assert {o.page for o in res.occurrences} == {"881", "882"}
        assert any("printed pages 881–882; 2 of 3 pages" in w for w in res.warnings), res.warnings


def test_old_style_lists():
    """An old book's list with roman chapter numbers: "Heb. iii. 7, ix. 8, x. 15"."""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    with tempfile.TemporaryDirectory() as d:
        pdf = Path(d, "Old.pdf")
        c = canvas.Canvas(str(pdf), pagesize=letter)
        for folio, line in (("41", "The priesthood is passed on (Heb. iii. 7, ix. 8, x. 15), as the"),
                            ("42", "apostle shows; and the Sermon (Matt. v. 3, 9, vi. 9) agrees.")):
            c.setFont("Times-Roman", BODY)
            for k in range(8):
                c.drawString(72, 700 - k * LEAD, line if k == 3 else "Filler text of an old book, set in one column here.")
            c.setFont("Times-Roman", 9)
            c.drawCentredString(306, 40, folio)
            c.showPage()
        c.save()
        res = X.scan_pdf(pdf, copy.deepcopy(DEFAULTS), log=lambda *a: None)
        got = [(o.ref.display(), o.page) for o in res.occurrences if o.ref is not None and o.include]
        assert got == [("Hebrews 3:7", "41"), ("Hebrews 9:8", "41"), ("Hebrews 10:15", "41"),
                       ("Matthew 5:3", "42"), ("Matthew 5:9", "42"), ("Matthew 6:9", "42")], got


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
