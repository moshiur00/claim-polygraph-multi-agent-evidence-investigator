import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const page = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");

test("UI.3 navigation destinations are functional and URL backed", () => {
  assert.match(page, /navigateWorkspace\("review_queue"\)/);
  assert.match(page, /navigateWorkspace\("system_health"\)/);
  assert.match(page, /history\.pushState/);
  assert.match(page, /addEventListener\("popstate"/);
});

test("UI.3 uses canonical review and health APIs", () => {
  assert.match(page, /request<ReviewRequest\[]>\("\/api\/reviews"\)/);
  assert.match(page, /`\/api\/reviews\/\$\{item\.request_id\}`/);
  assert.match(page, /request<ApiStatus>\("\/health"\)/);
  assert.match(page, /request<TelemetrySnapshot>\("\/api\/operations\/telemetry"\)/);
});

test("UI.3 exposes search and complete operational states", () => {
  assert.match(page, /aria-label="Search investigations"/);
  assert.match(page, /No matching cases/);
  assert.match(page, /No review requests/);
  assert.match(page, /Review queue unavailable/);
  assert.match(page, /Loading durable review records/);
  assert.match(page, /Telemetry unavailable/);
});
