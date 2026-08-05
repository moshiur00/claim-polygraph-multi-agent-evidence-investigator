import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const page = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");
const css = await readFile(new URL("../app/globals.css", import.meta.url), "utf8");
const annotation = await readFile(new URL("../app/annotation/page.tsx", import.meta.url), "utf8");

test("UI.4 exposes landmarks, a skip link and named compact navigation", () => {
  assert.match(page, /className="skip-link" href="#workspace-content"/);
  assert.match(page, /id="workspace-content" tabIndex=\{-1\}/);
  assert.match(page, /aria-label="Claim Polygraph workspace"/);
  assert.match(page, /aria-current=\{workspaceView === "investigations"/);
  assert.doesNotMatch(page, /<main>\s*\n/);
});

test("UI.4 report tabs implement the ARIA and keyboard interaction contract", () => {
  assert.match(page, /role="tablist" aria-label="Investigation report sections"/);
  assert.match(page, /aria-controls="report-section-panel"/);
  assert.match(page, /role="tabpanel"/);
  assert.match(page, /"ArrowLeft", "ArrowRight", "Home", "End"/);
  assert.match(page, /tabIndex=\{section === item \? 0 : -1\}/);
});

test("UI.4 provides focus, reduced-motion and narrow-screen safeguards", () => {
  assert.match(css, /:focus-visible/);
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)/);
  assert.match(css, /@media \(forced-colors: active\)/);
  assert.match(css, /@media \(max-width: 480px\)/);
  assert.match(css, /\.tabs \{[^}]*overflow-x: auto/s);
});

test("annotation notifications have an accessible dismissal name", () => {
  assert.match(annotation, /aria-label="Dismiss notification"/);
});
