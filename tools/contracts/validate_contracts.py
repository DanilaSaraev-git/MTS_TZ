#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    harness = root / "tools/contracts/orval"
    subprocess.run(["npm", "run", "validate"], cwd=harness, check=True)
    subprocess.run(["npm", "run", "generate"], cwd=harness, check=True)
    subprocess.run(["npm", "run", "typecheck"], cwd=harness, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
