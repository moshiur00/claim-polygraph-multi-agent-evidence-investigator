import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const page = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");
const css = await readFile(new URL("../app/globals.css", import.meta.url), "utf8");

test("system health leads with operational availability and configured providers", () => {
  assert.match(page, /The evidence service is reachable/);
  assert.match(page, /RESEARCH PROVIDER/);
  assert.match(page, /MODEL PROVIDER/);
  assert.match(page, /DURABLE WORKFLOW/);
  assert.match(page, /Sequential rollback remains available/);
});

test("system health gives telemetry an explicit cumulative scope", () => {
  assert.match(page, /CUMULATIVE SERVICE ACTIVITY/);
  assert.match(page, /Process\/store-wide observations—not the selected investigation/);
  assert.match(page, /Latency cards show averages, not accumulated duration/);
  assert.match(page, /API response time/);
  assert.match(page, /Workflow-step time/);
  assert.match(page, /metric\.total \/ metric\.count/);
});

test("configuration remains available without dominating health status", () => {
  assert.match(page, /<details className="health-diagnostics">/);
  assert.match(page, /Configuration and diagnostics/);
  assert.match(page, /workspaceView === "investigations" && <div className="workspace-tools">/);
  assert.match(page, /Reviews awaiting action/);
});

test("system health layout adapts to narrow screens", () => {
  assert.match(css, /\.health-summary \{/);
  assert.match(css, /\.telemetry-heading \{/);
  assert.match(css, /\.health-diagnostic-grid \{/);
  assert.match(css, /@media \(max-width: 680px\)[\s\S]*\.health-diagnostic-grid \{ grid-template-columns: 1fr; \}/);
});
