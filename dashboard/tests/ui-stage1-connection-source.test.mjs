import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const page = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");

test("UI.1 imports the saved configuration loader it invokes", () => {
  assert.match(page, /loadApiConfiguration,/);
  assert.match(page, /loadApiConfiguration\(window\.localStorage, window\.location\)/);
});

test("UI.1 exposes explicit connection states and recoverable controls", () => {
  assert.match(page, /type ConnectionState = "initializing" \| "connecting" \| "connected" \| "unavailable" \| "invalid"/);
  assert.match(page, /loadApiConfiguration\(window\.localStorage, window\.location\)/);
  assert.match(page, /saveApiConfiguration\(window\.localStorage, apiDraft\)/);
  assert.match(page, /resetApiConfiguration\(window\.localStorage, window\.location\)/);
  assert.match(page, /Save & retry/);
  assert.match(page, /Reset to local default/);
  assert.match(page, /setConnectionRetry\(\(value\) => value \+ 1\)/);
  assert.match(page, /role="status" aria-live="polite"/);
});

test("UI.1 does not interpolate window hostname into an unvalidated URL", () => {
  assert.doesNotMatch(page, /window\.location\.hostname}:8000/);
  assert.doesNotMatch(page, /localStorage\.setItem\("claim-polygraph-api", inferred\)/);
});
