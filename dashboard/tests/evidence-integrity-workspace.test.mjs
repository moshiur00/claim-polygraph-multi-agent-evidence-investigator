import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const page = readFileSync(new URL("../app/page.tsx", import.meta.url), "utf8");

test("evidence workspace prioritizes canonical integrity and bounded quotes", () => {
  assert.match(page, /report\.evidence_integrity/);
  assert.match(page, /BEST MATCHING EXCERPT/);
  assert.match(page, /SOURCE-SPAN VERIFIED QUOTE/);
  assert.match(page, /Compatibility diagnostic · stored raw capture/);
  assert.match(page, /DIAGNOSTIC EXCERPT · NOT EVIDENCE/);
  assert.match(page, /Publication blocked by this evidence item/);
});

test("evidence workspace exposes filters, grouping, and source-quality context", () => {
  assert.match(page, /PASSAGE HYGIENE/);
  assert.match(page, /Eligible decisive only/);
  assert.match(page, /evidence-source-group/);
  assert.match(page, /SOURCE-QUALITY ASSESSMENT/);
  assert.match(page, /A high relevance score never proves truth/);
  assert.match(page, /Approve bounded use/);
  assert.match(page, /Request replacement/);
  assert.match(page, /Request re-extraction/);
  assert.match(page, /Evidence decision history/);
  assert.match(page, /No eligible evidence remains/);
  assert.match(page, /Prepare fresh investigation/);
  assert.match(page, /MATERIAL REPORT SENTENCES USING THIS PASSAGE/);
  assert.match(page, /POSSIBLE DUPLICATE/);
  assert.match(page, /VERDICT-SELECTED · INELIGIBLE/);
  assert.match(page, /This passage is not citation-eligible/);
});
