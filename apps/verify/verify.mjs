// VeriDoc receipt verifier in vanilla JavaScript (INTEGRITY_SPEC section 10; PHASES.md Appendix D).
// The same checks and the same verdict as packages/integrity/verify.py. It reads one zip, uses the primitives in
// integrity.mjs and WebCrypto, writes nothing and uses no network. verify.html inlines this file and integrity.mjs.
import { TYPE_BYTE, chainLink, leafHash, merkleRoot, parseTimestamp, payloadDigestJson, plainHash, sha256, termsDigest } from "./integrity.mjs";

export const NOT_A_BUNDLE = "This file is not a VeriDoc receipt bundle.";
const SUPPORTED_SPEC_VERSIONS = new Set(["1.1"]);
const KNOWN_MEMBERS = new Set(["receipt.json", "leaves.jsonl", "chain.json", "import_record.json", "README.txt"]);
const KINDS = new Set(["message", "voice_audio", "transcript_span", "handshake_seal", "attachment", "term", "confirmation"]);
const hex = (u8) => Array.from(u8, (b) => b.toString(16).padStart(2, "0")).join("");
const unhex = (s) => {
  if (typeof s !== "string" || s.length % 2 || !/^[0-9a-fA-F]*$/.test(s)) throw new Error("bad hex");
  return Uint8Array.from(s.match(/../g) ?? [], (h) => parseInt(h, 16));
};
const sameBytes = (a, b) => a.length === b.length && a.every((x, i) => x === b[i]);
const isInt = (v) => Number.isInteger(v);

// ---- a small zip reader: stored and deflate entries, no zip64 ----

async function inflate(data) {
  const stream = new Blob([data]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

function openZip(bytes) {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  let end = -1;
  for (let i = bytes.length - 22; i >= Math.max(0, bytes.length - 22 - 65535); i--) {
    if (view.getUint32(i, true) === 0x06054b50) {
      end = i;
      break;
    }
  }
  if (end < 0) throw new Error("no zip directory");
  const count = view.getUint16(end + 10, true);
  let at = view.getUint32(end + 16, true);
  const entries = new Map();
  for (let n = 0; n < count; n++) {
    if (view.getUint32(at, true) !== 0x02014b50) throw new Error("bad zip directory");
    const method = view.getUint16(at + 10, true);
    const size = view.getUint32(at + 20, true);
    const nameLen = view.getUint16(at + 28, true);
    const extraLen = view.getUint16(at + 30, true);
    const commentLen = view.getUint16(at + 32, true);
    const offset = view.getUint32(at + 42, true);
    const name = new TextDecoder().decode(bytes.subarray(at + 46, at + 46 + nameLen));
    if (!name.endsWith("/")) entries.set(name, { method, size, offset });
    at += 46 + nameLen + extraLen + commentLen;
  }
  return {
    names: [...entries.keys()],
    has: (name) => entries.has(name),
    async read(name) {
      const { method, size, offset } = entries.get(name);
      if (view.getUint32(offset, true) !== 0x04034b50) throw new Error("bad zip entry");
      const start = offset + 30 + view.getUint16(offset + 26, true) + view.getUint16(offset + 28, true);
      const raw = bytes.subarray(start, start + size);
      if (method === 0) return raw;
      if (method === 8) return inflate(raw);
      throw new Error("unsupported zip method");
    },
  };
}

// ---- one leaf: the hash recomputed from what the bundle discloses, and whether the row is consistent ----

async function checkLeaf(row, files) {
  let listed;
  try {
    listed = unhex(row.leaf_hash);
  } catch {
    return [new Uint8Array(32), false];
  }
  try {
    const salt = row.salt ? unhex(row.salt) : null;
    const digest = row.payload_digest ? unhex(row.payload_digest) : null;
    let calc;
    if (row.payload !== null && row.payload !== undefined) calc = await payloadDigestJson(row.payload);
    else if (row.payload_file && files.has(row.payload_file)) calc = await sha256(files.get(row.payload_file));
    else calc = digest; // nothing disclosed to recompute from: taken as given
    const ok = digest === null || (calc !== null && sameBytes(calc, digest));
    const use = calc ?? digest;
    if (salt === null || use === null) return [listed, ok];
    const recomputed = await leafHash(row.type_byte, salt, use);
    return [recomputed, ok && sameBytes(recomputed, listed)];
  } catch {
    return [listed, false];
  }
}

function difference(kind, seq = null, version_n = null) {
  return { kind, seq: isInt(seq) && seq >= 1 ? seq : null, version_n: isInt(version_n) && version_n >= 1 ? version_n : null };
}

export async function verifyBundle(zipBytes) {
  let zip, files, envelope, body, claimed, rows, chainJson, record;
  try {
    zip = openZip(zipBytes);
    if (!zip.has("receipt.json") || !zip.has("leaves.jsonl")) throw new Error("missing member");
    files = new Map();
    for (const name of zip.names) files.set(name, await zip.read(name));
    const text = (name) => new TextDecoder("utf-8", { fatal: true }).decode(files.get(name));
    envelope = JSON.parse(text("receipt.json"));
    body = envelope.body;
    claimed = envelope.receipt_hash;
    rows = text("leaves.jsonl").split("\n").filter((l) => l.trim()).map((l) => JSON.parse(l));
    chainJson = files.has("chain.json") ? JSON.parse(text("chain.json")) : [];
    record = files.has("import_record.json") ? JSON.parse(text("import_record.json")) : null;
    if (!body || typeof body !== "object" || !Array.isArray(rows) || !rows.every((r) => r && typeof r === "object") || !Array.isArray(chainJson)) {
      throw new Error("bad shape");
    }
    if (typeof body.spec_version === "undefined") throw new Error("no spec version");
  } catch {
    throw new Error(NOT_A_BUNDLE);
  }
  if (!SUPPORTED_SPEC_VERSIONS.has(body.spec_version)) {
    throw Object.assign(new Error(`spec version ${JSON.stringify(body.spec_version)} is not supported`), { name: "UnsupportedSpecVersion" });
  }
  const bodyChain = Array.isArray(body.chain) ? body.chain : [];
  const checks = [];
  const candidates = {};
  const warnings = [...files.keys()].filter((n) => !KNOWN_MEMBERS.has(n) && !n.startsWith("media/")).map((n) => `unknown file ignored: ${n}`);

  // the envelope: the receipt hash covers the body only
  let envelopeOk = false;
  try {
    envelopeOk = hex(await plainHash(TYPE_BYTE.RECEIPT, body)) === claimed;
  } catch {
    envelopeOk = false;
  }
  checks.push({ name: "spec_version", ok: envelopeOk, detail: `spec ${body.spec_version}; ${envelopeOk ? "receipt hash matches" : "receipt hash does not match its body"}` });
  if (!envelopeOk) candidates.receipt = difference("receipt");

  // leaves
  const recomputed = [];
  let leafBad = null;
  for (let index = 0; index < rows.length; index++) {
    const [leaf, ok] = await checkLeaf(rows[index], files);
    recomputed.push(leaf);
    if ((!ok || rows[index].seq !== index + 1) && leafBad === null) leafBad = rows[index];
  }
  if (leafBad !== null) candidates.leaf = difference(KINDS.has(leafBad.kind) ? leafBad.kind : "message", leafBad.seq);
  checks.push({
    name: "leaves",
    ok: leafBad === null,
    detail: leafBad === null ? `${rows.length} leaves checked` : `leaf ${leafBad.seq} (${leafBad.kind}) does not match`,
  });

  // the Merkle root, rebuilt from the recomputed leaf hashes
  let rootOk = false;
  try {
    rootOk = rows.length > 0 && hex(await merkleRoot(recomputed)) === body.root && body.leaf_count === rows.length;
  } catch {
    rootOk = false;
  }
  checks.push({ name: "merkle_root", ok: rootOk, detail: rootOk ? "root matches" : "root does not match the leaves" });
  if (!rootOk) candidates.root = difference("root");

  // the version chain and the version roots
  const byVersion = new Map(chainJson.filter((e) => e && typeof e === "object").map((e) => [e.version_n, e]));
  const chainBad = [];
  const rootsBad = [];
  let good = 0;
  let previous = null;
  for (const entry of bodyChain) {
    const version = entry ? entry.version_n : null;
    const full = byVersion.get(version);
    let chainOk = false;
    let rootsOk = false;
    if (full !== undefined) {
      try {
        const digest = await termsDigest(full.terms_set);
        const link = await chainLink(previous, digest, unhex(full.root));
        chainOk = hex(digest) === full.terms_digest && full.terms_digest === entry.terms_digest && hex(link) === full.link && full.link === entry.link && full.root === entry.root;
        previous = link;
        const count = full.leaf_count;
        rootsOk = isInt(count) && count >= 1 && count <= recomputed.length && hex(await merkleRoot(recomputed.slice(0, count))) === full.root;
      } catch {
        // stays false
      }
    }
    if (chainOk) good++;
    else chainBad.push(version);
    if (!rootsOk) rootsBad.push(version);
  }
  const inBody = new Set(bodyChain.map((e) => (e ? e.version_n : null)));
  for (const v of byVersion.keys()) if (!inBody.has(v)) chainBad.push(v);
  const lowest = (list) => {
    const ints = list.filter(isInt);
    return ints.length ? Math.min(...ints) : null;
  };
  checks.push({ name: "chain", ok: chainBad.length === 0, detail: bodyChain.length ? `${good} of ${bodyChain.length} links verified` : "no versions yet" });
  checks.push({ name: "version_roots", ok: rootsBad.length === 0, detail: rootsBad.length ? `version ${lowest(rootsBad)} root does not match` : "every version root matches its leaves" });
  if (chainBad.length) candidates.chain = difference("chain_link", null, lowest(chainBad));
  if (rootsBad.length) candidates.version_roots = difference("chain_link", null, lowest(rootsBad));

  // the import record (I-09)
  let recordOk = false;
  try {
    recordOk = record !== null && hex(await plainHash(TYPE_BYTE.IMPORT_RECORD, record)) === body.import_record_hash;
  } catch {
    recordOk = false;
  }
  checks.push({ name: "import_record", ok: recordOk, detail: recordOk ? "import record matches" : "import record does not match the receipt" });
  if (!recordOk) candidates.import_record = difference("import_record");

  // timestamps: an inconsistent order is a warning, never ALTERED on its own
  let timeOk = false;
  try {
    const recorded = parseTimestamp(body.recorded_at).date.getTime();
    const messageTimes = rows.filter((r) => r.kind === "message" && r.payload && "ts" in r.payload).map((r) => parseTimestamp(r.payload.ts).date.getTime());
    const created = chainJson.filter((e) => e && "created_at" in e).map((e) => parseTimestamp(e.created_at).date.getTime());
    timeOk = [...messageTimes, ...created].every((t) => t <= recorded) && created.every((t, i) => i === 0 || created[i - 1] <= t);
  } catch {
    timeOk = false;
  }
  checks.push({ name: "timestamps", ok: timeOk, detail: timeOk ? "times are in a consistent order" : "times are inconsistent" });
  if (!timeOk) warnings.push("timestamps are inconsistent: the receipt time is earlier than a message or versions are out of order");

  const anchor = body.anchor ?? null;
  checks.push({
    name: "anchor",
    ok: true,
    detail: anchor === null
      ? "not anchored: the time comes from the device clock"
      : `anchored on ${anchor.network} (${anchor.tx}); checking the anchor itself needs the network and is not done offline`,
  });

  const first = ["leaf", "chain", "version_roots", "import_record", "root", "receipt"].map((k) => candidates[k]).find(Boolean) ?? null;
  return { verdict: first ? "ALTERED" : "UNCHANGED", checks, first_difference: first, warnings };
}
