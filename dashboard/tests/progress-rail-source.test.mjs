import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("authoritative progress rail keeps all twelve stages on one track", async () => {
  const css = await readFile(new URL("../app/globals.css", import.meta.url), "utf8");

  const investigationRule = css.match(/\.investigation-graph\s*\{([^}]+)\}/);
  assert.ok(investigationRule, "investigation graph needs an explicit responsive rule");
  assert.match(investigationRule[1], /grid-template-columns:\s*repeat\(12,/);
  assert.match(investigationRule[1], /overflow-x:\s*auto/);
  assert.doesNotMatch(investigationRule[1], /repeat\(7,/);
});
