"""JSON output formatting and file writing."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fit2json import __version__
from fit2json.models import Activity, OutputDocument


def build_output(activities: List[Activity]) -> OutputDocument:
    """Wrap activities in an OutputDocument with metadata."""
    return OutputDocument(
        activities=activities,
        metadata={
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tool_version": __version__,
            "file_count": len(activities),
        },
    )


def write_json(
    doc: OutputDocument,
    output_path: Optional[str] = None,
    indent: int = 2,
) -> str:
    """Serialize and write the output document to a file or stdout.

    Args:
        doc: The OutputDocument to serialize.
        output_path: Path to write JSON to. If None, writes to stdout.
        indent: JSON indentation level.

    Returns:
        The JSON string that was written.
    """
    json_str = doc.to_json(indent=indent)

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json_str, encoding="utf-8")
    else:
        sys.stdout.write(json_str)
        sys.stdout.write("\n")

    return json_str
