// Test helper: print the JavaScript verifier's verdict for one bundle as JSON.
// Usage: node tests/phase_07/js/verify_cli.mjs <bundle.zip>
import { readFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..", "..", "..");
const { verifyBundle } = await import(pathToFileURL(path.join(root, "apps", "verify", "verify.mjs")).href);

const result = await verifyBundle(new Uint8Array(readFileSync(process.argv[2])));
const fd = result.first_difference;
process.stdout.write(
  JSON.stringify({
    verdict: result.verdict,
    kind: fd ? fd.kind : null,
    seq: fd ? (fd.seq ?? null) : null,
    version_n: fd ? (fd.version_n ?? null) : null,
  }),
);
