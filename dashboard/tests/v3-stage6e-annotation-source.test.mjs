import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const source = fs.readFileSync(
  new URL("../app/annotation/page.tsx", import.meta.url),
  "utf8",
);
const packet = JSON.parse(
  fs.readFileSync(
    new URL("../public/v3-stage6e-fresh-calibration.json", import.meta.url),
    "utf8",
  ),
);

test("V3.6e is exposed as a dedicated fresh-review packet", () => {
  assert.match(source, /Start V3\.6e fresh review/);
  assert.match(source, /v3-stage6e-fresh-calibration\.json/);
  assert.match(
    source,
    /verification_construction_v3_stage6e_fresh_calibration_workbook_v1_APPROVED\.json/,
  );
  assert.equal(packet.cases.length, 20);
  assert.equal(new Set(packet.cases.map((item) => item.origin_family_id)).size, 10);
});

test("reviewer names are defaults but decisions remain incomplete", () => {
  assert.match(source, /annotator_identity: "Md Moshiur Rahman"/);
  assert.match(source, /approver_identity: "Md Rashedul Islam"/);
  assert.match(source, /Record reviewed annotation/);
  assert.equal(packet.cases.every((item) => item.annotation === null), true);
  assert.equal(packet.cases.every((item) => item.approval === null), true);
  assert.equal(
    packet.cases.every(
      (item) =>
        item.proposal.suggested_gold_label &&
        item.proposal.comparator_or_relation &&
        item.proposal.dimension_bucket,
    ),
    true,
  );
});

test("V3.6e does not pre-check or fabricate independent approval", () => {
  assert.match(source, /decision: "return_for_revision"/);
  assert.match(source, /checked_dimension: false/);
  assert.match(source, /checked_expected_state: false/);
});
