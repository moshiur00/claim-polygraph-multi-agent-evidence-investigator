import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("dashboard preserves the complete social-evidence transparency trace", async () => {
  const source = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");

  for (const label of [
    "SOCIAL-EVIDENCE POLICY",
    "Identity & authenticity",
    "Original source",
    "Approved use",
    "Verdict effect",
    "ACCOUNT AND ATTRIBUTION",
    "PROVENANCE AND INDEPENDENCE",
    "QUALITY AND LIMITATIONS",
    "Why this classification was assigned",
    "Relevance means topical match",
  ]) {
    assert.match(source, new RegExp(label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  }

  assert.match(source, /social_evidence_policy\?\.publication_blocked/);
  assert.match(source, /publication_decision\.publication_allowed/);
  assert.match(source, /PROVISIONAL REPORT · HUMAN DECISION PENDING/);
});
