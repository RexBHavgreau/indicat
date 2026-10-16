"""Check GitHub for a newer release, and install it next to the running copy.

UPDATE_REPO is the GitHub repository (owner/name).  The check reads the latest release's tag
(e.g. "v0.4.1") and compares it with the running version.  Nothing is downloaded unless the user
says so.

Each version's program carries its version in its name ("Indicat 0.4.1.exe"), so a new version is
saved beside the running one and never has to overwrite it.  The new version, at its first start,
offers to delete the older copies in its folder and to point shortcuts to itself.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import APP_NAME, REPO, __version__

UPDATE_REPO = REPO
API = "https://api.github.com/repos/{repo}/releases/latest"
# "Indicat 0.4.1.exe"; GitHub turns spaces in release file names into dots ("Indicat.0.4.1.exe");
# 0.4.0 and earlier were plain "Indicat.exe"
EXE_RE = re.compile(r"^indicat(?:[ ._-]+(\d+(?:\.\d+){1,2}))?\.exe$", re.I)


class UpdateError(Exception):
    """A plain message for the user."""


def _parse(v: str) -> tuple:
    nums = re.findall(r"\d+", v or "")
    return tuple(int(n) for n in nums[:3]) + (0,) * (3 - len(nums[:3]))


def configured() -> bool:
    return bool(UPDATE_REPO)


def exe_name(version: str) -> str:
    return f"{APP_NAME} {version}.exe"


def _pick_asset(assets: list) -> dict | None:
    for a in assets or []:
        if EXE_RE.match(a.get("name") or "") and a.get("browser_download_url"):
            return {"name": a["name"], "url": a["browser_download_url"], "size": a.get("size") or 0,
                    "digest": a.get("digest") or ""}
    return None


def check(timeout: float = 5.0) -> dict:
    """{'status': 'newer'|'current'|'norelease'|'unconfigured'|'error', 'latest', 'url', 'notes',
    'asset' (the program to download, or None), 'error'}"""
    if not UPDATE_REPO:
        return {"status": "unconfigured"}
    try:
        req = urllib.request.Request(API.format(repo=UPDATE_REPO),
                                     headers={"Accept": "application/vnd.github+json",
                                              "User-Agent": f"Indicat/{__version__}"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        latest = data.get("tag_name") or data.get("name") or ""
        status = "newer" if _parse(latest) > _parse(__version__) else "current"
        return {"status": status, "latest": latest.lstrip("v"), "url": data.get("html_url", ""),
                "notes": (data.get("body") or "")[:1500], "asset": _pick_asset(data.get("assets"))}
    except urllib.error.HTTPError as exc:
        if exc.code == 404:          # no release published yet
            return {"status": "norelease"}
        return {"status": "error", "error": str(exc)}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


# ---------------------------------------------------------------------------
# Installing
# ---------------------------------------------------------------------------
def running_exe() -> Path | None:
    """The program file of this copy, when it runs as the built .exe (not from source)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()
    return None


def can_install() -> bool:
    return sys.platform == "win32" and running_exe() is not None


def downloads_folder() -> Path:
    return Path.home() / "Downloads"


def download(asset: dict, dest: Path, progress=None, timeout: float = 30.0, opener=None) -> Path:
    """Download `asset` to `dest` (through dest + ".part"), checking its size and SHA-256 digest.
    Raises PermissionError/OSError when `dest`'s folder can't be written, UpdateError otherwise."""
    progress = progress or (lambda f, t="": None)
    part = dest.with_name(dest.name + ".part")
    with open(part, "wb") as out:            # fails here, before downloading, if the folder is read-only
        try:
            req = urllib.request.Request(asset["url"], headers={"User-Agent": f"Indicat/{__version__}"})
            with (opener or urllib.request.urlopen)(req, timeout=timeout) as r:
                total = int(asset.get("size") or r.headers.get("Content-Length") or 0)
                got = 0
                h = hashlib.sha256()
                while True:
                    chunk = r.read(256 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    h.update(chunk)
                    got += len(chunk)
                    if total:
                        progress(min(got / total, 1.0), f"Downloading {dest.name}")
        except Exception as exc:
            out.close()
            part.unlink(missing_ok=True)
            raise UpdateError(f"The download didn't finish ({exc}). Nothing was changed; try again later.") \
                from exc
    digest = (asset.get("digest") or "").lower()
    bad = (total and got != total) or (digest.startswith("sha256:") and h.hexdigest() != digest[7:])
    if bad:
        part.unlink(missing_ok=True)
        raise UpdateError("The downloaded file didn't match the release (it may have been damaged on the way), "
                          "so it was deleted. Nothing was changed; try again later.")
    if dest.exists():
        dest.unlink()
    part.rename(dest)
    return dest


def install(asset: dict, version: str, progress=None, folder: Path | None = None,
            fallback: Path | None = None, opener=None) -> tuple[Path, bool]:
    """Download the new version into the running copy's folder, or, when that folder can't be
    written to, into Downloads.  Returns (the new program, True if it went to the fallback)."""
    folder = folder or running_exe().parent
    try:
        return download(asset, folder / exe_name(version), progress, opener=opener), False
    except UpdateError:
        raise
    except OSError:
        fb = fallback or downloads_folder()
        fb.mkdir(parents=True, exist_ok=True)
        return download(asset, fb / exe_name(version), progress, opener=opener), True


def launch(exe: Path) -> None:
    """Start another copy of Indicat, independent of this one."""
    env = dict(os.environ)
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"     # the new copy must not reuse this one's unpacked files
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([str(exe)], cwd=str(exe.parent), env=env, close_fds=True, creationflags=flags)


# ---------------------------------------------------------------------------
# After an update: older copies and shortcuts
# ---------------------------------------------------------------------------
def version_in_name(name: str) -> tuple | None:
    """(0, 4, 1) for "Indicat 0.4.1.exe", (0, 0, 0) for the old "Indicat.exe", None if not Indicat."""
    m = EXE_RE.match(name)
    if not m:
        return None
    return _parse(m.group(1)) if m.group(1) else (0, 0, 0)


def older_copies(folder: Path, current: Path) -> list[Path]:
    """Copies of Indicat in `folder` older than this version (never the running one, never a newer one)."""
    mine = _parse(__version__)
    out = []
    for p in sorted(folder.glob("*.exe")):
        v = version_in_name(p.name)
        if v is None or v >= mine:
            continue
        try:
            if p.resolve() == current.resolve():
                continue
        except OSError:
            continue
        out.append(p)
    return out


def delete_old(paths: list[Path], wait: float = 15.0) -> tuple[list[Path], list[Path]]:
    """Delete older copies; one that is still closing gets a few more tries.  (deleted, not deleted)"""
    deleted, left = [], list(paths)
    end = time.time() + wait
    while left:
        still = []
        for p in left:
            try:
                p.unlink()
                deleted.append(p)
            except FileNotFoundError:
                deleted.append(p)
            except OSError:
                still.append(p)
        left = still
        if not left or time.time() >= end:
            break
        time.sleep(1.0)
    return deleted, left


def shortcut_folders() -> list[Path]:
    """Where Windows keeps shortcuts to programs: the desktop, the Start menu, taskbar pins."""
    out = []
    try:
        import win32com.client
        sh = win32com.client.Dispatch("WScript.Shell")
        for name in ("Desktop", "AllUsersDesktop", "Programs", "AllUsersPrograms"):
            try:
                p = sh.SpecialFolders(name)
                if p:
                    out.append(Path(p))
            except Exception:
                pass
    except Exception:
        home = Path.home()
        out.append(home / "Desktop")
    appdata = os.environ.get("APPDATA")
    if appdata:
        pinned = Path(appdata) / "Microsoft" / "Internet Explorer" / "Quick Launch" / "User Pinned"
        out += [pinned / "TaskBar", pinned / "StartMenu"]
    return [p for p in out if p.is_dir()]


def retarget_shortcuts(old: list[Path], new: Path, folders: list[Path] | None = None, shell=None) -> int:
    """Point shortcuts (.lnk) that open one of the `old` copies to `new`.  Returns how many were changed;
    shortcuts to anything else, and ones that can't be written (e.g. all users' without admin rights),
    are left alone."""
    if shell is None:
        try:
            import win32com.client
            shell = win32com.client.Dispatch("WScript.Shell")
        except Exception:
            return 0
    norm = lambda p: os.path.normcase(os.path.abspath(str(p)))     # noqa: E731
    olds = {norm(p) for p in old}
    old_dirs = {norm(Path(p).parent) for p in old}
    changed = 0
    for folder in (folders if folders is not None else shortcut_folders()):
        for lnk in folder.rglob("*.lnk"):
            try:
                sc = shell.CreateShortcut(str(lnk))
                if norm(sc.TargetPath) not in olds:
                    continue
                sc.TargetPath = str(new)
                if sc.WorkingDirectory and norm(sc.WorkingDirectory) in old_dirs:
                    sc.WorkingDirectory = str(new.parent)
                icon = (sc.IconLocation or "").rsplit(",", 1)[0]
                if icon and norm(icon) in olds:
                    sc.IconLocation = f"{new},0"
                sc.Save()
                changed += 1
            except Exception:
                continue
    return changed
