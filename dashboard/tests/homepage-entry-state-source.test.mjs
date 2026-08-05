import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const page = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");

test("the root investigation workspace does not auto-select a historical case", () => {
  assert.doesNotMatch(page, /if \(!selectedId && items\.length[^\n]*setSelectedId/);
  assert.match(page, /setSelectedId\(navigation\.investigationId\)/);
  assert.match(page, /onClick=\{\(\) => selectInvestigation\(item\.investigation_id\)\}/);
});

test("the neutral homepage shows readiness rather than process-wide cost", () => {
  assert.match(page, /!report && !jobActive && !jobFailed \? <div className="top-actions">/);
  assert.match(page, /Ready to investigate/);
  assert.match(page, /: <div className="top-actions">\s*<div className="cost-chip"/);
});

test("completed and review-paused records cannot take over the root while failed jobs remain diagnosable", () => {
  assert.match(page, /const terminalOrPaused = \["completed", "interrupted", "cancelled", "failed", "dead_letter"\]/);
  assert.match(page, /if \(terminalOrPaused\) \{\s*window\.localStorage\.removeItem\("claim-polygraph-active-job"\);\s*if \(\["failed", "dead_letter"\]\.includes\(restored\.job\.status\)\)/);
  assert.match(page, /setError\(null\)/);
  assert.match(page, /Historical job/);
  assert.doesNotMatch(page, /restored\.report_available && restored\.investigation_id\) setSelectedId/);
});
