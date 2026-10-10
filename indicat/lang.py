"""Compile a language profile + user settings into the matcher the parser uses."""
from __future__ import annotations

import re
import unicodedata

from .catalog import Catalog
from .profiles import PROFILES

SP = "[    ]"
GERESH = "׳"        # ׳
GERSHAYIM = "״"     # ״
GERESH_CLASS = "[׳'’]"
GERSHAYIM_CLASS = "[״\"”]"
ROMAN = {"1": "I", "2": "II", "3": "III"}


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def norm_spelling(s: str) -> str:
    """Canonical key for a matched book spelling."""
    s = re.sub(SP + "+", " ", s.strip())
    s = s.replace("'", GERESH).replace("’", GERESH)
    s = s.replace('"', GERSHAYIM).replace("”", GERSHAYIM)
    s = re.sub(r"^([123])\.?\s*(?=\D)", r"\1 ", s)          # 1Sam / 1. Sam / 1 Sam
    if s.endswith(".") and not s.endswith(".."):
        s = s[:-1]
    return s


def core_len(s: str) -> int:
    return len(re.sub(r"[\d\s.׳״]", "", s))


class Language:
    """Matcher for one language: spellings -> book ids, plus reading rules."""

    def __init__(self, profile: dict, settings: dict, catalog: Catalog):
        self.p = profile
        self.code = profile["code"]
        self.cat = catalog
        lset = settings.get("languages", {}).get(self.code, {})
        disabled = set(lset.get("disabled_sets", []))
        overrides = lset.get("books", {})
        # key -> (book_id, kind, short, bare_ok)
        self.spellings: dict[str, tuple] = {}
        self.conflicts: list[str] = []
        bare_ok = set(profile.get("bare_ok", []))
        risky = set(profile.get("risky_abbr", []))
        deferred: list[tuple[str, str, str]] = []

        def add(spelling: str, bid: str, kind: str):
            if bid not in catalog.books:
                return
            key = norm_spelling(spelling)
            if not key:
                return
            short = kind == "abbr" and core_len(key) <= 2 and key.rstrip(".") in risky
            entry = (bid, kind, short, kind == "full" and bid in bare_ok)
            old = self.spellings.get(key)
            if old and old[0] != bid:
                self.conflicts.append(f"“{key}” is used for both {catalog.name(old[0])} and "
                                      f"{catalog.name(bid)}; keeping {catalog.name(old[0])}.")
                return
            if old and old[1] == "full":
                return
            self.spellings[key] = entry

        def add_variants(spelling: str, bid: str, kind: str):
            add(spelling, bid, kind)
            m = re.match(r"^([123]) (.+)$", spelling)
            if m:
                n, rest = m.groups()
                if profile.get("roman"):
                    add(f"{ROMAN[n]} {rest}", bid, kind)
                if kind == "full" or True:
                    for w in profile.get("ordinals", {}).get(n, []):
                        add(f"{w} {rest}", bid, kind)
                        if profile.get("ordinal_de"):
                            add(f"{w} de {rest}", bid, kind)
            if self.code in ("es", "pt", "fr", "de"):
                plain = strip_accents(spelling)
                if plain != spelling:
                    deferred.append((plain, bid, kind))

        removed = {bid: set(norm_spelling(x) for x in o.get("remove", [])) for bid, o in overrides.items()}
        for bid, names in profile.get("full", {}).items():
            for s in names:
                if norm_spelling(s) not in removed.get(bid, ()):
                    add_variants(s, bid, "full")
        dn = lset.get("names", {})
        for bid, nm in dn.items():
            add_variants(nm, bid, "full")
        for set_name, table in profile.get("sets", {}).items():
            if set_name in disabled:
                continue
            for bid, abbrs in table.items():
                for s in abbrs:
                    if norm_spelling(s) not in removed.get(bid, ()):
                        add_variants(s, bid, "abbr")
        for bid, o in overrides.items():
            for s in o.get("add", []):
                add_variants(s, bid, "abbr" if core_len(s) < 5 else "full")
        for cb in settings.get("custom_books", []):
            bid = cb.get("id")
            for s in [cb.get("name", "")] + list(cb.get("spellings", [])):
                if s:
                    add_variants(s, bid, "full")
            for s in cb.get("abbreviations", []):
                add_variants(s, bid, "abbr")

        # unaccented variants only where they don't collide with a real spelling
        for plain, bid, kind in deferred:
            if norm_spelling(plain) not in self.spellings:
                add(plain, bid, kind)
        self.book_re = self._build_regex()

    # -- regex ------------------------------------------------------------------
    def _pattern_for(self, key: str) -> str:
        out = []
        m = re.match(r"^([123]) (.+)$", key)
        if m:
            out.append(m.group(1))
            out.append(r"\.?" + SP + "*" if self.p.get("dot_after_number") else SP + "?")
            key = m.group(2)
        for ch in key:
            if ch == " ":
                out.append(SP + "+")
            elif ch == GERESH:
                out.append(GERESH_CLASS)
            elif ch == GERSHAYIM:
                out.append(GERSHAYIM_CLASS)
            else:
                out.append(re.escape(ch))
        return "".join(out)

    def _build_regex(self):
        keys = sorted(self.spellings, key=len, reverse=True)
        alt = "|".join(self._pattern_for(k) for k in keys) or "(?!)"
        pre = ""
        if self.p.get("prefix_letters"):
            pre = "(?:[" + self.p["prefix_letters"] + "]{1,2})?"
        return re.compile(r"(?<![\w])" + pre + r"(?P<name>" + alt + r")(?P<dot>\.)?(?![\w])")

    def resolve(self, text: str):
        return self.spellings.get(norm_spelling(text))

    def candidates_at(self, text: str, pos: int):
        """All spellings that match at `pos` (longest first) -- used to back off
        when the longest match isn't followed by a number."""
        out = []
        for key in sorted(self.spellings, key=len, reverse=True):
            m = re.compile(self._pattern_for(key) + r"(?:\.)?(?![\w])").match(text, pos)
            if m:
                out.append((m, self.spellings[key]))
        return out


def get_language(code: str, settings: dict, catalog: Catalog) -> Language:
    return Language(PROFILES.get(code, PROFILES["en"]), settings, catalog)
