## Mevzuat RAG - Preparation Utilities

This repository contains helper scripts that:
- Split Turkish legislation documents into individual articles and export them to JSON.
- Generate embeddings for each article using an OpenAI embedding model.
- Store the embeddings and related metadata in a MariaDB (Vector) database.

### 1. Installation

- **Install Python dependencies:**

```bash
pip install -r requirements.txt
```

> Note: The project has been tested with Python 3.10+.

### 2. MariaDB / Vector Table Setup

This project is designed and tested with **MariaDB 12.1.2**, which includes native support for the `vector` type and `VECTOR KEY` indexes. Older versions of MariaDB do (might, some versions might support it, i did not test them yet) **not** support these features.

1. On your MariaDB server (with Vector support enabled), create the `mevzuat_rag` database and the vector tables (`mevzuat_doc`, `mevzuat_rag`).

> Note: this repo previously used an older table named `kanun_embeddingler`. The current pipeline targets `mevzuat_doc` + `mevzuat_rag` (see the schemas you provided).

### 3. Environment Variables and `.env`

Sensitive configuration is managed via environment variables in a `.env` file instead of being hard-coded. Create a `.env` file in the project root.

#### 3.1. Example `.env` file

```bash
# Database configuration

# Database user name used to connect to MariaDB.
DB_USER=root

# Database user password used to connect to MariaDB.
DB_PASSWORD=your_database_password

# Hostname or IP address of the MariaDB server.
DB_HOST=127.0.0.1

# Port of the MariaDB server (default for this project: 3307).
DB_PORT=3307

# Name of the application database.
# Current runtime expects both app tables and RAG tables in the same schema.
DB_NAME=mevzuat

# Optional: MariaDB connection pool size for the backend runtime.
DB_POOL_SIZE=10


# OpenAI configuration

# Weighted rotation keys used by the backend OpenAI client pool.
OPENAI_API_KEY_1=sk-your-openai-api-key-1
OPENAI_API_KEY_2=sk-your-openai-api-key-2

EMBED_CONCURRENCY=30

# Optional Redis configuration (used by the new agent for short-term memory)
REDIS_URL=redis://localhost:6379/0

# If Redis is not reachable, the CLI will fall back to in-process memory.
# Optional JSON configuration

# Optional: path to the JSON file that contains the pre-processed articles.
# If not set, the application uses <project_root>/mevzuat_ready_to_embed.json by default.
# Example:
# JSON_FILE=D:/mevzuat-pdfler-rag/mevzuat_ready_to_embed.json
```

The `python-app/prep/embed_and_load2db.py` script uses `python-dotenv` to automatically load this `.env` file.

### 4. Usage Workflow

#### 4.0. New PDF pipeline (Phase 1 -> Phase 2)

Phase 1 (PDF -> inspectable JSON):

```bash
py -m chunking.phase1_build_json --out mevzuat_chunked.json
```

Phase 2 (JSON -> MariaDB + embeddings):

```bash
py -m chunking.phase2_ingest_db --json mevzuat_chunked.json --embedding-mode openai --concurrency 16
```

#### 4.1. Split legislation documents into articles (chunking)

The `python-app/prep/chunking.py` script reads `.docx` files from the `mevzuat-docs` folder, splits them into articles, and writes the output to JSON.

```bash
python python-app/prep/chunking.py
```

The output file should be configured so that it will be consumed as `mevzuat_ready_to_embed.json` in the project root (update the `SOURCE_FOLDER` and `OUTPUT_FILE` constants in `chunking.py` if your directory layout differs).

#### 4.2. Load JSON and write embeddings to MariaDB

```bash
python python-app/prep/embed_and_load2db.py
```

This script:

- Connects to MariaDB using the DB settings defined in `.env`.
- Uses the `text-embedding-3-large` model to generate embeddings for each article in `mevzuat_ready_to_embed.json`.
- Persists the results to the database using `VEC_FromText` for the `embedding` column.

#### 4.3. New agent (openai-agents SDK) + hybrid memory + usage tracking

1) Create/import the application schema using:

```bash
mysql -u root -p < mevzuat.sql
```

Note: DB schema/migrations are managed externally. The backend does not create/alter tables or triggers at runtime.

2) Run the backend locally:

```bash
py main.py
```

3) Optional: verify connectivity (Redis + DB):

```bash
py -m src.utils.selfcheck
```

#### 4.4. API server (FastAPI) - productized interface

Install dependencies:

```bash
py -m pip install -r requirements.txt
```

Run the API (example):

```bash
py -m uvicorn src.api.app:app --host 0.0.0.0 --port 8000
```

MVP shipping (Docker):

- Copy `env.example` to `.env` and fill it.
- Run:

```bash
docker compose -f ../deploy/docker-compose.yaml up --build
```

Structured logging:

- API prints one JSON line per request to stdout (configure with `LOG_LEVEL`).

Auth:

- This API uses **JWT Bearer** auth.
- Set env vars:
  - `JWT_SECRET` (required)
  - `JWT_ALG` (default: `HS256`)
  - `JWT_ISSUER` (default: `mevzuat-agent`)
  - `JWT_ACCESS_TTL_SECONDS` (default: `900`)
  - `JWT_REFRESH_TTL_SECONDS` (default: `2592000`)
  - `JWT_LEEWAY_SECONDS` (default: `30`)  # clock-skew tolerance for exp/iat
  - `JWT_REFRESH_REUSE_GRACE_SECONDS` (default: `5`)  # concurrent refresh grace
  - `ADMIN_USER_IDS` (example: `1,2`)  # allowlist of user_ids for admin endpoints
- The middleware reads `sub` from the JWT and treats it as `user_id`.
- Recommended: set `sub` as a string (e.g. `"1"`). The server will cast it to int.
- You do NOT pass `user_id` in request bodies.

Token types:

- Access token: `token_type="access"` (required for /v1/chat/* endpoints)
- Refresh token: `token_type="refresh"` with `jti` (used only for /v1/auth/refresh and /v1/auth/logout)

Refresh flow:

1) (Dev only) Issue tokens (requires `AUTH_DEV_MODE=1`):
   - `POST /v1/auth/dev/issue` body: `{ "user_id": 1 }`
   - Returns: access + refresh

2) Refresh tokens (rotating refresh):
   - `POST /v1/auth/refresh` body: `{ "refresh_token": "..." }`
   - Returns: new access + new refresh (old refresh jti is revoked)

3) Logout (revoke refresh):
   - `POST /v1/auth/logout` body: `{ "refresh_token": "..." }`

Register/login:

- `POST /v1/auth/register`
  - Body: `{ "username": "...", "email": "...", "full_name": "...", "password": "..." }`
  - Returns: `{ ok, user_id, access_token, refresh_token, access_expires_at, refresh_expires_at }`

- `POST /v1/auth/login`
  - Body: `{ "identifier": "username-or-email", "password": "..." }`
  - Returns: `{ ok, user_id, access_token, refresh_token, access_expires_at, refresh_expires_at }`

Account:

- `GET /v1/auth/me`
- `PATCH /v1/auth/me`
  - Body: `{ "username": "...", "email": "...", "full_name": "..." }` (all optional)
- `PATCH /v1/auth/admin/users/{user_id}/rate_limit` (admin-only)
  - Body: `{ "rate_limit_rps": 50 }`

Security note:

- Refresh tokens are rotating. If a revoked refresh token is used again, the server treats it as **reuse** and revokes **all** refresh tokens for that user.

Rate limiting:

- **50 requests/second per user**.
- Default per-user limit is **50 req/sec**, configurable per user via `users.rate_limit_rps`.
- Redis-backed using `REDIS_URL` if available; falls back to in-process per-worker limits if Redis is down.

Early RAG (new chats):

- For the **first 3 user messages** in a chat, the server runs a semantic search **for each message separately**
  and appends a short **EARLY RAG CONTEXT** item into hot memory (Redis history) so the agent grounds faster.
- This is **not persisted to the SQL chat_messages** table. If it fails (no embeddings/DB), the chat still proceeds.

Endpoints:

- `POST /v1/chat/create`
  - Body: `{ "title": "..." }`
  - Returns: `{ "ok": true, "chat_id": 123 }`

- `POST /v1/chat/list`
  - Body: `{ "limit": 50, "offset": 0 }`

- `GET /v1/chat/history/{chat_id}`

- `POST /v1/chat/stream` (NDJSON streaming)
  - Body: `{ "chat_id": 123, "message": "...", "reasoning": "low|medium|high" }`
  - Events (one JSON per line):
    - `{"type":"text_delta","chunk":"..."}`
    - `{"type":"tool_call","name":"...","args":{...}}`
    - `{"type":"done","chat_id":123,"final_text":"...","reasoning":"..."}`
    - `{"type":"error","message":"..."}`

- `POST /v1/chat/message` (non-streaming)
  - Body: `{ "chat_id": 123, "message": "...", "reasoning": "low|medium|high" }`
  - Returns: `{ "ok": true, "chat_id": 123, "final_text": "...", "reasoning": "..." }`

### 5. Notes

- Before pushing this repository to any remote (e.g., GitHub), ensure that `.env` is excluded via `.gitignore` and that no secrets are present in commit history.
- If you change the embedding model or vector dimensionality, update both the model configuration in `embed_and_load2db.py` and the `vector(3072)` definition in the SQL DDL accordingly.
