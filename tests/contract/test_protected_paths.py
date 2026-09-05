from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_protected_paths_unchanged_from_docs_commit() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/contracts/check_protected_paths.py"),
            "--baseline",
            "a5792150b280f8e3b7704af5296de99166d4f845",
            "--json",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload == {"changed": [], "status": "ok"}
