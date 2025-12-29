# lantern

A small, local-first RAG assistant scaffold for macOS. It ingests local text/markdown files into a persistent ChromaDB vector store, retrieves relevant chunks, and generates answers via a configurable local LLM endpoint.

## Requirements
- Python 3.11+
- macOS

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Configure
Copy `.env.example` to `.env` and edit as needed:
```bash
cp .env.example .env
```

At minimum, set your local LLM endpoint if you want answers generated. For OpenAI-compatible servers, use a base URL like `http://localhost:3001/v1`.

## Ingest documents
By default, this reads `./data/docs` recursively for `.txt` and `.md` files:
```bash
python scripts/ingest_folder.py --path ./data/docs
```

## Ask questions
```bash
python scripts/ask.py "What is this project?"
```

If no LLM endpoint is configured, the app will still run and will print a helpful configuration message.

## Ingest Asana tasks
Set these env vars in `.env`:
- `LANTERN_ASANA_PAT` (personal access token)
- `LANTERN_ASANA_WORKSPACE_GID`
- One of: `LANTERN_ASANA_PROJECT_GID` or `LANTERN_ASANA_USER_GID`
- Optional: `LANTERN_ASANA_LIMIT` (default 200)

Then run:
```bash
python scripts/ingest_asana.py
```

Optional: limit ingestion to the first N tasks:
```bash
python scripts/ingest_asana.py --top-n 50
```
