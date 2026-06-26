# ResQBites Backend

FastAPI backend for **ResQBites — Saving Food, Feeding Hope**: a mobile platform
(Flutter client) that reduces food waste in Cebu City. Individuals and
establishments donate surplus food; **LGUs/barangays** receive it, manage it as
community food banks, and distribute it to beneficiaries. Donors earn points and
badges for completed donations.

> No AI/LLM components — this is a plain CRUD + workflow API.
>
> Building the Flutter client? See **[ARCHITECTURE.md](ARCHITECTURE.md)** for the
> full endpoint reference, request/response schemas, enums, and auth model.

## Stack

- **FastAPI** (async) + **uvicorn**
- **SQLAlchemy 2.0** async + **SQLite** (`aiosqlite`) — single file, no DB server
- **JWT** auth (`python-jose`, HS256) + **bcrypt** (`passlib`)
- Config via `os.getenv` + `python-dotenv`

## Quickstart

```bash
# 1. Create + activate a virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure (optional — sensible defaults exist)
copy .env.example .env          # Windows;  cp on macOS/Linux

# 4. Initialise + seed the database
python scripts/utils/init_db.py
python scripts/utils/seed.py

# 5. Run the dev server
uvicorn app.main:app --reload
```

Open the interactive API docs at **http://127.0.0.1:8000/docs**.

> On Windows, if `python` resolves to the wrong interpreter, call the venv one
> directly: `.\venv\Scripts\python.exe <script>`.

### Seeded accounts (from `seed.py`)

| Role  | Email                          | Password    |
|-------|--------------------------------|-------------|
| Admin | `admin@resqbites.org`          | `admin12345`|
| LGU   | `lgu.lahug@resqbites.org`      | `lgu12345`  |

Donor accounts are created via `POST /auth/signup`. (Emails must use a valid
public domain — reserved TLDs like `.local` are rejected by the email validator.)

## Try the core flow

1. `POST /auth/signup` → `{ "email", "password", "role": "individual" }` → copy `token`.
2. `POST /onboarding/individual` (Bearer token).
3. `POST /donations` with `donation_method: "dropoff"`.
4. Log in as the seeded LGU account → `POST /lgu/donations/{id}/accept` → `/schedule` → `/complete`.
5. Back as the donor: `GET /users/me/points` shows the awarded points; `GET /notifications` shows updates.

Authenticate in Swagger by sending the header `Authorization: Bearer <token>` (the
`/docs` "Authorize" button, or pass it per request).

## Project layout

```
app/
├── main.py            # entrypoint + public auth endpoints (signup/login/logout)
├── core/              # config, auth dependencies (get_current_user, require_role)
├── db/                # async engine/session + ORM models
├── routes/            # one router per resource (donations, lgu, admin, ...)
├── schemas/           # Pydantic request/response models
└── services/          # security, history, notifications, gamification
scripts/utils/         # init_db.py, seed.py
tests/
├── smoke/             # in-process pytest (fast, no server)
└── blackbox/          # live-server scripts that hit http://localhost:8000
results/               # JSON logs produced by the black-box suite (gitignored)
```

## Roles & access

| Role            | Capabilities                                                         |
|-----------------|---------------------------------------------------------------------|
| `individual`    | Donate (dropoff only), track, history, points/badges, nearby LGUs   |
| `establishment` | Donate (pickup or dropoff) + everything an individual can do         |
| `lgu`           | Manage donation queue, inventory, beneficiaries, distribution, reports |
| `admin`         | Manage users/LGUs, verify LGUs, reward rules, settings, audit logs  |

LGU accounts must be linked to an `LGU` record via `managing_lgu_id`. **There is no
HTTP endpoint for this linkage** — it is done by `seed.py` (or a direct DB write).
A freshly self-registered LGU account cannot act until linked.

## Testing

Two complementary suites — see [ARCHITECTURE.md](ARCHITECTURE.md#test-suites) for
how each works internally.

### 1. Smoke tests — `tests/smoke/` (fast, in-process, no server)

pytest runs the app through an ASGI transport against a fresh throwaway SQLite DB
per test. Nothing external required.

```bash
pytest                          # or:  .\venv\Scripts\python.exe -m pytest -q
```

Expected: `4 passed`. (Two harmless deprecation/bcrypt warnings are normal.)
The `pytest.ini` `testpaths = tests/smoke` ensures only this suite is collected.

### 2. Black-box tests — `tests/blackbox/` (live server, produces logs)

Standalone scripts that hit a **real running server** over HTTP and write a
timestamped JSON log per run into `results/<type>_results/`. This is what catches
issues the in-process suite can't (real HTTP, real serialization, seeded accounts).

**Prerequisites:** a seeded DB and a running server.

```bash
# Terminal 1 — start the server
python scripts/utils/init_db.py
python scripts/utils/seed.py
uvicorn app.main:app                 # serves http://localhost:8000

# Terminal 2 — run any/all scripts
python tests/blackbox/test_auth.py
python tests/blackbox/test_individual_cannot_pickup.py
python tests/blackbox/test_role_gating.py
python tests/blackbox/test_donation_loop.py          # needs the seeded LGU
python tests/blackbox/test_lgu_workflow.py           # needs the seeded LGU
```

Each script prints a one-line summary, e.g.
`[PASS] auth run=ef59ddcc -> results/auth_results/2026-06-24T08-21-36_ef59ddcc.json`,
exits `0` on pass / `1` on fail, and always writes a JSON log (steps, status codes,
trimmed request/response, overall result). If the server is unreachable it writes an
`UNREACHABLE` log and exits `2` — no traceback. Re-runs never collide (each generates
unique test emails).

| Script | Asserts |
|--------|---------|
| `test_auth` | signup, login, token use, wrong-password 401, no-token 401 |
| `test_individual_cannot_pickup` | individuals cannot use `donation_method=pickup` (400) |
| `test_role_gating` | donor token barred from LGU (403) and admin (403) endpoints |
| `test_donation_loop` | full lifecycle + points + notification + history audit trail |
| `test_lgu_workflow` | LGU login, pending/inventory/analytics, beneficiary→inventory→distribution |

## Notes

- **No migrations.** Change `app/db/models.py`, then re-run `scripts/utils/init_db.py`.
- **Photos** are stored as base64 text on the donation row; list endpoints omit the
  photo payload (`DonationSummary`) and only the detail endpoint returns it.
- **Logout** is a client-side token discard — `POST /auth/logout` is a no-op (JWTs
  are stateless).
- To move to MySQL/Postgres later, change `DB_URL` and the driver in
  `requirements.txt`; the async SQLAlchemy layer is unchanged.
