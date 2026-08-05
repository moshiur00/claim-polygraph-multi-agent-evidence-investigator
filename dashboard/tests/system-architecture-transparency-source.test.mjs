import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("system architecture distinguishes accepted design from observed runtime", async () => {
  const source = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");

  for (const required of [
    "Current runtime configuration",
    "AUTHORITATIVE LIFECYCLE",
    "AUTHORITY AND DATA FLOW",
    "CURRENT INVESTIGATION ENVELOPE",
    "GRAPH BUDGET COUNTERS",
    "OBSERVED COST ACCOUNTING",
    "RECOVERY GUARANTEES",
    "CAPABILITY BOUNDARIES",
    "Receipt-protected paid operations",
    "Cannot invent or approve evidence",
    "Hash-chained decisions and approvals",
  ]) {
    assert.match(source, new RegExp(required));
  }

  assert.match(source, /apiStatus\?\.orchestrator/);
  assert.match(source, /runtime\.checkpoint_sequence/);
  assert.match(source, /runtime\.consumption\.estimated_cost_usd/);
  assert.match(source, /observedCost\.toFixed/);
  assert.match(source, /providerLabel\(apiStatus\?\.model_provider\)/);
  assert.match(source, /review\?\.chain_valid/);
});

test("architecture workspace has responsive lifecycle and authority views", async () => {
  const css = await readFile(new URL("../app/globals.css", import.meta.url), "utf8");

  for (const selector of [
    ".architecture-runtime",
    ".architecture-lifecycle",
    ".architecture-flow-grid",
    ".architecture-observability",
    ".architecture-authority-table",
  ]) {
    assert.match(css, new RegExp(selector.replace(".", "\\.")));
  }
});
