// Phase 1: the JavaScript integrity module must reproduce every Python test vector.
// Run: node --test "tests/phase_01/js/*.test.mjs"
// Module under test: apps/verify/integrity.mjs (PHASES.md Phase 1, task 9).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..", "..", "..");
const vec = (name) =>
  JSON.parse(readFileSync(path.join(root, "test-vectors", "integrity", name), "utf8"));
const I = await import(pathToFileURL(path.join(root, "apps", "verify", "integrity.mjs")).href);

const hex = (u8) => Buffer.from(u8).toString("hex");
const unhex = (s) => new Uint8Array(Buffer.from(s, "hex"));
// Cases marked "only": "python" test Python-specific number handling (PHASES.md Appendix B).
const forJs = (cases) => cases.filter((c) => c.only !== "python");

test("sha256 vectors", async () => {
  for (const c of forJs(vec("sha256.json").cases)) {
    const got = await I.sha256(new TextEncoder().encode(c.input.utf8));
    assert.equal(hex(got), c.expected.hex, c.name);
  }
});

test("jcs vectors", () => {
  for (const c of forJs(vec("jcs.json").cases)) {
    const obj = JSON.parse(c.input.json_text);
    if (c.expected.reject) {
      assert.throws(() => I.canonicalize(obj), c.name);
    } else {
      assert.equal(I.canonicalize(obj), c.expected.canonical, c.name);
    }
  }
});

test("normalize vectors", () => {
  for (const c of forJs(vec("normalize.json").cases)) {
    assert.deepEqual(I.normalizeRecord(c.input.value), c.expected.value, c.name);
  }
});

test("leaf vectors", async () => {
  for (const c of forJs(vec("leaves.json").cases)) {
    const salt = unhex(c.input.salt_hex);
    if (c.expected.reject) {
      const digest = await I.sha256(unhex(c.input.payload_hex ?? ""));
      await assert.rejects(() => I.leafHash(c.input.type_byte, salt, digest), c.name);
      continue;
    }
    const digest =
      "payload_json" in c.input
        ? await I.payloadDigestJson(c.input.payload_json)
        : await I.sha256(unhex(c.input.payload_hex));
    assert.equal(hex(digest), c.expected.payload_digest, c.name);
    assert.equal(hex(await I.leafHash(c.input.type_byte, salt, digest)), c.expected.leaf, c.name);
  }
});

test("plain vectors", async () => {
  for (const c of forJs(vec("plain.json").cases)) {
    if (c.expected.reject) {
      await assert.rejects(() => I.plainHash(c.input.type_byte, c.input.object), c.name);
    } else {
      assert.equal(hex(await I.plainHash(c.input.type_byte, c.input.object)), c.expected.hash, c.name);
    }
  }
});

test("merkle vectors", async () => {
  for (const c of forJs(vec("merkle.json").cases)) {
    const leaves = c.input.leaves.map(unhex);
    if (c.expected.reject) {
      await assert.rejects(() => I.merkleRoot(leaves), c.name);
      continue;
    }
    assert.equal(hex(await I.merkleRoot(leaves)), c.expected.root, c.name);
    for (let i = 0; i < leaves.length; i++) {
      const proof = (await I.inclusionProof(leaves, i)).map(([side, h]) => ({ side, hash: hex(h) }));
      assert.deepEqual(proof, c.expected.proofs[i], `${c.name} proof ${i}`);
    }
  }
});

test("chain vectors", async () => {
  for (const c of forJs(vec("chain.json").cases)) {
    let prev = null;
    for (const [i, v] of c.input.versions.entries()) {
      const td = await I.termsDigest(v.terms_set);
      assert.equal(hex(td), c.expected.terms_digests[i]);
      prev = await I.chainLink(prev, td, unhex(v.root));
      assert.equal(hex(prev), c.expected.links[i]);
    }
  }
});

test("echo vectors", async () => {
  for (const c of forJs(vec("echo.json").cases)) {
    if ("recap" in c.input) {
      const rh = await I.recapHash(c.input.recap);
      assert.equal(hex(rh), c.expected.recap_hash, c.name);
      assert.equal(await I.echoCode(rh), c.expected.code, c.name);
    } else {
      assert.equal(I.codesMatch(c.input.reply, c.input.code), c.expected.match, c.name);
    }
  }
});

test("timestamp vectors", () => {
  for (const c of forJs(vec("timestamp.json").cases)) {
    if (c.expected.valid) {
      assert.doesNotThrow(() => I.parseTimestamp(c.input.text), c.name);
    } else {
      assert.throws(() => I.parseTimestamp(c.input.text), c.name);
    }
  }
});

test("worked example root", async () => {
  const leaves = [
    "eeb767408a78a214391a6ac1741af71f760942fc6a622ac339f71ea353b1a031",
    "fb6c734564c502a8fad2b84a96a5b65ce61c4c4b29d8793ba9415f49aff04ed6",
    "819e4dd2d881aea6aacd2ff2660e87ce2bf6adcdcc61c45d968c90d5d3ec5191",
  ].map(unhex);
  assert.equal(
    hex(await I.merkleRoot(leaves)),
    "eabcf74ed1892907946af628a5c56b54b6ef1ec1fb22746d847fd2fc19eca2a5",
  );
});

test("module makes no network calls", () => {
  const src = readFileSync(path.join(root, "apps", "verify", "integrity.mjs"), "utf8");
  for (const banned of ["fetch(", "XMLHttpRequest", "WebSocket", "http://", "https://", "import("]) {
    assert.ok(!src.includes(banned), `integrity.mjs must not contain ${banned}`);
  }
});

test("timestamps round trip with the offset kept", () => {
  for (const text of ["2026-10-12T10:02:00+05:30", "2026-01-02T03:04:05-03:30", "2026-06-15T12:00:00+00:00"]) {
    const { date, offsetMinutes } = I.parseTimestamp(text);
    assert.equal(I.formatTimestamp(date, offsetMinutes), text);
  }
  assert.equal(I.parseTimestamp("2026-10-12T10:02:00+05:30").date.toISOString(), "2026-10-12T04:32:00.000Z");
  assert.throws(() => I.formatTimestamp(new Date(Date.UTC(2026, 0, 1, 0, 0, 0, 500)), 0));
});

test("canonicalize rejects non-JSON values", () => {
  for (const bad of [undefined, () => 1, 10n, NaN, Infinity, { x: new Date(0) }, [Symbol("s")]]) {
    assert.throws(() => I.canonicalize(bad));
  }
  assert.equal(I.canonicalize({ "～": 1, "😀": 2 }), '{"😀":2,"～":1}');
  assert.equal(I.canonicalize([-0, 1e21, 1e-7]), "[0,1e+21,1e-7]");
});

test("normalizeText keeps keys and spaces, fixes NFC and line endings", () => {
  assert.equal(I.normalizeText("é\r\na\rb  "), "é\na\nb  ");
  assert.deepEqual(I.normalizeRecord({ "é": ["é", 1, null] }), { "é": ["é", 1, null] });
});

test("inclusion proofs verify and tampering fails", async () => {
  const leaves = await Promise.all([0, 1, 2, 3, 4].map((i) => I.sha256(new TextEncoder().encode(`leaf-${i}`))));
  const root = await I.merkleRoot(leaves);
  for (let i = 0; i < leaves.length; i++) {
    assert.ok(await I.verifyInclusion(leaves[i], await I.inclusionProof(leaves, i), root));
  }
  const proof = await I.inclusionProof(leaves, 1);
  assert.ok(!(await I.verifyInclusion(leaves[0], proof, root)));
  assert.ok(!(await I.verifyInclusion(leaves[1], [["up", proof[0][1]], ...proof.slice(1)], root)));
  await assert.rejects(() => I.inclusionProof(leaves, 5));
  await assert.rejects(() => I.merkleRoot([new Uint8Array(31)]));
});

test("echo code extraction maps look-alikes on the code token only", () => {
  assert.equal(I.extractCode("CONFIRM ABCD"), "ABCD");
  assert.equal(I.extractCode("confirm o1li"), "0111");
  assert.equal(I.extractCode("CONFIRMED 7F3K"), null);
  assert.equal(I.extractCode("CONFIRM 7F3U"), null);
  assert.ok(I.codesMatch("  ok   confirm 7f3k  ", "7F3K"));
});

test("chain and echo operands must be raw 32 bytes", async () => {
  const d = new Uint8Array(32);
  await assert.rejects(() => I.chainLink(new Uint8Array(31), d, d));
  await assert.rejects(() => I.chainLink(null, d, "00".repeat(32)));
  await assert.rejects(() => I.echoCode("00".repeat(32)));
});
