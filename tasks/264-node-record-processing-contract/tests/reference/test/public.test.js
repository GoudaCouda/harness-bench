"use strict";

const assert = require("node:assert/strict");
const { spawnSync } = require("node:child_process");
const path = require("node:path");
const test = require("node:test");

const entrypoint = path.join(__dirname, "..", "src", "process.js");

function run(input) {
  return spawnSync(process.execPath, [entrypoint], {
    input,
    encoding: "utf8",
    timeout: 3000,
  });
}

test("normalizes, sorts and summarizes a small valid input", () => {
  const result = run(JSON.stringify({
    records: [
      { id: " b ", category: "ops", amount: 3, active: false },
      { id: "a", category: "ops", amount: 5, priority: 2 },
      { id: "c", category: "dev", amount: 1.25 },
    ],
  }));
  assert.equal(result.status, 0);
  assert.equal(result.stderr, "");
  const parsed = JSON.parse(result.stdout);
  assert.deepEqual(parsed.records.map((item) => item.id), ["c", "a", "b"]);
  assert.equal(parsed.summary.totalAmount, 9.25);
  assert.equal(parsed.summary.activeCount, 2);
});

test("reports malformed JSON without a stack trace", () => {
  const result = run("{not-json");
  assert.equal(result.status, 2);
  assert.equal(result.stdout, "");
  assert.deepEqual(JSON.parse(result.stderr), {
    error: { code: "INVALID_JSON", message: "Input is not valid JSON." },
  });
});
