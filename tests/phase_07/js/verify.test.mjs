// Phase 7: the JavaScript verifier over the generated tamper fixtures.
// Fixtures: test-vectors/integrity/tamper/*.zip with expected.json (scripts/make_tamper_fixtures.py).
// Run: node --test tests/phase_07/js/
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..", "..", "..");
const dir = path.join(root, "test-vectors", "integrity", "tamper");
const { verifyBundle } = await import(pathToFileURL(path.join(root, "apps", "verify", "verify.mjs")).href);
const expected = JSON.parse(readFileSync(path.join(dir, "expected.json"), "utf8"));

test("fixture set is complete", () => {
  const zips = readdirSync(dir).filter((f) => f.endsWith(".zip"));
  assert.ok(zips.length >= 8, "unchanged + seven tamper cases (+ import record)");
  for (const z of zips) assert.ok(z in expected, `${z} has an expected verdict`);
});

for (const [file, exp] of Object.entries(expected)) {
  test(`verdict for ${file}`, async () => {
    const result = await verifyBundle(new Uint8Array(readFileSync(path.join(dir, file))));
    assert.equal(result.verdict, exp.verdict);
    const fd = result.first_difference;
    assert.equal(fd ? fd.kind : null, exp.kind ?? null);
    assert.equal(fd ? (fd.seq ?? null) : null, exp.seq ?? null);
    assert.equal(fd ? (fd.version_n ?? null) : null, exp.version_n ?? null);
  });
}

test("not a bundle", async () => {
  await assert.rejects(() => verifyBundle(new Uint8Array([1, 2, 3])), /This file is not a VeriDoc receipt bundle\./);
});
