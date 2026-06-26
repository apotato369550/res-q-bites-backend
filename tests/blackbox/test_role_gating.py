import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from _client import Run, unique_email, new_run_id


def main() -> int:
    run = Run("role_gating", "role_gating_results")
    rid = new_run_id()

    # Step 1: signup individual donor
    email = unique_email("donor", rid)
    r = run.call("POST", "/auth/signup", expect=200, json={
        "email": email,
        "password": "password123",
        "role": "individual"
    })
    token = r.json()["token"]

    # Step 2: GET /lgu/donations/pending with donor token (should fail)
    run.call("GET", "/lgu/donations/pending", expect=403, token=token)

    # Step 3: GET /admin/users with donor token (should fail)
    run.call("GET", "/admin/users", expect=403, token=token)

    # Step 4: GET /users/me with no token (should fail)
    run.call("GET", "/users/me", expect=401)

    return run.finish()


if __name__ == "__main__":
    sys.exit(main())
