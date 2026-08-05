import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const page = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");

test("empty social evidence does not inherit the overall publication label", () => {
  assert.match(page, /<dt>Social-policy impact<\/dt>/);
  assert.match(page, /No blocker recorded/);
  assert.doesNotMatch(page, /<dt>Publication<\/dt><dd>\{titleCase\(report\.publication_decision/);
});

test("empty social evidence distinguishes recorded facts from unknown discovery use", () => {
  assert.match(page, /No social-media passage was retained in the evidence packet/);
  assert.match(page, /No retained evidence item is classified as social-platform content/);
  assert.match(page, /current integrity and disposition records remain authoritative/);
  assert.match(page, /Whether social links served as discovery leads was not recorded/);
  assert.match(page, /<dt>Social discovery leads<\/dt><dd>Not recorded<\/dd>/);
  assert.doesNotMatch(page, /The approved evidence packet and provenance analysis remain authoritative/);
});

test("empty social evidence exposes separate evidence and review actions", () => {
  assert.match(page, /View all retained evidence/);
  assert.match(page, /See why human review is required/);
  assert.match(page, /How social evidence would be evaluated/);
});
