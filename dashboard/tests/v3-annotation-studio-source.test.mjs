import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../app/annotation/page.tsx", import.meta.url), "utf8");

test("V3 annotation studio preserves human-review and quota safeguards", () => {
  for (const expected of [
    "Human Annotation Studio",
    "Import annotation workbook",
    "Start from AI-filled draft",
    "AI draft has not been accepted by a human annotator",
    "Exact claim span",
    "Use as gold evidence",
    "Record independent approval",
    "Approver must be distinct",
    "Quota monitor",
    "Classify honestly",
    "Export blocked",
    "_simulation_notice",
  ]) {
    assert.match(source, new RegExp(expected.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  }
});

test("V3 annotation studio tracks every frozen dimension and construction label", () => {
  for (const expected of [
    "percentage_or_rate",
    "pressure",
    "currency",
    "speed",
    "temporal_interval_or_status",
    "deterministic_constructible",
    "fallback_eligible",
    "unconstructible",
    "not_applicable",
  ]) {
    assert.match(source, new RegExp(expected));
  }
});
