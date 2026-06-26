import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from _client import Run, unique_email, new_run_id


def main() -> int:
    run = Run("auth", "auth_results")
    rid = new_run_id()

    # Step 1: signup a new individual donor
    email = unique_email("auth", rid)
    r = run.call("POST", "/auth/signup", expect=200, json={
        "email": email,
        "password": "password123",
        "role": "individual"
    })
    token = r.json()["token"]
    run.check("token returned", bool(token))

    # Step 2: login with the same email and password
    r = run.call("POST", "/auth/login", expect=200, json={
        "email": email,
        "password": "password123"
    })
    token2 = r.json()["token"]
    run.check("login token returned", bool(token2))

    # Step 3: GET /users/me with token
    r = run.call("GET", "/users/me", expect=200, token=token)
    run.check("email matches", r.json()["email"] == email, detail=f"expected {email}, got {r.json().get('email')}")

    # Step 4: login with wrong password
    run.call("POST", "/auth/login", expect=401, json={
        "email": email,
        "password": "wrongpass1"
    })

    # Step 5: GET /users/me with no token
    run.call("GET", "/users/me", expect=401)

    return run.finish()


if __name__ == "__main__":
    sys.exit(main())
