import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("verification presents canonical assertions, findings, provenance, and limitations", async () => {
  const source = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");

  for (const required of [
    "verification_packet",
    "ASSERTION-LEVEL VERIFICATION",
    "ACTIONABLE VERIFICATION FINDINGS",
    "EVIDENCE-GROUNDED RESULT",
    "TEMPORAL EVIDENCE TIMELINE",
    "Compatibility diagnostic · raw context extraction",
    "No numerical operand was expected because numerical verification was not required",
    "How to interpret verification",
    "claim_observations",
    "evidence_observations",
    "recommended_action",
    "readiness_impact",
    "missingRequiredAssertions",
    "unclassified tokens found in retained passages",
    "additional token(s) hidden",
    "WHY VERIFICATION WAS REQUESTED",
    "VERIFICATION TRACE",
    "ASSERTIONS CONSTRUCTED",
    "CONSTRUCTION FAILURES",
    "Prepare a clarified claim",
    "Marking a requirement “not applicable”",
    "observationCategory",
    "observationExcerpt",
    "CLAIM-SCOPE REVIEW SIGNALS",
    "Not a numerical or temporal check",
    "Current evidence authority",
    "Scope qualifiers detected",
    "Historical packet reference",
  ]) {
    assert.match(source, new RegExp(required.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  }
});

test("semantic scope signals cannot masquerade as typed verification failures", async () => {
  const source = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");

  assert.match(source, /scopeFindingCodes/);
  assert.match(source, /legacyNumericalFindings\.filter\(\(finding\) => !scopeFindingCodes\.has\(finding\.code\)\)/);
  assert.match(source, /!verificationRequired\s*\? "Not applicable"/);
  assert.doesNotMatch(source, /<dt>Approved evidence available<\/dt>/);
  assert.doesNotMatch(source, /<dt>Exactness terms<\/dt>/);
});

test("verification workspace has responsive gates, findings, traces, and timelines", async () => {
  const css = await readFile(new URL("../app/globals.css", import.meta.url), "utf8");

  for (const selector of [
    ".verification-workspace",
    ".verification-gate",
    ".verification-metrics",
    ".verification-findings",
    ".scope-review-findings",
    ".verification-assertion",
    ".verification-evidence",
    ".temporal-observations",
    ".legacy-context",
    ".verification-method",
    ".verification-requirements",
    ".verification-trace",
    ".verification-recovery",
    ".observation-groups",
  ]) {
    assert.match(css, new RegExp(selector.replace(".", "\\.")));
  }
});
