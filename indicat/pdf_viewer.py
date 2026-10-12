"""Open a PDF at a given page in the reader the user prefers.

Page jumps are supported by Adobe Acrobat / Reader (/A "page=N"), SumatraPDF
(-page N), Foxit (/A page=N) and the browsers (file URL with #page=N).  If none
is found, the PDF is opened normally and the page number is reported so the
user can go to it.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

VIEWERS = {
    "auto": "Find one automatically",
    "acrobat": "Adobe Acrobat or Acrobat Reader",
    "sumatra": "SumatraPDF",
    "foxit": "Foxit PDF Reader",
    "edge": "Microsoft Edge",
    "chrome": "Google Chrome",
    "firefox": "Mozilla Firefox",
    "default": "The default PDF app (can't jump to a page)",
    "custom": "Another program…",
}
AUTO_ORDER = ["acrobat", "sumatra", "foxit", "edge", "chrome", "firefox"]
EXE_NAMES = {
    "acrobat": ["Acrobat.exe", "AcroRd32.exe"],
    "sumatra": ["SumatraPDF.exe"],
    "foxit": ["FoxitPDFReader.exe", "FoxitReader.exe", "FoxitPDFEditor.exe", "FoxitPhantomPDF.exe"],
    "edge": ["msedge.exe"],
    "chrome": ["chrome.exe"],
    "firefox": ["firefox.exe"],
}
COMMON_DIRS = {
    "acrobat": [r"Adobe\Acrobat DC\Acrobat", r"Adobe\Acrobat Reader DC\Reader", r"Adobe\Acrobat\Acrobat",
                r"Adobe\Acrobat Reader\Reader"],
    "sumatra": [r"SumatraPDF"],
    "foxit": [r"Foxit Software\Foxit PDF Reader", r"Foxit Software\Foxit Reader", r"Foxit Software\Foxit PDF Editor"],
    "edge": [r"Microsoft\Edge\Application"],
    "chrome": [r"Google\Chrome\Application"],
    "firefox": [r"Mozilla Firefox"],
}


def find_exe(kind: str) -> str | None:
    """Path of a viewer's program on this computer (Windows), or None."""
    if sys.platform != "win32":
        return None
    try:
        import winreg
    except Exception:
        winreg = None
    for exe in EXE_NAMES.get(kind, []):
        if winreg is not None:
            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    with winreg.OpenKey(hive, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe}") as k:
                        val = winreg.QueryValue(k, None)
                        if val and Path(val.strip('"')).is_file():
                            return val.strip('"')
                except OSError:
                    pass
        for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"),
                     os.environ.get("LOCALAPPDATA") and str(Path(os.environ["LOCALAPPDATA"]) / "Programs")):
            if not base:
                continue
            for sub in COMMON_DIRS.get(kind, []):
                p = Path(base) / sub / exe
                if p.is_file():
                    return str(p)
    return None


def command(kind: str, exe: str, pdf: Path, page: int) -> list[str]:
    """The command line that opens `pdf` at `page` (1-based) with this kind of viewer."""
    if kind == "acrobat":
        return [exe, "/A", f"page={page}", str(pdf)]
    if kind == "sumatra":
        return [exe, "-reuse-instance", "-page", str(page), str(pdf)]
    if kind == "foxit":
        return [exe, "/A", f"page={page}", str(pdf)]
    if kind in ("edge", "chrome", "firefox"):
        return [exe, pdf.resolve().as_uri() + f"#page={page}"]
    return [exe, str(pdf)]                    # custom: the program, then the file


def open_at(pdf: str | Path, page: int, settings: dict) -> str:
    """Open the PDF at `page` (1-based: the PDF's own page, not the printed number).
    Returns a message for the user ("" when the jump was made)."""
    pdf = Path(pdf)
    choice = settings.get("pdf_viewer", "auto")
    kinds = AUTO_ORDER if choice == "auto" else [choice]
    if choice == "custom":
        exe = settings.get("pdf_viewer_path") or ""
        if exe and Path(exe).is_file():
            subprocess.Popen(command("custom", exe, pdf, page))
            return f"Opened the PDF. Go to page {page} of the PDF file."
        kinds = AUTO_ORDER
    if choice != "default":
        for kind in kinds:
            exe = find_exe(kind)
            if exe:
                try:
                    subprocess.Popen(command(kind, exe, pdf, page))
                    return ""
                except OSError:
                    continue
    _open_default(pdf)
    return f"Opened the PDF. Go to page {page} of the PDF file (the reader can't be told the page)."


def _open_default(pdf: Path) -> None:
    if sys.platform == "win32":
        os.startfile(str(pdf))            # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(pdf)])
    else:
        subprocess.Popen(["xdg-open", str(pdf)])
