# CLAUDE.md

Guidance for working in this repository.

## What this is

Backend for **ResQBites**, a food-donation platform for Cebu City (Flutter mobile
client). Donors (individuals/establishments) post surplus food; **LGUs** receive,
manage, and distribute it; donors earn points/badges. **No AI/LLM** — plain CRUD +
workflow API. The structure follows `references/ARCHITECTURE.md` with all AI parts
removed.

## Stack & conventions

- FastAPI (async) + SQLAlchemy 2.0 async + SQLite (`aiosqlite`).
- JWT HS256 (`python-jose`) + bcrypt (`passlib`). Config via `os.getenv` + dotenv.
- Routes are **thin orchestrators**; cross-cutting logic lives in `app/services/`
  (`history.py`, `notifications.py`, `gamification.py`, `security.py`).
- Routers are registered in `app/main.py` with **no prefix** — each route declares
  its own full path. Public endpoints (`/`, `/health`, `/auth/*`) are inline in
  `main.py`.
- **No migrations.** Edit `app/db/models.py`, then re-run `scripts/utils/init_db.py`.
- All ORM models live in the single file `app/db/models.py`. `created_at` uses
  `server_default=func.now()`; categorical columns use SQL `Enum`; structured
  fields use `JSON`.

## Auth & roles

- `app/core/auth.py`: `get_current_user` (Bearer JWT → `User`) and
  `require_role(*roles)` (403 on mismatch). Bundles: `require_donor`, `require_lgu`,
  `require_admin`.
- Roles: `individual`, `establishment`, `lgu`, `admin`. LGU accounts act on behalf
  of the `LGU` referenced by `User.managing_lgu_id`.
- Self-registration (`/auth/signup`) is limited to donors and LGU; admins are seeded.

## Domain rules to preserve

- Donation lifecycle: `pending → accepted → scheduled → completed`, with
  `rejected` (from pending) and `cancelled` (from pending/accepted). Each transition
  writes a `DonationHistory` row via `services/history.record(...)` and usually a
  notification.
- **Individuals drop off only** (`donation_method=dropoff`, no `pickup_location`);
  establishments may pick up or drop off. Enforced in `app/routes/donations.py`.
- On `complete`, the LGU route awards points/badges via
  `services/gamification.award_for_completion(...)` and creates an `InventoryItem`.
- Photos are base64 in `Donation.photo_base64`; list views use `DonationSummary`
  (no photo) — keep the heavy payload off list endpoints.

## Commands

```bash
pip install -r requirements.txt
python scripts/utils/init_db.py     # create tables
python scripts/utils/seed.py        # admin + LGU + badges + reward rule
uvicorn app.main:app --reload       # dev server → /docs
pytest                              # end-to-end tests
```

## Service helpers do not commit

`history.record`, `notifications.notify`, and the gamification helpers add to the
session but leave the **commit to the calling route**. Keep that contract when
adding new flows.

## Map to requirements

Feature scope tracks `references/functionality_list.csv` (the authoritative list);
each route file notes the relevant CSV item numbers in its docstring/comments.
