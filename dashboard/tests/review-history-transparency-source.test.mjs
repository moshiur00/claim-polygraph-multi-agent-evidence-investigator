import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("review history exposes the immutable request, actors, decisions and chain", async () => {
  const source = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");

  for (const required of [
    "IMMUTABLE EVENT TIMELINE",
    "REVIEW REQUEST",
    "REVIEW FINDINGS",
    "REVIEWER DECISIONS",
    "DISTINCT APPROVALS",
    "VERDICT REVISIONS",
    "Append-only hash continuity",
    "event.event_hash.slice",
    "ReviewHistoryView",
  ]) {
    assert.match(source, new RegExp(required));
  }
});

test("evidence-blocked review prioritizes requesting evidence", async () => {
  const source = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");
  const requestIndex = source.indexOf('["request_evidence", "Request more evidence"]');
  const reviseIndex = source.indexOf('["revise", "Revise verdict"]');

  assert.ok(requestIndex >= 0);
  assert.ok(reviseIndex > requestIndex);
  assert.match(source, /value !== "approve" \|\| !approvalBlockedByEvidence/);
});
