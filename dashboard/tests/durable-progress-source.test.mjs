import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const hook = await readFile(new URL("../app/use-durable-event-stream.ts", import.meta.url), "utf8");
const page = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");

test("durable stream resumes from a persisted cursor and prevents duplicate streams", () => {
  assert.match(hook, /window\.sessionStorage\.getItem\(storageKey\)/);
  assert.match(hook, /window\.sessionStorage\.setItem\(storageKey, String\(cursor\)\)/);
  assert.match(hook, /after=\$\{Math\.max\(0, cursor\)}/);
  assert.match(hook, /source\?\.close\(\);/);
  assert.match(hook, /cancelled = true/);
  assert.match(hook, /window\.clearTimeout\(reconnectTimer\)/);
  assert.match(hook, /window\.clearInterval\(pollTimer\)/);
});

test("durable stream uses bounded backoff, polling and stale-state detection", () => {
  assert.match(hook, /Math\.min\(8_000, 500 \* 2 \*\*/);
  assert.match(hook, /if \(failures >= 3\) startPolling\(\)/);
  assert.match(hook, /pollingIntervalMs \?\? 2_000/);
  assert.match(hook, /staleAfterMs \?\? 15_000/);
  assert.match(hook, /"Progress is stale\./);
  assert.match(hook, /"Live events are unavailable; persisted state polling is active\./);
});

test("malformed events fail safely without mutating authoritative state", () => {
  assert.match(hook, /JSON\.parse\(event\.data\)/);
  assert.match(hook, /malformedEvents \+= 1/);
  assert.match(hook, /"A malformed progress event was ignored safely\./);
});

test("dashboard uses the durable hook instead of one-shot EventSource effects", () => {
  assert.match(page, /useDurableEventStream<AuthoritativeJob>/);
  assert.match(page, /useDurableEventStream<GraphSnapshot>/);
  assert.match(page, /sequenceOf: \(_eventName, state\) => state\.graph/);
  assert.match(page, /poll: \(\) => request<AuthoritativeJob>/);
  assert.match(page, /Review state · Awaiting decision/);
  assert.match(page, /Safely paused at a persisted checkpoint/);
  assert.doesNotMatch(page, /new EventSource\(/);
  assert.doesNotMatch(page, /stream\.onerror = \(\) => stream\.close\(\)/);
});
