import os
import time
from pathlib import Path

# os.replace() over a destination another process holds open is a non-issue
# on POSIX, where rename ignores other openers entirely. On Windows it
# raises PermissionError, and the processes doing the holding are not
# exotic: antivirus real-time scanners and the search indexer both open
# files briefly and unpredictably right after they are written. The handle
# is released in milliseconds, so a short backoff turns a spurious failure
# into a pause nobody notices — while a genuinely locked file still
# surfaces its error rather than being swallowed (SPEC.md §2 rule 7).
#
# Five attempts at 20/40/80/160 ms is 300 ms of patience in the worst case.
# Applied on every platform: the retry is harmless where it never triggers,
# and one code path is easier to trust than two.
REPLACE_ATTEMPTS = 5
REPLACE_INITIAL_DELAY_S = 0.02


def _replace_with_retry(source: Path, destination: Path) -> None:
    delay = REPLACE_INITIAL_DELAY_S
    for attempt in range(REPLACE_ATTEMPTS):
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if attempt == REPLACE_ATTEMPTS - 1:
                raise
            time.sleep(delay)
            delay *= 2


def write_atomic(path: Path, text: str) -> None:
    """Write text to path via a temp file + fsync + os.replace. A crash
    mid-save must never leave a truncated file at `path`, and a failure
    must never leave a `.tmp` beside it either — an orphaned
    `watch.toml.tmp` sitting in a watch folder looks like corruption to
    someone browsing their collection in a file manager, which is exactly
    the audience this storage format exists for.

    The replace retries briefly before giving up; see the note above."""
    tmp_path = path.with_name(path.name + ".tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        _replace_with_retry(tmp_path, path)
    except BaseException:
        # BaseException rather than Exception: a KeyboardInterrupt landing
        # between the write and the replace would otherwise leave the temp
        # file behind too. The original is always re-raised — this cleans
        # up, it never swallows.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
