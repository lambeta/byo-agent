"""Liveness: is the process that wrote a turn still there?

Mechanism: one pid check with os.kill(pid, 0). ProcessLookupError means dead,
PermissionError means alive (a process exists that we may not signal). Nothing is
cached and nothing is written.

Rejected alternative: an inactivity watchdog. A legitimate model call can take a
minute, so a timeout would mark a live turn interrupted and trade one lie for another.
"""

from __future__ import annotations

import os


def alive(pid) -> bool:
    """True only when the operating system says this pid exists."""
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True
