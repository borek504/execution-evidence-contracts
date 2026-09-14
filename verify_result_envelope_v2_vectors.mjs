import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

// Cross-language verifier for the frozen Result Envelope v2 golden vectors.
// It intentionally does not import, invoke, or translate the Python encoder.
// A tiny lossless JSON parser is included so signed int64 boundary values are
// preserved as BigInt instead of being rounded by JavaScript Number.

const MAX_CANONICAL_BYTES = 262144;
const MAX_NESTING_DEPTH = 16;
const MAX_OBJECT_KEYS = 128;
const MAX_COLLECTION_ITEMS = 256;
const MAX_STRING_BYTES = 4096;
const I64_MIN = -(1n << 63n);
const I64_MAX = (1n << 63n) - 1n;
const HASH_DOMAIN = Buffer.from(
  "EXECUTION-EVIDENCE-CONTRACTS\0RESULT-ENVELOPE\0V2\0",
  "utf8",
);

class LosslessJsonParser {
  constructor(text) {
    this.text = text;
    this.pos = 0;
  }

  parse() {
    const value = this.parseValue();
    this.skipWhitespace();
    if (this.pos !== this.text.length) throw new Error("trailing JSON input");
    return value;
  }

  skipWhitespace() {
    while (this.pos < this.text.length && /[\t\n\r ]/.test(this.text[this.pos])) {
      this.pos += 1;
    }
  }

  parseValue() {
    this.skipWhitespace();
    const ch = this.text[this.pos];
    if (ch === "{") return this.parseObject();
    if (ch === "[") return this.parseArray();
    if (ch === '"') return this.parseString();
    if (ch === "t" && this.text.startsWith("true", this.pos)) {
      this.pos += 4;
      return true;
    }
    if (ch === "f" && this.text.startsWith("false", this.pos)) {
      this.pos += 5;
      return false;
    }
    if (ch === "n" && this.text.startsWith("null", this.pos)) {
      this.pos += 4;
      return null;
    }
    return this.parseNumber();
  }

  parseObject() {
    this.pos += 1;
    const out = Object.create(null);
    const seen = new Set();
    this.skipWhitespace();
    if (this.text[this.pos] === "}") {
      this.pos += 1;
      return out;
    }
    while (true) {
      this.skipWhitespace();
      if (this.text[this.pos] !== '"') throw new Error("object key must be string");
      const key = this.parseString();
      if (seen.has(key)) throw new Error(`duplicate key: ${key}`);
      seen.add(key);
      this.skipWhitespace();
      if (this.text[this.pos] !== ":") throw new Error("missing colon");
      this.pos += 1;
      out[key] = this.parseValue();
      this.skipWhitespace();
      if (this.text[this.pos] === "}") {
        this.pos += 1;
        return out;
      }
      if (this.text[this.pos] !== ",") throw new Error("missing comma");
      this.pos += 1;
    }
  }

  parseArray() {
    this.pos += 1;
    const out = [];
    this.skipWhitespace();
    if (this.text[this.pos] === "]") {
      this.pos += 1;
      return out;
    }
    while (true) {
      out.push(this.parseValue());
      this.skipWhitespace();
      if (this.text[this.pos] === "]") {
        this.pos += 1;
        return out;
      }
      if (this.text[this.pos] !== ",") throw new Error("missing comma");
      this.pos += 1;
    }
  }

  parseString() {
    const start = this.pos;
    this.pos += 1;
    let escaped = false;
    while (this.pos < this.text.length) {
      const ch = this.text[this.pos];
      this.pos += 1;
      if (escaped) {
        escaped = false;
        continue;
      }
      if (ch === "\\") {
        escaped = true;
        continue;
      }
      if (ch === '"') {
        return JSON.parse(this.text.slice(start, this.pos));
      }
      if (ch.charCodeAt(0) < 0x20) throw new Error("control character in string");
    }
    throw new Error("unterminated string");
  }

  parseNumber() {
    const rest = this.text.slice(this.pos);
    const match = /^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/.exec(rest);
    if (!match) throw new Error(`invalid JSON value at ${this.pos}`);
    const token = match[0];
    this.pos += token.length;
    if (token.includes(".") || token.includes("e") || token.includes("E")) {
      throw new Error("floats are not permitted by the v2 canonical profile");
    }
    return BigInt(token);
  }
}

function u64(value) {
  const out = Buffer.alloc(8);
  out.writeBigUInt64BE(BigInt(value));
  return out;
}

function i64(value) {
  if (value < I64_MIN || value > I64_MAX) throw new Error("int64 range");
  const out = Buffer.alloc(8);
  out.writeBigInt64BE(value);
  return out;
}

function encodeCanonical(value, depth = 0) {
  if (depth > MAX_NESTING_DEPTH) throw new Error("depth limit");
  if (value === null) return Buffer.from("N");
  if (typeof value === "boolean") return Buffer.from(value ? "T" : "F");
  if (typeof value === "bigint") return Buffer.concat([Buffer.from("I"), i64(value)]);
  if (typeof value === "number") throw new Error("Number is not a canonical integer source");
  if (typeof value === "string") {
    if (value.normalize("NFC") !== value) throw new Error("NFC required");
    const data = Buffer.from(value, "utf8");
    if (data.length > MAX_STRING_BYTES) throw new Error("string limit");
    return Buffer.concat([Buffer.from("S"), u64(data.length), data]);
  }
  if (Array.isArray(value)) {
    if (value.length > MAX_COLLECTION_ITEMS) throw new Error("collection limit");
    return Buffer.concat([
      Buffer.from("L"),
      u64(value.length),
      ...value.map((item) => encodeCanonical(item, depth + 1)),
    ]);
  }
  if (typeof value === "object") {
    const keys = Object.keys(value);
    if (keys.length > MAX_OBJECT_KEYS) throw new Error("object-key limit");
    for (const key of keys) {
      if (key.normalize("NFC") !== key) throw new Error("NFC key required");
    }
    keys.sort((a, b) => Buffer.compare(Buffer.from(a, "utf8"), Buffer.from(b, "utf8")));
    const parts = [Buffer.from("O"), u64(keys.length)];
    for (const key of keys) {
      parts.push(encodeCanonical(key, depth + 1));
      parts.push(encodeCanonical(value[key], depth + 1));
    }
    return Buffer.concat(parts);
  }
  throw new Error(`unsupported type: ${typeof value}`);
}

function sha256Hex(buffer) {
  return createHash("sha256").update(buffer).digest("hex");
}

const text = readFileSync("RESULT_ENVELOPE_V2_GOLDEN_VECTORS.json", "utf8");
const vectorsFile = new LosslessJsonParser(text).parse();

if (vectorsFile.vector_set !== "execution-result-envelope-v2-golden-v1") {
  throw new Error("unexpected vector set");
}
if (vectorsFile.hash_protocol !== "execution-result-envelope-hash-v1") {
  throw new Error("unexpected hash protocol");
}
if (!Array.isArray(vectorsFile.vectors) || vectorsFile.vectors.length !== 3) {
  throw new Error("expected exactly three frozen vectors");
}

for (const vector of vectorsFile.vectors) {
  const canonical = encodeCanonical(vector.unsigned_envelope);
  if (canonical.length > MAX_CANONICAL_BYTES) throw new Error(`${vector.name}: canonical size limit`);

  const expectedLength = Number(vector.expected_canonical_length);
  const canonicalSha = sha256Hex(canonical);
  const resultHash = sha256Hex(Buffer.concat([HASH_DOMAIN, canonical]));

  if (canonical.length !== expectedLength) {
    throw new Error(`${vector.name}: canonical length ${canonical.length} != ${expectedLength}`);
  }
  if (canonicalSha !== vector.expected_canonical_sha256) {
    throw new Error(`${vector.name}: canonical SHA-256 mismatch`);
  }
  if (resultHash !== vector.expected_result_hash) {
    throw new Error(`${vector.name}: domain-separated result hash mismatch`);
  }

  console.log(`PASS ${vector.name} len=${canonical.length} sha256=${canonicalSha} result=${resultHash}`);
}

console.log("PASS independent Node.js golden-vector verification");
