import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const page = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");

test("UI.5 distinguishes investigation cost from process telemetry", () => {
  assert.match(page, /CURRENT JOB USAGE/);
  assert.match(page, /CURRENT INVESTIGATION COST/);
  assert.match(page, /API PROCESS TELEMETRY/);
  assert.match(page, /job\.investigation_id === selectedId/);
  assert.match(page, /activeJobOwnsUsage = Boolean\(job && jobActive\)/);
  assert.match(page, /scopedJobOwnsUsage \? 0 : telemetryModelCost/);
  assert.match(page, /this submitted job only/);
  assert.match(page, /all activity observed by this API process/);
  assert.doesNotMatch(page, /LOCAL COST TOTAL/);
});

test("UI.5 exposes an inclusive task-oriented evidence-investigation handoff", () => {
  assert.match(page, /aria-label="Recommended review path"/);
  assert.match(page, /1 · OUTCOME/);
  assert.match(page, /2 · EVIDENCE/);
  assert.match(page, /3 · SAFEGUARDS/);
  assert.match(page, /4 · DECISION/);
  assert.match(page, /Inspect evidence/);
  assert.match(page, /Open decision/);
});

test("UI.5 clearly distinguishes a blocked draft from a publishable export", () => {
  assert.match(page, /Download provisional draft/);
  assert.match(page, /Open provisional report draft; publication is blocked/);
  assert.match(page, /Open publication-ready report/);
});
