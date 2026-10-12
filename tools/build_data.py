"""Build Indicat's reference data from open sources (run once; output is committed).

    python tools/build_data.py SOURCES_DIR

SOURCES_DIR must contain:
  morphhb/          github.com/openscriptures/morphhb       (lemmas: CC BY 4.0; WLC text: public domain)
  HebrewLexicon/    github.com/openscriptures/HebrewLexicon (HebrewStrong.xml: CC BY 4.0 / public domain)
  sblgnt/           github.com/morphgnt/sblgnt              (MorphGNT lemmas: CC BY-SA; SBLGNT: SBLGNT EULA)
  KJVA.csv          github.com/scrollmapper/bible_databases formats/csv/KJVA.csv (public domain text)

Writes:
  indicat/data/verses.json   highest verse of every chapter, English (KJV) and Hebrew (WLC) numbering
  indicat/data/lexicon.json  word form -> dictionary form, for Hebrew (OSHB) and Greek (MorphGNT)
"""
import csv
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from indicat import terms as T  # noqa: E402

SRC = Path(sys.argv[1])
OUT = ROOT / "indicat" / "data"

KJV_NAMES = {
    "Genesis": "Gen", "Exodus": "Exod", "Leviticus": "Lev", "Numbers": "Num", "Deuteronomy": "Deut",
    "Joshua": "Josh", "Judges": "Judg", "Ruth": "Ruth", "I Samuel": "1Sam", "II Samuel": "2Sam",
    "I Kings": "1Kgs", "II Kings": "2Kgs", "I Chronicles": "1Chr", "II Chronicles": "2Chr", "Ezra": "Ezra",
    "Nehemiah": "Neh", "Esther": "Esth", "Job": "Job", "Psalms": "Ps", "Proverbs": "Prov",
    "Ecclesiastes": "Eccl", "Song of Solomon": "Song", "Isaiah": "Isa", "Jeremiah": "Jer",
    "Lamentations": "Lam", "Ezekiel": "Ezek", "Daniel": "Dan", "Hosea": "Hos", "Joel": "Joel", "Amos": "Amos",
    "Obadiah": "Obad", "Jonah": "Jonah", "Micah": "Mic", "Nahum": "Nah", "Habakkuk": "Hab",
    "Zephaniah": "Zeph", "Haggai": "Hag", "Zechariah": "Zech", "Malachi": "Mal",
    "Tobit": "Tob", "Judith": "Jdt", "Additions to Esther": "AddEsth", "Wisdom": "Wis", "Sirach": "Sir",
    "Baruch": "Bar", "Prayer of Azariah": "PrAzar", "Susanna": "Sus", "Bel and the Dragon": "Bel",
    "I Maccabees": "1Macc", "II Maccabees": "2Macc", "I Esdras": "1Esd", "II Esdras": "2Esd",
    "Prayer of Manasses": "PrMan",
    "Matthew": "Matt", "Mark": "Mark", "Luke": "Luke", "John": "John", "Acts": "Acts", "Romans": "Rom",
    "I Corinthians": "1Cor", "II Corinthians": "2Cor", "Galatians": "Gal", "Ephesians": "Eph",
    "Philippians": "Phil", "Colossians": "Col", "I Thessalonians": "1Thess", "II Thessalonians": "2Thess",
    "I Timothy": "1Tim", "II Timothy": "2Tim", "Titus": "Titus", "Philemon": "Phlm", "Hebrews": "Heb",
    "James": "Jas", "I Peter": "1Pet", "II Peter": "2Pet", "I John": "1John", "II John": "2John",
    "III John": "3John", "Jude": "Jude", "Revelation of John": "Rev",
}
NT_ORDER = ["Matt", "Mark", "Luke", "John", "Acts", "Rom", "1Cor", "2Cor", "Gal", "Eph", "Phil", "Col",
            "1Thess", "2Thess", "1Tim", "2Tim", "Titus", "Phlm", "Heb", "Jas", "1Pet", "2Pet", "1John",
            "2John", "3John", "Jude", "Rev"]


def verses():
    eng = defaultdict(dict)
    with open(SRC / "KJVA.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            b = KJV_NAMES.get(row["Book"])
            if not b:
                continue
            c, v = int(row["Chapter"]), int(row["Verse"])
            eng[b][c] = max(eng[b].get(c, 0), v)
    heb = defaultdict(dict)
    for x in sorted((SRC / "morphhb" / "wlc").glob("*.xml")):
        for m in re.finditer(r'<verse osisID="([^".]+)\.(\d+)\.(\d+)"', x.read_text(encoding="utf-8")):
            b, c, v = m.group(1), int(m.group(2)), int(m.group(3))
            heb[b][c] = max(heb[b].get(c, 0), v)
    # NT: MorphGNT (SBL numbering) alongside KJV
    for i, b in enumerate(NT_ORDER):
        p = next((SRC / "sblgnt").glob(f"{61 + i}-*-morphgnt.txt"))
        for line in p.read_text(encoding="utf-8").splitlines():
            c, v = int(line[2:4]), int(line[4:6])
            heb[b][c] = max(heb[b].get(c, 0), v)       # second numbering column = "original" text
    def pack(d):
        return {b: [d[b].get(c, 0) for c in range(1, max(d[b]) + 1)] for b in d}
    return {"eng": pack(eng), "orig": pack(heb),
            "note": "Highest verse of each chapter. eng = KJV (with Apocrypha); orig = WLC (OT) / SBLGNT (NT)."}


CANT = set(range(0x0591, 0x05B0)) | {0x05BD, 0x05BF, 0x05C0, 0x05C3, 0x05C4, 0x05C5, 0x05C6}


def heb_pointed(s):
    s = unicodedata.normalize("NFD", s.replace("/", "").replace("־", ""))
    s = "".join(ch for ch in s if ord(ch) not in CANT and ch not in "‍‌͏")
    s = s.replace("ׇ", "ָ")          # qamats qatan -> qamats
    return unicodedata.normalize("NFC", s).strip()


def greek_pointed(s):
    s = unicodedata.normalize("NFD", s.lower()).replace("̀", "́")
    return unicodedata.normalize("NFC", s).replace("ς", "σ")


def lexicon():
    strong = {}
    xml = (SRC / "HebrewLexicon" / "HebrewStrong.xml").read_text(encoding="utf-8")
    for m in re.finditer(r'<entry id="H(\d+)">\s*<w [^>]*>([^<]+)</w>', xml):
        strong[int(m.group(1))] = m.group(2).strip()
    he_lemmas, he_idx = [], {}
    he_p, he_c = defaultdict(lambda: defaultdict(int)), defaultdict(lambda: defaultdict(int))
    for x in sorted((SRC / "morphhb" / "wlc").glob("*.xml")):
        if x.name == "VerseMap.xml":
            continue
        for m in re.finditer(r'<w lemma="([^"]*)"[^>]*>([^<]+)</w>', x.read_text(encoding="utf-8")):
            nums = [int(n) for n in re.findall(r"(?<![a-z])(\d+)", m.group(1))]
            if not nums or nums[0] not in strong:
                continue
            head = strong[nums[0]]
            if head not in he_idx:
                he_idx[head] = len(he_lemmas)
                he_lemmas.append(head)
            li = he_idx[head]
            he_p[heb_pointed(m.group(2))][li] += 1
            he_c[T.fold_str(m.group(2).replace("/", ""))][li] += 1
    gr_lemmas, gr_idx = [], {}
    gr_p, gr_c = defaultdict(lambda: defaultdict(int)), defaultdict(lambda: defaultdict(int))
    for p in sorted((SRC / "sblgnt").glob("*-morphgnt.txt")):
        for line in p.read_text(encoding="utf-8").splitlines():
            parts = line.split(" ")
            word, norm, lemma = parts[4], parts[5], parts[6]
            if lemma not in gr_idx:
                gr_idx[lemma] = len(gr_lemmas)
                gr_lemmas.append(lemma)
            li = gr_idx[lemma]
            for w in {word, norm}:
                gr_p[greek_pointed(w)][li] += 1
                gr_c[T.fold_str(w)][li] += 1

    def resolve(counts, lemmas):
        """One lemma when the form is unambiguous: a single lemma, or one that accounts for 90% of
        the form's occurrences, or the only one-word lemma among several (compound names such
        as יוּשַׁב חֶסֶד share their parts' forms).  Otherwise all candidates."""
        if len(counts) == 1:
            return list(counts)
        total = sum(counts.values())
        top = max(counts, key=counts.get)
        if counts[top] >= 0.9 * total:
            return [top]
        single = [i for i in counts if not re.search(r"[\s\u05be]", lemmas[i])]
        if len(single) == 1:
            return single
        return sorted(counts, key=lambda i: -counts[i])

    def pack(pointed, plain, lemmas):
        """plain key -> lemma ids; pointed keys only where they say something the plain key doesn't."""
        out_plain = {k: ",".join(map(str, resolve(v, lemmas))) for k, v in sorted(plain.items()) if k}
        out_pointed = {}
        for k, v in sorted(pointed.items()):
            r = ",".join(map(str, resolve(v, lemmas)))
            if k and r != out_plain.get(T.fold_str(k)):
                out_pointed[k] = r
        return out_pointed, out_plain

    # a dictionary form always files under itself (authors cite lexical forms)
    for i, lem in enumerate(he_lemmas):
        for part in [lem] + ([] if re.search(r"[\s\u05be]", lem) else []):
            he_p[heb_pointed(part)] = {i: 10 ** 6}
            he_c[T.fold_str(part)][i] = he_c[T.fold_str(part)].get(i, 0) + 10 ** 6
    for i, lem in enumerate(gr_lemmas):
        gr_p[greek_pointed(lem)] = {i: 10 ** 6}
        gr_c[T.fold_str(lem)][i] = gr_c[T.fold_str(lem)].get(i, 0) + 10 ** 6
    # MorphGNT files impersonal δεῖ under δέω; lexicons treat it as its own word
    if "δεῖ" not in gr_idx:
        gr_idx["δεῖ"] = len(gr_lemmas)
        gr_lemmas.append("δεῖ")
    for w in ("δεῖ", "ἔδει", "δέον", "δεήσει"):
        gr_p[greek_pointed(w)] = {gr_idx["δεῖ"]: 10 ** 6}
        gr_c[T.fold_str(w)] = {gr_idx["δεῖ"]: 10 ** 6}
    hp, hc = pack(he_p, he_c, he_lemmas)
    gp, gc = pack(gr_p, gr_c, gr_lemmas)
    return {"hebrew": {"lemmas": he_lemmas, "pointed": hp, "plain": hc},
            "greek": {"lemmas": gr_lemmas, "pointed": gp, "plain": gc},
            "credit": "Hebrew: Open Scriptures Hebrew Bible (CC BY 4.0) and Strong's dictionary via the "
                      "Open Scriptures Hebrew Lexicon. Greek: MorphGNT SBLGNT lemmatization (CC BY-SA), "
                      "SBLGNT text (SBLGNT EULA)."}


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verses.json").write_text(json.dumps(verses(), ensure_ascii=False, separators=(",", ":")),
                                     encoding="utf-8")
    (OUT / "lexicon.json").write_text(json.dumps(lexicon(), ensure_ascii=False, separators=(",", ":")),
                                      encoding="utf-8")
    for f in ("verses.json", "lexicon.json"):
        print(f, (OUT / f).stat().st_size)
