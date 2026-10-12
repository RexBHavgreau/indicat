"""Tests for original-language word indexes, term sets and settings migration.

    python tests/test_terms.py
"""
import copy
import json
import os
import sys

# Windows consoles default to a code page that has no Greek or Hebrew
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from indicat import terms as T              # noqa: E402

WORDS_ON = {"words": {"scripts": {"greek": {"enabled": True}, "hebrew": {"enabled": True}}}}


def scan(text, settings=None, meta=None):
    s = copy.deepcopy(settings or WORDS_ON)
    return T.TermEngine(s).scan(text, meta or T.SegMeta())


def found(hits, status="word"):
    return [h.ref.heading if h.ref else None for h in hits
            if h.status == status or (status == "word" and h.status == "word-check")]


def test_lists_are_kept():
    h = scan("The verbs ἀγαπάω, φιλέω, στέργω, ἐράω, ποθέω and so on.")
    assert found(h) == ["ἀγαπάω", "φιλέω", "στέργω", "ἐράω", "ποθέω"], found(h)


def test_quotations_are_skipped():
    h = scan("John writes Ἐν ἀρχῇ ἦν ὁ λόγος, καὶ ὁ λόγος ἦν πρὸς τὸν θεόν here.")
    assert found(h) == [] and len(found(h, "quotation")) == 1, h
    q = [x for x in h if x.status == "quotation"][0]
    assert "12-word" in q.reason and len(q.words) == 4      # stop words (ἐν, ἦν, ὁ, καί…) are not entries


def test_short_runs_are_words():
    h = scan("the phrase ἐν ἀρχῇ ἦν and λόγος")
    assert found(h) == ["ἀρχή", "λόγος"], found(h)         # ἐν and ἦν (εἰμί) are skipped words


def test_run_limit_setting():
    s = copy.deepcopy(WORDS_ON)
    s["words"]["max_run"] = 2
    h = scan("the phrase ἐν ἀρχῇ ἦν here", s)
    assert found(h) == [] and found(h, "quotation") == [None]


def test_block_quotes():
    long_q = "An indented paragraph of prose quoting someone who mentions λόγος among a dozen words or more."
    assert found(scan(long_q, meta=T.SegMeta("indent"))) == []
    assert found(scan("λόγος short", meta=T.SegMeta("indent"))) == ["λόγος"]      # a short indented line
    assert found(scan("λόγος", meta=T.SegMeta("style"))) == []
    assert found(scan("λόγος", meta=T.SegMeta("style", table=True))) == ["λόγος"]  # tables: cell by cell
    s = copy.deepcopy(WORDS_ON)
    s["words"]["skip_block_quotes"] = False
    assert found(scan("λόγος", s, T.SegMeta("style"))) == ["λόγος"]


def test_hebrew_maqaf_points_and_grouping():
    h = scan("חֶסֶד and חסד in כָּל־הָאָרֶץ")
    refs = [x.ref for x in h if x.status.startswith("word")]
    T.choose_headings(refs)
    assert [r.heading for r in refs] == ["חֶסֶד", "חֶסֶד", "אֶרֶץ"], [r.heading for r in refs]
    assert [x.status for x in h] == ["word", "word-check", "word"]       # unpointed חסד could be חָסַד


def test_grouping_off_keeps_forms_apart():
    s = copy.deepcopy(WORDS_ON)
    s["words"]["group_forms"] = False
    s["words"]["dictionary_forms"] = False
    refs = [x.ref for x in scan("λόγος and λογος", s) if x.status == "word"]
    T.choose_headings(refs)
    assert [r.heading for r in refs] == ["λόγος", "λογος"]
    assert refs[0].sort != refs[1].sort


def test_greek_sort_and_case():
    refs = [x.ref for x in scan("Λόγος, ΛΟΓΟΣ and λόγος") if x.status == "word"]
    T.choose_headings(refs)
    assert {r.heading for r in refs} == {"λόγος"}
    assert T.sort_code("ἀγάπη") < T.sort_code("βίος") < T.sort_code("ὠδή")
    assert T.sort_code("אָב") < T.sort_code("תּוֹרָה") and T.sort_code("מֶלֶךְ") == T.sort_code("מלכ")


def test_elision_and_syriac():
    s = copy.deepcopy(WORDS_ON)
    s["words"]["scripts"]["syriac"] = {"enabled": True}
    h = scan("δι’ αὐτοῦ ἐγένετο; and ܡܠܬܐ", s)
    assert found(h) == ["γίνομαι", "ܡܠܬܐ"], found(h)        # δι’ is διά, a skipped word


def test_dictionary_forms():
    h = scan("λόγος, λόγου, and τοῖς λόγοις; then κεχαριτωμένη; then ἐστιν, ἐγώ, σου, τίς; then κατ’ ἐμέ")
    assert found(h) == ["λόγος", "λόγος", "λόγος", "χαριτόω"], found(h)
    h = scan("וַיִּתְהַלֵּךְ and וְהָאָרֶץ and הִוא")
    assert found(h) == ["הָלַךְ", "אֶרֶץ"], found(h)                     # הוּא is a skipped word
    s = copy.deepcopy(WORDS_ON)
    s["words"]["forms_as_subentries"] = True
    assert [x.ref.display() for x in scan("λόγου and λόγοις", s)] == ["λόγος, λόγου", "λόγος, λόγοις"]
    s["words"]["dictionary_forms"] = False
    assert found(scan("λόγου and λόγοις", s)) == ["λόγου", "λόγοις"]
    assert found(scan("ἄρτοσχ and λόγε")) == ["ἄρτοσχ", "λόγε"]          # not in the lexicon: as written


def test_tagged_language():
    s = {"words": {"tagged": [{"lang": "la", "enabled": True, "skip": "et"}]}}
    text = "The phrase sola gratia et fide is Latin; gratia here is not tagged."
    langs = [None] * len(text)
    for k in range(text.index("sola"), text.index(" is Latin")):
        langs[k] = "la-Latn"
    h = scan(text, s, T.SegMeta(langs=langs))
    assert found(h) == ["sola", "gratia", "fide"], found(h)


def test_hebrew_book_turns_hebrew_index_off():
    msgs = []
    s = copy.deepcopy(WORDS_ON)
    s["language"] = "he"
    ids = [d.id for d in T.index_defs(s, messages=msgs)]
    assert ids == ["script:greek"] and msgs


def term_set(entries, **opts):
    return {"term_sets": [{"id": "set1", "name": "S", "enabled": True, "title": "Subject Index",
                           "options": opts, "entries": entries}]}


def test_term_set_matching():
    s = term_set([{"heading": "covenant", "forms": ["covenant"]},
                  {"heading": "covenant", "sub": "new", "forms": ["new covenant"]},
                  {"heading": "grace", "forms": ["grace"]}], plurals=True)
    h = scan("The new covenant and covenants of GRACE; graceful is not grace-less.", s)
    got = [(x.ref.display(), x.status) for x in h]
    assert got == [("covenant, new", "term"), ("covenant", "term"), ("grace", "term"), ("grace", "term")], got


def test_term_set_case_and_marks():
    s = term_set([{"heading": "Word", "forms": ["Word"]}], case_sensitive=True)
    assert [x.ref.heading for x in scan("the Word and a word", s)] == ["Word"]
    s = term_set([{"heading": "λόγος", "forms": ["λογος"]}])
    assert len(scan("λόγος, Λόγος", s)) == 2
    s = term_set([{"heading": "λόγος", "forms": ["λογος"]}], ignore_marks=False)
    assert len(scan("λόγος", s)) == 0


def test_term_set_hebrew_prefixes():
    s = term_set([{"heading": "אֶרֶץ", "forms": ["ארץ"]}], hebrew_prefixes=True)
    h = scan("וּבְאֶרֶץ and אֶרֶץ", s)
    assert [x.ref.heading for x in h] == ["אֶרֶץ", "אֶרֶץ"], h
    s = term_set([{"heading": "אֶרֶץ", "forms": ["ארץ"]}])
    assert len(scan("וּבְאֶרֶץ and אֶרֶץ", s)) == 1


def test_term_set_block_quotes():
    s = term_set([{"heading": "grace", "forms": ["grace"]}])
    h = scan("grace", s, T.SegMeta("style"))
    assert [x.status for x in h] == ["quotation"]
    s["term_sets"][0]["options"]["skip_block_quotes"] = False
    assert [x.status for x in scan("grace", s, T.SegMeta("style"))] == ["term"]


def test_cross_references():
    d = T.index_defs(term_set([{"heading": "favor", "see": "grace"},
                               {"heading": "grace", "forms": ["grace"], "see_also": "mercy"}]))[0]
    cs = T.compile_set(d)
    assert [(r.heading, k, t) for r, k, t in cs.crossrefs] == [("favor", "see", "grace"), ("grace", "see_also", "mercy")]
    assert [f for f, _ in cs.forms] == ["grace"]


def test_read_files():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d, "terms.txt")
        p.write_text("# comment\nλόγος | λόγου | λόγῳ\n\ncovenant\n", encoding="utf-8")
        e, probs = T.read_term_file(p)
        assert [x["heading"] for x in e] == ["λόγος", "covenant"] and e[0]["forms"] == ["λόγος", "λόγου", "λόγῳ"]
        c = Path(d, "terms.csv")
        c.write_text(T.sample_csv(), encoding="utf-8-sig")
        e, probs = T.read_term_file(c)
        assert len(e) == 7 and e[3]["sub"] == "Davidic" and e[5]["see"] == "חֶסֶד" and not probs, (e, probs)
        out = Path(d, "out.csv")
        T.write_term_csv(out, e)
        e2, _ = T.read_term_file(out)
        assert e2 == e
        n = Path(d, "noheader.csv")
        n.write_text("grace,,grace | gracious\n,missing heading\n", encoding="cp1252")
        e, probs = T.read_term_file(n)
        assert e[0]["forms"] == ["grace", "gracious"] and len(probs) == 1


def test_greek_skip_list_upgrade():
    from indicat import settings as S
    old = {"_settings_version": 3, "words": {"scripts": {"greek": {"enabled": True, "skip": "και δε μυ"}}}}
    new = S.migrate(old)
    sk = new["words"]["scripts"]["greek"]["skip"].split()
    assert sk[:3] == ["και", "δε", "μυ"] and "εγω" in sk and "ειμι" in sk and sk.count("και") == 1
    old = {"_settings_version": 3, "term_sets": [{"name": "Subjects (CSV UTF-8)", "title": "Index of Subjects (CSV UTF-8)"},
                                                 {"name": "Names", "title": "My Names"}]}
    ts = S.migrate(old)["term_sets"]
    assert ts[0]["name"] == "Subjects" and ts[0]["title"] == "Index of Subjects" and ts[1]["title"] == "My Names"
    assert T.clean_set_name("Subjects (CSV, Windows)") == "Subjects"


def test_settings_migration():
    with tempfile.TemporaryDirectory() as d:
        old = Path(d, "ScriptureIndexBuilder")
        old.mkdir()
        (old / "settings.json").write_text(json.dumps({"language": "es", "separator": "tab_dot",
                                                       "custom_books": [{"id": "X_1En", "name": "1 Enoch"}]}))
        os.environ["APPDATA"] = d
        import importlib
        from indicat import settings as S
        importlib.reload(S)
        s = S.load()
        assert s["language"] == "es" and s["custom_books"][0]["name"] == "1 Enoch" and S.migration_note
        assert Path(d, "Indicat", "settings.json").is_file()
        s["term_sets"] = [{"id": "set1", "name": "x"}]
        S.save(s)
        importlib.reload(S)
        s2 = S.load()
        assert s2["term_sets"][0]["name"] == "x" and not S.migration_note
        exp = Path(d, "exp.json")
        S.export_to(s2, exp)
        assert "term_sets" in json.loads(exp.read_text(encoding="utf-8")) and "last_file" not in json.loads(exp.read_text(encoding="utf-8"))


def main():
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_")]
    bad = 0
    for name, fn in tests:
        try:
            fn()
            print("ok", name)
        except AssertionError as exc:
            bad += 1
            print("FAIL", name, exc)
    print(f"{len(tests) - bad}/{len(tests)} passed")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
