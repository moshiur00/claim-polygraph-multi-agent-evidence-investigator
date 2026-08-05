import assert from "node:assert/strict";
import test from "node:test";
import { parseNavigationState, serializeNavigationState } from "../app/navigation-state.mjs";

test("defaults to investigations", () => {
  assert.deepEqual(parseNavigationState(""), { view: "investigations", investigationId: null });
});

test("restores a selected investigation", () => {
  assert.deepEqual(parseNavigationState("?investigation=case-1"), { view: "investigations", investigationId: "case-1" });
});

test("restores named workspace views", () => {
  assert.equal(parseNavigationState("?view=review_queue").view, "review_queue");
  assert.equal(parseNavigationState("?view=system_health").view, "system_health");
});

test("rejects unknown views", () => {
  assert.equal(parseNavigationState("?view=admin").view, "investigations");
});

test("serializes selection and view deterministically", () => {
  assert.equal(serializeNavigationState({ view: "investigations", investigationId: "case-1" }), "?investigation=case-1");
  assert.equal(serializeNavigationState({ view: "review_queue", investigationId: null }), "?view=review_queue");
  assert.equal(serializeNavigationState({ view: "investigations", investigationId: null }), "/");
});
