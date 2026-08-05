import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const page = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");

test("decision rationale exposes proposition-level resolution and label derivation", () => {
  assert.match(page, /PROPOSITION-LEVEL REASONING/);
  assert.match(page, /role="table" aria-label="Argument ledger propositions"/);
  assert.match(page, /aria-label="Decision derivation"/);
  assert.match(page, /An unresolved proposition cannot inherit support from historical or ineligible evidence links/);
  assert.match(page, /EFFECTIVE ARGUMENT LEDGER/);
  assert.match(page, /HISTORICAL PROVISIONAL VERDICT/);
  assert.match(page, /Archived explanation — not a current conclusion/);
  assert.match(page, /HISTORICAL POLICY DECISION/);
  assert.match(page, /does not describe the current unresolved effective ledger/);
});

test("challenger findings expose wording, effect and evidence links", () => {
  assert.match(page, /CHALLENGER AND SUFFICIENCY FINDINGS/);
  assert.match(page, /Current evidence gaps and challenges/);
  assert.match(page, /Relevant claim wording/);
  assert.match(page, /Verdict effect/);
  assert.match(page, /No current verdict can be supported/);
  assert.match(page, /Open evidence \{shortId\(id\)\}/);
  assert.match(page, /No currently eligible evidence link was recorded for this finding/);
  assert.match(page, /replace\("The approved packet", "The current eligible packet"\)/);
});

test("decisive evidence is grouped and carries bounded roles", () => {
  assert.match(page, /CURRENTLY ELIGIBLE DECISIVE EVIDENCE/);
  assert.match(page, /HISTORICAL VERDICT EVIDENCE · CURRENTLY INELIGIBLE/);
  assert.match(page, /historical-evidence"><summary>/);
  assert.match(page, /No passage is currently eligible for decisive use/);
  assert.match(page, /Supports proposition/);
  assert.match(page, /Qualifies proposition/);
  assert.match(page, /titleCase\(item\.evidentiary_use\)/);
});

test("alternative verdicts and exact wording are explained without private reasoning", () => {
  assert.match(page, /WHY NOT ANOTHER VERDICT/);
  assert.match(page, /No separate comparative rationale was persisted/);
  assert.match(page, /Current label comparison is blocked/);
  assert.match(page, /Exact-wording check/);
  assert.match(page, /does not expose or reconstruct private model chain-of-thought/);
});

test("follow-up preparation discloses calls and cost boundary", () => {
  assert.match(page, /Prepare follow-up claim/);
  assert.match(page, /It makes no search or model call/);
  assert.match(page, /Costs can occur only if you submit a new investigation/);
  assert.match(page, /decisive-list \$\{decisiveEvidenceGroups\.length \? "" : "compact-empty"\}/);
});
