# Plans

Working list for the next version. Nothing here is built yet; building starts once the list
has a handful of items and Beaux says go.

## 0.4.1

### 1. Update in place

**Now:** Help > Check for updates (and the check at start-up) reads the latest GitHub release
and offers to open the download page in the browser. The user downloads `Indicat.exe` by hand.

**Wanted (decided):**

- The .exe carries its version in its name: `Indicat 0.4.1.exe`. A new version never has to
  overwrite the running one.
- The check at start-up (and Help > Check for updates) offers: "Indicat X is available (you
  have Y). Install it in the same folder?" with the release notes. Buttons: Install / Open the
  download page / Not now.
- Install downloads `Indicat X.exe` into the folder the running copy is in, with the progress
  bar, checks the size and the SHA-256 digest GitHub gives for the file (deletes it and says
  so if they don't match), then offers to start the new version and close this one.
- The .jsx is not downloaded.

Fall-backs, each with a plain message; the running copy is never touched:

- Folder not writable (e.g. under Program Files): save to Downloads and open that folder.
- Running from source (`python run_app.py`), not the .exe: open the download page as now.
- No connection, download cut off, digest mismatch: nothing is kept.

Settings carry over as before (`%APPDATA%\Indicat`).

Code: `updates.py` (find the `Indicat *.exe` asset, download, verify), `gui.py`
`_check_updates` (dialog, progress, start the new copy), `build.yml` and `build_exe.bat`
(`--name "Indicat X.Y.Z"`, read from `__init__.py`; the data-file check follows the new name).
Tests against a fake release served locally: find, download, verify, the fall-backs.

Note: 0.4.0 still only opens the download page; the in-place install starts with updates
*from* 0.4.1 onward.

Can't be tested here: the real download and restart on Windows, and SmartScreen/antivirus on a
freshly downloaded unsigned .exe. Needs a run on Beaux's machine (0.4.1 updating to a test
release).

**Open questions for Beaux:**

- Old copies stay in the folder (`Indicat 0.4.1.exe`, `Indicat 0.4.2.exe`, …), and desktop
  shortcuts and taskbar pins still point to the old one. Should the new version offer to
  delete the old copy at its first start? Should it make or update a desktop / Start menu
  shortcut called "Indicat"?
- "Don't remind me about this version"?

### 2. Stop publishing the InDesign script in the release

The build still writes `Indicat for InDesign.jsx` as a check that Indicat generates a correct
script, but the release no longer carries it (users make their own from the app). In
`build.yml`: write it outside `dist/` (or drop it before publishing) so `files: dist/*` only
publishes the .exe.

### 3. …

(more updates, improvements and fixes to add here)
