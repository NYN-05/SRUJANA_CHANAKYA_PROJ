// VeriDoc integrity primitives in vanilla JavaScript (INTEGRITY_SPEC sections 2 to 8).
// Byte for byte the same as packages/integrity; checked by test-vectors/integrity/*.json.
// No dependencies and no network: WebCrypto for SHA-256 and an inline RFC 8785 canonicaliser.

export const TYPE_BYTE = Object.freeze({
  MERKLE_NODE: 0x01,
  MESSAGE: 0x10,
  VOICE_AUDIO: 0x11,
  TRANSCRIPT_SPAN: 0x12,
  HANDSHAKE_SEAL: 0x13,
  ATTACHMENT: 0x14,
  TERM: 0x15,
  IMPORT_RECORD: 0x16,
  TERMS_SET: 0x20,
  RECAP: 0x21,
  CONFIRMATION: 0x22,
  CHAIN_LINK: 0x30,
  RECEIPT: 0x40,
  ECHO_CODE: 0x50,
});
export const SALTED_TYPES = new Set([0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x22]);
export const PLAIN_TYPES = new Set([0x16, 0x20, 0x21, 0x30, 0x40, 0x50]);
export const ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";

const utf8 = new TextEncoder();

function concat(...parts) {
  const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let at = 0;
  for (const p of parts) {
    out.set(p, at);
    at += p.length;
  }
  return out;
}

function requireBytes(value, size, name) {
  if (!(value instanceof Uint8Array) || value.length !== size) {
    throw new Error(`${name} must be ${size} raw bytes`);
  }
  return value;
}

function typeByte(t, allowed, form) {
  if (!Number.isInteger(t) || !allowed.has(t)) throw new Error(`type byte ${t} is not a ${form} record type`);
  return Uint8Array.of(t);
}

function equalBytes(a, b) {
  return a.length === b.length && a.every((x, i) => x === b[i]);
}

export async function sha256(bytes) {
  return new Uint8Array(await globalThis.crypto.subtle.digest("SHA-256", bytes));
}

// ---- normalisation and RFC 8785 ----

export function normalizeText(s) {
  return s.normalize("NFC").replace(/\r\n?/g, "\n");
}

export function normalizeRecord(o) {
  if (typeof o === "string") return normalizeText(o);
  if (Array.isArray(o)) return o.map(normalizeRecord);
  if (o !== null && typeof o === "object") {
    return Object.fromEntries(Object.entries(o).map(([k, v]) => [k, normalizeRecord(v)]));
  }
  return o;
}

// RFC 8785: ECMAScript number and string serialisation, object keys sorted by UTF-16 code units
// (the default comparison of Array.prototype.sort), no whitespace. Returns a string.
export function canonicalize(o) {
  if (o === null || typeof o === "boolean") return JSON.stringify(o);
  if (typeof o === "number") {
    if (!Number.isFinite(o)) throw new Error("NaN and infinities cannot be canonicalised");
    return JSON.stringify(o); // -0 becomes "0"
  }
  if (typeof o === "string") return JSON.stringify(o);
  if (Array.isArray(o)) return `[${o.map(canonicalize).join(",")}]`;
  if (typeof o === "object" && Object.getPrototypeOf(o) === Object.prototype) {
    const keys = Object.keys(o).sort();
    return `{${keys.map((k) => `${JSON.stringify(k)}:${canonicalize(o[k])}`).join(",")}}`;
  }
  throw new Error(`${typeof o} is not a JSON type`);
}

const recordBytes = (o) => utf8.encode(canonicalize(normalizeRecord(o)));

// ---- leaves and plain hashes ----

export async function payloadDigestJson(o) {
  return sha256(recordBytes(o));
}

export async function leafHash(t, salt, payloadDigest) {
  const prefix = typeByte(t, SALTED_TYPES, "salted");
  return sha256(concat(prefix, requireBytes(salt, 16, "salt"), requireBytes(payloadDigest, 32, "payload digest")));
}

export async function plainHash(t, o) {
  return sha256(concat(typeByte(t, PLAIN_TYPES, "plain"), recordBytes(o)));
}

// ---- Merkle tree: odd last node carried up, never duplicated ----

const node = (left, right) => sha256(concat(Uint8Array.of(TYPE_BYTE.MERKLE_NODE), left, right));

async function levels(leaves) {
  if (!leaves.length) throw new Error("an empty tree has no root");
  leaves.forEach((leaf) => requireBytes(leaf, 32, "leaf"));
  const out = [leaves];
  for (let level = leaves; level.length > 1; out.push(level)) {
    const next = [];
    for (let i = 0; i + 1 < level.length; i += 2) next.push(await node(level[i], level[i + 1]));
    if (level.length % 2) next.push(level[level.length - 1]);
    level = next;
  }
  return out;
}

export async function merkleRoot(leaves) {
  const all = await levels(leaves);
  return all[all.length - 1][0];
}

export async function inclusionProof(leaves, index) {
  const all = await levels(leaves);
  if (!Number.isInteger(index) || index < 0 || index >= leaves.length) throw new RangeError(`leaf index ${index} out of range`);
  const proof = [];
  for (const level of all.slice(0, -1)) {
    if (index % 2) proof.push(["left", level[index - 1]]);
    else if (index + 1 < level.length) proof.push(["right", level[index + 1]]);
    index = Math.floor(index / 2);
  }
  return proof;
}

export async function verifyInclusion(leaf, proof, root) {
  let current = leaf;
  for (const [side, sibling] of proof) {
    if (side === "left") current = await node(sibling, current);
    else if (side === "right") current = await node(current, sibling);
    else return false;
  }
  return equalBytes(current, root);
}

// ---- version chain ----

export async function termsDigest(termsSet) {
  return plainHash(TYPE_BYTE.TERMS_SET, termsSet);
}

export async function chainLink(prevLink, digest, root) {
  const prev = prevLink === null || prevLink === undefined ? new Uint8Array(32) : requireBytes(prevLink, 32, "previous link");
  return sha256(
    concat(Uint8Array.of(TYPE_BYTE.CHAIN_LINK), prev, requireBytes(digest, 32, "terms digest"), requireBytes(root, 32, "root")),
  );
}

// ---- echo code ----

export async function recapHash(content) {
  return plainHash(TYPE_BYTE.RECAP, content);
}

export async function echoCode(recapDigest) {
  const d = await sha256(concat(Uint8Array.of(TYPE_BYTE.ECHO_CODE), requireBytes(recapDigest, 32, "recap hash")));
  const bits = ((d[0] << 16) | (d[1] << 8) | d[2]) >>> 4;
  return [15, 10, 5, 0].map((shift) => ALPHABET[(bits >>> shift) & 0x1f]).join("");
}

const CODE_AFTER_CONFIRM = /(?<![0-9A-Z])CONFIRM ([0-9A-Z]{4})(?![0-9A-Z])/;

// Find CONFIRM first, then map O->0 and I/L->1 on the code token only (I-08).
export function extractCode(reply) {
  const text = reply.normalize("NFC").toUpperCase().split(/\s+/).filter(Boolean).join(" ");
  const m = CODE_AFTER_CONFIRM.exec(text);
  if (!m) return null;
  const code = m[1].replace(/O/g, "0").replace(/[IL]/g, "1");
  return [...code].every((ch) => ALPHABET.includes(ch)) ? code : null;
}

export function codesMatch(reply, code) {
  const found = extractCode(reply);
  return found !== null && found === code;
}

// ---- timestamps: YYYY-MM-DDTHH:MM:SS+HH:MM, whole seconds, never Z ----

const TS = /^([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})([+-])([0-9]{2}):([0-9]{2})$/;
const pad = (n, width = 2) => String(n).padStart(width, "0");

// Returns {date: Date (the instant), offsetMinutes}. Throws on any form the Python parser rejects.
export function parseTimestamp(text) {
  const m = typeof text === "string" ? TS.exec(text) : null;
  if (!m) throw new Error("timestamp must be YYYY-MM-DDTHH:MM:SS+HH:MM");
  const [y, mo, d, h, mi, s, sign, oh, om] = m.slice(1).map((v, i) => (i === 6 ? v : Number(v)));
  if (sign === "-" && oh === 0 && om === 0) throw new Error("offset -00:00 is not allowed; write +00:00");
  if (oh > 23 || om > 59) throw new Error("offset out of range");
  if (y < 1 || h > 23 || mi > 59 || s > 59) throw new Error("time out of range");
  const local = new Date(Date.UTC(y, mo - 1, d, h, mi, s));
  local.setUTCFullYear(y); // years below 100 are not shifted to 19xx
  if (local.getUTCMonth() !== mo - 1 || local.getUTCDate() !== d) throw new Error("impossible date");
  const offsetMinutes = (sign === "-" ? -1 : 1) * (oh * 60 + om);
  return { date: new Date(local.getTime() - offsetMinutes * 60000), offsetMinutes };
}

// Writes the instant `date` as seen at `offsetMinutes` (default: this device's offset at that instant).
export function formatTimestamp(date, offsetMinutes = -date.getTimezoneOffset()) {
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) throw new Error("invalid date");
  if (date.getUTCMilliseconds()) throw new Error("timestamps are whole seconds");
  if (!Number.isInteger(offsetMinutes) || Math.abs(offsetMinutes) > 23 * 60 + 59) throw new Error("offset out of range");
  const t = new Date(date.getTime() + offsetMinutes * 60000);
  const off = Math.abs(offsetMinutes);
  return (
    `${pad(t.getUTCFullYear(), 4)}-${pad(t.getUTCMonth() + 1)}-${pad(t.getUTCDate())}` +
    `T${pad(t.getUTCHours())}:${pad(t.getUTCMinutes())}:${pad(t.getUTCSeconds())}` +
    `${offsetMinutes < 0 ? "-" : "+"}${pad(Math.floor(off / 60))}:${pad(off % 60)}`
  );
}
