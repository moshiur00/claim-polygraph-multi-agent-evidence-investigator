import assert from "node:assert/strict";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);
  return worker.fetch(new Request("http://localhost/"), {
    ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) },
  }, { waitUntil() {}, passThroughOnException() {} });
}

test("renders the Claim Polygraph review console", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  const html = await response.text();
  assert.match(html, /Claim Polygraph/);
  assert.match(html, /Investigate a factual claim/);
  assert.match(html, /CLAIM TO INVESTIGATE/);
  assert.match(html, /CONNECTION REQUIRED/);
  assert.match(html, /CLAIM DESK/);
  assert.match(html, /Research safeguards/);
  assert.match(html, /Evidence service/);
  assert.match(html, /InvestigationService authority/);
  assert.doesNotMatch(html, /codex-preview|react-loading-skeleton/);
});
