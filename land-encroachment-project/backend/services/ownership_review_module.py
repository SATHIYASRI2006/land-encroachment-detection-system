"""
SQLite-backed ownership review module.

This module stores existing claims in a local database and verifies
newly entered claims against those records. It supports conflict
detection only and does not determine legal ownership.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, List


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "ownership_review.db"

ClaimRecord = Dict[str, str]


def sample_claims() -> List[ClaimRecord]:
    """Seed records used as the existing ownership-review dataset."""
    return [
        {
            "claim_id": "C001",
            "claimant_name": "Arun Kumar",
            "claimed_owner_name": "Ravi Chandran",
            "survey_number": "SN-101",
            "plot_id": "P-01",
            "land_type": "Private",
            "status": "Pending",
        },
        {
            "claim_id": "C002",
            "claimant_name": "Meena Devi",
            "claimed_owner_name": "Ravi Chandran",
            "survey_number": "SN-101",
            "plot_id": "P-01",
            "land_type": "Private",
            "status": "Under Review",
        },
        {
            "claim_id": "C003",
            "claimant_name": "Suresh Babu",
            "claimed_owner_name": "Lakshmi Priya",
            "survey_number": "SN-102",
            "plot_id": "P-02",
            "land_type": "Private",
            "status": "Pending",
        },
        {
            "claim_id": "C004",
            "claimant_name": "Suresh Babu",
            "claimed_owner_name": "Lakshmi Priya",
            "survey_number": "SN-102",
            "plot_id": "P-02",
            "land_type": "Private",
            "status": "Under Review",
        },
        {
            "claim_id": "C005",
            "claimant_name": "Kalaivani",
            "claimed_owner_name": "Government of Tamil Nadu",
            "survey_number": "SN-103",
            "plot_id": "P-03",
            "land_type": "Government",
            "status": "Pending",
        },
        {
            "claim_id": "C006",
            "claimant_name": "Dinesh Raj",
            "claimed_owner_name": "Dinesh Raj",
            "survey_number": "SN-103",
            "plot_id": "P-03",
            "land_type": "Government",
            "status": "Pending",
        },
        {
            "claim_id": "C007",
            "claimant_name": "Fathima Noor",
            "claimed_owner_name": "Fathima Noor",
            "survey_number": "SN-104",
            "plot_id": "P-04",
            "land_type": "Private",
            "status": "Under Review",
        },
        {
            "claim_id": "C008",
            "claimant_name": "Ganesh",
            "claimed_owner_name": "R. Mohan",
            "survey_number": "SN-104",
            "plot_id": "P-04",
            "land_type": "Private",
            "status": "Pending",
        },
        {
            "claim_id": "C009",
            "claimant_name": "Hari Prasad",
            "claimed_owner_name": "Government of Tamil Nadu",
            "survey_number": "SN-105",
            "plot_id": "P-05",
            "land_type": "Government",
            "status": "Under Review",
        },
        {
            "claim_id": "C010",
            "claimant_name": "Indhu",
            "claimed_owner_name": "Indhu",
            "survey_number": "SN-105",
            "plot_id": "P-05",
            "land_type": "Government",
            "status": "Pending",
        },
    ]


def normalize_value(value: str) -> str:
    return (value or "").strip().lower()


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    """Create the storage table for ownership review claims."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ownership_review_claims (
                claim_id TEXT PRIMARY KEY,
                claimant_name TEXT NOT NULL,
                claimed_owner_name TEXT NOT NULL,
                survey_number TEXT NOT NULL,
                plot_id TEXT NOT NULL,
                land_type TEXT NOT NULL,
                status TEXT NOT NULL
            )
            """
        )


def seed_sample_data() -> None:
    """Insert sample records once so verification has existing data."""
    with get_connection() as conn:
        conn.executemany(
            """
            INSERT OR IGNORE INTO ownership_review_claims (
                claim_id,
                claimant_name,
                claimed_owner_name,
                survey_number,
                plot_id,
                land_type,
                status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    record["claim_id"],
                    record["claimant_name"],
                    record["claimed_owner_name"],
                    record["survey_number"],
                    record["plot_id"],
                    record["land_type"],
                    record["status"],
                )
                for record in sample_claims()
            ],
        )


def fetch_matching_records(claim: ClaimRecord) -> List[ClaimRecord]:
    """Load existing records that share the same plot or survey number."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT claim_id, claimant_name, claimed_owner_name, survey_number, plot_id, land_type, status
            FROM ownership_review_claims
            WHERE lower(plot_id) = lower(?)
               OR lower(survey_number) = lower(?)
            ORDER BY claim_id
            """,
            (claim["plot_id"], claim["survey_number"]),
        ).fetchall()
    return [dict(row) for row in rows]


def detect_government_land_conflict(claim: ClaimRecord) -> bool:
    """Flag private ownership attempts over government land."""
    return (
        normalize_value(claim["land_type"]) == "government"
        and "government" not in normalize_value(claim["claimed_owner_name"])
    )


def detect_ownership_conflict(claim: ClaimRecord, existing_records: List[ClaimRecord]) -> bool:
    """Flag plot/survey disputes where claimants differ across matching records."""
    current_claimant = normalize_value(claim["claimant_name"])
    for record in existing_records:
        if normalize_value(record["claimant_name"]) != current_claimant:
            return True
    return False


def detect_data_mismatch(claim: ClaimRecord, existing_records: List[ClaimRecord]) -> bool:
    """Flag owner-name mismatch against stored records for the same land."""
    current_owner = normalize_value(claim["claimed_owner_name"])
    known_owners = {normalize_value(record["claimed_owner_name"]) for record in existing_records}
    known_owners.discard("")
    return bool(known_owners) and current_owner not in known_owners


def determine_conflict_type(claim: ClaimRecord, existing_records: List[ClaimRecord]) -> str:
    """Return the most relevant conflict type for the entered claim."""
    if detect_government_land_conflict(claim):
        return "Government Land Conflict"
    if detect_ownership_conflict(claim, existing_records):
        return "Ownership Conflict"
    if detect_data_mismatch(claim, existing_records):
        return "Data Mismatch"
    return "None"


def determine_risk_level(conflict_type: str) -> str:
    if conflict_type in {"Government Land Conflict", "Ownership Conflict"}:
        return "High"
    if conflict_type == "Data Mismatch":
        return "Medium"
    return "Low"


def determine_status(conflict_type: str) -> str:
    if conflict_type == "None":
        return "Safe"
    if conflict_type == "Data Mismatch":
        return "Under Review"
    return "Flagged"


def verify_claim(claim: ClaimRecord) -> Dict[str, object]:
    """
    Verify a new claim by checking it against existing DB records
    with the same plot or survey number.
    """
    existing_records = fetch_matching_records(claim)
    conflict_type = determine_conflict_type(claim, existing_records)
    return {
        "input_claim_id": claim["claim_id"],
        "matching_records_found": len(existing_records),
        "matched_claim_ids": [record["claim_id"] for record in existing_records],
        "conflict_type": conflict_type,
        "risk_level": determine_risk_level(conflict_type),
        "status": determine_status(conflict_type),
    }


def store_claim(claim: ClaimRecord) -> None:
    """Save a newly entered claim after verification if needed."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO ownership_review_claims (
                claim_id,
                claimant_name,
                claimed_owner_name,
                survey_number,
                plot_id,
                land_type,
                status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                claim["claim_id"],
                claim["claimant_name"],
                claim["claimed_owner_name"],
                claim["survey_number"],
                claim["plot_id"],
                claim["land_type"],
                claim["status"],
            ),
        )


def print_verification_result(result: Dict[str, object]) -> None:
    print("\nOWNERSHIP REVIEW RESULT")
    print(f"Input Claim ID: {result['input_claim_id']}")
    print(f"Matching existing records: {result['matching_records_found']}")
    print(f"Matched Claim IDs: {', '.join(result['matched_claim_ids']) or 'None'}")
    print(f"Conflict Type: {result['conflict_type']}")
    print(f"Risk Level: {result['risk_level']}")
    print(f"Status: {result['status']}")


def main() -> None:
    init_db()
    seed_sample_data()

    # Demo input. Replace these values with the claim entered by the user.
    new_claim = {
        "claim_id": "C011",
        "claimant_name": "Ramesh",
        "claimed_owner_name": "Ramesh",
        "survey_number": "SN-103",
        "plot_id": "P-03",
        "land_type": "Government",
        "status": "Pending",
    }

    result = verify_claim(new_claim)
    print_verification_result(result)

    # Uncomment this if you want to store the entered claim after verification.
    # store_claim(new_claim)


if __name__ == "__main__":
    main()
