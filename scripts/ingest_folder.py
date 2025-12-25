#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from lantern.config import load_config
from lantern.ingest import ingest_folder


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest a folder of .txt and .md files")
    parser.add_argument("--path", default="./data/docs", help="Folder path to ingest")
    args = parser.parse_args()

    folder = Path(args.path).expanduser()
    if not folder.exists():
        print(f"Folder not found: {folder}")
        return 1

    config = load_config()
    total = ingest_folder(folder, config)
    print(f"Ingested {total} chunks from {folder}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

