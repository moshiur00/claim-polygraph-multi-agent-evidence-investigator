"""Command-line integration tests."""

import json
from uuid import UUID

from claim_polygraph_ng.cli import main


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
    assert "Development mode" in investigate_output.out

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
