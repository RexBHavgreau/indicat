"""Check GitHub for a newer release.

UPDATE_REPO is the GitHub repository (owner/name).  The check reads the latest release's tag (e.g. "v0.2.1") and compares it with
the running version.  It never downloads or installs anything by itself.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

from . import REPO, __version__

UPDATE_REPO = REPO
API = "https://api.github.com/repos/{repo}/releases/latest"


def _parse(v: str) -> tuple:
    nums = re.findall(r"\d+", v or "")
    return tuple(int(n) for n in nums[:3]) + (0,) * (3 - len(nums[:3]))


def configured() -> bool:
    return bool(UPDATE_REPO)


def check(timeout: float = 5.0) -> dict:
    """{'status': 'newer'|'current'|'unconfigured'|'error', 'latest', 'url', 'notes', 'error'}"""
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
                "notes": (data.get("body") or "")[:1500]}
    except urllib.error.HTTPError as exc:
        if exc.code == 404:          # no release published yet
            return {"status": "norelease"}
        return {"status": "error", "error": str(exc)}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
