import assert from "node:assert/strict";
import test from "node:test";

import {
  API_STORAGE_KEY,
  ApiConfigurationError,
  inferApiAddress,
  loadApiConfiguration,
  normalizeApiAddress,
  resetApiConfiguration,
  saveApiConfiguration,
} from "../app/api-configuration.mjs";

const storage = (initial = {}) => {
  const values = new Map(Object.entries(initial));
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
    values,
  };
};

test("normalizes origins and repairs an unbracketed IPv6 host with a port", () => {
  assert.equal(normalizeApiAddress(" http://localhost:8000/ "), "http://localhost:8000");
  assert.equal(normalizeApiAddress("http://::1:8000"), "http://[::1]:8000");
  assert.equal(normalizeApiAddress("https://[2001:db8::1]:8443"), "https://[2001:db8::1]:8443");
});

test("infers safe IPv4, hostname and bracketed IPv6 API origins", () => {
  assert.equal(inferApiAddress({ protocol: "http:", hostname: "127.0.0.1" }), "http://127.0.0.1:8000");
  assert.equal(inferApiAddress({ protocol: "https:", hostname: "desk.local" }), "https://desk.local:8000");
  assert.equal(inferApiAddress({ protocol: "http:", hostname: "::1" }), "http://[::1]:8000");
  assert.equal(inferApiAddress({ protocol: "http:", hostname: "[::1]" }), "http://[::1]:8000");
});

test("loads a saved address before the inferred default", () => {
  const local = storage({ [API_STORAGE_KEY]: "http://10.0.0.4:9000/" });
  assert.deepEqual(loadApiConfiguration(local, { protocol: "http:", hostname: "localhost" }), {
    address: "http://10.0.0.4:9000",
    source: "saved",
    warning: null,
  });
});

test("fails safely to the inferred origin when saved configuration is invalid", () => {
  const local = storage({ [API_STORAGE_KEY]: "not a url" });
  const result = loadApiConfiguration(local, { protocol: "http:", hostname: "localhost" });
  assert.equal(result.address, "http://localhost:8000");
  assert.equal(result.source, "inferred");
  assert.match(result.warning, /saved API address was invalid/i);
});

test("rejects credentials, paths, queries, fragments and unsupported input", () => {
  for (const value of [
    "localhost:8000",
    "ftp://localhost:8000",
    "http://user:secret@localhost:8000",
    "http://localhost:8000/api",
    "http://localhost:8000?token=secret",
    "http://localhost:8000#health",
  ]) {
    assert.throws(() => normalizeApiAddress(value), ApiConfigurationError);
  }
});

test("save persists normalized origins and reset removes the override", () => {
  const local = storage();
  assert.equal(saveApiConfiguration(local, "http://localhost:9000/"), "http://localhost:9000");
  assert.equal(local.values.get(API_STORAGE_KEY), "http://localhost:9000");
  assert.equal(resetApiConfiguration(local, { protocol: "http:", hostname: "::1" }), "http://[::1]:8000");
  assert.equal(local.values.has(API_STORAGE_KEY), false);
});
