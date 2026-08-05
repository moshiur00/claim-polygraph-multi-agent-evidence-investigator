import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("review brief uses effective safeguards and keeps historical recommendations separate", async () => {
  const source = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");

  for (const required of [
    "CURRENT EFFECTIVE DECISION",
    "Historical recommendation:",
    "EFFECTIVE CITATION ASSURANCE",
    "EFFECTIVE INDEPENDENCE",
    "Current effective decision",
    "Historical recommendation",
    "Approval is unavailable while effective evidence or citation safeguards are blocked.",
    "No typed check required",
    "recorded routing signals",
    "Effective citation failures",
    "Ineligible retained passages",
    "Effective clause coverage",
  ]) {
    assert.match(source, new RegExp(required.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  }

  assert.match(source, /effectiveCitationStatus/);
  assert.match(source, /report\.effective_full_report_assurance\?\.critical_failure_count/);
  assert.match(source, /argumentEligibleCount \?/);
  assert.doesNotMatch(source, /Obtain at least one directly relevant academic or primary historical source/);
});

test("review rationale requires an actual reviewer statement", async () => {
  const source = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");

  assert.match(source, /const \[rationale, setRationale\] = useState\(""\)/);
  assert.match(source, /placeholder="Explain what you verified and why this action is justified\."/);
  assert.match(source, /rationale\.trim\(\)\.length < 3/);
  assert.doesNotMatch(source, /useState\("I reviewed the evidence/);
});

test("review gate layout does not leave empty grid cells", async () => {
  const css = await readFile(new URL("../app/globals.css", import.meta.url), "utf8");
  assert.match(css, /\.review-gates article:last-child \{ grid-column: 1 \/ -1; min-height: 0; \}/);
});
