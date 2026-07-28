import assert from "node:assert/strict";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("a11y", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);
  return worker.fetch(
    new Request("http://localhost/"),
    { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } },
    { waitUntil() {}, passThroughOnException() {} },
  );
}

test("server-rendered console exposes its essential accessibility structure", async () => {
  const response = await render();
  const html = await response.text();

  assert.equal(response.status, 200);
  assert.match(html, /<html[^>]+lang="en"/);
  assert.match(html, /<main[^>]+class="app-shell"/);
  assert.match(html, /<nav[^>]+aria-label="Investigations"/);
  assert.match(html, /<h1[^>]*>Investigate a factual claim<\/h1>/);
  assert.match(html, /<label[^>]+for="claim-input"/);
  assert.match(html, /<input[^>]+id="claim-input"/);
  assert.match(html, /<input[^>]+aria-label="API address"/);
  assert.doesNotMatch(html, /<button[^>]*>\s*<\/button>/);
  assert.doesNotMatch(html, /tabindex="-1"/i);
});
