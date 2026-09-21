#!/usr/bin/env python3
"""Copy alex-database into the SAM db layer as /opt/python/src."""

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "backend" / "database" / "src"
DEST = ROOT / "infra" / "sam" / "layer-db" / "python" / "src"


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"Database package not found: {SRC}")
    if DEST.exists():
        shutil.rmtree(DEST)
    DEST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SRC, DEST)
    print(f"Copied {SRC} -> {DEST}")
    print("Next: cd infra/sam && sam build --use-container")


if __name__ == "__main__":
    main()
