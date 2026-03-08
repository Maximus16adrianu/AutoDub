"""Threading helpers."""

from __future__ import annotations

from queue import Empty, Queue
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


def drain_queue(queue: Queue[T], callback: Callable[[T], None]) -> int:
    count = 0
    while True:
        try:
            item = queue.get_nowait()
        except Empty:
            break
        callback(item)
        count += 1
    return count
