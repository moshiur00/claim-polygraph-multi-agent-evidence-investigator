import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const page = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");
const css = await readFile(new URL("../app/globals.css", import.meta.url), "utf8");

test("review queue only waits for distinct approval when the recorded decision requires it", () => {
  assert.match(page, /\["approve", "revise"\]\.includes\(latestDecision\.kind\)/);
  assert.match(page, /approval\.decision_record_id === latestDecision\.record_id/);
  assert.match(page, /reviewQueue\.filter\(\(item\) => reviewStateOf\(item\) !== "complete"\)/);
  assert.match(page, /pending \? "Review brief" : "Review history"/);
});

test("evidence decisions use an accessible in-app confirmation instead of a browser prompt", () => {
  assert.doesNotMatch(page, /window\.confirm\(/);
  assert.match(page, /className="confirmation-dialog" role="dialog" aria-modal="true"/);
  assert.match(page, /Distinct approver identity/);
  assert.match(page, /The reviewer and distinct approver must be different people/);
  assert.match(css, /\.confirmation-backdrop/);
});

test("request dispositions disclose that they record follow-up without starting paid work", () => {
  assert.match(page, /This records a durable follow-up request\. It does not start research or extraction/);
  assert.match(page, /the passage remains ineligible while the request is pending/i);
  assert.match(page, /useState\(""\);\s*const \[pendingDisposition/);
});

test("a successful disposition refreshes every authoritative dashboard surface", () => {
  assert.match(page, /request<Report>\(`\/api\/investigations\/\$\{investigationId\}\/report`\)/);
  assert.match(page, /request<AuthoritativeJob>\(`\/api\/investigations\/\$\{investigationId\}\/authoritative-job`\)/);
  assert.match(page, /request<Investigation\[]>\("\/api\/investigations"\)/);
  assert.match(page, /setGraph\(authoritativeGraphSnapshot\(freshJob\)\)/);
  assert.match(page, /await loadReviewQueue\(\)/);
});

test("metric explanations are operable and expose accessible disclosure state", () => {
  assert.match(page, /function MetricHelp/);
  assert.match(page, /aria-expanded=\{open\}/);
  assert.match(page, /role="note" className="metric-help-popover"/);
  assert.match(page, /<MetricHelp id="confidence-help"/);
  assert.match(page, /<MetricHelp id="citation-support-help"/);
  assert.match(css, /\.metric-help-popover/);
});
