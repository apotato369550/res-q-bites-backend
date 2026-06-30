# ResQBites API — Run & Use Guide

Practical guide to running the backend locally and calling it with **curl** or
**JavaScript** (`fetch`). For the full endpoint/schema reference see
[ARCHITECTURE.md](ARCHITECTURE.md); for the data model see
[ENTITY_RELATIONSHIPS.md](ENTITY_RELATIONSHIPS.md).

- [1. Run it locally](#1-run-it-locally)
- [2. Basics (base URL, auth, errors)](#2-basics)
- [3. Seeded accounts](#3-seeded-accounts)
- [4. Donor flow (curl)](#4-donor-flow-curl)
- [5. LGU flow (curl)](#5-lgu-flow-curl)
- [6. JavaScript (fetch)](#6-javascript-fetch)

---

## 1. Run it locally

```bash
# 1. Virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

# 2. Dependencies
pip install -r requirements.txt

# 3. Create tables + seed baseline data (admin + demo LGU + LGU account)
python scripts/utils/init_db.py
python scripts/utils/seed.py

# 4. Start the dev server
uvicorn app.main:app --reload
```

The server runs at **http://127.0.0.1:8000**. Interactive Swagger UI is at
**http://127.0.0.1:8000/docs** — you can try every endpoint there without curl.

> Windows note: if `python` resolves to the wrong interpreter, use the venv one
> directly: `.\venv\Scripts\python.exe scripts/utils/seed.py`.

Quick health check:

```bash
curl http://127.0.0.1:8000/health
# {"status":"healthy"}
```

## 2. Basics

- **Base URL:** `http://127.0.0.1:8000` — no path prefix; every endpoint is a full path.
- **Format:** JSON in, JSON out. Send `Content-Type: application/json` on requests with a body.
- **Auth:** log in to get a JWT `token`, then send it as a header on every protected call:
  `Authorization: Bearer <token>`. There is no refresh token — on `401`, log in again.
- **Errors:** error bodies are `{ "detail": "<message>" }`. Validation errors (`422`)
  use FastAPI's shape: `{ "detail": [ { "loc": [...], "msg": "...", "type": "..." } ] }`.
- **Common status codes:** `401` missing/invalid token · `403` wrong role · `400`
  domain-rule violation · `404` not found / not yours · `409` conflict (duplicate
  email, illegal state transition, insufficient inventory) · `422` bad request body.

> Emails must use a valid public domain. Reserved TLDs like `.local` are rejected by
> the validator — use e.g. `@example.com` in tests.

## 3. Seeded accounts

| Role  | Email                     | Password    |
|-------|---------------------------|-------------|
| Admin | `admin@resqbites.org`     | `admin12345`|
| LGU   | `lgu.lahug@resqbites.org` | `lgu12345`  |

Donor accounts are created with `POST /auth/signup`.

## 4. Donor flow (curl)

The examples below capture the token into a shell variable. On Windows use Git Bash
(the project's Bash shell) so these work as written.

```bash
BASE=http://127.0.0.1:8000

# 1. Sign up as an individual donor → returns a token
TOKEN=$(curl -s -X POST $BASE/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"juan@example.com","password":"password123","role":"individual"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['token'])")

# 2. Fill in the profile
curl -s -X POST $BASE/onboarding/individual \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"first_name":"Juan","last_name":"Cruz"}'

# 3. Create a drop-off donation (individuals must drop off)
curl -s -X POST $BASE/donations \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
        "title":"Surplus rice meals",
        "food_category":"cooked_meal",
        "donation_method":"dropoff",
        "dropoff_location":"Lahug LGU",
        "quote":"Share a meal, share hope."
      }'

# 4. List my donations / my completed history / notifications
curl -s $BASE/donations/my          -H "Authorization: Bearer $TOKEN"
curl -s $BASE/donations/history     -H "Authorization: Bearer $TOKEN"
curl -s $BASE/notifications         -H "Authorization: Bearer $TOKEN"
```

**Establishment donor?** Sign up with `"role":"establishment"`, onboard with
`POST /onboarding/establishment` (`establishment_name`, `establishment_type`, …), and
you may use `"donation_method":"pickup"` with a `pickup_location`.

## 5. LGU flow (curl)

Log in as the seeded LGU account, work the donation queue, then manage inventory and
distributions.

```bash
BASE=http://127.0.0.1:8000

# 1. Log in as the seeded LGU
LGU=$(curl -s -X POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"lgu.lahug@resqbites.org","password":"lgu12345"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['token'])")

# 2. See pending donations (unassigned, or directed at this LGU)
curl -s $BASE/lgu/donations/pending -H "Authorization: Bearer $LGU"

# 3. Move one donation through the lifecycle (replace 1 with a real id)
curl -s -X POST $BASE/lgu/donations/1/accept   -H "Authorization: Bearer $LGU"
curl -s -X POST $BASE/lgu/donations/1/schedule -H "Authorization: Bearer $LGU" \
  -H "Content-Type: application/json" -d '{"scheduled_pickup_at":"2026-07-01T09:00:00"}'
curl -s -X POST $BASE/lgu/donations/1/complete -H "Authorization: Bearer $LGU"
# completing creates an inventory item from the donation

# 4. Register a beneficiary and add an inventory item
curl -s -X POST $BASE/lgu/beneficiaries -H "Authorization: Bearer $LGU" \
  -H "Content-Type: application/json" \
  -d '{"name":"Dela Cruz Family","household_size":4,"barangay":"Lahug"}'

curl -s -X POST $BASE/lgu/inventory -H "Authorization: Bearer $LGU" \
  -H "Content-Type: application/json" \
  -d '{"food_category":"mixed","quantity":10,"unit":"meals"}'

# 5. Record a distribution: one inventory item → one beneficiary (replace ids)
curl -s -X POST $BASE/lgu/distributions -H "Authorization: Bearer $LGU" \
  -H "Content-Type: application/json" \
  -d '{"beneficiary_id":1,"inventory_item_id":1,"quantity":3}'

# 6. Analytics
curl -s $BASE/lgu/analytics -H "Authorization: Bearer $LGU"
```

## 6. JavaScript (fetch)

Works in the browser or Node 18+ (global `fetch`). Same flow as above.

```js
const BASE = "http://127.0.0.1:8000";

// Helper: JSON request with optional bearer token
async function api(method, path, { token, body } = {}) {
  const res = await fetch(BASE + path, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`${res.status}: ${JSON.stringify(await res.json())}`);
  return res.json();
}

// 1. Sign up + onboard a donor
const { token } = await api("POST", "/auth/signup", {
  body: { email: "juan@example.com", password: "password123", role: "individual" },
});
await api("POST", "/onboarding/individual", {
  token,
  body: { first_name: "Juan", last_name: "Cruz" },
});

// 2. Create a donation
const donation = await api("POST", "/donations", {
  token,
  body: {
    title: "Surplus rice meals",
    food_category: "cooked_meal",
    donation_method: "dropoff",
    dropoff_location: "Lahug LGU",
  },
});
console.log("created donation", donation.id, donation.status);

// 3. Read back lists
const mine = await api("GET", "/donations/my", { token });
const notifications = await api("GET", "/notifications", { token });
console.log(mine.length, "donations,", notifications.length, "notifications");
```

> Enum fields (`role`, `food_category`, `donation_method`, `status`, …) are the exact
> lowercase strings listed in [ARCHITECTURE.md §6](ARCHITECTURE.md#6-data-model--enums).
