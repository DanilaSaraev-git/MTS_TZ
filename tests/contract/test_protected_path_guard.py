from __future__ import annotations

import subprocess
import sys

import pytest

from tools.contracts.check_protected_paths import main


@pytest.mark.parametrize(
    ("changed", "allowed", "expected"),
    [
        ("MTS/README.md\n", [], 1),
        ("MTS/README.md\n", ["MTS/README.md"], 0),
        ("MTS/README.md\nMTS/another.md\n", ["MTS/README.md"], 1),
        ("MTS/README.md\n", ["MTS/*"], 1),
    ],
)
def test_guard_allows_only_explicit_exact_paths(
    monkeypatch: pytest.MonkeyPatch, changed: str, allowed: list[str], expected: int
) -> None:
    # Git is the external interface; the CLI still parses its real options.
    def git_diff(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 0, stdout=changed)

    monkeypatch.setattr(subprocess, "run", git_diff)
    argv = ["check_protected_paths.py", "--json"]
    for path in allowed:
        argv.extend(["--allow-path", path])
    monkeypatch.setattr(sys, "argv", argv)
    assert main() == expected
