# ResQBites Backend — Architecture

Reference for understanding the service and building clients (the Flutter mobile
app in particular). Headings are stable and grep-able; jump to what you need.

- [1. Overview](#1-overview)
- [2. Stack & runtime](#2-stack--runtime)
- [3. Project layout](#3-project-layout)
- [4. Request lifecycle](#4-request-lifecycle)
- [5. Authentication & authorization](#5-authentication--authorization)
- [6. Data model & enums](#6-data-model--enums)
- [7. Domain rules](#7-domain-rules)
- [8. Endpoint reference](#8-endpoint-reference)
- [9. DTO / schema reference](#9-dto--schema-reference)
- [10. Conventions for the Flutter client](#10-conventions-for-the-flutter-client)
- [11. Test suites](#11-test-suites)

---

## 1. Overview

ResQBites routes surplus food **Donor → LGU → Beneficiary**:

- **Donors** (`individual` / `establishment`) post surplus food donations.
- **LGUs** (barangay-level government units) work a queue of incoming donations,
  accept/schedule/complete them, hold completed food as **inventory**, register
  **beneficiaries**, and record **distributions**.
- **Donors** earn **points** and **badges** when their donations complete.
- **Admins** manage users, LGUs, reward rules, settings, and audit logs.

It is a plain CRUD + workflow API — no AI/LLM.

## 2. Stack & runtime

| Concern | Choice |
|---------|--------|
| Web framework | FastAPI (async) on uvicorn |
| ORM | SQLAlchemy 2.0 async (`Mapped`/`mapped_column`) |
| Database | SQLite via `aiosqlite` (single file `resqbites.db`) |
| Auth | JWT HS256 (`python-jose`) + bcrypt password hashing (`passlib`) |
| Config | `os.getenv` + `.env` (dotenv) |
| Migrations | **None** — edit `app/db/models.py`, re-run `scripts/utils/init_db.py` |

**Config defaults** (`app/core/config.py`, override via env):

| Var | Default |
|-----|---------|
| `DB_URL` | `sqlite+aiosqlite:///./resqbites.db` |
| `JWT_SECRET` | `change-me-to-a-long-random-string` |
| `JWT_ALGORITHM` | `HS256` |
| `ACCESS_TOKEN_EXPIRE_HOURS` | `24` |
| `ADMIN_EMAIL` | `admin@resqbites.org` |
| `ADMIN_PASSWORD` | `admin12345` |

The async session factory uses **`expire_on_commit=False`** and `autoflush=False`
(`app/db/session.py`). This is load-bearing — see [§7](#7-domain-rules).

## 3. Project layout

```
app/
├── main.py            # app, public routes (/, /health, /auth/*), router registration
├── core/
│   ├── config.py      # env-backed settings
│   └── auth.py        # get_current_user, require_role, role bundles
├── db/
│   ├── models.py      # ALL ORM models + enums (single file)
│   └── session.py     # async engine, sessionmaker, get_db() dependency
├── routes/            # one router per resource; each declares its own full path
├── schemas/           # Pydantic request/response models
└── services/          # history, notifications, gamification, security
scripts/utils/         # init_db.py, seed.py
tests/smoke/           # in-process pytest
tests/blackbox/        # live-server scripts
results/               # black-box JSON logs (gitignored)
```

**Routers are registered with no prefix** (`app/main.py`); every route declares its
full path. Registered: `onboarding, users, dashboard, notifications, donations, lgu,
analytics, gamification, admin`.

## 4. Request lifecycle

```
HTTP request
  → FastAPI route (app/routes/*.py)         # thin orchestrator
    → Depends(get_current_user / require_*) # auth + role gate (app/core/auth.py)
    → Depends(get_db)                        # yields an AsyncSession (app/db/session.py)
    → service helpers (app/services/*)       # history.record, notifications.notify, gamification.*
    → db.commit()                            # the ROUTE commits, not the services
  → response_model (Pydantic) serializes the ORM object → JSON
```

Routes are intentionally thin; cross-cutting workflow logic lives in `services/`.

## 5. Authentication & authorization

- **Scheme:** stateless JWT bearer. `POST /auth/signup` and `POST /auth/login` both
  return an `AuthResponse` containing `token`. Send it on every protected request:
  `Authorization: Bearer <token>`.
- **Logout** (`POST /auth/logout`) is a no-op; the client simply discards the token.
- **Token claims:** `sub` = user id (string). Expires after `ACCESS_TOKEN_EXPIRE_HOURS`.
- **Resolution:** `get_current_user` decodes the token and loads the `User`; 401 on any
  failure. `require_role(*roles)` → 403 on mismatch. Bundles: `require_donor`
  (individual + establishment), `require_lgu`, `require_admin`.
- **Self-signup roles:** `individual`, `establishment`, `lgu` only. `admin` is seeded.
- **LGU linkage:** an `lgu` user acts on behalf of the `LGU` in `User.managing_lgu_id`.
  **No HTTP endpoint sets this** — `seed.py` (or a direct DB write) links the account.
  An unlinked LGU user gets a 400 on LGU actions. (The seeded LGU account is linked.)

**Status codes a client must handle:** `401` (missing/invalid/expired token),
`403` (wrong role), `400` (domain-rule violation), `404` (not found / not yours),
`409` (conflict — e.g. duplicate email, illegal state transition, insufficient
inventory), `422` (request body/validation error, including invalid email domains).

## 6. Data model & enums

Core entities (all in `app/db/models.py`): `User`, `EstablishmentProfile`, `LGU`,
`BarangayCoverage`, `Donation`, `DonationHistory`, `Notification`, `InventoryItem`,
`Beneficiary`, `Distribution`, `DistributionItem`, `Badge`, `UserBadge`,
`PointsLedger`, `RewardRule`, `Setting`, `AuditLog`.

Relationships relevant to clients: `User 1—0..1 EstablishmentProfile`;
`User 1—* Donation`; `Donation 1—* DonationHistory`; `LGU 1—* InventoryItem /
Beneficiary / Distribution`; `Distribution 1—* DistributionItem`.

**Enums (exact string values — the API accepts/returns these literal strings):**

| Enum | Values |
|------|--------|
| `UserRole` | `individual`, `establishment`, `lgu`, `admin` |
| `EstablishmentType` | `restaurant`, `hotel`, `grocery`, `bakery`, `catering`, `other` |
| `FoodCategory` | `cooked_meal`, `baked_goods`, `vegetables`, `fruits`, `canned_goods`, `mixed` |
| `DonationMethod` | `pickup`, `dropoff` |
| `DonationStatus` | `pending`, `accepted`, `scheduled`, `rejected`, `completed`, `cancelled` |
| `FoodSafetyStatus` | `pending`, `passed`, `failed` |
| `InventoryStatus` | `in_stock`, `distributed`, `expired` |

## 7. Domain rules

- **Donation lifecycle:**
  `pending → accepted → scheduled → completed`, with `rejected` (from `pending`) and
  `cancelled` (from `pending` or `accepted`). Illegal transitions return `409`.
  Every transition writes a `DonationHistory` row and usually a notification.
- **Individuals drop off only:** `individual` donors must use
  `donation_method=dropoff` with no `pickup_location` (else `400`). `establishment`
  donors may pick up or drop off; `pickup` requires `pickup_location`.
- **On `complete`:** the LGU route awards points/badges
  (`gamification.award_for_completion`, default 10 pts via the active `RewardRule`)
  and creates an `InventoryItem` from the donation.
- **Editing:** only `pending` donations can be edited (`PUT`) — else `409`.
- **Photos:** base64 in `Donation.photo_base64`. List endpoints return
  `DonationSummary` (no photo); only the detail endpoint returns the full payload.
- **Service helpers don't commit:** `history.record`, `notifications.notify`, and the
  gamification helpers add to the session; the **calling route commits**.
- **`expire_on_commit=False` caveat (for backend devs):** after `db.commit()`, a route
  that returns an ORM object whose `response_model` includes a **relationship** must
  re-load it eagerly *and* force it, e.g.
  `await db.get(Model, id, options=[selectinload(Model.rel)], populate_existing=True)`.
  Without `populate_existing=True` the cached instance is returned with the
  relationship unloaded → `MissingGreenlet` 500 on serialize. (See `users.py`,
  `onboarding.py`, `lgu.py` distribution route for the correct pattern.)

## 8. Endpoint reference

No global prefix. Auth column: `—` public, `Bearer` any authenticated user, or the
required role. Request/response names link to [§9](#9-dto--schema-reference).

### Meta

| Method | Path | Auth | Response |
|--------|------|------|----------|
| GET | `/` | — | `{service, status}` |
| GET | `/health` | — | `{status: "healthy"}` |

### Auth (`app/main.py`)

| Method | Path | Auth | Request | Response | Notes |
|--------|------|------|---------|----------|-------|
| POST | `/auth/signup` | — | `SignupRequest` | `AuthResponse` (200) | 409 if email taken; 422 invalid email/short password |
| POST | `/auth/login` | — | `LoginRequest` | `AuthResponse` (200) | 401 bad creds |
| POST | `/auth/logout` | — | — | `Message` (200) | client discards token |

### Onboarding

| Method | Path | Auth | Request | Response |
|--------|------|------|---------|----------|
| POST | `/onboarding/individual` | individual | `IndividualOnboarding` | `UserOut` (200) |
| POST | `/onboarding/establishment` | establishment | `EstablishmentOnboarding` | `UserOut` (200) |

### Users / profile

| Method | Path | Auth | Request | Response |
|--------|------|------|---------|----------|
| GET | `/users/me` | Bearer | — | `UserOut` |
| PUT | `/users/me` | Bearer | `UserUpdate` | `UserOut` |
| GET | `/users/me/points` | donor | — | `PointsSummary` |
| GET | `/users/me/badges` | donor | — | `list[UserBadgeOut]` |
| GET | `/badges` | Bearer | — | `list[BadgeOut]` (catalog) |

### Dashboard

| Method | Path | Auth | Response |
|--------|------|------|----------|
| GET | `/dashboard` | Bearer | role-dependent dict (donor / lgu / admin shapes) |

### Donations (donor side)

| Method | Path | Auth | Request | Response | Notes |
|--------|------|------|---------|----------|-------|
| POST | `/donations` | donor | `DonationCreate` | `DonationOut` (201) | dropoff/pickup rules apply (400) |
| GET | `/donations/my` | donor | `?status=` | `list[DonationSummary]` | own donations |
| GET | `/donations/history` | donor | — | `list[DonationSummary]` | completed only |
| GET | `/donations/{id}` | Bearer | — | `DonationOut` | full payload incl. photo |
| GET | `/donations/{id}/history` | Bearer | — | `list[DonationHistoryOut]` | audit trail |
| PUT | `/donations/{id}` | donor | `DonationUpdate` | `DonationOut` | 409 unless `pending` |
| DELETE | `/donations/{id}` | donor | — | `Message` | cancel; 409 unless pending/accepted |

### Donation queue (LGU side)

| Method | Path | Auth | Request | Response | Result |
|--------|------|------|---------|----------|--------|
| GET | `/lgu/donations` | lgu | `?status=` | `list[DonationSummary]` | |
| GET | `/lgu/donations/pending` | lgu | — | `list[DonationSummary]` | unassigned or this LGU |
| POST | `/lgu/donations/{id}/accept` | lgu | `ActionNote` (optional) | `DonationOut` | → `accepted` |
| POST | `/lgu/donations/{id}/reject` | lgu | `ActionNote` (optional) | `DonationOut` | → `rejected` |
| POST | `/lgu/donations/{id}/schedule` | lgu | `ScheduleRequest` | `DonationOut` | → `scheduled` |
| POST | `/lgu/donations/{id}/complete` | lgu | `ActionNote` (optional) | `DonationOut` | → `completed`, awards points + inventory |
| POST | `/lgu/donations/{id}/food-safety` | lgu | `FoodSafetyRequest` | `Message` | records result |

### LGU inventory / beneficiaries / distribution

| Method | Path | Auth | Request | Response |
|--------|------|------|---------|----------|
| GET | `/lgu/inventory` | lgu | `?status=` | `list[InventoryItemOut]` |
| POST | `/lgu/inventory` | lgu | `InventoryItemCreate` | `InventoryItemOut` (201) |
| PUT | `/lgu/inventory/{id}` | lgu | `InventoryItemUpdate` | `InventoryItemOut` |
| DELETE | `/lgu/inventory/{id}` | lgu | — | `Message` |
| GET | `/lgu/beneficiaries` | lgu | — | `list[BeneficiaryOut]` |
| POST | `/lgu/beneficiaries` | lgu | `BeneficiaryCreate` | `BeneficiaryOut` (201) |
| PUT | `/lgu/beneficiaries/{id}` | lgu | `BeneficiaryUpdate` | `BeneficiaryOut` |
| DELETE | `/lgu/beneficiaries/{id}` | lgu | — | `Message` |
| GET | `/lgu/distributions` | lgu | — | `list[DistributionOut]` |
| GET | `/lgu/distributions/{id}` | lgu | — | `DistributionOut` |
| POST | `/lgu/distributions` | lgu | `DistributionCreate` | `DistributionOut` (201) | 409 insufficient qty |

### LGU analytics

| Method | Path | Auth | Response |
|--------|------|------|----------|
| GET | `/lgu/analytics` | lgu | `{donations_by_status, donations_by_category, in_stock_items, total_distributions, total_beneficiaries}` |
| GET | `/lgu/reports` | lgu | `{lgu_id, completed_donations, completed_by_category}` |

### Nearby LGUs

| Method | Path | Auth | Query | Response |
|--------|------|------|-------|----------|
| GET | `/lgus/nearby` | donor | `lat` (req), `lng` (req), `limit` (≤50) | `list[LGUNearbyOut]` (sorted by `distance_km`) |

### Notifications

| Method | Path | Auth | Query | Response |
|--------|------|------|-------|----------|
| GET | `/notifications` | Bearer | `unread_only` (bool) | `list[NotificationOut]` |
| POST | `/notifications/{id}/read` | Bearer | — | `Message` |

### Admin

| Method | Path | Auth | Request | Response |
|--------|------|------|---------|----------|
| GET | `/admin/users` | admin | `?role=` | `list[AdminUserOut]` |
| GET | `/admin/users/{id}` | admin | — | `AdminUserOut` |
| PUT | `/admin/users/{id}` | admin | `AdminUserUpdate` | `AdminUserOut` |
| GET | `/admin/lgus` | admin | — | `list[LGUOut]` |
| POST | `/admin/lgus` | admin | `LGUCreate` | `LGUOut` (201) |
| PUT | `/admin/lgus/{id}` | admin | `LGUUpdate` | `LGUOut` |
| POST | `/admin/lgus/{id}/verify` | admin | — | `LGUOut` |
| GET | `/admin/analytics` | admin | — | system-wide dict |
| GET / POST | `/admin/reward-rules` | admin | `RewardRuleCreate` | `RewardRuleOut` |
| PUT | `/admin/reward-rules/{id}` | admin | `RewardRuleUpdate` | `RewardRuleOut` |
| GET / POST | `/admin/barangay-coverage` | admin | `BarangayCoverageCreate` | `BarangayCoverageOut` |
| DELETE | `/admin/barangay-coverage/{id}` | admin | — | `Message` |
| GET | `/admin/settings` | admin | — | `list[SettingOut]` |
| PUT | `/admin/settings` | admin | `SettingUpsert` | `SettingOut` |
| GET | `/admin/audit-logs` | admin | `limit` (≤500) | `list[AuditLogOut]` |

## 9. DTO / schema reference

Field notation: `type` (required) · `type?` (optional / nullable) · `= x` (default).
Datetimes are ISO-8601 strings. Enums are the literal strings from [§6](#6-data-model--enums).

### Auth (`app/schemas/auth.py`)

```
SignupRequest      { email, password(8–128), role=individual, first_name?, last_name?, phone? }
LoginRequest       { email, password }
AuthResponse       { user_id:int, email, role:UserRole, token:str }
IndividualOnboarding     { first_name, last_name, phone? }
EstablishmentOnboarding  { establishment_name, establishment_type:EstablishmentType, address?, phone? }
```

### Users (`app/schemas/user.py`)

```
EstablishmentProfileOut { establishment_name, establishment_type, address?, verified:bool }
UserOut   { id:int, email, role:UserRole, first_name?, last_name?, phone?, is_active:bool,
            points_balance:int, managing_lgu_id?:int, created_at:datetime,
            establishment_profile?:EstablishmentProfileOut }
UserUpdate       { first_name?, last_name?, phone? }
NotificationOut  { id:int, title, message?, is_read:bool, created_at:datetime }
```

### Donations (`app/schemas/donation.py`)

```
DonationCreate  { title, description?, quantity?, food_category:FoodCategory, quote?,
                  photo_base64?, donation_method:DonationMethod, pickup_location?,
                  dropoff_location?, lgu_id?:int }
DonationUpdate  { same fields, all optional }
DonationOut     { id, donor_id, lgu_id?, title, description?, quantity?, food_category,
                  quote?, photo_base64?, donation_method, pickup_location?,
                  dropoff_location?, status:DonationStatus, scheduled_pickup_at?:datetime,
                  created_at, updated_at }
DonationSummary { id, donor_id, lgu_id?, title, food_category, donation_method,
                  status, scheduled_pickup_at?, created_at }            # NO photo
DonationHistoryOut { id, action:str, notes?, actor_id?:int, created_at }
ScheduleRequest { scheduled_pickup_at:datetime, notes? }
ActionNote      { notes? }
LGUOut          { id, name, address?, contact_number?, barangay?, latitude?:float,
                  longitude?:float, verified:bool }
LGUNearbyOut    { ...LGUOut, distance_km?:float }
```

### LGU ops (`app/schemas/lgu_ops.py`)

```
FoodSafetyRequest   { result:FoodSafetyStatus, notes? }
InventoryItemCreate { food_category, quantity:float=0, unit?, donation_id?:int,
                      expiry_date?:datetime, food_safety_status:FoodSafetyStatus=pending }
InventoryItemUpdate { quantity?, unit?, food_safety_status?, expiry_date?, status?:InventoryStatus }
InventoryItemOut    { id, lgu_id, donation_id?, food_category, quantity:float, unit?,
                      food_safety_status, expiry_date?, status:InventoryStatus, received_at:datetime }
BeneficiaryCreate   { name, household_size?:int, barangay?, address?, contact?, notes? }
BeneficiaryUpdate   { all optional }
BeneficiaryOut      { id, lgu_id, name, household_size?, barangay?, address?, contact?, notes?, created_at }
DistributionItemIn  { inventory_item_id:int, quantity:float(>0) }
DistributionCreate  { beneficiary_id:int, notes?, items:[DistributionItemIn] }
DistributionItemOut { id, inventory_item_id, quantity:float }
DistributionOut     { id, lgu_id, beneficiary_id, recorded_by?:int, notes?,
                      distributed_at:datetime, items:[DistributionItemOut]=[] }
```

### Gamification & admin (`app/schemas/admin.py`)

```
PointsLedgerOut { id, donation_id?:int, points:int, reason?, created_at }
PointsSummary   { balance:int, entries:[PointsLedgerOut] }
BadgeOut        { id, code, name, description?, threshold_points:int }
UserBadgeOut    { badge:BadgeOut, awarded_at:datetime }
AdminUserOut    { id, email, role:str, first_name?, last_name?, is_active:bool,
                  points_balance:int, created_at }
AdminUserUpdate { is_active?, role? }              # note: cannot set managing_lgu_id
LGUCreate / LGUUpdate          { name, address?, contact_number?, barangay?, latitude?, longitude? [, verified?] }
RewardRuleCreate { name, points_per_donation:int=10, active:bool=True }
RewardRuleOut    { id, name, points_per_donation, active, created_at }
BarangayCoverageCreate { lgu_id:int, barangay }    BarangayCoverageOut { id, lgu_id, barangay }
SettingUpsert  { key, value:any }                  SettingOut { key, value?:any }
AuditLogOut    { id, actor_id?, action, entity_type?, entity_id?:int, detail?:any, created_at }
```

### Common (`app/schemas/common.py`)

```
Message { detail:str }      # all simple action confirmations and many error bodies
```

## 10. Conventions for the Flutter client

- **Base URL:** `http://<host>:8000`, no path prefix. Dev: `http://localhost:8000`
  (Android emulator: `http://10.0.2.2:8000`).
- **Auth header:** `Authorization: Bearer <token>` on every protected call. Persist the
  `token` from `AuthResponse` (e.g. secure storage); there is no refresh endpoint —
  on `401`, send the user back to login.
- **Content type:** JSON in and out. `422` bodies are FastAPI validation errors:
  `{ "detail": [ { "loc": [...], "msg": "...", "type": "..." } ] }`. Other errors are
  `{ "detail": "<message>" }`. Code against both shapes.
- **Enums are strings** exactly as in [§6](#6-data-model--enums) — model them as Dart
  enums with explicit string mappings.
- **Datetimes** are ISO-8601 strings; parse with `DateTime.parse`.
- **List vs detail:** list endpoints return `DonationSummary` (no `photo_base64`);
  fetch `GET /donations/{id}` for the photo. Keep big base64 off list screens.
- **Role-aware UI:** `UserOut.role` drives navigation. `lgu` users also carry
  `managing_lgu_id`; if null, LGU features will 400 (account not yet linked).
- **Money/quantity:** `quantity` on a donation is free-text (`str?`); inventory/
  distribution `quantity` is numeric (`float`).
- **Generate models from OpenAPI:** the server exposes a live schema at
  `http://localhost:8000/openapi.json` (and Swagger at `/docs`). You can drive a Dart
  model/codegen tool from that instead of hand-writing every DTO in [§9](#9-dto--schema-reference).

## 11. Test suites

Two suites by kind. See [README.md](README.md#testing) for commands.

### Smoke (`tests/smoke/`) — in-process, fast

pytest with `pytest-asyncio`. `conftest.py` sets `DB_URL` to a throwaway temp SQLite
file *before* importing the app, then drops/recreates all tables before each test
(`_fresh_db` autouse fixture) and yields an httpx `AsyncClient` bound to the ASGI app
(`client` fixture) — **no network, no running server**. `pytest.ini` scopes collection
to `tests/smoke`. Run with `pytest` → `4 passed`.

### Black-box (`tests/blackbox/`) — live server, log-producing

Standalone scripts (run directly, **not** via pytest) that hit a real server over
HTTP and write a JSON log per run. Shared helper `_client.py` provides:

- `BASE_URL`, `SEEDED_LGU`, `SEEDED_ADMIN` constants.
- `new_run_id()`, `unique_email(prefix, run_id)`, `auth_header(token)`.
- `Run(test_name, results_subfolder)` — on construction pings `/health` and
  `sys.exit(2)`s with an `UNREACHABLE` log if the server is down. Methods:
  `call(method, path, *, expect, token=None, json=None, params=None)` records a step
  and returns the response; `check(name, condition, detail=None)` records a non-HTTP
  assertion; `finish()` writes `results/<subfolder>/<date>_<run_id>.json` and returns
  `0`/`1`.

Log shape: `{ run_id, test, base_url, started_at, finished_at, result, steps[], failure }`.
Tokens are redacted and long values truncated in logs. Each run uses unique emails, so
re-runs never collide on the shared DB. **Prerequisite:** seeded DB + running server;
the LGU-touching scripts log in as the seeded LGU account.

These two suites are complementary: smoke proves the app logic in isolation; black-box
proves the *deployed* surface (real HTTP, serialization, seeded data, auth headers).
