"""Evaluation-set hygiene and the reviewed-case export."""

import json
import uuid
from pathlib import Path

from truthshield.investigations.dataset import (
    assign_split, jaccard, load_sets, near_duplicates, shingles, template,
)

EVAL = Path(__file__).resolve().parent / "eval"
REFERENCE = "fraud_final_blind5"


def test_the_reference_final_set_has_no_near_duplicate_anywhere_else():
    """A reworded development item in the test set would measure memory, not generalisation."""
    hits = near_duplicates(load_sets(EVAL), threshold=0.4, only_between=[REFERENCE])
    assert hits == [], hits[:5]


def test_template_variants_are_near_duplicates():
    a = "Your SBI account will be blocked today. Update KYC at http://a.top/x or call 9876543210."
    b = "Your SBI account will be blocked today. Update KYC at http://b.top/y or call 9123456780."
    assert template(a) == template(b)
    assert jaccard(shingles(a), shingles(b)) == 1.0
    assert jaccard(shingles(a), shingles("Lunch is at one on Thursday, see you there.")) < 0.1


def test_splits_are_stable_and_keep_variants_together():
    a = "Pay Rs 500 now to release your parcel: http://x.top/1"
    b = "Pay Rs 900 now to release your parcel: http://y.top/2"
    assert assign_split(a) == assign_split(a) == assign_split(b)
    counts = {"development": 0, "validation": 0, "test": 0}
    for i in range(2000):
        # Letters only: digits are blanked by the template, which would merge them all.
        word = "".join(chr(97 + int(c, 16)) for c in uuid.UUID(int=i * 7919 + 1).hex[-12:])
        counts[assign_split(f"message about {word}")] += 1
    assert 0.6 < counts["development"] / 2000 < 0.8 and 0.08 < counts["test"] / 2000 < 0.22


def test_export_refuses_without_consent(tmp_path, capsys):
    from truthshield.investigations.export_reviewed import main

    assert main(["--out", str(tmp_path / "x.jsonl")]) == 2
    assert not (tmp_path / "x.jsonl").exists()


def test_export_takes_resolved_appeals_only_with_redacted_text(client, tmp_path):
    from tests.test_v2_reviews import account, feedback, investigate
    from truthshield.investigations.export_reviewed import main

    user, analyst = account(client), account(client, role="ANALYST")
    scam = investigate(client, user, "Share the OTP 482913 now or your SBI account is blocked: http://sbi-kyc.top/x")
    appeal = feedback(client, user, scam["id"], label="legitimate", appeal=True).json()
    client.patch(f"/api/v1/admin/reviews/{appeal['id']}", headers=analyst, json={"label": "fraud"})
    plain = investigate(client, user, "See you at the station at six, bring the tickets.")
    feedback(client, user, plain["id"], label="legitimate")          # feedback, not an appeal

    out = tmp_path / "reviewed.jsonl"
    assert main(["--out", str(out), "--confirm-consent"]) == 0
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    mine = [r for r in rows if r["id"] == f"r-{scam['public_id']}"]
    assert len(mine) == 1 and mine[0]["label"] == "fraud" and mine[0]["source"] == "reviewer_decision"
    assert "482913" not in mine[0]["content"], "only the redacted copy is exported"
    assert mine[0]["split"] in ("development", "validation", "test")
    assert not any(r["id"] == f"r-{plain['public_id']}" for r in rows)
