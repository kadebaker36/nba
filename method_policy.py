"""Parse canonical policy and identify its exact content and source revision."""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METHOD = ROOT / "METHOD.md"
REPOSITORY = "https://github.com/kadebaker36/nba"
SECTION = re.compile(r"^## ([^\n]+)\n<!-- sheet-row: (\d+) -->\n\s*\n(.*?)(?=^## |\Z)", re.M | re.S)


def sheet_rows(path=METHOD):
    text = Path(path).read_text(encoding="utf-8")
    rows = []
    seen = set()
    for match in SECTION.finditer(text):
        label, number, prose = match.groups()
        number = int(number)
        if number in seen or number < 6 or number > 53 or not prose.strip():
            raise ValueError("Invalid or duplicate method row")
        seen.add(number)
        rows.append((number, label.strip(), prose.strip()))
    if not rows or not {35, 36, 37, 38, 43, 45, 48, 51, 52, 53}.issubset(seen):
        raise ValueError("Required canonical method sections are missing")
    return rows


def metadata(path=METHOD):
    path = Path(path).resolve()
    content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    commit = None
    clean = False
    try:
        relative = path.relative_to(ROOT)
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, stderr=subprocess.DEVNULL, text=True
        ).strip()
        recorded = subprocess.check_output(
            ["git", "show", f"HEAD:{relative.as_posix()}"], cwd=ROOT, stderr=subprocess.DEVNULL
        )
        clean = hashlib.sha256(recorded).hexdigest() == content_hash
        if not clean:
            commit = None
    except (OSError, ValueError, subprocess.CalledProcessError):
        supplied = os.environ.get("BBB_METHOD_COMMIT", "")
        if supplied:
            if not re.fullmatch(r"[0-9a-f]{40}", supplied):
                raise ValueError("BBB_METHOD_COMMIT must be an actual full commit SHA")
            commit, clean = supplied, True
    return {
        "repository": REPOSITORY,
        "method_commit": commit,
        "method_sha256": content_hash,
        "method_committed": clean,
        "method_source": f"{REPOSITORY}/blob/{commit or 'main'}/METHOD.md",
    }


def grounded_header():
    info = metadata()
    revision = info["method_commit"] or "uncommitted or source revision unavailable"
    return (
        f"Canonical method: {info['method_source']}\n\n"
        f"Method revision: {revision}. METHOD.md SHA-256: {info['method_sha256']}.\n\n"
        "Automated output is research input. Apply the full method before final selection; "
        "a legacy sorter is not a shortlist. Volume and shot quality must be assessed separately.\n\n"
    )
