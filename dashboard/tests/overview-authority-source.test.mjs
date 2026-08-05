import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("overview prioritizes effective publication authority over the historical verdict", async () => {
  const source = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");

  for (const required of [
    "CURRENT EFFECTIVE STATUS",
    "Publication blocked",
    "HISTORICAL VERDICT RETAINED FOR AUDIT",
    "PUBLICATION DIAGNOSIS",
    "RESEARCH AND EFFECTIVE COVERAGE",
    "EVIDENCE INTEGRITY",
    "NEXT BEST ACTION",
  ]) {
    assert.match(source, new RegExp(required));
  }

  assert.match(source, /argumentEligibleCount\} of \{evidence\.length/);
  assert.match(source, /decisiveEligibleIds\.size/);
  assert.match(source, /effectiveCitationStatus/);
  assert.match(source, /historicalVerdictEvidenceIds\.size/);
  assert.match(source, /Request replacement evidence, revise, or reject/);
  assert.match(source, /Retained-packet stance · not an effective support count/);
  assert.match(source, /Not established for effective packet/);
  assert.match(source, /No typed check required/);
  assert.match(source, /WHY PUBLICATION IS BLOCKED/);
  assert.match(source, /Unknown source-quality signals/);
  assert.match(source, /Effective evidence<\/b>/);
  assert.match(source, /Decisive use<\/b>/);
  assert.match(source, /Historical verdict<\/b>/);
  assert.match(source, /setSection\("Evidence"\)/);
});

test("overview authority hierarchy is responsive", async () => {
  const css = await readFile(new URL("../app/globals.css", import.meta.url), "utf8");

  for (const selector of [
    ".overview-status-hero",
    ".overview-authority-warning",
    ".overview-next-action",
    ".overview-integrity-card",
    ".overview-blocker-list",
  ]) {
    assert.match(css, new RegExp(selector.replace(".", "\\.")));
  }

  assert.match(css, /\.overview-status-hero \{ grid-template-columns: 1fr; \}/);
});
