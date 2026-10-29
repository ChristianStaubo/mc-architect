"""One file lock for state shared between processes (edits, the architect's sessions)."""

import contextlib
import fcntl


@contextlib.contextmanager
def locked(directory):
    """Exclusive while inside: other processes wait. The lock file is `directory/.lock`."""
    directory.mkdir(parents=True, exist_ok=True)
    with open(directory / ".lock", "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
