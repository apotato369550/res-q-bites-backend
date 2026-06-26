"""
test_lgu_workflow.py

LGU management surface: pending donations, inventory, analytics, beneficiaries, distributions.

PREREQUISITE: python scripts/utils/seed.py must be run against the live server's DB first.
The seeded LGU account (SEEDED_LGU) is required for all LGU operations.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from _client import Run, SEEDED_LGU, new_run_id


def main() -> int:
    run = Run("lgu_workflow", "lgu_workflow_results")
    rid = new_run_id()

    # 1. Login as seeded LGU
    r = run.call(
        "POST",
        "/auth/login",
        expect=200,
        json={"email": SEEDED_LGU[0], "password": SEEDED_LGU[1]},
    )
    lgu_token = r.json()["token"]

    # 2. Get pending donations
    run.call(
        "GET",
        "/lgu/donations/pending",
        expect=200,
        token=lgu_token,
    )

    # 3. Get inventory
    run.call(
        "GET",
        "/lgu/inventory",
        expect=200,
        token=lgu_token,
    )

    # 4. Get analytics
    run.call(
        "GET",
        "/lgu/analytics",
        expect=200,
        token=lgu_token,
    )

    # 5. Create a beneficiary
    r = run.call(
        "POST",
        "/lgu/beneficiaries",
        expect=201,
        token=lgu_token,
        json={"name": f"Test Beneficiary {rid}", "household_size": 4, "barangay": "Lahug"},
    )
    beneficiary_id = r.json()["id"]

    # 6. Create an inventory item
    r = run.call(
        "POST",
        "/lgu/inventory",
        expect=201,
        token=lgu_token,
        json={"food_category": "mixed", "quantity": 10, "unit": "meals"},
    )
    item_id = r.json()["id"]

    # 7. Create a distribution
    run.call(
        "POST",
        "/lgu/distributions",
        expect=201,
        token=lgu_token,
        json={
            "beneficiary_id": beneficiary_id,
            "items": [{"inventory_item_id": item_id, "quantity": 1}],
        },
    )

    return run.finish()


if __name__ == "__main__":
    sys.exit(main())
