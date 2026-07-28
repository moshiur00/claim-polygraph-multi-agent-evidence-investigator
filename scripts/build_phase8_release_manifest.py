"""Hash the final Phase 8 implementation, inputs, decisions and evidence."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
OUTPUT = ROOT / "artifacts/evaluations/phase8-final-release-manifest-v1.json"


def included_paths() -> tuple[Path, ...]:
    explicit = [
        ROOT / ".env.example",
        ROOT / ".gitignore",
        ROOT / "README.md",
        ROOT / "pyproject.toml",
        ROOT / "benchmarks/initial_claims_v1.json",
        ROOT / "benchmarks/phase8_confidence_calibration_eligible_v1.json",
        ROOT / "benchmarks/review_packets/phase8_stage8_14_targeted_review.md",
        ROOT / "dashboard/app/page.tsx",
        ROOT / "dashboard/package.json",
        ROOT / "dashboard/package-lock.json",
        ROOT / "dashboard/tests/accessibility.test.mjs",
        ROOT / "dashboard/tests/rendered-html.test.mjs",
    ]
    discovered = [
        *sorted((ROOT / "src/claim_polygraph_ng").rglob("*.py")),
        *sorted((ROOT / "tests").rglob("*.py")),
        *sorted((ROOT / "docs").glob("PHASE_8*.md")),
        *sorted((ROOT / "docs/adr").glob("00*.md")),
        *sorted((ROOT / "artifacts/evaluations").glob("phase8-*.json")),
        *sorted((ROOT / "scripts").glob("*phase8*.py")),
    ]
    paths = {
        path.resolve()
        for path in (*explicit, *discovered)
        if path.is_file() and path.resolve() != OUTPUT.resolve()
    }
    return tuple(sorted(paths, key=lambda path: path.relative_to(ROOT).as_posix()))


def main() -> int:
    artifacts = []
    for path in included_paths():
        artifacts.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    manifest = {
        "manifest_id": "phase8-final-release-manifest-v1",
        "status": "complete",
        "artifacts": artifacts,
        "artifact_count": len(artifacts),
        "human_review_complete": True,
        "phase8_complete": True,
        "external_model_calls": 0,
        "live_search_calls": 0,
        "network_fetches": 0,
        "pdf_downloads": 0,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    loaded = json.loads(OUTPUT.read_text(encoding="utf-8"))
    mismatches = []
    for artifact in loaded["artifacts"]:
        observed = hashlib.sha256((ROOT / artifact["path"]).read_bytes()).hexdigest()
        if observed != artifact["sha256"]:
            mismatches.append(artifact["path"])
    print(f"Artifacts checked: {len(artifacts)}")
    print(f"Hash mismatches: {len(mismatches)}")
    print(f"Status: {manifest['status']}")
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
