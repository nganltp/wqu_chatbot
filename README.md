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

4. Crawl and index the public Help Center:

   ```bash
   python -m wqu_chatbot.ingest_help --verbose
   ```

5. Start the API:

   ```bash
   uvicorn wqu_chatbot.api:app --reload
   ```

   The health endpoint is available at `http://127.0.0.1:8000/health`.

The initial ingest downloads the embedding model. Re-run the ingest command to refresh Help Center content; stable chunk IDs allow Qdrant to upsert existing records.

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

`web/config.js` is public and intentionally ignored by Git. Never place `OPENAI_API_KEY`, `HF_TOKEN`, or another secret in that file. The demo has no authentication or rate limiting, so protect the API before sharing it broadly.

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
