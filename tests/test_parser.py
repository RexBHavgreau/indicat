"""Parser regression tests: run with `python -m pytest tests` (or just `python tests/test_parser.py`)."""
import sys

# Windows consoles default to a code page that has no Greek or Hebrew
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import copy  # noqa: E402

from indicat.parser import Scanner, parse_label  # noqa: E402
from indicat.settings import DEFAULTS, make_context  # noqa: E402


def ctx(lang="en", **kw):
    s = copy.deepcopy(DEFAULTS)
    s["language"] = lang
    s["apocrypha"] = True
    s.update(kw)
    return make_context(s)


def refs(text, italic=None, lang="en", **kw):
    cat, L = ctx(lang, **kw)
    hits, _ = Scanner(L).scan_segment(text, italic or [False] * len(text), 0)
    return [(h.status, h.ref.display() if h.ref else None) for h in hits]


def test_chain_and_continuation():
    assert refs("(1 Sam. 25:43; 27:3) and (5:1, 7)") == [
        ("explicit", "1 Samuel 25:43"), ("chain", "1 Samuel 27:3"),
        ("inferred", "1 Samuel 5:1"), ("inferred", "1 Samuel 5:7")]


def test_cross_chapter_range_kept_whole():
    assert refs("Then, in Song of Solomon 5:9–6:1, reconciliation")[0] == (
        "explicit", "Song of Solomon 5:9–6:1")


def test_refrain_list_with_trailing_colon():
    r = refs("the refrain of Song of Solomon 2:7, 3:5, and 8:4: “Do not")
    assert [x[1] for x in r] == ["Song of Solomon 2:7", "Song of Solomon 3:5", "Song of Solomon 8:4"]


def test_spelled_out_numbers():
    r = refs("First Kings 11:1–8 says. First John 3:4 tells us. First Corinthians 11:3 tells.")
    assert [x[1] for x in r] == ["1 Kings 11:1–8", "1 John 3:4", "1 Corinthians 11:3"]


def test_book_from_running_text():
    assert refs("In Proverbs, Solomon says (10:12; 5:4)")[0] == ("inferred", "Proverbs 10:12")


def test_ambiguous_name_needs_number():
    assert refs("Peter said this. (3:16)") == [("unresolved", None)]
    assert refs("the book of Acts (17:23–31)") == [("explicit", "Acts 17:23–31")]


def test_citations_rejected():
    r = refs("(Brill, 2000), 1:279. HALOT, 1:43–44. Commentary (Abingdon Press, 1970), 2:463.")
    assert all(s == "citation" for s, _ in r) and len(r) == 3


def test_verse_only_and_chapter_only():
    r = refs("Starting in Ephesians 5. Starting in verse 21, he says (v. 23).")
    assert r == [("chapter-only", "Ephesians 5"), ("verse-only", "Ephesians 5:21"),
                 ("verse-only", "Ephesians 5:23")]


def test_single_chapter_book_and_suffix():
    r = refs("Jude 5 and 1 Cor 7:4a")
    assert r == [("explicit", "Jude 5"), ("explicit", "1 Corinthians 7:4a")]


def test_italic_title_vs_block_quote():
    t = "Christensen, Deuteronomy 1–21:9, rev. ed."
    ital = [False] * len(t)
    for i in range(13, 30):
        ital[i] = True
    assert refs(t, ital)[0][0] == "italic"
    q = "make your sons whore after their gods. (Exod. 34:15–16)"
    assert refs(q, [True] * len(q))[0] == ("explicit", "Exodus 34:15–16")


def test_sort_keys_canonical():
    cat, _ = ctx()
    a, b, c = (parse_label(cat, "Song", x) for x in ("7:11–13", "7:11–8:7", "7:11"))
    assert sorted([a, b, c], key=lambda r: r.sort_key()) == [c, a, b]


def test_cmos_and_sbl():
    r = refs("Gn 1:1, Exod. 3:14, Eccles. 3:1, Philem. 4, Song of Sol. 2:1, 1 Thes 4:16, Rv 22:20")
    assert [x[1] for x in r] == ["Genesis 1:1", "Exodus 3:14", "Ecclesiastes 3:1", "Philemon 4",
                                 "Song of Solomon 2:1", "1 Thessalonians 4:16", "Revelation 22:20"]


def test_risky_two_letter_abbreviations():
    assert refs("Is 5 enough?") == []
    assert refs("Is 53:5") == [("explicit", "Isaiah 53:5")]


def test_apocrypha_toggle():
    # always recognized (never misread as another book), indexed only when switched on
    assert refs("Sir 24:3", apocrypha=False) == [("apocrypha", "Sirach 24:3")]
    assert refs("Sir 24:3") == [("explicit", "Sirach 24:3")]


def test_spanish():
    r = refs("Primera de Corintios 13:4; Jn 3:16 y Hch 2:38", lang="es")
    assert [x[1] for x in r] == ["1 Corintios 13:4", "Juan 3:16", "Hechos 2:38"]


def test_portuguese_jo_is_john():
    assert refs("Jo 3:16 e Jn 1:2", lang="pt") == [("explicit", "João 3:16"), ("explicit", "Jonas 1:2")]


def test_german_comma_notation():
    r = refs("Joh 3,16; 1. Mose 1,1; Röm 8,28.30. Es kostet 3,5 Euro.", lang="de")
    assert [x[1] for x in r if x[1]] == ["Johannes 3,16", "Genesis 1,1", "Römer 8,28", "Römer 8,30"]
    assert ("unresolved", None) in r      # "3,5 Euro" is not indexed


def test_list_does_not_swallow_numbered_book():
    r = refs("vgl. Sir 24,3 und 1. Mose 1,1.", lang="de")
    assert [x[1] for x in r] == ["Jesus Sirach 24,3", "Genesis 1,1"]


def test_french():
    r = refs("Jn 3,16 et Gn 1,1-3 ; 2,4.7. Voir 1 Co 13,4s.", lang="fr")
    assert [x[1] for x in r] == ["Jean 3,16", "Genèse 1,1–3", "Genèse 2,4", "Genèse 2,7", "1 Corinthiens 13,4–5"]


def test_hebrew_numerals_and_prefixes():
    r = refs("כתוב בבראשית א, א ובשמות ג:יד. ראו תה׳ כג, א-ג; גם שמ״א טז, ז.", lang="he")
    assert [x[1] for x in r] == ["בראשית א, א", "שמות ג, יד", "תהלים כג, א–ג", "שמואל א טז, ז"]


def test_hebrew_tanakh_order():
    cat, _ = ctx("he")
    assert cat.book_key("Mal") < cat.book_key("Ps") < cat.book_key("1Chr")
    cat, _ = ctx("en")
    assert cat.book_key("Ps") < cat.book_key("Mal")


def test_custom_book():
    cb = {"id": "X_1Enoch", "name": "1 Enoch", "spellings": [], "abbreviations": ["1 En"],
          "section": "OTHER", "position": 1, "chapters": 108}
    r = refs("As 1 En 1:9 says", custom_books=[cb])
    assert r == [("explicit", "1 Enoch 1:9")]



# ---------------------------------------------------------------------------
# 0.4.0: cases from the dissertation and the test manuscript
# ---------------------------------------------------------------------------
def test_unknown_abbreviation_never_borrows_a_book():
    off = {"languages": {"en": {"disabled_sets": ["CMOS shorter"]}}}
    r = refs("In Genesis 3:15 the promise. Later Ex. 24:16; 40:34–35.", **off)
    assert r[1][0] == "unknown-book" and r[1][1] is None and r[2][0] == "unknown-book", r
    r = refs("Genesis 3:15 … see Geneses 3:15 (a typo).")
    assert r[1] == ("unknown-book", None)


def test_apocrypha_forms_and_vulgate_kings():
    r = refs("Tob 5:15, 6:8; 1 Mac 12:11; 2 Mac 1:18; Letter J 5; WS 2:24", apocrypha=True)
    assert [x[1] for x in r] == ["Tobit 5:15", "Tobit 6:8", "1 Maccabees 12:11", "2 Maccabees 1:18",
                                 "Letter of Jeremiah 5", "Wisdom of Solomon 2:24"]
    assert refs("(3 Kings 8:10–11)") == [("check-name", "1 Kings 8:10–11")]
    assert refs("the woman of the Apocalypse (12:1)") == [("explicit", "Revelation 12:1")]


def test_gospel_writer_as_subject_and_person_named_like_a_book():
    r = refs("In Luke 24 the verb recurs. Matthew uses it (16:21; 17:10), Mark uses it (8:31), "
             "and John uses it (3:7, 14). As we read in Mark (3:34).")
    assert [x[1] for x in r] == ["Luke 24", "Matthew 16:21", "Matthew 17:10", "Mark 8:31", "John 3:7",
                                 "John 3:14", "Mark 3:34"]
    r = refs("In Luke 1 the angel comes. Zechariah responds with doubt (1:20), Mary with belief (1:38).")
    assert [x[1] for x in r] == ["Luke 1", "Luke 1:20", "Luke 1:38"]
    assert refs("the book of Numbers counts the tribes. James argues the point (2:17).") == \
        [("inferred", "James 2:17")]


def test_ranges_suffixes_and_impossible_verses():
    assert [x[1] for x in refs("Col 2:16–7, Dan 2:28–9")] == ["Colossians 2:16–17", "Daniel 2:28–29"]
    r = refs("Exod 40:34f, Exod 40:34f., Rev 2:18ff., Exod 40:38f")
    assert r == [("explicit", "Exodus 40:34–35"), ("explicit", "Exodus 40:34–35"),
                 ("explicit", "Revelation 2:18ff."), ("f-end", "Exodus 40:38f.")]
    assert [x[0] for x in refs("Joel 1:118 and Zechariah 1:62 and Isaiah 67:7")] == ["invalid"] * 3


def test_sort_order_with_suffixes():
    cat, _ = ctx()
    labels = ["34", "34a", "34ff", "34–35", "34–36", "35"]
    refs_ = [parse_label(cat, "Exod", "40:" + x) for x in labels]
    assert [r.label() for r in sorted(refs_, key=lambda r: r.sort_key())] == \
        ["40:34", "40:34a", "40:34ff.", "40:34–35", "40:34–36", "40:35"]


def test_chapter_unclear_after_chapter_range():
    r = refs("1 Kings 1–11 narrates his reign. In verse 23 it is repeated.")
    assert r == [("chapter-only", "1 Kings 1–11"), ("unresolved", None)]


def test_hebrew_numbering():
    r = refs("Mal 3:23 [4:5]; Ps 51:1 (Eng.) is 51:3 in the MT; Joel 3:1 [2:28].")
    assert r == [("mt", "Malachi 3:23 [MT]"), ("chain", "Malachi 4:5"), ("explicit", "Psalms 51:1"),
                 ("mt", "Psalms 51:3 [MT]"), ("mt", "Joel 3:1 [MT]"), ("chain", "Joel 2:28")]


def test_titles_and_citations_in_italics():
    t = "Pace, “Dulia,” The Catholic Encyclopedia, 5:188; Gruenthaner, Mariology, 1:118; Bock, Luke 1:1–9:50."
    it = [False] * len(t)
    for w in ("The Catholic Encyclopedia", "Mariology", "Luke 1:1–9:50"):
        i = t.index(w)
        it[i:i + len(w)] = [True] * len(w)
    assert [x[0] for x in refs(t, it)] == ["citation", "citation", "italic"]

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
