"""
Ingestion: pull files from a Google Drive folder, chunk, embed, store in Supabase.
Run once to (re)build the knowledge base:  python ingest.py
"""
import os
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from openai import OpenAI
from supabase import create_client

load_dotenv()

SERVICE_ACCOUNT_FILE = os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"]
DRIVE_FOLDER_ID = os.environ["DRIVE_FOLDER_ID"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

EMBEDDING_MODEL = "text-embedding-3-small"  # 1536 dims, matches the DB schema

openai_client = OpenAI(api_key=OPENAI_API_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    return build("drive", "v3", credentials=creds)


def list_files(service):
    query = f"'{DRIVE_FOLDER_ID}' in parents and trashed = false"
    results = service.files().list(
        q=query, fields="files(id, name, mimeType)"
    ).execute()
    return results.get("files", [])


def read_file_text(service, file):
    mime = file["mimeType"]
    if mime == "application/vnd.google-apps.document":
        data = service.files().export(fileId=file["id"], mimeType="text/plain").execute()
    else:
        data = service.files().get_media(fileId=file["id"]).execute()
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="ignore")
    return str(data)


def chunk_text(text, max_chars=1000, overlap=150):
    text = text.strip()
    if not text:
        return []
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks, current = [], ""
    for p in paragraphs:
        if len(current) + len(p) + 2 <= max_chars:
            current = (current + "\n\n" + p).strip()
        else:
            if current:
                chunks.append(current)
            if len(p) <= max_chars:
                current = p
            else:
                start = 0
                while start < len(p):
                    chunks.append(p[start:start + max_chars])
                    start += max_chars - overlap
                current = ""
    if current:
        chunks.append(current)
    return chunks


def embed(texts):
    resp = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in resp.data]


def main():
    service = get_drive_service()
    files = list_files(service)
    print(f"Found {len(files)} file(s) in the Drive folder.")
    if not files:
        print("No files found. Check that the folder is shared with the service account.")
        return

    total_chunks = 0
    for file in files:
        text = read_file_text(service, file)
        chunks = chunk_text(text)
        if not chunks:
            print(f"  {file['name']}: empty, skipped.")
            continue

        embeddings = embed(chunks)
        file_url = f"https://drive.google.com/file/d/{file['id']}/view"

        # Clear any previous rows for this file so re-runs stay clean.
        supabase.table("research_chunks").delete().eq("file_id", file["id"]).execute()

        rows = [
            {
                "file_id": file["id"],
                "file_name": file["name"],
                "file_url": file_url,
                "chunk_index": i,
                "content": chunk,
                "embedding": embeddings[i],
            }
            for i, chunk in enumerate(chunks)
        ]
        supabase.table("research_chunks").insert(rows).execute()
        total_chunks += len(rows)
        print(f"  {file['name']}: {len(rows)} chunk(s) stored.")

    print(f"Done. {total_chunks} chunk(s) total in the knowledge base.")


if __name__ == "__main__":
    main()
