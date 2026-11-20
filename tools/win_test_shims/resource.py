"""Minimal ``resource`` stand-in for running Home Assistant tests on Windows.

Home Assistant is Linux-only; its test harness imports ``homeassistant.runner``,
which reads the open file descriptor limit. This shim makes that import work.
Test environment only.
"""

from __future__ import annotations

RLIMIT_CPU = 0
RLIMIT_FSIZE = 1
RLIMIT_DATA = 2
RLIMIT_STACK = 3
RLIMIT_CORE = 4
RLIMIT_NOFILE = 7
RLIM_INFINITY = -1


def getrlimit(resource: int) -> tuple[int, int]:
    """Return a generous but finite descriptor limit."""
    return (8192, 8192)


def setrlimit(resource: int, limits: tuple[int, int]) -> None:
    """Ignore attempts to change limits."""
    return None
