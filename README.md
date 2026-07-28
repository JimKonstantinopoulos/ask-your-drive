# Ask Your Drive: a ChatGPT connector for your own documents

Connect a Google Drive folder to ChatGPT and ask questions about it. Answers come
back grounded in your documents, with the source named, and "I don't know" when
the answer isn't in the folder.

This is a working MCP (Model Context Protocol) server. ChatGPT calls it directly
as a custom connector, so the documents stay in your Drive and your Supabase
database. Nothing is pasted into the chat.

## What it does

1. `ingest.py` reads the files in a shared Drive folder, splits them into
   passages, embeds them, and stores them in Supabase (pgvector).
2. `spike.py` exposes two tools to ChatGPT over MCP:
   - `search(query)` — returns the passages most relevant to the question
   - `fetch(id)` — returns the full text of one passage, with its source
3. ChatGPT decides when to call them, then answers using only what comes back,
   citing the file each passage came from.

The demo folder holds research documents about Napoleon, including two that
deliberately contradict each other, so you can see the assistant handle
conflicting sources instead of blending them into one confident wrong answer.

## Stack

Python, FastMCP (streamable HTTP transport), Supabase pgvector, OpenAI
embeddings, Google Drive API.

## Running it

```bash
pip install -r requirements-ingest.txt   # server deps + Google Drive libs
cp .env.example .env                     # fill in your keys
python ingest.py                         # one time, loads the Drive folder
python spike.py                          # serves MCP on localhost:8000
```

Add it to ChatGPT: Settings → Connectors → add a custom connector pointing at
the server's `/mcp` URL.

## Deploying

The server needs `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, and `OPENAI_API_KEY`.
It does **not** need the Google service account: only `ingest.py` reads Drive,
and that runs locally. `requirements.txt` (without the Google libraries) is what
the host installs.

Bind to `$PORT` is handled automatically when the host sets it.
