"""Load .fit files from local filesystem."""

from __future__ import annotations

from pathlib import Path
from typing import List


def collect_fit_files(path: str | Path) -> List[Path]:
    """Collect .fit file paths from a file or directory.

    Args:
        path: A single .fit file or a directory containing .fit files.

    Returns:
        Sorted list of Path objects for each .fit file found.

    Raises:
        FileNotFoundError: If the path does not exist.
        ValueError: If a file path is not a .fit file.
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Path not found: {path}")

    if path.is_file():
        if path.suffix.lower() != ".fit":
            raise ValueError(f"Not a .fit file: {path}")
        return [path]

    if path.is_dir():
        files = sorted(path.glob("**/*.fit"), key=lambda p: p.name)
        if not files:
            raise FileNotFoundError(f"No .fit files found in: {path}")
        return files

    raise ValueError(f"Path is neither a file nor directory: {path}")
