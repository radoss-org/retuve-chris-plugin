import time
from typing import Optional

import psutil


def wait_for_cpu_drop(
    *,
    high_threshold: float = 85.0,  # consider CPU "high" if >= this percentage
    below_threshold: float = 70.0,  # proceed only when CPU < this percentage
    require_consecutive: int = 5,  # number of consecutive below-threshold samples
    poll_interval: float = 1.0,  # seconds between polls
    max_wait: Optional[
        float
    ] = None,  # seconds before giving up (None = unlimited)
    print_status: bool = True,
) -> bool:
    """
    Blocks until CPU usage drops and stays below `below_threshold` for
    `require_consecutive` consecutive polls, assuming it was high before.

    Returns True if condition satisfied, False if max_wait exceeded.
    """

    start = time.time()
    consecutive_ok = 0

    # Optional: quickly confirm we are indeed under "constant high usage"
    # before waiting for it to drop. If you don't need this, remove this block.
    # This step checks if CPU is currently >= high_threshold for a few checks.
    high_confirm = 0
    for _ in range(3):
        usage = psutil.cpu_percent(interval=poll_interval)
        if print_status:
            print(f"[confirm] CPU: {usage:.1f}%")
        if usage >= high_threshold:
            high_confirm += 1
    # If not confirmed high, we still proceed to waiting logic; adjust as needed.

    while True:
        usage = psutil.cpu_percent(interval=poll_interval)

        if print_status:
            print(
                f"[wait] CPU: {usage:.1f}% | "
                f"ok={consecutive_ok}/{require_consecutive}"
            )

        if usage < below_threshold:
            consecutive_ok += 1
        else:
            consecutive_ok = 0

        if consecutive_ok >= require_consecutive:
            if print_status:
                print("CPU has stayed low long enough. Proceeding.")
            return True

        if max_wait is not None and (time.time() - start) > max_wait:
            if print_status:
                print("Timed out waiting for CPU to drop.")
            return False
