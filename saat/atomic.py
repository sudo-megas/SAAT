import os
from pathlib import Path


def write_atomic(path: Path, text: str) -> None:
    """Write text to path via a temp file + fsync + os.replace. A crash mid-save
    must never leave a truncated file at `path`."""
    tmp_path = path.with_name(path.name + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)
