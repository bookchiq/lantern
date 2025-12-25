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

## Next: Asana loader
To add an Asana loader later, create `src/lantern/loaders/asana.py` with a function that yields `Document` objects from Asana tasks. Then call it from `ingest.py` or a new script to feed those documents into the same chunking + vectorstore pipeline.
