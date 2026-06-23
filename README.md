# ResQBites Backend

FastAPI backend for **ResQBites — Saving Food, Feeding Hope**: a mobile platform
(Flutter client) that reduces food waste in Cebu City. Individuals and
establishments donate surplus food; **LGUs/barangays** receive it, manage it as
community food banks, and distribute it to beneficiaries. Donors earn points and
badges for completed donations.

> No AI/LLM components — this is a plain CRUD + workflow API.

## Stack

- **FastAPI** (async) + **uvicorn**
- **SQLAlchemy 2.0** async + **SQLite** (`aiosqlite`) — single file, no DB server
- **JWT** auth (`python-jose`, HS256) + **bcrypt** (`passlib`)
- Config via `os.getenv` + `python-dotenv`

## Quickstart

```bash
# 1. Create a virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure (optional — sensible defaults exist)
cp .env.example .env        # Windows: copy .env.example .env

# 4. Initialise + seed the database
python scripts/utils/init_db.py
python scripts/utils/seed.py

# 5. Run the dev server
uvicorn app.main:app --reload
```

Open the interactive API docs at **http://127.0.0.1:8000/docs**.

### Seeded accounts (from `seed.py`)

| Role  | Email                          | Password    |
|-------|--------------------------------|-------------|
| Admin | `admin@resqbites.local`        | `admin12345`|
| LGU   | `lgu.lahug@resqbites.local`    | `lgu12345`  |

Donor accounts are created via `POST /auth/signup`.

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
tests/                 # end-to-end flow tests
```

## Roles & access

| Role            | Capabilities                                                         |
|-----------------|---------------------------------------------------------------------|
| `individual`    | Donate (dropoff only), track, history, points/badges, nearby LGUs   |
| `establishment` | Donate (pickup or dropoff) + everything an individual can do         |
| `lgu`           | Manage donation queue, inventory, beneficiaries, distribution, reports |
| `admin`         | Manage users/LGUs, verify LGUs, reward rules, settings, audit logs  |

LGU accounts must be linked to an `LGU` record via `managing_lgu_id` (the seed
script does this; admins can set it through `/admin` endpoints).

## Build phases

- **Phase 1** — auth, onboarding, profiles, dashboard, notifications, donation
  lifecycle (`pending → accepted → scheduled → completed`/`rejected`/`cancelled`),
  history, nearby-LGU, points awarded on completion.
- **Phase 2** — food-safety validation, inventory, beneficiaries, distribution.
- **Phase 3** — gamification reads + badges, LGU/admin analytics & reports, full
  admin surface.

## Tests

```bash
pytest
```

Tests run against an isolated temporary SQLite file and exercise the full Phase-1
loop plus role-gating and auth checks.

## Notes

- **No migrations.** Change `app/db/models.py`, then re-run `scripts/utils/init_db.py`.
- **Photos** are stored as base64 text on the donation row; list endpoints omit the
  photo payload (`DonationSummary`) and only the detail endpoint returns it.
- **Logout** is a client-side token discard — `POST /auth/logout` is a no-op (JWTs
  are stateless).
- To move to MySQL/Postgres later, change `DB_URL` and the driver in
  `requirements.txt`; the async SQLAlchemy layer is unchanged.
