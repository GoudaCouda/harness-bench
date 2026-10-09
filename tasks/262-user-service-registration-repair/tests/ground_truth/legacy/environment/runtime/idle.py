from __future__ import annotations

import signal
import time


running = True


def stop(_signum: int, _frame: object) -> None:
    global running
    running = False


signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)

while running:
    time.sleep(0.25)
