"""Word output: pairing marked (note) page numbers in Word's index with the notes they stand
for, and Chicago-style See / See also in the finished index.

    python tests/test_note_matching.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from indicat.word_com import match_note_locators, _n_suffix, cmos_crossref_edits   # noqa: E402


class R:
    def __init__(self, book, label):
        self.book_name, self._l = book, label

    def label(self):
        return self._l


class O:
    def __init__(self, kind, ordinal, page, number=None, book="Elijah", label=""):
        self.note_kind, self.note_ordinal, self.page = kind, ordinal, page
        self.note_number = number or str(ordinal)
        self.ref = R(book, label)


def entry(*locs):
    return [{"book": "Elijah", "entry": "", "locs": [{"text": t, "marked": m} for t, m in locs]}]


def test_term_twice_in_one_note():
    a, b = O("footnote", 3, "4"), O("footnote", 3, "4")
    assign, un = match_note_locators(entry(("2", False), ("4", True)), [a, b])
    assert assign[(0, 1)] == [a, b] and not un
    assert _n_suffix([o.note_number for o in assign[(0, 1)]]) == "n3"


def test_endnotes_pair_after_footnotes():
    # anchors in reading order: footnote (p. 1), endnote i (printed p. 16), footnote (p. 7)
    f1, e1, f2 = O("footnote", 1, "1"), O("endnote", 1, "16", "i"), O("footnote", 2, "7")
    assign, un = match_note_locators(entry(("1", True), ("7", True), ("16", True)), [f1, e1, f2])
    assert assign[(0, 0)] == [f1] and assign[(0, 1)] == [f2] and assign[(0, 2)] == [e1] and not un


def test_long_note_on_two_pages():
    a, b = O("footnote", 5, "3"), O("footnote", 5, "4")
    assign, un = match_note_locators(entry(("3", True), ("4", True)), [a, b])
    assert assign[(0, 0)] == [a] and assign[(0, 1)] == [b] and not un


def test_two_notes_one_page():
    a, b = O("footnote", 4, "3"), O("footnote", 5, "3")
    assign, un = match_note_locators(entry(("3", True),), [a, b])
    assert assign[(0, 0)] == [a, b] and _n_suffix(["4", "5"]) == "nn4–5"


def test_note_on_page_of_body_reference():
    a = O("footnote", 2, "5")
    assign, un = match_note_locators(entry(("5", False),), [a])
    assert assign == {} and un == []


def test_cmos_cross_references():
    def apply(t, sep=", "):
        for a, b, n in cmos_crossref_edits(t, sep):
            t = t[:a] + ". " + t[b:]
        return t
    assert apply("Our Lady, See Mary\r") == "Our Lady. See Mary\r"
    assert apply("Assumption, i, 9, See also Dormition; Mary\r") == "Assumption, i, 9. See also Dormition; Mary\r"
    assert apply("favor\tSee grace\r", "\t") == "favor. See grace\r"
    assert apply("Seeds, 4, 5\r") == "Seeds, 4, 5\r"
    assert apply("gracia, Véase también favor\r") == "gracia. Véase también favor\r"


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
