"""Language profiles: book names, abbreviation sets and the reading rules for
each language.

Abbreviations are stored without a final period (a period is always
optional).  Numbered books are written with a leading "1 ", "2 " or "3 ";
the parser adds the variants itself (no space, roman numerals, ordinal words,
"1." in German).

Sources: SBL Handbook of Style (2nd ed.); Chicago Manual of Style
(traditional and shorter forms); Deutsche Bibelgesellschaft / Loccumer
Richtlinien; Bible de Jérusalem and Segond columns (Lacroux); Spanish
abbreviations per catholic-resources.org bilingual table and Reina-Valera
usage; Portuguese per bibliaon.com (Almeida).  Sets marked "unconfirmed"
are starter lists for the user to review in Settings.
"""
from __future__ import annotations


def T(block: str) -> dict:
    """'Gen Genesis|Gn' lines -> {'Gen': ['Genesis', 'Gn']}"""
    out = {}
    for line in block.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        bid, _, rest = line.partition(" ")
        out[bid] = [x.strip() for x in rest.split("|") if x.strip()]
    return out


def N(block: str) -> dict:
    """'Gen Genesis' lines -> {'Gen': 'Genesis'} (first item = display name)"""
    return {k: v[0] for k, v in T(block).items()}


# ===========================================================================
# ENGLISH
# ===========================================================================
EN_FULL = T("""
Gen Genesis
Exod Exodus
Lev Leviticus
Num Numbers
Deut Deuteronomy
Josh Joshua
Judg Judges
Ruth Ruth
1Sam 1 Samuel
2Sam 2 Samuel
1Kgs 1 Kings
2Kgs 2 Kings
1Chr 1 Chronicles
2Chr 2 Chronicles
Ezra Ezra
Neh Nehemiah
Esth Esther
Job Job
Ps Psalms|Psalm
Prov Proverbs
Eccl Ecclesiastes|Qoheleth
Song Song of Solomon|Song of Songs|Canticles
Isa Isaiah
Jer Jeremiah
Lam Lamentations
Ezek Ezekiel
Dan Daniel
Hos Hosea
Joel Joel
Amos Amos
Obad Obadiah
Jonah Jonah
Mic Micah
Nah Nahum
Hab Habakkuk
Zeph Zephaniah
Hag Haggai
Zech Zechariah
Mal Malachi
Tob Tobit
Jdt Judith
AddEsth Additions to Esther|Rest of Esther|Greek Esther
Wis Wisdom of Solomon|Wisdom
Sir Sirach|Ecclesiasticus|Ben Sira
Bar Baruch
EpJer Letter of Jeremiah|Epistle of Jeremiah
AddDan Additions to Daniel
PrAzar Prayer of Azariah|Song of the Three Jews|Song of the Three Young Men|Song of Three Children
Sus Susanna
Bel Bel and the Dragon
1Macc 1 Maccabees
2Macc 2 Maccabees
3Macc 3 Maccabees
4Macc 4 Maccabees
1Esd 1 Esdras
2Esd 2 Esdras|4 Ezra
PrMan Prayer of Manasseh|Prayer of Manasses
Ps151 Psalm 151
Matt Matthew
Mark Mark
Luke Luke
John John
Acts Acts|Acts of the Apostles
Rom Romans
1Cor 1 Corinthians
2Cor 2 Corinthians
Gal Galatians
Eph Ephesians
Phil Philippians
Col Colossians
1Thess 1 Thessalonians
2Thess 2 Thessalonians
1Tim 1 Timothy
2Tim 2 Timothy
Titus Titus
Phlm Philemon
Heb Hebrews
Jas James
1Pet 1 Peter
2Pet 2 Peter
1John 1 John
2John 2 John
3John 3 John
Jude Jude
Rev Revelation|Apocalypse
""")

EN_SBL = T("""
Gen Gen
Exod Exod
Lev Lev
Num Num
Deut Deut
Josh Josh
Judg Judg
1Sam 1 Sam
2Sam 2 Sam
1Kgs 1 Kgs
2Kgs 2 Kgs
1Chr 1 Chr
2Chr 2 Chr
Esth Esth
Ps Ps|Pss
Prov Prov
Eccl Eccl|Qoh
Song Song|Cant
Isa Isa
Jer Jer
Lam Lam
Ezek Ezek
Dan Dan
Hos Hos
Obad Obad
Mic Mic
Nah Nah
Hab Hab
Zeph Zeph
Hag Hag
Zech Zech
Mal Mal
Tob Tob
Jdt Jdt
AddEsth Add Esth
Wis Wis
Sir Sir
Bar Bar
EpJer Ep Jer|Let Jer
AddDan Add Dan
PrAzar Pr Azar|Sg Three
Sus Sus
Bel Bel
1Macc 1 Macc
2Macc 2 Macc
3Macc 3 Macc
4Macc 4 Macc
1Esd 1 Esd
2Esd 2 Esd
PrMan Pr Man
Ps151 Ps 151
Matt Matt
Rom Rom
1Cor 1 Cor
2Cor 2 Cor
Gal Gal
Eph Eph
Phil Phil
Col Col
1Thess 1 Thess
2Thess 2 Thess
1Tim 1 Tim
2Tim 2 Tim
Phlm Phlm
Heb Heb
Jas Jas
1Pet 1 Pet
2Pet 2 Pet
Rev Rev
""")

EN_CMOS_TRAD = T("""
Gen Gen
Exod Exod
Lev Lev
Num Num
Deut Deut
Josh Josh
Judg Judg
1Sam 1 Sam
2Sam 2 Sam
1Chr 1 Chron
2Chr 2 Chron
Neh Neh
Ps Ps|Pss
Prov Prov
Eccl Eccles
Song Song of Sol
Isa Isa
Jer Jer
Lam Lam
Ezek Ezek
Dan Dan
Obad Obad
Jonah Jon
Mic Mic
Nah Nah
Hab Hab
Zeph Zeph
Hag Hag
Zech Zech
Mal Mal
Tob Tob
Jdt Jth
AddEsth Rest of Esther
Wis Wisd of Sol
Sir Ecclus
Bar Bar
Sus Sus
Bel Bel and Dr
1Macc 1 Macc
2Macc 2 Macc
3Macc 3 Macc
4Macc 4 Macc
1Esd 1 Esd
2Esd 2 Esd
PrMan Pr of Man
Matt Matt
Rom Rom
1Cor 1 Cor
2Cor 2 Cor
Gal Gal
Eph Eph
Phil Phil
Col Col
1Thess 1 Thess
2Thess 2 Thess
1Tim 1 Tim
2Tim 2 Tim
Phlm Philem
Heb Heb
1Pet 1 Pet
2Pet 2 Pet
Rev Rev
""")

EN_CMOS_SHORT = T("""
Gen Gn
Exod Ex
Lev Lv
Num Nm
Deut Dt
Josh Jo
Judg Jgs
Ruth Ru
1Sam 1 Sm
2Sam 2 Sm
1Kgs 1 Kgs
2Kgs 2 Kgs
1Chr 1 Chr
2Chr 2 Chr
Ezra Ezr
Neh Neh
Esth Est
Job Jb
Ps Ps|Pss
Prov Prv
Eccl Eccl
Song Sg
Isa Is
Jer Jer
Lam Lam
Ezek Ez
Dan Dn
Hos Hos
Joel Jl
Amos Am
Obad Ob
Jonah Jon
Mic Mi
Nah Na
Hab Hb
Zeph Zep
Hag Hg
Zech Zec
Mal Mal
Tob Tb
Jdt Jdt
Wis Wis
Sir Sir
Bar Bar
Sus Sus
Bel Bel
1Macc 1 Mc
2Macc 2 Mc
3Macc 3 Mc
4Macc 4 Mc
1Esd 1 Esd
2Esd 2 Esd
PrMan Pr Man
Matt Mt
Mark Mk
Luke Lk
John Jn
Rom Rom
1Cor 1 Cor
2Cor 2 Cor
Gal Gal
Eph Eph
Phil Phil
Col Col
1Thess 1 Thes
2Thess 2 Thes
1Tim 1 Tm
2Tim 2 Tm
Titus Ti
Phlm Phlm
Heb Heb
Jas Jas
1Pet 1 Pt
2Pet 2 Pt
1John 1 Jn
2John 2 Jn
3John 3 Jn
Rev Rv
""")

EN_COMMON = T("""
Exod Exo
Ps Psa
Prov Pr
Eccl Ecc
Ezek Eze
Matt Mat
1Kgs 1 Ki
2Kgs 2 Ki
Titus Tit
1Pet 1 Pt
Rev Apoc
Wis Wisd
1Macc 1 Mac
2Macc 2 Mac
3Macc 3 Mac
4Macc 4 Mac
""")

# Spellings that are recognized but always flagged for checking (kept apart from the sets
# so they can't be switched off by accident)
EN_FLAGGED = {
    "1Kgs": [("3 Kings", "Vulgate numbering: 3 Kings = 1 Kings"),
             ("III Kings", "Vulgate numbering: 3 Kings = 1 Kings")],
    "2Kgs": [("4 Kings", "Vulgate numbering: 4 Kings = 2 Kings"),
             ("IV Kings", "Vulgate numbering: 4 Kings = 2 Kings")],
    "Wis": [("WS", "unusual abbreviation for Wisdom")],
    "1Chr": [("1 Paralip", "Vulgate name: 1 Paralipomenon = 1 Chronicles"),
             ("1 Paralipomenon", "Vulgate name: 1 Paralipomenon = 1 Chronicles")],
    "2Chr": [("2 Paralip", "Vulgate name: 2 Paralipomenon = 2 Chronicles"),
             ("2 Paralipomenon", "Vulgate name: 2 Paralipomenon = 2 Chronicles")],
    "EpJer": [("Letter J", "unusual abbreviation for the Letter of Jeremiah")],
}

# A writer named as the subject of a sentence ("Matthew uses δεῖ eight times (16:21)") sets the
# book for the references that follow.  A person who shares a book's name doing something else
# ("Zechariah responds with doubt (1:20)") does not.
EN_AUTHOR_VERBS = ("says said writes wrote records recorded notes noted uses used employs employed "
                   "quotes quoted cites cited mentions mentioned describes described tells told reports "
                   "reported argues argued explains explained declares declared prophesies prophesied "
                   "teaches taught insists insisted adds added states stated observes observed emphasizes "
                   "emphasized presents presented portrays portrayed narrates narrated recounts recounted "
                   "refers referred speaks spoke calls called repeats repeated echoes echoed alludes "
                   "alluded").split()
PERSON_BOOKS = ["Josh", "Ruth", "Ezra", "Neh", "Esth", "Job", "Isa", "Jer", "Ezek", "Dan", "Hos", "Joel",
                "Amos", "Obad", "Jonah", "Mic", "Nah", "Hab", "Zeph", "Hag", "Zech", "Mal", "Matt", "Mark",
                "Luke", "John", "Jas", "Jude", "Tob", "Jdt", "Sus"]
# Capitalized words that often stand right before a chapter:verse without being a book name
EN_NOT_BOOKS = ("See Cf Compare Contra In At And Also On Of For To From By With The A An As Verse Verses "
                "Chapter Chapters Ch Chap Chs P Pp Vol Vols No Nos Col Cols Fig Table Note Notes Line Lines "
                "Book Books Part Section Sec Art Item Page Pages Esp Especially Eg Ie Viz Ibid Idem Loc "
                "Op Cit Sura Surah Year Years Age Ages Version Edition Ed Eds").split()

ENGLISH = {
    "code": "en", "name": "English", "dir": "ltr", "numerals": "arabic", "label_sep": ":",
    "cv_seps": [":"], "verse_list_tight": [], "verse_list_spaced": [","],
    "suffixes": [("ff", 99), ("f", 1)], "verse_words": ["v.", "vv.", "verse", "verses", "Verse", "Verses", "ver."],
    "and_words": ["and", "&"], "cf_words": ["cf.", "see", "see also", "contra"],
    "flagged": EN_FLAGGED, "author_verbs": EN_AUTHOR_VERBS, "person_books": PERSON_BOOKS,
    "not_books": EN_NOT_BOOKS, "mt_words": ["in the MT", "(MT)", "[MT]", "MT", "(Heb.)", "(Heb)", "(Hebrew)"],
    "intro": ["book of", "Book of", "Gospel of", "gospel of", "letter to", "Letter to",
              "epistle to", "Epistle to"],
    "ordinals": {"1": ["First"], "2": ["Second"], "3": ["Third"]},
    "ordinal_de": False, "dot_after_number": False, "roman": True, "prefix_letters": "",
    "bare_requires_parens": False, "default_ot_order": "christian",
    "index_title": "Scripture Index",
    "section_titles": {"OT": "Old Testament", "AP": "Apocrypha", "NT": "New Testament",
                       "OTHER": "Other Ancient Sources"},
    "names": {k: v[0] for k, v in EN_FULL.items()},
    "full": EN_FULL,
    "sets": {"SBL": EN_SBL, "CMOS traditional": EN_CMOS_TRAD, "CMOS shorter": EN_CMOS_SHORT,
             "Other common": EN_COMMON},
    "unconfirmed_sets": [],
    "risky_abbr": ["Is", "Am", "Ex", "Jo", "Mi", "Na", "Ob", "Ti", "Ac", "Ap", "Re", "Ru", "So", "Sg"],
    "bare_ok": ["Gen", "Exod", "Lev", "Deut", "Josh", "Ps", "Prov", "Eccl", "Song", "Isa", "Jer",
                "Lam", "Ezek", "Hos", "Obad", "Zeph", "Hag", "Zech", "Hab", "Rom", "Gal", "Eph",
                "Phil", "Col", "Heb", "1Sam", "2Sam", "1Kgs", "2Kgs", "1Chr", "2Chr", "1Cor",
                "2Cor", "1Thess", "2Thess", "1Tim", "2Tim", "1Pet", "2Pet", "1John", "2John",
                "3John", "Neh", "Sir", "1Macc", "2Macc"],
}

# ===========================================================================
# SPANISH
# ===========================================================================
ES_FULL = T("""
Gen Génesis
Exod Éxodo
Lev Levítico
Num Números
Deut Deuteronomio
Josh Josué
Judg Jueces
Ruth Rut
1Sam 1 Samuel
2Sam 2 Samuel
1Kgs 1 Reyes
2Kgs 2 Reyes
1Chr 1 Crónicas
2Chr 2 Crónicas
Ezra Esdras
Neh Nehemías
Esth Ester
Job Job
Ps Salmos|Salmo
Prov Proverbios
Eccl Eclesiastés
Song Cantares|Cantar de los Cantares
Isa Isaías
Jer Jeremías
Lam Lamentaciones
Ezek Ezequiel
Dan Daniel
Hos Oseas
Joel Joel
Amos Amós
Obad Abdías
Jonah Jonás
Mic Miqueas
Nah Nahúm|Nahum
Hab Habacuc
Zeph Sofonías
Hag Hageo|Ageo
Zech Zacarías
Mal Malaquías
Tob Tobías
Jdt Judit
Wis Sabiduría
Sir Eclesiástico|Sirácida|Sirácides
Bar Baruc
1Macc 1 Macabeos
2Macc 2 Macabeos
Matt Mateo
Mark Marcos
Luke Lucas
John Juan
Acts Hechos|Hechos de los Apóstoles
Rom Romanos
1Cor 1 Corintios
2Cor 2 Corintios
Gal Gálatas
Eph Efesios
Phil Filipenses
Col Colosenses
1Thess 1 Tesalonicenses
2Thess 2 Tesalonicenses
1Tim 1 Timoteo
2Tim 2 Timoteo
Titus Tito
Phlm Filemón
Heb Hebreos
Jas Santiago
1Pet 1 Pedro
2Pet 2 Pedro
1John 1 Juan
2John 2 Juan
3John 3 Juan
Jude Judas
Rev Apocalipsis
""")
ES_COMMON = T("""
Gen Gn|Gén
Exod Éx|Ex|Éxod
Lev Lv|Lev
Num Nm|Núm
Deut Dt|Deut
Josh Jos
Judg Jue|Jc
Ruth Rt
1Sam 1 S|1 Sam|1 Sm
2Sam 2 S|2 Sam|2 Sm
1Kgs 1 R|1 Re|1 Rey
2Kgs 2 R|2 Re|2 Rey
1Chr 1 Cr|1 Cró|1 Cro
2Chr 2 Cr|2 Cró|2 Cro
Ezra Esd
Neh Neh|Ne
Esth Est
Ps Sal
Prov Pr|Prov|Pro
Eccl Ec|Ecl
Song Cnt|Cant
Isa Is
Jer Jer|Jr
Lam Lm|Lam
Ezek Ez|Ezeq
Dan Dn|Dan
Hos Os
Joel Jl
Amos Am
Obad Abd
Jonah Jon
Mic Miq|Mi
Nah Nah|Na
Hab Hab
Zeph Sof
Hag Hag|Ag
Zech Zac|Za
Mal Mal
Tob Tob|Tb
Jdt Jdt
Wis Sab
Sir Sir|Si|Eclo
Bar Bar|Ba
1Macc 1 Mac
2Macc 2 Mac
Matt Mt|Mat
Mark Mr|Mc|Mar
Luke Lc|Luc
John Jn
Acts Hch|Hech
Rom Ro|Rom
1Cor 1 Co|1 Cor
2Cor 2 Co|2 Cor
Gal Gá|Gál
Eph Ef|Efes
Phil Fil|Flp
Col Col
1Thess 1 Ts|1 Tes
2Thess 2 Ts|2 Tes
1Tim 1 Ti|1 Tim
2Tim 2 Ti|2 Tim
Titus Tit
Phlm Flm|Filem
Heb He|Heb
Jas Stg|Sant|St
1Pet 1 P|1 Pe
2Pet 2 P|2 Pe
1John 1 Jn
2John 2 Jn
3John 3 Jn
Jude Jud|Jds
Rev Ap|Apoc
""")
SPANISH = {
    "code": "es", "name": "Español (Spanish)", "dir": "ltr", "numerals": "arabic", "label_sep": ":",
    "cv_seps": [":"], "verse_list_tight": [], "verse_list_spaced": [","],
    "suffixes": [], "verse_words": ["v.", "vv.", "vers.", "versículo", "versículos", "Versículo",
                                    "Versículos"],
    "and_words": ["y", "e"], "cf_words": ["cf.", "véase", "vea", "ver"],
    "intro": ["libro de", "Libro de", "Evangelio de", "evangelio de", "carta a", "Carta a",
              "epístola a", "Epístola a"],
    "ordinals": {"1": ["Primera", "Primero", "Primer"], "2": ["Segunda", "Segundo"],
                 "3": ["Tercera", "Tercero"]},
    "ordinal_de": True, "dot_after_number": False, "roman": True, "prefix_letters": "",
    "bare_requires_parens": False, "default_ot_order": "christian",
    "index_title": "Índice de citas bíblicas",
    "section_titles": {"OT": "Antiguo Testamento", "AP": "Libros deuterocanónicos",
                       "NT": "Nuevo Testamento", "OTHER": "Otras fuentes antiguas"},
    "names": {k: v[0] for k, v in ES_FULL.items()},
    "full": ES_FULL,
    "sets": {"Común (RVR)": ES_COMMON},
    "unconfirmed_sets": [],
    "risky_abbr": ["Is", "Os", "Ex", "Es", "Re", "He", "Ap", "Mi", "Na", "Ti", "Ba", "Si", "Ag", "Am", "Ef", "Ro", "St", "Za", "Ne", "Lc", "Mr", "Mc"],
    "person_books": PERSON_BOOKS, "mt_words": ["en el TM", "(TM)", "[TM]", "TM", "(heb.)", "(hebreo)"], "not_books": "Véase Vea Ver Cf En Y De Del La El Los Las Cap Caps Vol Vols Pág Págs Nota Notas Libro Versículo Versículos".split(),
    "bare_ok": ["Gen", "Exod", "Lev", "Deut", "Ps", "Prov", "Eccl", "Lam", "Rom", "Gal", "Eph",
                "Phil", "Col", "Heb", "Isa", "Jer", "Ezek", "1Cor", "2Cor", "1Thess", "2Thess",
                "1Tim", "2Tim", "1Pet", "2Pet", "1Sam", "2Sam", "1Kgs", "2Kgs", "1Chr", "2Chr"],
}

# ===========================================================================
# PORTUGUESE
# ===========================================================================
PT_FULL = T("""
Gen Gênesis|Génesis
Exod Êxodo
Lev Levítico
Num Números
Deut Deuteronômio|Deuteronómio
Josh Josué
Judg Juízes
Ruth Rute
1Sam 1 Samuel
2Sam 2 Samuel
1Kgs 1 Reis
2Kgs 2 Reis
1Chr 1 Crônicas|1 Crónicas
2Chr 2 Crônicas|2 Crónicas
Ezra Esdras
Neh Neemias
Esth Ester
Job Jó
Ps Salmos|Salmo
Prov Provérbios
Eccl Eclesiastes
Song Cântico dos Cânticos|Cânticos|Cantares
Isa Isaías
Jer Jeremias
Lam Lamentações
Ezek Ezequiel
Dan Daniel
Hos Oseias|Oséias
Joel Joel
Amos Amós
Obad Obadias
Jonah Jonas
Mic Miqueias|Miquéias
Nah Naum
Hab Habacuque
Zeph Sofonias
Hag Ageu
Zech Zacarias
Mal Malaquias
Tob Tobias
Jdt Judite
Wis Sabedoria
Sir Eclesiástico
Bar Baruc|Baruque
1Macc 1 Macabeus
2Macc 2 Macabeus
Matt Mateus
Mark Marcos
Luke Lucas
John João
Acts Atos
Rom Romanos
1Cor 1 Coríntios
2Cor 2 Coríntios
Gal Gálatas
Eph Efésios
Phil Filipenses
Col Colossenses
1Thess 1 Tessalonicenses
2Thess 2 Tessalonicenses
1Tim 1 Timóteo
2Tim 2 Timóteo
Titus Tito
Phlm Filemom|Filémon
Heb Hebreus
Jas Tiago
1Pet 1 Pedro
2Pet 2 Pedro
1John 1 João
2John 2 João
3John 3 João
Jude Judas
Rev Apocalipse
""")
PT_ALMEIDA = T("""
Gen Gn
Exod Êx|Ex
Lev Lv
Num Nm
Deut Dt
Josh Js
Judg Jz
Ruth Rt
1Sam 1 Sm
2Sam 2 Sm
1Kgs 1 Rs
2Kgs 2 Rs
1Chr 1 Cr
2Chr 2 Cr
Ezra Ed
Neh Ne
Esth Et
Job Jó
Ps Sl
Prov Pv
Eccl Ec
Song Ct
Isa Is
Jer Jr
Lam Lm
Ezek Ez
Dan Dn
Hos Os
Joel Jl
Amos Am
Obad Ob
Jonah Jn
Mic Mq
Nah Na
Hab Hc
Zeph Sf
Hag Ag
Zech Zc
Mal Ml
Matt Mt
Mark Mc
Luke Lc
John Jo
Acts At
Rom Rm
1Cor 1 Co
2Cor 2 Co
Gal Gl
Eph Ef
Phil Fp
Col Cl
1Thess 1 Ts
2Thess 2 Ts
1Tim 1 Tm
2Tim 2 Tm
Titus Tt
Phlm Fm
Heb Hb
Jas Tg
1Pet 1 Pe
2Pet 2 Pe
1John 1 Jo
2John 2 Jo
3John 3 Jo
Jude Jd
Rev Ap
""")
PORTUGUESE = {
    "code": "pt", "name": "Português (Portuguese)", "dir": "ltr", "numerals": "arabic",
    "label_sep": ":", "cv_seps": [":"], "verse_list_tight": [], "verse_list_spaced": [","],
    "suffixes": [], "verse_words": ["v.", "vv.", "vers.", "versículo", "versículos", "Versículo",
                                    "Versículos"],
    "and_words": ["e"], "cf_words": ["cf.", "ver", "veja"],
    "intro": ["livro de", "Livro de", "Evangelho de", "evangelho de", "carta aos", "Carta aos"],
    "ordinals": {"1": ["Primeira", "Primeiro"], "2": ["Segunda", "Segundo"],
                 "3": ["Terceira", "Terceiro"]},
    "ordinal_de": True, "dot_after_number": False, "roman": True, "prefix_letters": "",
    "bare_requires_parens": False, "default_ot_order": "christian",
    "index_title": "Índice de referências bíblicas",
    "section_titles": {"OT": "Antigo Testamento", "AP": "Livros deuterocanônicos",
                       "NT": "Novo Testamento", "OTHER": "Outras fontes antigas"},
    "names": {k: v[0] for k, v in PT_FULL.items()},
    "full": PT_FULL,
    "sets": {"Almeida": PT_ALMEIDA},
    "unconfirmed_sets": [],
    "risky_abbr": ["Is", "Os", "Ex", "Ed", "Et", "Na", "Ne", "Ob", "Am", "Ag", "Ap", "Ct", "Sl", "Ml", "At", "Cl", "Gl", "Fm", "Tg", "Tt"],
    "person_books": PERSON_BOOKS, "mt_words": ["no TM", "(TM)", "[TM]", "TM", "(heb.)", "(hebraico)"], "not_books": "Ver Veja Cf Em E De Do Da Os As Cap Caps Vol Vols Pág Págs Nota Notas Livro Versículo Versículos".split(),
    "bare_ok": ["Gen", "Exod", "Lev", "Deut", "Ps", "Prov", "Eccl", "Lam", "Rom", "Gal", "Eph",
                "Phil", "Col", "Heb", "Isa", "Ezek", "1Cor", "2Cor", "1Thess", "2Thess",
                "1Tim", "2Tim", "1Pet", "2Pet", "1Sam", "2Sam", "1Kgs", "2Kgs", "1Chr", "2Chr"],
}

# ===========================================================================
# FRENCH
# ===========================================================================
FR_FULL = T("""
Gen Genèse
Exod Exode
Lev Lévitique
Num Nombres
Deut Deutéronome
Josh Josué
Judg Juges
Ruth Ruth
1Sam 1 Samuel
2Sam 2 Samuel
1Kgs 1 Rois
2Kgs 2 Rois
1Chr 1 Chroniques
2Chr 2 Chroniques
Ezra Esdras
Neh Néhémie
Esth Esther
Job Job
Ps Psaumes|Psaume
Prov Proverbes
Eccl Ecclésiaste|Qohéleth|Qohélet
Song Cantique des cantiques|Cantique des Cantiques|Cantique
Isa Ésaïe|Isaïe|Esaïe
Jer Jérémie
Lam Lamentations
Ezek Ézéchiel|Ezéchiel
Dan Daniel
Hos Osée
Joel Joël
Amos Amos
Obad Abdias
Jonah Jonas
Mic Michée
Nah Nahum
Hab Habacuc
Zeph Sophonie
Hag Aggée
Zech Zacharie
Mal Malachie
Tob Tobie|Tobit
Jdt Judith
Wis Sagesse
Sir Siracide|Ecclésiastique
Bar Baruch
1Macc 1 Maccabées
2Macc 2 Maccabées
Matt Matthieu
Mark Marc
Luke Luc
John Jean
Acts Actes|Actes des Apôtres
Rom Romains
1Cor 1 Corinthiens
2Cor 2 Corinthiens
Gal Galates
Eph Éphésiens|Ephésiens
Phil Philippiens
Col Colossiens
1Thess 1 Thessaloniciens
2Thess 2 Thessaloniciens
1Tim 1 Timothée
2Tim 2 Timothée
Titus Tite
Phlm Philémon
Heb Hébreux
Jas Jacques
1Pet 1 Pierre
2Pet 2 Pierre
1John 1 Jean
2John 2 Jean
3John 3 Jean
Jude Jude
Rev Apocalypse
""")
FR_BJ = T("""
Gen Gn
Exod Ex
Lev Lv
Num Nb
Deut Dt
Josh Jos
Judg Jg
Ruth Rt
1Sam 1 S
2Sam 2 S
1Kgs 1 R
2Kgs 2 R
1Chr 1 Ch
2Chr 2 Ch
Ezra Esd
Neh Ne
Esth Est
Job Jb
Ps Ps
Prov Pr
Eccl Qo
Song Ct
Isa Is
Jer Jr
Lam Lm
Ezek Ez
Dan Dn
Hos Os
Joel Jl
Amos Am
Obad Ab
Jonah Jon
Mic Mi
Nah Na
Hab Ha
Zeph So
Hag Ag
Zech Za
Mal Ml
Tob Tb
Jdt Jdt
Wis Sg
Sir Si
Bar Ba
1Macc 1 M
2Macc 2 M
Matt Mt
Mark Mc
Luke Lc
John Jn
Acts Ac
Rom Rm
1Cor 1 Co
2Cor 2 Co
Gal Ga
Eph Ep
Phil Ph
Col Col
1Thess 1 Th
2Thess 2 Th
1Tim 1 Tm
2Tim 2 Tm
Titus Tt
Phlm Phm
Heb He
Jas Jc
1Pet 1 P
2Pet 2 P
1John 1 Jn
2John 2 Jn
3John 3 Jn
Jude Jude
Rev Ap
""")
FR_SEGOND = T("""
Gen Ge
Exod Ex
Lev Lé
Num No
Deut De
Josh Jos
Judg Jg
Ruth Ru
1Sam 1 S
2Sam 2 S
1Kgs 1 R
2Kgs 2 R
1Chr 1 Ch
2Chr 2 Ch
Ezra Esd
Neh Né
Esth Est
Job Job
Ps Ps
Prov Pr
Eccl Ec
Song Ca
Isa Es
Jer Jé
Lam La
Ezek Ez
Dan Da
Hos Os
Joel Joë
Amos Am
Obad Ab
Jonah Jon
Mic Mi
Nah Na
Hab Ha
Zeph So
Hag Ag
Zech Za
Mal Mal
Tob Tob
Wis Sag
Sir Sir
Bar Bar
1Macc 1 Mac
2Macc 2 Mac
Matt Mt
Mark Mc
Luke Lu
John Jn
Acts Ac
Rom Ro
1Cor 1 Co
2Cor 2 Co
Gal Ga
Eph Ep
Phil Ph
Col Col
1Thess 1 Th
2Thess 2 Th
1Tim 1 Ti
2Tim 2 Ti
Titus Tit
Phlm Phm
Heb Hé
Jas Ja
1Pet 1 Pi
2Pet 2 Pi
1John 1 Jn
2John 2 Jn
3John 3 Jn
Jude Jud
Rev Ap
""")
FRENCH = {
    "code": "fr", "name": "Français (French)", "dir": "ltr", "numerals": "arabic",
    "label_sep": ",", "cv_seps": [",", ":"], "verse_list_tight": ["."], "verse_list_spaced": [],
    "suffixes": [("s", 1), ("ss", 99)],
    "verse_words": ["v.", "vv.", "verset", "versets", "Verset", "Versets"],
    "and_words": ["et"], "cf_words": ["cf.", "voir"],
    "intro": ["livre de", "Livre de", "livre d'", "Évangile selon", "évangile selon",
              "épître aux", "Épître aux"],
    "ordinals": {"1": ["Premier", "Première"], "2": ["Deuxième", "Second", "Seconde"],
                 "3": ["Troisième"]},
    "ordinal_de": False, "dot_after_number": False, "roman": True, "prefix_letters": "",
    "bare_requires_parens": True, "default_ot_order": "christian",
    "index_title": "Index des références bibliques",
    "section_titles": {"OT": "Ancien Testament", "AP": "Livres deutérocanoniques",
                       "NT": "Nouveau Testament", "OTHER": "Autres sources anciennes"},
    "names": {k: v[0] for k, v in FR_FULL.items()},
    "full": FR_FULL,
    "sets": {"Bible de Jérusalem / TOB": FR_BJ, "Segond": FR_SEGOND},
    "unconfirmed_sets": [],
    "risky_abbr": ["Es", "Os", "Ex", "Am", "Ac", "Ap", "Ga", "Ha", "Mi", "Na", "So", "Ba", "Si", "He", "Lu", "La", "Ca", "Da", "De", "Ge", "No", "Ru", "Ro", "Ja", "Tt", "Ph", "Ep", "Ag", "Za", "Ab", "Sg", "Ne", "Ml", "Mc", "Lc", "Ct", "Jg", "Dt"],
    "person_books": PERSON_BOOKS, "mt_words": ["(TM)", "[TM]", "TM", "(hébr.)", "(hébreu)"], "not_books": "Voir Cf En Et De Du La Le Les Chap Vol Vols Note Notes Livre Verset Versets".split(),
    "bare_ok": ["Gen", "Exod", "Lev", "Deut", "Ps", "Prov", "Eccl", "Lam", "Rom", "Gal", "Eph",
                "Phil", "Col", "Heb", "Isa", "Ezek", "Jer"],
}

# ===========================================================================
# GERMAN
# ===========================================================================
DE_FULL = T("""
Gen Genesis|1 Mose
Exod Exodus|2 Mose
Lev Levitikus|3 Mose
Num Numeri|4 Mose
Deut Deuteronomium|5 Mose
Josh Josua
Judg Richter
Ruth Rut|Ruth
1Sam 1 Samuel
2Sam 2 Samuel
1Kgs 1 Könige
2Kgs 2 Könige
1Chr 1 Chronik
2Chr 2 Chronik
Ezra Esra
Neh Nehemia
Esth Ester|Esther
Job Ijob|Hiob
Ps Psalmen|Psalm
Prov Sprichwörter|Sprüche
Eccl Kohelet|Prediger
Song Hoheslied|Hohelied
Isa Jesaja
Jer Jeremia
Lam Klagelieder
Ezek Ezechiel|Hesekiel
Dan Daniel
Hos Hosea
Joel Joel|Joël
Amos Amos
Obad Obadja
Jonah Jona
Mic Micha
Nah Nahum
Hab Habakuk
Zeph Zefanja
Hag Haggai
Zech Sacharja
Mal Maleachi
Tob Tobit|Tobias
Jdt Judit
AddEsth Ester (griechisch)|Stücke zu Ester
Wis Weisheit|Weisheit Salomos
Sir Jesus Sirach|Sirach
Bar Baruch
EpJer Brief des Jeremia
AddDan Zusätze zu Daniel|Stücke zu Daniel
1Macc 1 Makkabäer
2Macc 2 Makkabäer
3Macc 3 Makkabäer
4Macc 4 Makkabäer
1Esd 3 Esra
2Esd 4 Esra
PrMan Gebet des Manasse
Matt Matthäus
Mark Markus
Luke Lukas
John Johannes
Acts Apostelgeschichte
Rom Römer
1Cor 1 Korinther
2Cor 2 Korinther
Gal Galater
Eph Epheser
Phil Philipper
Col Kolosser
1Thess 1 Thessalonicher
2Thess 2 Thessalonicher
1Tim 1 Timotheus
2Tim 2 Timotheus
Titus Titus
Phlm Philemon
Heb Hebräer
Jas Jakobus
1Pet 1 Petrus
2Pet 2 Petrus
1John 1 Johannes
2John 2 Johannes
3John 3 Johannes
Jude Judas
Rev Offenbarung
""")
DE_LOCCUM = T("""
Gen Gen
Exod Ex
Lev Lev
Num Num
Deut Dtn
Josh Jos
Judg Ri
Ruth Rut
1Sam 1 Sam
2Sam 2 Sam
1Kgs 1 Kön
2Kgs 2 Kön
1Chr 1 Chr
2Chr 2 Chr
Ezra Esra
Neh Neh
Esth Est
Job Ijob
Ps Ps
Prov Spr
Eccl Koh
Song Hld
Isa Jes
Jer Jer
Lam Klgl
Ezek Ez
Dan Dan
Hos Hos
Joel Joël|Joel
Amos Am
Obad Obd
Jonah Jona
Mic Mi
Nah Nah
Hab Hab
Zeph Zef
Hag Hag
Zech Sach
Mal Mal
Tob Tob
Jdt Jdt
AddEsth EstG|EstZ
Wis Weish
Sir Sir
Bar Bar
EpJer BrJer
AddDan DanZ
1Macc 1 Makk
2Macc 2 Makk
Matt Mt
Mark Mk
Luke Lk
John Joh
Acts Apg
Rom Röm
1Cor 1 Kor
2Cor 2 Kor
Gal Gal
Eph Eph
Phil Phil
Col Kol
1Thess 1 Thess
2Thess 2 Thess
1Tim 1 Tim
2Tim 2 Tim
Titus Tit
Phlm Phlm
Heb Hebr
Jas Jak
1Pet 1 Petr
2Pet 2 Petr
1John 1 Joh
2John 2 Joh
3John 3 Joh
Jude Jud
Rev Offb
""")
DE_LUTHER = T("""
Gen 1 Mo|1 Mos
Exod 2 Mo|2 Mos
Lev 3 Mo|3 Mos
Num 4 Mo|4 Mos
Deut 5 Mo|5 Mos
Job Hi|Hiob
Eccl Pred
Ezek Hes
Rev Apk
""")
GERMAN = {
    "code": "de", "name": "Deutsch (German)", "dir": "ltr", "numerals": "arabic",
    "label_sep": ",", "cv_seps": [",", ":"], "verse_list_tight": ["."], "verse_list_spaced": [],
    "suffixes": [("f", 1), ("ff", 99)],
    "verse_words": ["V.", "Vers", "Verse", "Versen"],
    "and_words": ["und"], "cf_words": ["vgl.", "s.", "siehe"],
    "intro": ["Buch", "Evangelium nach", "Brief an die", "Brief des"],
    "ordinals": {"1": ["Erster", "Erste"], "2": ["Zweiter", "Zweite"], "3": ["Dritter", "Dritte"]},
    "ordinal_de": False, "dot_after_number": True, "roman": True, "prefix_letters": "",
    "bare_requires_parens": True, "default_ot_order": "christian",
    "index_title": "Bibelstellenregister",
    "section_titles": {"OT": "Altes Testament", "AP": "Apokryphen / Spätschriften",
                       "NT": "Neues Testament", "OTHER": "Weitere antike Quellen"},
    "names": {k: v[0] for k, v in DE_FULL.items()},
    "full": DE_FULL,
    "sets": {"Loccumer Richtlinien": DE_LOCCUM, "Luther / traditionell": DE_LUTHER},
    "unconfirmed_sets": [],
    "risky_abbr": ["Am", "Ex", "Mi", "Ri", "Hi", "Mo"],
    "person_books": PERSON_BOOKS, "mt_words": ["(MT)", "[MT]", "MT", "(hebr.)", "(Hebr.)"], "not_books": "Vgl Siehe In Und Der Die Das Kap Bd Bde Anm Buch Vers Verse".split(),
    "bare_ok": ["Gen", "Exod", "Lev", "Deut", "Ps", "Prov", "Eccl", "Song", "Lam", "Rom", "Gal",
                "Eph", "Phil", "Col", "Heb", "Isa", "Jer", "Ezek", "Rev"],
}

# ===========================================================================
# HEBREW  (Tanakh order by default; numerals as Hebrew letters)
# ===========================================================================
HE_FULL = T("""
Gen בראשית
Exod שמות
Lev ויקרא
Num במדבר
Deut דברים
Josh יהושע
Judg שופטים
Ruth רות
1Sam שמואל א|שמואל א׳
2Sam שמואל ב|שמואל ב׳
1Kgs מלכים א|מלכים א׳
2Kgs מלכים ב|מלכים ב׳
1Chr דברי הימים א|דברי הימים א׳
2Chr דברי הימים ב|דברי הימים ב׳
Ezra עזרא
Neh נחמיה
Esth אסתר
Job איוב
Ps תהלים|תהילים
Prov משלי
Eccl קהלת
Song שיר השירים
Isa ישעיהו|ישעיה
Jer ירמיהו|ירמיה
Lam איכה
Ezek יחזקאל
Dan דניאל
Hos הושע
Joel יואל
Amos עמוס
Obad עובדיה
Jonah יונה
Mic מיכה
Nah נחום
Hab חבקוק
Zeph צפניה
Hag חגי
Zech זכריה
Mal מלאכי
Tob טוביה|טוביט
Jdt יהודית
Wis חכמת שלמה
Sir בן סירא
Bar ברוך
1Macc מקבים א|חשמונאים א
2Macc מקבים ב|חשמונאים ב
Matt מתי
Mark מרקוס
Luke לוקס
John יוחנן
Acts מעשי השליחים
Rom הרומים|רומים
1Cor קורינתים א|הראשונה אל הקורינתים
2Cor קורינתים ב|השנייה אל הקורינתים
Gal גלטים|הגלטים
Eph אפסים|האפסים
Phil פיליפים|הפיליפים
Col קולוסים|הקולוסים
1Thess תסלוניקים א
2Thess תסלוניקים ב
1Tim טימותיאוס א
2Tim טימותיאוס ב
Titus טיטוס
Phlm פילימון
Heb עברים|העברים
Jas יעקב
1Pet פטרוס א
2Pet פטרוס ב
1John יוחנן א
2John יוחנן ב
3John יוחנן ג
Jude יהודה
Rev ההתגלות|התגלות|חזון יוחנן
""")
HE_COMMON = T("""
Gen בר׳
Exod שמ׳
Lev ויק׳
Num במ׳|במד׳
Deut דב׳|דבר׳
Josh יהו׳|יהוש׳
Judg שופ׳
1Sam שמ״א
2Sam שמ״ב
1Kgs מל״א
2Kgs מל״ב
1Chr דה״א
2Chr דה״ב
Ezra עז׳
Neh נחמ׳
Esth אס׳
Ps תה׳|תהל׳
Prov מש׳
Eccl קה׳|קהל׳
Song שה״ש
Isa יש׳|ישע׳
Jer יר׳|ירמ׳
Lam איכ׳
Ezek יח׳|יחז׳
Dan דנ׳
Hos הו׳
Joel יוא׳
Amos עמ׳
Obad עוב׳
Jonah יונ׳
Mic מי׳
Nah נח׳
Hab חב׳
Zeph צפ׳
Hag חג׳
Zech זכ׳
Mal מל׳
""")
HEBREW = {
    "code": "he", "name": "עברית (Hebrew)", "dir": "rtl", "numerals": "hebrew",
    "label_sep": ", ", "cv_seps": [":", ","], "verse_list_tight": [], "verse_list_spaced": [],
    "suffixes": [], "verse_words": ["פסוק", "פסוקים", "פס׳"],
    "and_words": [], "cf_words": ["ראו", "ראה", "השוו", "והשוו", "עיינו", "עיין"],
    "intro": ["ספר", "בספר"],
    "ordinals": {}, "ordinal_de": False, "dot_after_number": False, "roman": False,
    "prefix_letters": "ובלמשהכ", "bare_requires_parens": True, "default_ot_order": "tanakh_jps",
    "index_title": "מפתח מקורות",
    "section_titles": {"OT": "תנ״ך", "AP": "הספרים החיצוניים", "NT": "הברית החדשה",
                       "OTHER": "מקורות קדומים אחרים"},
    "names": {k: v[0] for k, v in HE_FULL.items()},
    "full": HE_FULL,
    "sets": {"קיצורים נפוצים (common)": HE_COMMON},
    "unconfirmed_sets": ["קיצורים נפוצים (common)"],
    "unconfirmed_names": ["NT", "AP"],
    "risky_abbr": [],
    "person_books": [], "mt_words": [], "not_books": [],
    "bare_ok": ["Gen", "Exod", "Lev", "Num", "Deut", "Ps", "Prov", "Eccl", "Lam", "Isa", "Jer",
                "Ezek", "1Sam", "2Sam", "1Kgs", "2Kgs", "1Chr", "2Chr", "Song"],
}

PROFILES = {p["code"]: p for p in (ENGLISH, SPANISH, PORTUGUESE, FRENCH, GERMAN, HEBREW)}
LANGUAGE_ORDER = ["en", "es", "pt", "fr", "de", "he"]
