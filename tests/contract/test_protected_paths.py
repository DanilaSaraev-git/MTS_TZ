from __future__ import annotations

import json
import os
import shlex
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
            "280ab87e22ed02c2e16ccb1baa53d74ab64d5542",
            "--json",
            *shlex.split(os.environ.get("PROTECTED_PATH_ARGS", "")),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["unexpected_changes"] == []
