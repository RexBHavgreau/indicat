# Plans

Working list for the next version. Nothing here is built yet; building starts once the list
has a handful of items and Beaux says go.

## 0.4.1

### 1. Update in place

**Now:** Help > Check for updates (and the check at start-up) reads the latest GitHub release
and offers to open the download page in the browser. The user downloads `Indicat.exe` by hand
and has to put it where the old one was.

**Wanted:** when a newer version is found, Indicat downloads it and puts it in the same folder
as the copy that is running, then offers to restart.

How it would work (Windows, the built .exe):

1. "Version X is available (you have Y). Download and install it now?" with the release notes,
   and buttons Install / Open the download page / Not now.
2. Download the release's `Indicat.exe` asset next to the running one as `Indicat.exe.new`,
   with the progress bar. Check the size and the SHA-256 digest GitHub gives for the asset;
   if they don't match, delete it and say so.
3. Windows won't let a running .exe be overwritten, but it can be renamed: rename the running
   copy to `Indicat.exe.old`, rename `Indicat.exe.new` to the exe's own name. The file name
   stays the same, so shortcuts and pinned taskbar icons keep working.
4. "Indicat X is installed. Restart now?" Restart starts the new copy and closes this one.
5. At the next start, delete the leftover `Indicat.exe.old`.

When it can't do that, it falls back to the browser, with a plain message:

- The folder isn't writable (e.g. under Program Files): save to Downloads and open that folder.
- Running from source (`python run_app.py`), not the .exe: open the download page as now.
- No connection, download cut off, digest mismatch: nothing is replaced; the old copy keeps
  running.

Settings and the user's documents are untouched (settings live in `%APPDATA%\Indicat`).

Code: `indicat/updates.py` (find the asset, download, verify, swap), `gui.py`
`_check_updates` (dialogs, progress, restart), clean-up of `.old` at start-up. Tests against a
fake release (a local file server) for the download, verify, swap and fall-backs.

Can't be tested here: a real swap of a running .exe on Windows, antivirus/SmartScreen
reactions to a freshly downloaded unsigned .exe. Needs a check on Beaux's machine with two
real releases (0.4.1 updating to a test 0.4.2, or a test release on a branch).

**Questions for Beaux:**

- Also update `Indicat for InDesign.jsx` if a copy sits in the same folder? (It is in each
  release.)
- Should the start-up check offer to install, or only say a new version exists and leave
  installing to Help > Check for updates?
- Skip a version ("Don't remind me about X")?

### 2. …

(more updates, improvements and fixes to add here)
