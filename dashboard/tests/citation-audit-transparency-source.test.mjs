import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("citation audit exposes the canonical publication and passage trace", async () => {
  const source = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");

  for (const required of [
    "full_report_assurance",
    "effective_full_report_assurance",
    "final_audit.findings",
    "EFFECTIVE FULL-REPORT CITATION ASSURANCE",
    "HISTORICAL AUDIT PRESERVED",
    "WHY PUBLICATION IS BLOCKED",
    "CITATION-TO-PASSAGE MAPPING",
    "MATCHED PHRASES",
    "REVISED AND RE-AUDITED",
    "How to interpret citation assurance",
    "What it does not prove",
    "Clause phrase coverage",
    "Current citation eligibility",
    "Attached references",
    "Eligible references",
    "Not evaluated — citation eligibility failed first.",
  ]) {
    assert.match(source, new RegExp(required.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  }

  assert.match(source, /initial\.status !== finding\.status/);
  assert.match(source, /assurance\?\.final_audit\.approved_evidence_ids\.includes/);
  assert.match(source, /Verdict label changed:/);
  assert.match(source, /value !== "approve" \|\| !approvalBlockedByEvidence/);
  assert.match(source, /Approval is unavailable until the current evidence and citation blockers are resolved/);
  assert.match(source, /integrity\?\.citation_eligible === true \? "Eligible" : "Ineligible"/);
  assert.ok(source.indexOf('["request_evidence", "Request more evidence"]') < source.indexOf('["revise", "Revise verdict"]'));
});

test("citation audit has responsive summary, filters, findings, and revisions", async () => {
  const css = await readFile(new URL("../app/globals.css", import.meta.url), "utf8");

  for (const selector of [
    ".citation-gate",
    ".citation-metrics",
    ".citation-controls",
    ".citation-finding",
    ".citation-diagnosis",
    ".citation-mappings",
    ".revision-comparison",
    ".citation-method",
    ".citation-history-notice",
    ".citation-integrity-warning",
  ]) {
    assert.match(css, new RegExp(selector.replace(".", "\\.")));
  }
});
