"""Command-line integration tests."""

import json
from pathlib import Path
from uuid import UUID

import pytest

from claim_polygraph_ng.cli import main

BENCHMARK = Path(__file__).parents[2] / "benchmarks" / "initial_claims_v1.json"


@pytest.fixture(autouse=True)
def isolate_cli_environment(tmp_path, monkeypatch) -> None:
    """Prevent developer-local .env settings from changing deterministic tests."""
    monkeypatch.chdir(tmp_path)


def test_cli_investigate_list_and_show(tmp_path, capsys) -> None:
    database = tmp_path / "cli.sqlite3"
    artifacts = tmp_path / "artifacts"
    common = ["--database", str(database), "--artifacts", str(artifacts)]

    exit_code = main(
        [
            *common,
            "investigate",
            "The example programme reduced waste by ten percent.",
        ]
    )
    investigate_output = capsys.readouterr()

    assert exit_code == 0
    assert "Status: completed" in investigate_output.out
    assert "deterministic development provider" in investigate_output.out

    id_line = next(
        line for line in investigate_output.out.splitlines() if line.startswith("Investigation ID:")
    )
    investigation_id = UUID(id_line.split(":", maxsplit=1)[1].strip())
    output_directory = artifacts / str(investigation_id)

    assert (output_directory / "report.json").is_file()
    assert (output_directory / "report.md").is_file()
    assert (output_directory / "trace.json").is_file()

    report_payload = json.loads((output_directory / "report.json").read_text(encoding="utf-8"))
    trace_payload = json.loads((output_directory / "trace.json").read_text(encoding="utf-8"))
    assert report_payload["verdict"]["label"] == "mixed"
    assert trace_payload[-1]["event_type"] == "investigation_completed"

    assert main([*common, "list"]) == 0
    list_output = capsys.readouterr()
    assert str(investigation_id) in list_output.out
    assert "completed" in list_output.out

    assert main([*common, "show", str(investigation_id)]) == 0
    show_output = capsys.readouterr()
    assert "# Claim Polygraph NG Investigation" in show_output.out
    assert "## Provisional verdict" in show_output.out


def test_cli_reports_missing_investigation(tmp_path, capsys) -> None:
    missing_id = "00000000-0000-0000-0000-000000000001"

    exit_code = main(
        [
            "--database",
            str(tmp_path / "empty.sqlite3"),
            "show",
            missing_id,
        ]
    )
    output = capsys.readouterr()

    assert exit_code == 1
    assert "investigation not found" in output.err


def test_cli_runs_a_limited_deterministic_evaluation(tmp_path, capsys) -> None:
    summary_path = tmp_path / "evaluation.json"

    exit_code = main(
        [
            "--database",
            str(tmp_path / "evaluation.sqlite3"),
            "evaluate",
            "--dataset",
            str(BENCHMARK),
            "--output",
            str(summary_path),
            "--limit",
            "2",
        ]
    )
    output = capsys.readouterr()
    payload = json.loads(summary_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert "Cases: 2/2 completed" in output.out
    assert "Verdict accuracy: 0.00%" in output.out
    assert "AI-provisional agreement: 0.00% (2 compared; diagnostic only)" in output.out
    assert payload["provider_mode"] == ("deterministic_retrieval+deterministic_reasoning")
    assert payload["verdict_accuracy"] == 0.0


def test_cli_runs_a_limited_benchmark_evidence_evaluation(tmp_path, capsys) -> None:
    summary_path = tmp_path / "benchmark-evidence.json"

    exit_code = main(
        [
            "--database",
            str(tmp_path / "benchmark-evidence.sqlite3"),
            "evaluate",
            "--dataset",
            str(BENCHMARK),
            "--output",
            str(summary_path),
            "--limit",
            "2",
            "--benchmark-evidence",
        ]
    )
    output = capsys.readouterr()
    payload = json.loads(summary_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert "Cases: 2/2 completed" in output.out
    assert payload["provider_mode"] == "benchmark_evidence+deterministic_reasoning"
    assert payload["mean_sources_per_completed_case"] == 2.5
    assert any("evidence-oracle" in item for item in payload["limitations"])


def test_cli_rejects_benchmark_evidence_with_searxng(tmp_path, capsys) -> None:
    exit_code = main(
        [
            "--database",
            str(tmp_path / "conflict.sqlite3"),
            "--searxng-url",
            "http://localhost:8080",
            "evaluate",
            "--dataset",
            str(BENCHMARK),
            "--benchmark-evidence",
            "--limit",
            "1",
        ]
    )
    output = capsys.readouterr()

    assert exit_code == 1
    assert "are mutually exclusive" in output.err


def test_cli_retrieval_evaluation_requires_searxng(tmp_path, capsys) -> None:
    exit_code = main(
        [
            "evaluate-retrieval",
            "--dataset",
            str(BENCHMARK),
            "--output",
            str(tmp_path / "retrieval.json"),
        ]
    )
    output = capsys.readouterr()

    assert exit_code == 1
    assert "requires --searxng-url or SEARXNG_BASE_URL" in output.err


def test_cli_rejects_multiple_model_providers(tmp_path, capsys) -> None:
    exit_code = main(
        [
            "--database",
            str(tmp_path / "conflict.sqlite3"),
            "--ollama-model",
            "local-model",
            "--openai-model",
            "hosted-model",
            "investigate",
            "A factual claim.",
        ]
    )
    output = capsys.readouterr()

    assert exit_code == 1
    assert "choose either --ollama-model or --openai-model" in output.err


def test_cli_rejects_fast_model_without_primary_model(tmp_path, capsys) -> None:
    exit_code = main(
        [
            "--database",
            str(tmp_path / "missing-primary.sqlite3"),
            "--openai-fast-model",
            "gpt-4o-mini",
            "investigate",
            "A factual claim.",
        ]
    )
    output = capsys.readouterr()

    assert exit_code == 1
    assert "--openai-fast-model requires --openai-model" in output.err


def test_cli_shows_five_claim_review_status(tmp_path, capsys) -> None:
    exit_code = main(["review-status", "--dataset", str(BENCHMARK)])
    output = capsys.readouterr()

    assert exit_code == 0
    assert "CPNG-001" in output.out
    assert "CPNG-005" in output.out
    assert "Reviewed: 5/5" in output.out


def test_cli_ai_review_requires_explicit_models(tmp_path, capsys) -> None:
    exit_code = main(["ai-review", "--dataset", str(BENCHMARK), "--cases", "CPNG-001"])
    output = capsys.readouterr()

    assert exit_code == 1
    assert "AI review requires OPENAI_MODEL and OPENAI_FAST_MODEL" in output.err
