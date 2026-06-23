"""End-to-end Phase-1 donation loop + gamification side effects."""
import pytest
from sqlalchemy import select

from app.db.models import LGU, User, UserRole
from app.db.session import AsyncSessionLocal


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _make_lgu_account(email: str) -> None:
    """Create an LGU record and link the LGU user account to it."""
    async with AsyncSessionLocal() as db:
        lgu = LGU(name="Test LGU", barangay="Lahug", verified=True,
                  latitude=10.334, longitude=123.90)
        db.add(lgu)
        await db.flush()
        user = (await db.execute(select(User).where(User.email == email))).scalars().first()
        user.managing_lgu_id = lgu.id
        await db.commit()


async def test_full_donation_loop(client):
    # 1. Donor signs up + onboards
    r = await client.post("/auth/signup", json={
        "email": "donor@example.com", "password": "password123", "role": "individual"})
    assert r.status_code == 200, r.text
    donor_token = r.json()["token"]

    await client.post("/onboarding/individual",
                      json={"first_name": "Juan", "last_name": "Cruz"},
                      headers=_auth(donor_token))

    # 2. Donor creates a dropoff donation
    r = await client.post("/donations", json={
        "title": "Surplus rice meals",
        "food_category": "cooked_meal",
        "donation_method": "dropoff",
        "dropoff_location": "Lahug LGU",
        "quote": "Share a meal, share hope.",
        "photo_base64": "ZmFrZS1pbWFnZQ==",
    }, headers=_auth(donor_token))
    assert r.status_code == 201, r.text
    donation_id = r.json()["id"]
    assert r.json()["status"] == "pending"

    # 3. LGU account is provisioned and logs in
    await client.post("/auth/signup", json={
        "email": "lgu@example.com", "password": "password123", "role": "lgu"})
    await _make_lgu_account("lgu@example.com")
    r = await client.post("/auth/login",
                          json={"email": "lgu@example.com", "password": "password123"})
    lgu_token = r.json()["token"]

    # 4. LGU works the queue: accept → schedule → complete
    r = await client.post(f"/lgu/donations/{donation_id}/accept", headers=_auth(lgu_token))
    assert r.status_code == 200 and r.json()["status"] == "accepted", r.text

    r = await client.post(f"/lgu/donations/{donation_id}/schedule",
                          json={"scheduled_pickup_at": "2026-07-01T09:00:00"},
                          headers=_auth(lgu_token))
    assert r.status_code == 200 and r.json()["status"] == "scheduled", r.text

    r = await client.post(f"/lgu/donations/{donation_id}/complete", headers=_auth(lgu_token))
    assert r.status_code == 200 and r.json()["status"] == "completed", r.text

    # 5. Points awarded to the donor
    r = await client.get("/users/me", headers=_auth(donor_token))
    assert r.json()["points_balance"] == 10, r.text

    r = await client.get("/users/me/points", headers=_auth(donor_token))
    assert r.json()["balance"] == 10
    assert len(r.json()["entries"]) == 1

    # 6. Donor has notifications and an audit trail
    r = await client.get("/notifications", headers=_auth(donor_token))
    titles = [n["title"] for n in r.json()]
    assert "Donation accepted" in titles
    assert "Donation completed" in titles

    r = await client.get(f"/donations/{donation_id}/history", headers=_auth(donor_token))
    actions = [h["action"] for h in r.json()]
    assert actions == ["created", "accepted", "scheduled", "completed"]

    # 7. Completed donation shows in history
    r = await client.get("/donations/history", headers=_auth(donor_token))
    assert any(d["id"] == donation_id for d in r.json())


async def test_individual_cannot_pickup(client):
    r = await client.post("/auth/signup", json={
        "email": "ind@example.com", "password": "password123", "role": "individual"})
    token = r.json()["token"]
    r = await client.post("/donations", json={
        "title": "Bad request", "food_category": "mixed",
        "donation_method": "pickup", "pickup_location": "home",
    }, headers=_auth(token))
    assert r.status_code == 400, r.text


async def test_role_gating(client):
    # Donor cannot hit LGU endpoints
    r = await client.post("/auth/signup", json={
        "email": "d2@example.com", "password": "password123", "role": "individual"})
    token = r.json()["token"]
    r = await client.get("/lgu/donations/pending", headers=_auth(token))
    assert r.status_code == 403, r.text


async def test_auth_required(client):
    r = await client.get("/users/me")
    assert r.status_code == 401
