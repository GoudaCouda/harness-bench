"use strict";

const chunks = [];
process.stdin.on("data", (chunk) => chunks.push(chunk));
process.stdin.on("end", () => {
  const payload = JSON.parse(Buffer.concat(chunks).toString("utf8"));
  const output = [];
  const byCategory = [];

  for (const record of payload.records) {
    const normalized = {
      id: record.id,
      category: record.category,
      amount: Number(record.amount),
      priority: record.priority || 0,
      active: record.active || true,
    };
    output.push(normalized);

    let bucket = byCategory.find((item) => item.category === normalized.category);
    if (!bucket) {
      bucket = { category: normalized.category, count: 0, activeCount: 0, totalAmount: 0 };
      byCategory.push(bucket);
    }
    bucket.count += 1;
    bucket.activeCount += normalized.active ? 1 : 0;
    bucket.totalAmount += normalized.amount;
  }

  output.sort((left, right) => left.category.localeCompare(right.category));
  process.stdout.write(JSON.stringify({
    records: output,
    summary: {
      inputCount: output.length,
      activeCount: output.filter((item) => item.active).length,
      totalAmount: output.reduce((sum, item) => sum + item.amount, 0),
      byCategory,
    },
  }));
});
