import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const page = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");

test("connected landing state distinguishes a new investigation from a first claim", () => {
  assert.match(page, /investigations\.length > 0 \? "Start a new investigation" : "Submit your first claim"/);
  assert.match(page, /open an existing investigation from Recent Cases/);
});

test("connection recovery control is hidden while the evidence service is connected", () => {
  assert.match(page, /\{!connected && <button className="ghost"/);
  assert.match(page, />Retry connection<\/button>\}/);
  assert.match(page, /EVIDENCE WORKSPACE READY/);
  assert.match(page, /CONNECTION REQUIRED/);
});

test("investigation submission is resilient and immediately visible", () => {
  assert.match(page, /const clientRequestId = \(\) =>/);
  assert.match(page, /globalThis\.crypto\?\.randomUUID\?\.\(\)/);
  assert.match(page, /idempotency_key: `dashboard:\$\{clientRequestId\(\)\}`/);
  assert.match(page, /<button type="submit" className="primary"/);
  assert.match(page, /Starting…/);
  assert.match(page, /className="claim-submit-error" role="alert"/);
});

test("failed durable jobs remain visible and offer a no-cost retry preparation", () => {
  assert.match(page, /const jobFailed = job != null/);
  assert.match(page, /className="job-failure-card" role="alert"/);
  assert.match(page, /No report was produced for that attempt/);
  assert.match(page, /Use claim in a new attempt/);
  assert.match(page, /Earlier attempt stopped/);
  assert.match(page, /setClaim\(failedClaim\)/);
});
