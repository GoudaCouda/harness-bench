import asyncio
import unittest

from src.pool import run_batch


class PoolTests(unittest.IsolatedAsyncioTestCase):
    async def test_order_and_failure_isolation(self):
        items = [{"id": "slow", "payload": 0.02}, {"id": "bad", "payload": -1}, {"id": "fast", "payload": 0}]

        async def worker(item):
            if item["payload"] < 0:
                raise RuntimeError("synthetic")
            await asyncio.sleep(item["payload"])
            return item["id"].upper()

        result = await run_batch(items, worker, concurrency=2, queue_size=1)
        self.assertEqual([row["id"] for row in result], ["slow", "bad", "fast"])
        self.assertEqual([row["status"] for row in result], ["ok", "error", "ok"])

    async def test_shutdown_marks_incomplete_and_cleans_up(self):
        gate = asyncio.Event()

        async def worker(item):
            await gate.wait()
            return item["id"]

        items = [{"id": str(index), "payload": index} for index in range(4)]
        result = await run_batch(items, worker, concurrency=1, queue_size=1, shutdown_after=0.01)
        self.assertTrue(all(row["status"] == "cancelled" for row in result))


if __name__ == "__main__":
    unittest.main()
