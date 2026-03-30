# Document Grounded Chatbot

Small RAG chatbot for one PDF or DOCX per conversation.

What it does:
- extracts text from an uploaded document
- chunks and embeds that text locally with Ollama
- retrieves the most relevant chunks for each user question
- answers only from those chunks
- falls back to the exact sentence below when the answer is not supported by the document

`This information is not present in the provided document.`

It also stores conversations and messages in Firebase Firestore, so a user can return to an older conversation from the left sidebar and continue with the prior chat context.

## Stack
- `FastAPI` backend
- plain `HTML/CSS/JavaScript` frontend
- `Firebase Authentication` for Google sign-in
- `Cloud Firestore` for conversations and messages
- `Ollama` for local embeddings and local answer generation
- local `FAISS` index for retrieval

## Project Layout
- `app/main.py`: API routes and app wiring
- `app/services/rag.py`: main RAG flow in a single function-based pipeline
- `app/services/auth.py`: Firebase token verification
- `app/services/document_parser.py`: PDF/DOCX text extraction
- `app/services/text_chunker.py`: deterministic chunking
- `app/services/ollama_client.py`: small Ollama request helpers
- `app/services/vector_store.py`: FAISS index persistence and retrieval
- `app/storage/firebase_store.py`: Firestore persistence
- `app/frontend/`: minimal browser client

## Prerequisites
1. Install `uv`.
2. Python `3.11` or newer.
3. Install and start `Ollama`.
4. Pull the two local models:

```bash
ollama pull llama3.2
ollama pull nomic-embed-text
```

5. Create a Firebase project with:
   - Google sign-in enabled
   - Cloud Firestore enabled
   - one Web App created so you have the frontend config values
   - one Service Account JSON key downloaded for the backend
   - `127.0.0.1` and `localhost` added to Authorized Domains

## Local Setup
```bash
uv sync
cp .env.example .env
```

`uv sync` installs the project dependencies from [pyproject.toml](/Users/hasib/Code/RAG_chatbot/pyproject.toml) and [uv.lock](/Users/hasib/Code/RAG_chatbot/uv.lock) into `.venv/`.

Fill in `.env` with your Firebase values and the absolute path to the downloaded service account JSON file.

Alternative setup with plain `pip`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Run
```bash
uv run app/main.py
```

Open `http://127.0.0.1:8000`.

You can also run:

```bash
uv run uvicorn app.main:app --reload
```

## How Grounding Works
1. The backend parses the uploaded document.
2. The text is split into overlapping chunks.
3. Ollama creates embeddings for those chunks.
4. The chunk metadata and FAISS index are stored under `data/indexes/`.
5. Each chat request embeds the question, retrieves the closest chunks, and checks the top similarity score.
6. If the similarity is too weak, the backend returns:

`This information is not present in the provided document.`

7. If the similarity is strong enough, the backend sends only the retrieved chunks plus recent chat history to the LLM.

The chat history is used only for conversational continuity. The uploaded document remains the only knowledge source.

<!--
## Debugging Retrieval
To inspect what the retriever found for a question, send `debug: true` to `/api/chat`.

Example request body:

```json
{
  "conversation_id": "your-conversation-id",
  "message": "What does the document say about refunds?",
  "debug": true
}
```

The response will include:
- `debug.used_fallback`
- `debug.score_threshold`
- `debug.top_score`
- `debug.matches`

This makes it easier to see whether the issue is:
- bad extraction
- poor retrieval scores
- missing document support
- Ollama generation failure

## Notes
- V1 supports one document per conversation.
- If you restart the server, conversations remain in Firestore and the backend can rebuild the local index from the stored document file if needed.
- Uploaded files and FAISS indexes live on the local filesystem under `data/`.
-->
