"""Pure-Python stand-in for the ``lru-dict`` C extension.

Only used in the local test environment: Home Assistant 2026.2.x pins
``lru-dict==1.3.0``, which has no CPython 3.13 wheel for Windows and would
require a C compiler. This module implements the small dict-like ``LRU`` API
that Home Assistant actually uses, so the real Home Assistant test harness can
run unmodified. Production installs use the upstream C extension.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterator, MutableMapping
from typing import Any


class LRU(MutableMapping):
    """A fixed-size mapping that evicts the oldest entry."""

    def __init__(self, capacity: int) -> None:
        """Initialize the cache with a maximum size."""
        self._capacity = capacity
        self._data: OrderedDict[Any, Any] = OrderedDict()

    def __getitem__(self, key: Any) -> Any:
        value = self._data[key]
        self._data.move_to_end(key)
        return value

    def __setitem__(self, key: Any, value: Any) -> None:
        self._data[key] = value
        self._data.move_to_end(key)
        while len(self._data) > self._capacity:
            self._data.popitem(last=False)

    def __delitem__(self, key: Any) -> None:
        del self._data[key]

    def __iter__(self) -> Iterator[Any]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, key: object) -> bool:
        return key in self._data

    # --- API exposed by the upstream lru-dict extension ---
    def peek(self, key: Any, default: Any = None) -> Any:
        """Return a value without marking it as recently used."""
        return self._data.get(key, default)

    def peekitem(self, last: bool = True) -> tuple[Any, Any]:
        """Return the oldest or newest item without changing the order."""
        if not self._data:
            raise KeyError("LRU is empty")
        key = next(reversed(self._data)) if last else next(iter(self._data))
        return key, self._data[key]

    def get_size(self) -> int:
        """Return the maximum size."""
        return self._capacity

    def set_size(self, size: int) -> None:
        """Change the maximum size, evicting entries if needed."""
        self._capacity = size
        while len(self._data) > self._capacity:
            self._data.popitem(last=False)

    def clear(self) -> None:
        """Remove all entries."""
        self._data.clear()


__all__ = ["LRU"]
