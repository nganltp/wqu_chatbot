# WQU Support Chatbot

A retrieval-augmented generation (RAG) chatbot for answering student-support questions from the public [WorldQuant University Help Center](https://help.wqu.edu/en/). Every factual answer is grounded in retrieved content and includes source references.

The data model already supports `course` and `chapter` metadata, so authorised course material can be added later without changing the chat API schema.

## Architecture

- **API:** FastAPI
- **Vector database:** [Qdrant](https://qdrant.tech/), using cosine similarity and metadata-ready records
- **Embeddings:** `BAAI/bge-m3`, suitable for English and Vietnamese queries
- **Language model:** OpenAI Responses API (default: `gpt-5.6-luna`)
- **Frontend:** static HTML, CSS, and JavaScript in `web/`

## Requirements

- Python 3.11 or later
- An OpenAI API key
- Docker and Docker Compose for the default Qdrant setup, or a local filesystem for Docker-free Qdrant mode

## Local setup

1. Create your local environment file and add your OpenAI API key:

   ```bash
   cp .env.example .env
   ```

   Set `OPENAI_API_KEY` in `.env`. Never commit this file.

2. Create and activate a virtual environment, then install the project:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e '.[dev]'
   ```

3. Start Qdrant:

   ```bash
   docker compose up -d qdrant
   ```

4. Crawl the public Help Center to local documents only:

   ```bash
   python -m wqu_chatbot.crawl_help --replace-output --verbose
   ```

5. Review or edit the complete local documents in `data/wqu_help_raw/documents/help/`, then
   chunk and index them:

   ```bash
   python -m wqu_chatbot.reindex_help
   ```

6. Start the API:

   ```bash
   uvicorn wqu_chatbot.api:app --reload --no-proxy-headers
   ```

   The health endpoint is available at `http://127.0.0.1:8000/health`.

`crawl_help` never chunks or writes to Qdrant. Pass `--replace-output` to delete only the previous
generated `metadata/` and `content/` folders before saving the new snapshot. It stores one complete source document per Help Center
article at `data/wqu_help_raw/documents/help/`: `metadata/help-<id>.json` holds metadata and
`content/help-<id>.md` holds the full extracted content. The two files share the same ID.
`reindex_help --input-dir <folder>` only accepts WQU Help Center article documents, deletes the
configured Qdrant collection, then chunks and indexes that folder's current Help Center snapshot.

Use `crawl_help --output-dir <directory>` or `reindex_help --input-dir <directory>` to use another
WQU Help Center snapshot directory.

To save an authorised WQU SCORM launch as one complete, pre-chunk learning document (without
quiz/answer blocks), run `python -m wqu_chatbot.ingest_scorm '<launch URL>'`. Its default output
directory is `data/wqu_help_raw/documents/100-orientation-course/`, using the same `metadata/<id>.json`
and `content/<id>.md` layout as Help Center documents. The launch URL's query parameters are not
persisted.

### Docker-free Qdrant mode

To persist Qdrant locally without Docker, set this in `.env`:

```dotenv
QDRANT_LOCAL_PATH=data/qdrant
```

When set, `QDRANT_LOCAL_PATH` takes precedence over `QDRANT_URL`. Do not start the Docker service in this mode.

## Configuration

All configuration is loaded from `.env`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `QDRANT_URL` | `http://localhost:6333` | URL of the Qdrant service. |
| `QDRANT_COLLECTION` | `wqu_help` | Qdrant collection name. |
| `QDRANT_LOCAL_PATH` | unset | Local persistent Qdrant directory; overrides `QDRANT_URL`. |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | Sentence-transformer model used for retrieval. |
| `EMBEDDING_DEVICE` | `cpu` | Embedding device, such as `cpu` or `cuda`. |
| `HF_TOKEN` | unset | Optional Hugging Face token for authenticated embedding-model downloads. |
| `OPENAI_API_KEY` | unset | Server-side key used for chat generation. |
| `OPENAI_MODEL` | `gpt-5.6-luna` | OpenAI model used for chat generation. |
| `OPENAI_REASONING_EFFORT` | `low` | Reasoning effort: `none`, `low`, `medium`, `high`, `xhigh`, or `max`. |
| `CORS_ORIGINS` | local development origins | Comma-separated browser origins allowed to call the API. |
| `DAILY_QUESTION_LIMIT` | `10` | Accepted questions per public IP per calendar day. |
| `RATE_LIMIT_DB_PATH` | `data/chat_usage.sqlite3` | Persistent SQLite quota database shared by local workers. |
| `RATE_LIMIT_TIMEZONE` | `Asia/Singapore` | Timezone for midnight quota reset. |
| `TRUST_CLOUDFLARE_TUNNEL` | `false` | Trust visitor IP headers only from a loopback tunnel connection. |
| `TOP_K` | `5` | Number of chunks sent to the LLM after hybrid ranking. |
| `MIN_RETRIEVAL_SCORE` | `0.35` | Minimum dense cosine similarity for a dense candidate. |
| `HYBRID_DENSE_CANDIDATES` | `10` | Dense candidates collected before fusion. |
| `HYBRID_KEYWORD_CANDIDATES` | `10` | BM25 keyword candidates collected before fusion. |
| `HYBRID_MIN_KEYWORD_SCORE` | `1.0` | Minimum BM25 score for a keyword candidate. |
| `HYBRID_RRF_RANK_CONSTANT` | `60` | Reciprocal Rank Fusion smoothing constant. |

The API key remains on the backend only. For a support chatbot, the default `low` reasoning effort
balances response quality, latency, and token cost; validate it against the evaluation set before
raising it.

Retrieval uses a hybrid of dense cosine similarity and an in-process BM25 index over the Qdrant
payloads. It fuses only candidates that meet their dense or BM25 relevance threshold with
Reciprocal Rank Fusion (RRF), then sends the final `TOP_K` chunks to the LLM.

## API

Send a question to `POST /chat`:

```bash
curl -X POST http://localhost:8000/chat \
  -H 'content-type: application/json' \
  -d '{"question":"How can I contact student support?"}'
```

Example response:

```json
{
  "answer": "... [S1]",
  "sources": [
    {
      "label": "S1",
      "title": "...",
      "course": null,
      "chapter": null,
      "url": "https://help.wqu.edu/en/articles/..."
    }
  ]
}
```

An optional `history` array accepts up to 12 `user` or `assistant` messages:

```json
{
  "question": "What should I do next?",
  "history": [{"role": "user", "content": "I cannot access my account."}]
}
```

If no sufficiently relevant content is found, the API returns a safe fallback response and no sources.

## Daily question limit and logging

`POST /chat` accepts up to 10 validated questions per IP per day, resetting at midnight
in `Asia/Singapore`. The 11th request returns HTTP 429 with a readable `detail` and
`Retry-After` in seconds; the existing frontend displays this message. Quota is reserved
atomically before retrieval/model calls, including requests that later fail with 503.
Invalid request bodies and `/health` do not consume quota. New chat does not reset it.

SQLite retains the current day's IP/count, survives restarts, and shares counts across
workers using the same database file. Old days are removed on subsequent accepted requests.
Keep this file on persistent local storage; separate hosts need a shared quota service.
Users sharing a public IP share a quota; changing network/VPN/IP can bypass an IP-only limit.

Chat history is stored in `chat_requests` in the same SQLite file as `daily_usage`.
Each validated request with a valid client IP stores a UUID, optional conversation UUID,
UTC timestamp, question, answer, returned sources (JSON), status, latency, model, and error
class/code. Status is `processing`, `success`, `error`, or `rate_limited`. IP and full
conversation history are not copied into these rows. Invalid request bodies are not recorded.
The frontend sends an optional `conversation_id` UUID, persists it across reloads, and rotates
it on New chat. Older clients remain compatible but their rows have no conversation ID.
New chat clears browser history only; it does not delete server records.

Rows are retained until explicitly deleted by the operator; quota cleanup never deletes history.
Back up the SQLite file using SQLite's backup command/API. There is no public history endpoint.
If initial history storage fails the request returns 503 before calling the model. If finalization
fails or the process stops mid-request, the saved row can remain `processing`; finalization
failure is logged without discarding the answer. Returned sources include retrieval candidates,
not necessarily only sources cited in the answer.

Inspect recent questions locally:

```bash
sqlite3 -header -column data/chat_usage.sqlite3 \
  "SELECT created_at, question, status, latency_ms FROM chat_requests ORDER BY created_at DESC LIMIT 20;"
```

`DEBUG_RETRIEVAL=true` additionally emits retrieval details through configured Python INFO logging.

For the existing **local Cloudflare Tunnel**, set `TRUST_CLOUDFLARE_TUNNEL=true` in `.env`
and start the API with:

```bash
uvicorn wqu_chatbot.api:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

Point cloudflared at `http://127.0.0.1:8000`. Keep the backend reachable only locally.
The app reads [Cloudflare's CF-Connecting-IP](https://developers.cloudflare.com/fundamentals/reference/http-headers/)
only from loopback peers when explicitly enabled. [Uvicorn's --no-proxy-headers](https://uvicorn.dev/settings/)
keeps that peer check tied to the actual connection. Do not expose a trusted local proxy that
passes user-supplied headers through unchanged. For direct connections leave tunnel trust disabled
and also use `--no-proxy-headers`; X-Forwarded-For is not used by the app.

## Inspect indexed content

Export the indexed chunks as readable text:

```bash
python -m wqu_chatbot.export_chunks
```

The default output is `data/wqu_help_chunks.txt`. In Docker-free mode, make sure `QDRANT_LOCAL_PATH` remains set before running the command.

## Frontend deployment with Cloudflare Pages

The static frontend can be hosted on Cloudflare Pages while the FastAPI backend and Qdrant run elsewhere.

1. Run and index the backend locally, then expose it with a Cloudflare Quick Tunnel:

   ```bash
   cloudflared tunnel --url http://localhost:8000
   ```

2. Copy the frontend configuration and place the tunnel URL in `apiBaseUrl`:

   ```bash
   cp web/config.example.js web/config.js
   ```

3. Deploy the `web/` directory:

   ```bash
   npx wrangler login
   npx wrangler pages deploy web --project-name wqu-chatbot
   ```

4. Add the exact Pages domain to `CORS_ORIGINS` in `.env`, then restart the API:

   ```dotenv
   CORS_ORIGINS=https://wqu-chatbot.pages.dev,http://localhost:8000,http://localhost:5500
   ```

Quick Tunnel URLs change after a restart. For a stable deployment, use a named Cloudflare Tunnel and a dedicated domain.

`web/config.js` is public and intentionally ignored by Git. Never place `OPENAI_API_KEY`, `HF_TOKEN`, or another secret in that file. The demo has a daily IP quota but no authentication.

## Tests

Run the test suite with:

```bash
pytest
```

## RAG evaluation

Before changing retrieval, chunking, or prompts, run the English evaluation seed set against the
current index:

```bash
python -m wqu_chatbot.evaluate
```

It records retrieval recall@k, citation presence, fallback behavior, latency, errors, and all
case-level evidence in `data/evaluations/`. The CSV report also has fields for required human
groundedness and citation-correctness review. See [evaluation/README.md](evaluation/README.md)
for the dataset format, scoring rubric, and retrieval-only mode.

## Adding authorised course material

Create another ingester that emits `SourceChunk` records with `source_type="lecture"` plus `course`, `chapter`, `title`, and `url` metadata. Only index material that WQU authorises for chatbot use, and add access control before exposing private learning content.
