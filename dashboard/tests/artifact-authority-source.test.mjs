import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("shared dashboard summaries resolve canonical artifacts before fallbacks", async () => {
  const source = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");

  for (const required of [
    "canonicalVerdictLabel",
    "canonicalCitationSummary",
    "canonicalVerificationSummary",
    "Full-report citation assurance",
    "Assertion-level verification packet",
    "Legacy sentence-audit fallback",
    "Legacy compatibility fallback",
    "report.publication_decision.publication_allowed",
  ]) {
    assert.match(source, new RegExp(required.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  }

  assert.doesNotMatch(source, /const citationRate = report\?\.audits/);
  assert.doesNotMatch(source, /report\.publication_decision\s*\?\s*[\s\S]{0,120}:\s*true/);
});

test("review brief and overview identify canonical verification authority", async () => {
  const source = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");

  assert.match(source, /verificationSummary\?\.authority/);
  assert.match(source, /verificationSummary\?\.unresolved/);
  assert.match(source, /citationSummary\?\.authority/);
  assert.match(source, /resolvedVerdict/);
});
