"""Minimal ``fcntl`` stand-in for running Home Assistant tests on Windows.

Home Assistant itself is Linux-only; its test harness imports ``fcntl`` from
``homeassistant.runner``. This shim provides the tiny surface that import and
the (unused in tests) file lock need. Test environment only.
"""

from __future__ import annotations

import errno

LOCK_SH = 1
LOCK_EX = 2
LOCK_NB = 4
LOCK_UN = 8


def flock(fd: int, operation: int) -> None:
    """Pretend to acquire a lock (not needed by the test harness)."""
    return None


def fcntl(fd: int, cmd: int, arg: int = 0) -> int:
    """Raise like an unsupported platform call would."""
    raise OSError(errno.ENOSYS, "fcntl is not supported on Windows")


def ioctl(fd: int, request: int, arg: int = 0, mutate_flag: bool = True) -> int:
    """Raise like an unsupported platform call would."""
    raise OSError(errno.ENOSYS, "ioctl is not supported on Windows")
