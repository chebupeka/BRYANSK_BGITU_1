"""Bounded, per-application cache. Nothing is written to disk."""

import hashlib
import json
from collections import OrderedDict
from collections.abc import Callable
from threading import Lock
from time import monotonic

from app.schemas import ProcessRequest, ProcessResponse


def processing_key(request: ProcessRequest) -> str:
    data = request.model_dump()
    payload = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ProcessCache:
    def __init__(
        self, max_entries: int, ttl_seconds: float, *, clock: Callable[[], float] = monotonic
    ):
        self.enabled = max_entries > 0 and ttl_seconds > 0
        self._max_entries = max_entries
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._items: OrderedDict[str, tuple[float, ProcessResponse]] = OrderedDict()
        self._lock = Lock()

    def get(self, key: str) -> ProcessResponse | None:
        if not self.enabled:
            return None
        with self._lock:
            now = self._clock()
            for expired in [key for key, (expiry, _) in self._items.items() if expiry <= now]:
                del self._items[expired]
            entry = self._items.get(key)
            if entry is None:
                return None
            self._items.move_to_end(key)
            return entry[1].model_copy(deep=True)

    def put(self, key: str, result: ProcessResponse) -> None:
        if not self.enabled:
            return
        with self._lock:
            now = self._clock()
            for expired in [key for key, (expiry, _) in self._items.items() if expiry <= now]:
                del self._items[expired]
            self._items[key] = (now + self._ttl_seconds, result.model_copy(deep=True))
            self._items.move_to_end(key)
            while len(self._items) > self._max_entries:
                self._items.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
