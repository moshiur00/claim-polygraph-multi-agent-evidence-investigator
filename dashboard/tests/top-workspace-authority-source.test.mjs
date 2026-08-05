import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("top workspace distinguishes current authority from retained history", async () => {
  const source = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");

  for (const required of [
    "CURRENT EFFECTIVE DECISION",
    "Historical recommendation:",
    "EFFECTIVE INDEPENDENCE",
    "ELIGIBLE EVIDENCE",
    "Passages eligible for argument use · not a citation-support score",
    "REPORT CITATION SUPPORT",
    "CURRENT REPORT STATUS",
    "Evidence remediation required before a final decision",
    "NEXT REQUIRED STEP",
    "Approval is unavailable while safeguards are blocked.",
    "Review state · Awaiting decision",
    "No processing is expected until a review decision is recorded.",
    "Save decision & resume workflow",
    "INVESTIGATION WORKFLOW",
    "Completed stages are persisted.",
    "Start another investigation",
  ]) {
    assert.match(source, new RegExp(required.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  }

  assert.match(source, /overallPublicationReady \? titleCase\(resolvedVerdict \?\? report\.verdict\.label\) : "Unresolved"/);
  assert.match(source, /argumentEligibleCount\}\/\{evidence\.length/);
  assert.match(source, /summary-row \$\{overallPublicationReady \? "ready" : "blocked"\}/);
  assert.doesNotMatch(source, /Save decision & resume graph/);
});

test("provider names are translated before they reach system-health UI", async () => {
  const source = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");

  assert.match(source, /providerLabel\(apiStatus\?\.orchestrator\)/);
  assert.match(source, /providerLabel\(apiStatus\?\.retrieval_provider/);
  assert.match(source, /providerLabel\(apiStatus\?\.model_provider/);
});
