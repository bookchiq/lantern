#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from lantern.config import load_config
from lantern.embeddings import Embeddings
from lantern.ingest import ingest_documents
from lantern.loaders.asana import load_asana_tasks


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest Asana tasks into the local vector store")
    parser.add_argument("--top-n", type=int, default=None, help="Only ingest the first N tasks")
    args = parser.parse_args()

    config = load_config()
    tasks = load_asana_tasks(config)
    fetched_count = len(tasks)

    if args.top_n is not None:
        tasks = tasks[: max(args.top_n, 0)]

    embedder = Embeddings(config.embed_model)
    chunk_count = ingest_documents(tasks, embedder, config)

    print(f"Tasks fetched: {fetched_count}")
    print(f"Tasks ingested: {len(tasks)}")
    print(f"Chunks ingested: {chunk_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

