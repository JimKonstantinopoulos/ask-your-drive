"""
MCP server for ChatGPT: real retrieval over the Drive-sourced knowledge base.
Run:  python spike.py   (keep it running; expose it with the cloudflared tunnel)
"""
import os
from dotenv import load_dotenv
from fastmcp import FastMCP
from openai import OpenAI
from supabase import create_client
from starlette.requests import Request
from starlette.responses import JSONResponse

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
EMBEDDING_MODEL = "text-embedding-3-small"

openai_client = OpenAI(api_key=OPENAI_API_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

mcp = FastMCP("Research Assistant Demo")


def embed_query(text: str):
    resp = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=[text])
    return resp.data[0].embedding


@mcp.tool()
def search(query: str) -> dict:
    """Search the research project for passages relevant to the query. Returns matching source chunks with citations."""
    query_embedding = embed_query(query)
    response = supabase.rpc(
        "match_research_chunks",
        {"query_embedding": query_embedding, "match_count": 5},
    ).execute()
    rows = response.data or []
    results = [
        {
            "id": str(row["id"]),
            "title": row["file_name"],
            "url": row.get("file_url") or "",
            "text": row["content"],
        }
        for row in rows
    ]
    return {"results": results}


@mcp.tool()
def fetch(id: str) -> dict:
    """Return the full text of a single source passage, with its citation."""
    try:
        row_id = int(id)
    except (TypeError, ValueError):
        return {"id": id, "title": "Invalid id", "text": "", "url": "", "metadata": {}}

    response = supabase.table("research_chunks").select("*").eq("id", row_id).execute()
    rows = response.data or []
    if not rows:
        return {"id": id, "title": "Not found", "text": "", "url": "", "metadata": {}}

    row = rows[0]
    return {
        "id": str(row["id"]),
        "title": row["file_name"],
        "text": row["content"],
        "url": row.get("file_url") or "",
        "metadata": {"chunk_index": row["chunk_index"], "file_id": row["file_id"]},
    }


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    """Runs one tiny Supabase read. Two jobs: it proves the DB path is live so
    UptimeRobot can alert on a real failure, and the steady traffic keeps the
    free-tier Supabase project from idling into an auto-pause (a paused project
    stops resolving, which took the whole demo down once)."""
    try:
        supabase.table("research_chunks").select("id").limit(1).execute()
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=503)


if __name__ == "__main__":
    # A host (Railway/Render/Fly) assigns the port and needs 0.0.0.0 to route to
    # the container. Falls back to localhost:8000 for local runs.
    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1"
    mcp.run(transport="http", host=host, port=port)
