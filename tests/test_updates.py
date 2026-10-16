"""The updater: finding the new program in a release, downloading and checking it, the
fall-backs, and (at the new version's first start) older copies and shortcuts.

    python tests/test_updates.py

Downloads come from a small web server on this computer; shortcuts use a fake Windows
shortcut object."""
import hashlib
import http.server
import io
import json
import sys
import tempfile
import threading
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from indicat import __version__              # noqa: E402
from indicat import updates as U             # noqa: E402

fails = 0


def check(ok, what):
    global fails
    print(("OK   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


PROGRAM = b"MZ" + bytes(range(256)) * 4000           # about 1 MB standing in for the new .exe


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = PROGRAM[: len(PROGRAM) // 2] if self.path == "/short.exe" else PROGRAM
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def serve():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def test_names():
    check(U.exe_name("0.4.1") == "Indicat 0.4.1.exe", "the program is named with its version")
    check(U.version_in_name("Indicat 0.4.1.exe") == (0, 4, 1) and U.version_in_name("Indicat.0.4.2.exe") == (0, 4, 2)
          and U.version_in_name("Indicat.exe") == (0, 0, 0) and U.version_in_name("Other.exe") is None
          and U.version_in_name("Indicat for InDesign.jsx") is None,
          "versions read from names (with a space, with GitHub's dots, the old Indicat.exe)")
    assets = [{"name": "Indicat.for.InDesign.jsx", "browser_download_url": "u1"},
              {"name": "Indicat.0.4.2.exe", "browser_download_url": "u2", "size": 5, "digest": "sha256:ab"}]
    a = U._pick_asset(assets)
    check(a and a["url"] == "u2" and a["size"] == 5 and a["digest"] == "sha256:ab", "the .exe found in a release")
    check(U._pick_asset([{"name": "Source.zip", "browser_download_url": "x"}]) is None, "no .exe: nothing to install")


def test_check():
    data = {"tag_name": "v9.0.0", "html_url": "page", "body": "notes",
            "assets": [{"name": "Indicat.9.0.0.exe", "browser_download_url": "dl", "size": 1}]}
    real = U.urllib.request.urlopen

    class R(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    U.urllib.request.urlopen = lambda req, timeout=0: R(json.dumps(data).encode())
    try:
        r = U.check()
    finally:
        U.urllib.request.urlopen = real
    check(r["status"] == "newer" and r["latest"] == "9.0.0" and r["asset"]["url"] == "dl",
          "the check reports the new version and its program")


def test_download(tmp: Path, base: str):
    good = {"url": base + "/new.exe", "size": len(PROGRAM),
            "digest": "sha256:" + hashlib.sha256(PROGRAM).hexdigest()}
    folder = tmp / "Programs"
    folder.mkdir()
    seen = []
    path, moved = U.install(good, "9.0.0", progress=lambda f, t="": seen.append(f), folder=folder,
                            fallback=tmp / "Downloads")
    check(path == folder / "Indicat 9.0.0.exe" and not moved and path.read_bytes() == PROGRAM,
          "downloaded into the same folder as the running copy, under its versioned name")
    check(seen and seen[-1] == 1.0 and not list(folder.glob("*.part")), "with progress, and no part file left")

    bad = dict(good, digest="sha256:" + "0" * 64)
    try:
        U.install(bad, "9.0.1", folder=folder, fallback=tmp / "Downloads")
        check(False, "a damaged download is refused")
    except U.UpdateError as exc:
        check(not (folder / "Indicat 9.0.1.exe").exists() and not list(folder.glob("*.part"))
              and "didn't match" in str(exc), "a damaged download (wrong digest) is refused and deleted")

    short = {"url": base + "/short.exe", "size": len(PROGRAM), "digest": ""}
    try:
        U.install(short, "9.0.2", folder=folder, fallback=tmp / "Downloads")
        check(False, "a cut-off download is refused")
    except U.UpdateError:
        check(not (folder / "Indicat 9.0.2.exe").exists(), "a cut-off download (wrong size) is refused")

    nodigest = dict(good, digest="")
    path, _ = U.install(nodigest, "9.0.3", folder=folder, fallback=tmp / "Downloads")
    check(path.exists(), "a release without a digest is checked by size only")

    gone = {"url": "http://127.0.0.1:9/none.exe", "size": 10, "digest": ""}
    try:
        U.install(gone, "9.0.4", folder=folder, fallback=tmp / "Downloads")
        check(False, "no connection is reported")
    except U.UpdateError as exc:
        check("Nothing was changed" in str(exc) and not list(folder.glob("*.part")),
              "no connection: a plain message, nothing left behind")

    path, moved = U.install(good, "9.0.5", folder=tmp / "not writable", fallback=tmp / "Downloads")
    check(moved and path == tmp / "Downloads" / "Indicat 9.0.5.exe" and path.exists(),
          "a folder that can't be written to: saved in Downloads instead")


def test_old_copies(tmp: Path):
    folder = tmp / "Indicat"
    folder.mkdir()
    me = folder / U.exe_name(__version__)
    names = ["Indicat.exe", "Indicat 0.3.0.exe", "Indicat.0.4.0.exe", U.exe_name(__version__),
             "Indicat 99.0.0.exe", "Other.exe", "notes.txt"]
    for n in names:
        (folder / n).write_bytes(b"x")
    olds = U.older_copies(folder, me)
    check(sorted(p.name for p in olds) == ["Indicat 0.3.0.exe", "Indicat.0.4.0.exe", "Indicat.exe"],
          "older copies found; this one, a newer one and other programs left alone")
    stuck = folder / "Indicat 0.1.0.exe"
    stuck.mkdir()                                       # can't be deleted like a file
    deleted, left = U.delete_old(olds + [stuck, folder / "Indicat 0.0.9.exe"], wait=0)
    check(len(deleted) == 4 and left == [stuck] and me.exists() and (folder / "Indicat 99.0.0.exe").exists(),
          "older copies deleted; one that can't be is reported")


class FakeShortcut:
    def __init__(self, store, path):
        self.store, self.path = store, path
        self.__dict__.update(store[path])

    def Save(self):
        self.store[self.path] = {k: getattr(self, k) for k in ("TargetPath", "WorkingDirectory", "IconLocation")}


class FakeShell:
    def __init__(self, store):
        self.store = store

    def CreateShortcut(self, path):
        return FakeShortcut(self.store, path)


def test_shortcuts(tmp: Path):
    prog = tmp / "Apps"
    desk, pins = tmp / "Desktop", tmp / "TaskBar"
    for d in (prog, desk, pins):
        d.mkdir()
    old, older, new = prog / "Indicat.exe", prog / "Indicat 0.3.0.exe", prog / U.exe_name(__version__)
    store = {
        str(desk / "Indicat.lnk"): {"TargetPath": str(old), "WorkingDirectory": str(prog),
                                    "IconLocation": f"{old},0"},
        str(pins / "Indicat.lnk"): {"TargetPath": str(older), "WorkingDirectory": "", "IconLocation": ""},
        str(desk / "Word.lnk"): {"TargetPath": r"C:\Program Files\Word.exe", "WorkingDirectory": "",
                                 "IconLocation": ""},
    }
    for p in store:
        Path(p).write_bytes(b"")
    n = U.retarget_shortcuts([old, older], new, folders=[desk, pins], shell=FakeShell(store))
    d = store[str(desk / "Indicat.lnk")]
    check(n == 2 and d["TargetPath"] == str(new) and d["IconLocation"] == f"{new},0"
          and store[str(pins / "Indicat.lnk")]["TargetPath"] == str(new),
          "desktop shortcut and taskbar pin now open the new version (with its icon)")
    check(store[str(desk / "Word.lnk")]["TargetPath"] == r"C:\Program Files\Word.exe",
          "shortcuts to other programs left alone")


def main():
    srv, base = serve()
    try:
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            test_names()
            test_check()
            test_download(td, base)
            test_old_copies(td)
            test_shortcuts(td)
    finally:
        srv.shutdown()
    if fails:
        print(f"{fails} failed")
        sys.exit(1)
    print("All update tests passed.")


if __name__ == "__main__":
    main()
