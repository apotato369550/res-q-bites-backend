import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from _client import Run, unique_email, new_run_id


def main() -> int:
    run = Run("individual_cannot_pickup", "individual_pickup_results")
    rid = new_run_id()

    # Step 1: signup individual donor
    email = unique_email("individual", rid)
    r = run.call("POST", "/auth/signup", expect=200, json={
        "email": email,
        "password": "password123",
        "role": "individual"
    })
    token = r.json()["token"]

    # Step 2: POST /donations with pickup method (should fail)
    run.call("POST", "/donations", expect=400, token=token, json={
        "title": "Bad request pickup",
        "food_category": "mixed",
        "donation_method": "pickup",
        "pickup_location": "home"
    })

    return run.finish()


if __name__ == "__main__":
    sys.exit(main())
