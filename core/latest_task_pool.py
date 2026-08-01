"""Bounded background execution where only the latest result per stream wins."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
import threading
from typing import Callable, TypeVar

from utils.logger import logger


T = TypeVar("T")


class LatestTaskPool:
    """Bound threads and suppress obsolete async results by logical stream."""

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="translator-worker",
        )
        self._lock = threading.Lock()
        self._latest_generation: dict[str, int] = {}
        self._futures: dict[str, Future] = {}
        self._closed = False

    def submit_latest(
        self,
        stream: str,
        generation: int,
        work: Callable[[], T],
        publish: Callable[[T], None],
    ) -> Future | None:
        """Submit work and publish it only if it is still latest for stream."""
        with self._lock:
            if self._closed:
                return None
            self._latest_generation[stream] = generation
            previous = self._futures.get(stream)
            if previous is not None and not previous.done():
                previous.cancel()
            future = self._executor.submit(work)
            self._futures[stream] = future

        def finish(completed: Future):
            if completed.cancelled():
                return
            try:
                result = completed.result()
            except Exception as error:
                logger.error(f"Background stream '{stream}' failed: {error}")
                return

            with self._lock:
                is_latest = (
                    not self._closed
                    and self._latest_generation.get(stream) == generation
                )
                if self._futures.get(stream) is completed:
                    self._futures.pop(stream, None)
            if is_latest:
                publish(result)

        future.add_done_callback(finish)
        return future

    def shutdown(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            futures = list(self._futures.values())
            self._futures.clear()
        for future in futures:
            future.cancel()
        self._executor.shutdown(wait=False, cancel_futures=True)
