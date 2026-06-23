# Architecture

A reference for the structure and conventions of this FastAPI + async MySQL + LLM service.
Written to be reused as a template when scaffolding new backend prototypes.

## Stack

| Concern        | Choice                                              |
|----------------|-----------------------------------------------------|
| Web framework  | FastAPI (ASGI, served by uvicorn)                   |
| ORM            | SQLAlchemy 2.0 (async) + `aiomysql` driver          |
| DB             | MySQL 8                                             |
| Auth           | JWT HS256 via `python-jose`; bcrypt via `passlib`   |
| LLM            | OpenRouter `/chat/completions` over `httpx.AsyncClient` |
| Config         | `os.getenv()` + `python-dotenv` (no pydantic-settings) |

Async end to end: `async def` routes, `AsyncSession`, `get_db()` generator dependency, `httpx.AsyncClient`.

## Layout

```
app/
├── main.py              # entrypoint: app, startup hook, router registration, inline auth endpoints
├── core/
│   ├── config.py        # load_dotenv() + DB_URL string construction
│   └── auth.py          # get_current_user() JWT dependency
├── db/
│   ├── session.py       # async engine, AsyncSessionLocal, get_db()
│   └── models.py        # DeclarativeBase + 8 ORM models
├── routes/              # one file per resource; each defines an APIRouter
├── schemas/             # Pydantic request/response models
└── services/
    ├── llm.py           # call_llm, extract_json_content, extract_text_content, build_response, load_prompt
    └── chat_persistence.py  # save_turn, expire_old_messages
prompts/                 # <name>.txt LLM system prompts, loaded by load_prompt(name)
data/mock/               # <endpoint>.json fixtures returned in test mode
scripts/utils/           # DB init/seed/verify (sync mysql-connector-python)
scripts/testing/         # per-endpoint test drivers (--test, --debug)
```

## Layered request flow

```
HTTP → route handler (app/routes/*.py)
        ├─ Depends(get_current_user)  → User          (app/core/auth.py)
        ├─ Depends(get_db)            → AsyncSession   (app/db/session.py)
        ├─ services/llm.py            → OpenRouter + parsing
        └─ db.add / db.commit         → ORM models     (app/db/models.py)
```

Routes are thin orchestrators. Cross-cutting work (LLM calls, JSON extraction, chat persistence) lives in `services/`, never inline in routes.

## Entrypoint (`app/main.py`)

- Creates the `FastAPI` app and registers every router with **no prefix** — each route declares its own full path (e.g. `@router.post("/analyze_workout")`).
- **Startup hook** runs `Base.metadata.create_all` inside `engine.begin()`. DB failure is **non-fatal**: it logs and continues, so the service boots even without a database. `create_all` only adds missing tables; it never alters existing ones (no migration tooling).
- Holds the **public** endpoints inline: `GET /`, `GET /health`, `POST /register_user`, `POST /login_user`.
  - `register_user`: bcrypt-hash password, insert `User`, return `{user_id, email}`, `409` on duplicate email (catch `IntegrityError`).
  - `login_user`: verify bcrypt, return `{user_id, email, token}`. Token is JWT HS256, payload `{sub, email, exp}`, 24h expiry, signed with `JWT_SECRET`.
- No CORS / middleware / custom exception handlers — uncaught errors surface as FastAPI 500s.

## Configuration (`app/core/config.py`)

`load_dotenv()` at import, then build the SQLAlchemy URL from env vars:

```python
DB_URL = f"mysql+aiomysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
```

Plain `os.getenv()` — no validation layer. Use `DB_HOST=127.0.0.1` (not `localhost`) for Docker TCP. Required: `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `MODEL`, `DB_*`, `JWT_SECRET`.

## Database (`app/db/session.py`, `models.py`)

```python
engine = create_async_engine(DB_URL, pool_pre_ping=True, pool_size=5, max_overflow=10)
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
```

`expire_on_commit=False` so ORM instances keep loaded attributes after commit (lets a handler return `obj.id` post-commit).

Models inherit `class Base(DeclarativeBase)`. Eight tables, all child tables FK to `users.id` with cascade:

`users`, `user_profiles` (1:1), `gym_profiles` (1:1), `workout_sessions` (1:N) → `workout_exercises` (1:N) / `workout_analysis_results` (1:1), `workout_history_summaries`, `chat_messages`.

Conventions worth copying:
- `created_at` is `DateTime(server_default=func.now())`.
- Constrained categorical columns use SQL `Enum` (e.g. `range_period`, `role`).
- Structured fields use the `JSON` column type (`constraints`, `top_exercises`, `muscle_groups_targeted`).
- **Soft delete**: `chat_messages.deleted_at` (nullable, indexed) instead of row deletion.
- **Column names are the contract**: LLM output keys must match DB columns exactly (`read_description`, `top_exercises`, `range_period`) so persistence needs no per-field translation.

## Auth (`app/core/auth.py`)

`get_current_user` is a FastAPI dependency: reads the `Authorization: Bearer <token>` header, decodes with `JWT_SECRET`/HS256, loads `User` by the `sub` claim, returns the ORM object. Any failure (missing/malformed header, `JWTError`, missing subject, unknown user) → `401`.

Attach with `current_user: User = Depends(get_current_user)`. Every non-public route uses it — including AI routes in mock mode (a valid token is still required).

## LLM service (`app/services/llm.py`)

```python
def load_prompt(name) -> str                 # reads prompts/<name>.txt
async def call_llm(system_prompt, user_message) -> dict   # httpx POST to OpenRouter, 60s timeout, returns raw JSON
def extract_json_content(raw) -> dict        # pull message content, strip ```json fences, json.loads, regex {…} fallback
def extract_text_content(raw) -> str         # plain message content (chat)
def build_response(formatted, raw, debug)    # debug → {"formatted", "raw"}; else just formatted
```

`extract_json_content` is defensive: malformed envelope → `{"error": "malformed_envelope", "raw": raw}`; unparseable content → `{"raw_text": content}`. No retry/error handling around the HTTP call — exceptions propagate.

## AI endpoint pattern (the reusable core)

Every AI POST request schema carries two flags:

```python
test: bool = False    # load data/mock/<endpoint>.json and return immediately — no LLM, no DB write
debug: bool = False   # return {"formatted", "raw"} instead of just formatted
```

Normal-mode flow:

```
load_prompt → call_llm → extract_json_content (or extract_text_content)
            → persist to DB → build_response(formatted, raw, debug)
```

Per-route persistence:
- `analyze_workout` → `WorkoutSession` + `WorkoutExercise[]` + `WorkoutAnalysisResult`; returns `session_id`.
- `analyze_workout_history` → request is `{range, user_profile, test, debug}` (no client sessions). Route queries the user's sessions where `date >= today − RANGE_DAYS[range]` (week=7/month=30/3months=90), builds the payload server-side. Empty range → `EMPTY_SUMMARY` with `summary_id: null`, 200, no write. Else persists `WorkoutHistorySummary` and returns `summary_id`.
- `generate_gym_profile` → upserts the single `GymProfile` per user; has a `_normalize_profile()` shim to absorb LLM output drift.
- `chat` / `generate_gym_chat_completions` → use `extract_text_content`, return `{"message": str}`, and persist via `save_turn()`.

## Chat persistence & soft-delete (`app/services/chat_persistence.py`)

```python
CHAT_TTL_HOURS = 24
async def expire_old_messages(db, user_id)   # set deleted_at=now() where created_at < now-24h and not deleted; no commit
async def save_turn(db, user_id, user_content, assistant_content)  # expire, add user+assistant rows, commit
```

Reads filter on `deleted_at IS NULL`; `GET /chat_messages` calls `expire_old_messages` first. Effect: a rolling 24h chat window without hard deletes.

## Route inventory

| Route | Method | Auth | Notes |
|-------|--------|------|-------|
| `/`, `/health` | GET | public | liveness |
| `/register_user`, `/login_user` | POST | public | inline in `main.py` |
| `/analyze_workout` | POST | yes | AI; writes session+exercises+analysis |
| `/analyze_workout_history` | POST | yes | AI; server-side session query |
| `/generate_gym_profile` | POST | yes | AI; upsert gym profile |
| `/chat`, `/generate_gym_chat_completions` | POST | yes | AI text; `save_turn` |
| `/users/me` | GET/POST | yes | account; name updated here |
| `/user_profile` | GET/POST | yes | name read from `User`, not written here |
| `/gym_profile` | GET | yes | latest profile |
| `/workout_sessions`, `/workout_sessions/{id}` | GET | yes | paginated list / detail |
| `/workout_history_summaries` | GET | yes | latest, optional range filter |
| `/chat_messages` | GET | yes | expires old, filters soft-deleted |

## Adding a route (recipe)

1. Add the file to `app/routes/`, define `router = APIRouter()`, register it in `app/main.py`.
2. Define the request schema in `app/schemas/`; for AI routes add `test`/`debug` flags and a `MOCK_PATH`.
3. AI route body: `load_prompt → call_llm → extract_json_content → persist → build_response`.
4. Add the prompt to `prompts/<name>.txt` and a fixture to `data/mock/<endpoint>.json`.
5. Depend on `get_current_user` and `get_db`. Keep LLM/persistence logic in `services/`.
6. Schema change? Update `app/db/models.py` and re-run `scripts/utils/initialize_sql_tables.py` (no migrations).
