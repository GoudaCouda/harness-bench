"use strict";

const MAX_INPUT_BYTES = 2 * 1024 * 1024;
const MAX_RECORDS = 50000;
const ALLOWED_TOP_LEVEL = new Set(["records"]);
const ALLOWED_RECORD_KEYS = new Set(["id", "category", "amount", "priority", "active"]);

function fail(code, message) {
  process.stderr.write(`${JSON.stringify({ error: { code, message } })}\n`);
  process.exitCode = 2;
}

function isPlainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function codePointCompare(left, right) {
  const a = Array.from(left);
  const b = Array.from(right);
  const length = Math.min(a.length, b.length);
  for (let index = 0; index < length; index += 1) {
    const delta = a[index].codePointAt(0) - b[index].codePointAt(0);
    if (delta !== 0) return delta;
  }
  return a.length - b.length;
}

function toCents(amount) {
  if (typeof amount !== "number" || !Number.isFinite(amount) || amount < 0 || amount > 1000000000) {
    return null;
  }
  const cents = Math.round(amount * 100);
  if (Math.abs(cents / 100 - amount) > 1e-9) return null;
  return cents;
}

function normalizeRecord(record, index, seen) {
  if (!isPlainObject(record) || Object.keys(record).some((key) => !ALLOWED_RECORD_KEYS.has(key))) {
    throw new Error(`INVALID_RECORD:${index}`);
  }
  if (!("id" in record) || !("category" in record) || !("amount" in record)) {
    throw new Error(`INVALID_RECORD:${index}`);
  }
  if (typeof record.id !== "string" || typeof record.category !== "string") {
    throw new Error(`INVALID_RECORD:${index}`);
  }
  const id = record.id.trim();
  const category = record.category.trim();
  if (!id || !category) throw new Error(`INVALID_RECORD:${index}`);
  if (seen.has(id)) throw new Error(`DUPLICATE_ID:${index}`);
  seen.add(id);
  const cents = toCents(record.amount);
  const priority = record.priority === undefined ? 0 : record.priority;
  const active = record.active === undefined ? true : record.active;
  if (cents === null || !Number.isInteger(priority) || priority < -1000 || priority > 1000 || typeof active !== "boolean") {
    throw new Error(`INVALID_RECORD:${index}`);
  }
  return { id, category, amount: cents / 100, priority, active, cents, inputIndex: index };
}

function compareRecords(left, right) {
  return codePointCompare(left.category, right.category)
    || right.cents - left.cents
    || right.priority - left.priority
    || left.inputIndex - right.inputIndex;
}

function processPayload(payload) {
  if (!isPlainObject(payload) || Object.keys(payload).some((key) => !ALLOWED_TOP_LEVEL.has(key)) || !Array.isArray(payload.records) || payload.records.length > MAX_RECORDS) {
    throw new Error("INVALID_INPUT:top");
  }
  const seen = new Set();
  const normalized = payload.records.map((record, index) => normalizeRecord(record, index, seen));
  const buckets = new Map();
  let activeCount = 0;
  let totalCents = 0;
  for (const record of normalized) {
    activeCount += record.active ? 1 : 0;
    totalCents += record.cents;
    let bucket = buckets.get(record.category);
    if (!bucket) {
      bucket = { category: record.category, count: 0, activeCount: 0, totalCents: 0 };
      buckets.set(record.category, bucket);
    }
    bucket.count += 1;
    bucket.activeCount += record.active ? 1 : 0;
    bucket.totalCents += record.cents;
  }
  normalized.sort(compareRecords);
  const records = normalized.map(({ id, category, amount, priority, active }) => ({ id, category, amount, priority, active }));
  const byCategory = Array.from(buckets.values())
    .sort((left, right) => codePointCompare(left.category, right.category))
    .map(({ category, count, activeCount: countActive, totalCents: cents }) => ({
      category,
      count,
      activeCount: countActive,
      totalAmount: cents / 100,
    }));
  return {
    records,
    summary: {
      inputCount: records.length,
      activeCount,
      totalAmount: totalCents / 100,
      byCategory,
    },
  };
}

const chunks = [];
let inputBytes = 0;
let tooLarge = false;
process.stdin.on("data", (chunk) => {
  inputBytes += chunk.length;
  if (inputBytes > MAX_INPUT_BYTES) {
    tooLarge = true;
    return;
  }
  chunks.push(chunk);
});
process.stdin.on("end", () => {
  if (tooLarge) {
    fail("INVALID_INPUT", "Input exceeds the 2 MiB limit.");
    return;
  }
  let payload;
  try {
    payload = JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } catch {
    fail("INVALID_JSON", "Input is not valid JSON.");
    return;
  }
  try {
    process.stdout.write(`${JSON.stringify(processPayload(payload))}\n`);
  } catch (error) {
    if (error.message.startsWith("DUPLICATE_ID:")) {
      fail("DUPLICATE_ID", "Record ids must be unique after trimming.");
    } else if (error.message.startsWith("INVALID_RECORD:")) {
      fail("INVALID_RECORD", "A record violates the fixed record schema.");
    } else {
      fail("INVALID_INPUT", "Input must match the fixed top-level schema.");
    }
  }
});
