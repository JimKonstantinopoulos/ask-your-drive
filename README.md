# Ask Your Drive: a ChatGPT connector for your own documents

Connect a Google Drive folder to ChatGPT and ask questions about it. ChatGPT
searches your files through the connector and gets back the matching passages,
each with its file name and a link to the file. ChatGPT writes the answer; this
server only returns passages.

This is a working MCP (Model Context Protocol) server. ChatGPT calls it directly
as a custom connector. Your files stay in your Drive, and the search index
(passage text plus embeddings) lives in the configured Supabase database. Building the
index sends the text to the OpenAI embeddings API, and when you ask a question
the matching passages are sent to ChatGPT as the tool result.

## What it does

1. `ingest.py` reads the files at the top level of a shared Drive folder, splits
   them into passages, embeds them, and stores them in Supabase (pgvector). It
   reads only the first page of Drive results (approximately 100 files) and does
   not traverse subfolders. It handles Google Docs and plain-text files; other
   formats such as PDF or Word are not converted to text.
2. `spike.py` exposes two tools to ChatGPT over MCP:
   - `search(query)`: returns up to five passages closest to the question, each
     with its file name and link
   - `fetch(id)`: returns the full text of one passage, with its source
3. ChatGPT decides when to call them and writes the answer from what comes back.
   Whether it cites the files, or says the folder does not cover a question,
   is ChatGPT's behavior, not this server's.

The demo folder holds research documents about Napoleon, including two that
deliberately contradict each other, so you can check whether the assistant
reports the conflict or blends the sources into one answer.

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
