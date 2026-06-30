"""
test_donation_loop.py

Headline end-to-end donation workflow: signup → onboard → donate → accept → schedule → complete → verify notifications/history.

PREREQUISITE: python scripts/utils/seed.py must be run against the live server's DB first.
The seeded LGU account (SEEDED_LGU) is required for LGU actions.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from _client import Run, SEEDED_LGU, new_run_id, unique_email


def main() -> int:
    run = Run("donation_loop", "donation_loop_results")
    rid = new_run_id()

    # 1. Signup an individual donor
    donor_email = unique_email("loop", rid)
    r = run.call(
        "POST",
        "/auth/signup",
        expect=200,
        json={
            "email": donor_email,
            "password": "password123",
            "role": "individual",
        },
    )
    donor_token = r.json()["token"]

    # 2. Onboard the donor (individual profile)
    run.call(
        "POST",
        "/onboarding/individual",
        expect=200,
        token=donor_token,
        json={"first_name": "Juan", "last_name": "Cruz"},
    )

    # 3. Create a donation
    r = run.call(
        "POST",
        "/donations",
        expect=201,
        token=donor_token,
        json={
            "title": "Surplus rice meals",
            "food_category": "cooked_meal",
            "donation_method": "dropoff",
            "dropoff_location": "Lahug LGU",
            "quote": "Share a meal, share hope.",
            "photo_base64": "ZmFrZS1pbWFnZQ==",
        },
    )
    donation_id = r.json()["id"]
    run.check("status pending", r.json()["status"] == "pending")

    # 4. Login as seeded LGU
    r = run.call(
        "POST",
        "/auth/login",
        expect=200,
        json={"email": SEEDED_LGU[0], "password": SEEDED_LGU[1]},
    )
    lgu_token = r.json()["token"]

    # 5. Accept the donation
    r = run.call(
        "POST",
        f"/lgu/donations/{donation_id}/accept",
        expect=200,
        token=lgu_token,
    )
    run.check("accepted", r.json()["status"] == "accepted")

    # 6. Schedule the donation
    r = run.call(
        "POST",
        f"/lgu/donations/{donation_id}/schedule",
        expect=200,
        token=lgu_token,
        json={"scheduled_pickup_at": "2026-07-01T09:00:00"},
    )
    run.check("scheduled", r.json()["status"] == "scheduled")

    # 7. Complete the donation
    r = run.call(
        "POST",
        f"/lgu/donations/{donation_id}/complete",
        expect=200,
        token=lgu_token,
    )
    run.check("completed", r.json()["status"] == "completed")

    # 8. Check notification
    r = run.call(
        "GET",
        "/notifications",
        expect=200,
        token=donor_token,
    )
    titles = [n["title"] for n in r.json()]
    run.check("completed notification", "Donation completed" in titles)

    # 9. Check donation history
    r = run.call(
        "GET",
        f"/donations/{donation_id}/history",
        expect=200,
        token=donor_token,
    )
    actions = [h["action"] for h in r.json()]
    run.check(
        "history sequence",
        actions == ["created", "accepted", "scheduled", "completed"],
        detail=str(actions),
    )

    return run.finish()


if __name__ == "__main__":
    sys.exit(main())
