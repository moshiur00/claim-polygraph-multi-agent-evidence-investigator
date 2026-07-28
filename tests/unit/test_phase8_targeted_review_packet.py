"""Stage 8.14 review decision must remain human-owned and fully disclosed."""

import json
from pathlib import Path

ROOT = Path(__file__).parents[2]
PACKET = ROOT / "artifacts/evaluations/phase8-stage8.14-targeted-review-v1.json"
MARKDOWN = ROOT / "benchmarks/review_packets/phase8_stage8_14_targeted_review.md"


def test_targeted_packet_has_five_cases_and_recorded_human_approval() -> None:
    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    assert packet["status"] == "approved"
    assert len(packet["cases"]) == 5
    assert all(len(case["candidates"]) == 3 for case in packet["cases"])
    assert packet["reviewer_identity"] == "Md Moshiur Rahman"
    assert packet["review_date"] == "2026-07-28"
    assert packet["review_decision"] == "promote_observational_default"
    assert packet["approver_identity"] == "Md Rashedul Islam"
    assert packet["approval_date"] == "2026-07-28"
    assert packet["approval_decision"] == "approve"
    assert set(packet["case_judgments"].values()) == {"improved"}
    assert "synthetic" in packet["fixture_disclosure"]


def test_markdown_requires_every_case_checklist_and_distinct_approval() -> None:
    markdown = MARKDOWN.read_text(encoding="utf-8")
    assert markdown.count("Candidate roles are meaningfully distinct") == 5
    assert markdown.count("No candidate escaped into the authoritative packet") == 5
    assert markdown.count("- [x]") == 25
    assert markdown.count("Case judgment: `improved`") == 5
    assert "Distinct approver identity: Md Rashedul Islam" in markdown
    assert "Approval decision: `approve`" in markdown
