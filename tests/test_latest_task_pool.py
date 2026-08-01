"""Concurrency regression tests for bounded latest-result execution."""

import threading
import time

from core.latest_task_pool import LatestTaskPool


def test_only_latest_pending_result_is_published():
    pool = LatestTaskPool(max_workers=1)
    started = threading.Event()
    release = threading.Event()
    published = []
    latest_published = threading.Event()

    def blocked_old_work():
        started.set()
        assert release.wait(timeout=2)
        return "old"

    pool.submit_latest("translation", 1, blocked_old_work, published.append)
    assert started.wait(timeout=1)
    cancelled = pool.submit_latest(
        "translation", 2, lambda: "cancelled", published.append
    )
    pool.submit_latest(
        "translation",
        3,
        lambda: "latest",
        lambda result: (published.append(result), latest_published.set()),
    )
    release.set()

    assert latest_published.wait(timeout=2)
    assert cancelled.cancelled()
    assert published == ["latest"]
    pool.shutdown()


def test_worker_count_stays_bounded_under_burst_load():
    pool = LatestTaskPool(max_workers=2)
    release = threading.Event()

    def blocked_work():
        release.wait(timeout=2)
        return "done"

    for generation in range(100):
        pool.submit_latest("assistant", generation, blocked_work, lambda _: None)

    time.sleep(0.05)
    worker_threads = [
        thread
        for thread in threading.enumerate()
        if thread.name.startswith("translator-worker")
    ]
    assert len(worker_threads) <= 2
    release.set()
    pool.shutdown()
