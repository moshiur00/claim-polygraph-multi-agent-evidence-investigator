import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const page = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");
const css = await readFile(new URL("../app/globals.css", import.meta.url), "utf8");

test("review queue header reports queue context rather than selected-case controls", () => {
  assert.match(page, /workspaceView === "review_queue" \? <div className="top-actions queue-top-actions"/);
  assert.match(page, /AWAITING ACTION/);
  assert.match(page, /total review records/);
  assert.match(page, /Review workspace/);
});

test("review queue translates persisted reasons and exposes immutable identifiers", () => {
  assert.match(page, /reviewReasonLabel/);
  assert.match(page, /Safeguards require a human decision/);
  assert.match(page, /Evidence and policy assessments disagree/);
  assert.match(page, /Reason code/);
  assert.match(page, /Audit chain/);
  assert.match(page, /Request \{shortId\(history\.request\.request_id\)\}/);
});

test("review queue supports prioritization without discarding records", () => {
  assert.match(page, /placeholder="Claim, case ID, or review reason"/);
  assert.match(page, /Awaiting reviewer/);
  assert.match(page, /Awaiting distinct approval/);
  assert.match(page, /visibleReviewQueue\.map/);
  assert.match(page, /investigation\?\.input_claim/);
  assert.match(page, /Next owner/);
});

test("review queue controls and cards have responsive styles", () => {
  assert.match(css, /\.queue-toolbar \{/);
  assert.match(css, /\.queue-count-chip \{/);
  assert.match(css, /\.queue-case \.queue-reason/);
  assert.match(css, /@media \(max-width: 760px\)[\s\S]*\.queue-toolbar \{ grid-template-columns: 1fr; \}/);
});
