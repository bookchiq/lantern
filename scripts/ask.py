#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from lantern.config import load_config
from lantern.llm import LLMNotConfigured
from lantern.rag import answer_question


def main() -> int:
    parser = argparse.ArgumentParser(description="Ask a question against the local RAG index")
    parser.add_argument("question", help="Question to ask")
    parser.add_argument("--top-k", type=int, default=6, help="Number of chunks to retrieve")
    args = parser.parse_args()

    config = load_config()

    try:
        answer = answer_question(args.question, config, top_k=args.top_k)
    except LLMNotConfigured as exc:
        print(str(exc))
        return 1

    print(answer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

