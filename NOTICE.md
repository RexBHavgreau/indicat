# Indicat — copyright and additional terms

Indicat (Scripture Index Builder)
Copyright © 2026 Beaux Hargrove

Indicat is free software: you can redistribute it and/or modify it under the
terms of the GNU General Public License as published by the Free Software
Foundation, version 3 of the License (see `LICENSE`).

Indicat is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
A PARTICULAR PURPOSE. See the GNU General Public License for more details.

## Additional terms (GPL-3.0, section 7)

Under section 7(b) of the GNU General Public License, version 3, the
following terms apply to this program and to any work based on it:

1. **Author attribution.** Every copy and every modified version must keep
   the credit **"Indicat, created by Beaux Hargrove"**:
   * in the program's About box (or, for a version without one, in whatever
     place it displays its Appropriate Legal Notices), and
   * in the documentation distributed with it, and
   * in the header of every InDesign script the program generates.

2. **Name and icon (section 7(e)).** The name "Indicat" and the manicule
   icon are not licensed for use as the name or icon of a modified version.
   A modified version that is distributed must use a different name and icon,
   and may say that it is "based on Indicat, created by Beaux Hargrove".

These terms may not be removed from copies of this program, but may be
removed from parts of it that you use in a separate work that is not based
on Indicat.

## Third-party material

* The manicule (☞) in the app icon is drawn from Noto Serif CJK
  (© Adobe), used under the SIL Open Font License 1.1.
* The app uses lxml (BSD), python-docx (MIT), pdfplumber and pdfminer.six
  (MIT), pypdf (BSD), pypdfium2 (Apache 2.0 / BSD) and pywin32 (PSF), and is
  packaged with PyInstaller (GPL with a bootloader exception).

## Data files (`indicat/data`)

These are built by `tools/build_data.py` from the sources below, and keep
their own licenses:

* `lexicon.json`, Hebrew part: word forms and lemmas of the **Open Scriptures
  Hebrew Bible** (morphhb, CC BY 4.0, openscriptures.org) and headwords of the
  **Open Scriptures Hebrew Lexicon** (HebrewStrong.xml, CC BY 4.0), over the
  Westminster Leningrad Codex text (public domain).
* `lexicon.json`, Greek part: lemmas of **MorphGNT** (James Tauber et al.,
  morphgnt.org), licensed **CC BY-SA 3.0**; this part of the file is shared
  under the same license. The word forms are those of **The Greek New Testament:
  SBL Edition** (SBLGNT), copyright © 2010 Society of Biblical Literature and
  Logos Bible Software, used under its license.
* `verses.json`: the highest verse of each chapter, counted from the King James
  Version with Apocrypha (public domain), the Westminster Leningrad Codex
  (public domain) and the SBLGNT.
