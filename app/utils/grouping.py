"""Generic grouping utilities (orders, line keys, etc.)."""

from __future__ import annotations

from collections import defaultdict
from typing import Callable, Hashable, TypeVar

T = TypeVar("T")
K = TypeVar("K", bound=Hashable)


def group_by(items: list[T], key: Callable[[T], K]) -> dict[K, list[T]]:
    out: dict[K, list[T]] = defaultdict(list)
    for item in items:
        out[key(item)].append(item)
    return dict(out)
