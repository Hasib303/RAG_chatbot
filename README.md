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

## Docker
The Docker setup is split into:
- one `app` container for FastAPI and the built-in frontend
- one optional `ollama` container for local embeddings and chat generation
- external Firebase Auth and Firestore

Files:
- [Dockerfile](/Users/hasib/Code/RAG_chatbot/Dockerfile): production-style app image built with `uv`
- [compose.yaml](/Users/hasib/Code/RAG_chatbot/compose.yaml): local orchestration for `app` and optional `ollama`
- [.dockerignore](/Users/hasib/Code/RAG_chatbot/.dockerignore): keeps secrets and local artifacts out of the image

### Docker setup
1. Copy `.env.example` to `.env`.
2. Set your normal Firebase and Ollama values in `.env`.
3. Set `FIREBASE_SERVICE_ACCOUNT_FILE` in `.env` to the host path of your Firebase service account JSON.
4. For Docker Compose with the bundled Ollama service, keep:

```env
OLLAMA_BASE_URL_DOCKER=http://ollama:11434
```

5. For app-only Docker pointing at Ollama running on your machine, change:

```env
OLLAMA_BASE_URL_DOCKER=http://host.docker.internal:11434
```

The container does not use your host `FIREBASE_CREDENTIALS_PATH`. Compose mounts the JSON file into the container and overrides it with:

```env
FIREBASE_CREDENTIALS_PATH=/run/secrets/firebase-service-account.json
```

### Run with Docker Compose and bundled Ollama
Start the full local stack:

```bash
docker compose --profile local-ollama up --build
```

On first run, pull the two Ollama models inside the running Ollama container:

```bash
docker compose exec ollama ollama pull llama3.2
docker compose exec ollama ollama pull nomic-embed-text
```

Then open `http://127.0.0.1:8000`.

### Run app container only
If Ollama is already running outside Docker or on another host, set `OLLAMA_BASE_URL_DOCKER` in `.env` to that reachable URL and run:

```bash
docker compose up --build app
```

Examples:
- local host Ollama from Docker Desktop: `http://host.docker.internal:11434`
- remote Ollama server: `http://your-server:11434`

### Docker data and logs
- uploaded files live in the `app_uploads` volume
- FAISS indexes live in the `app_indexes` volume
- Ollama models live in the `ollama_data` volume

Useful commands:

```bash
docker compose logs -f app
docker compose logs -f ollama
docker compose down
```

### Common Docker issues
- If upload or chat fails immediately, check that `OLLAMA_BASE_URL_DOCKER` points to a reachable Ollama instance.
- If the app reports Firebase is not configured, check `FIREBASE_SERVICE_ACCOUNT_FILE` and the mounted JSON path.
- If chat fails with a missing model error, pull `llama3.2` and `nomic-embed-text` inside the Ollama container.
- If you recreate containers, your files and indexes remain because they are stored in Docker volumes rather than inside the image.

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

## Prompt Protection
- User questions and retrieved document passages are treated as untrusted text.
- The backend blocks obvious attempts to override the document-only policy, reveal hidden instructions, or force outside-knowledge answers.
- Retrieved chunks that look like assistant-targeting instructions are filtered out before they are sent to the model.
- If the request is unsafe or the remaining safe context is not enough to support the answer, the app returns:

`This information is not present in the provided document.`

- Prompt protection is heuristic and server-side. It reduces prompt injection risk, but it is not a perfect security boundary.

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
- `debug.protection_trigger`
- `debug.filtered_chunk_count`
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
