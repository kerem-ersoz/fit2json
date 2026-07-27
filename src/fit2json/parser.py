"""Losslessly decode .fit files into human-readable dicts using fitdecode.

Every FIT data message and every field is preserved. Messages are grouped by name
(occurrence order preserved within each group); each field keeps its decoded value,
with units collected once into a legend. Developer/unknown fields are retained.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any, Dict, List

import fitdecode

from fit2json.models import DecodedActivity


class _MultiValue(list):
    """Marker list used to accumulate repeated field names within one message."""


def _coerce(value: Any) -> Any:
    """Convert a decoded FIT value into a JSON-serializable form."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, datetime.datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=datetime.timezone.utc)
        return value.isoformat()
    if isinstance(value, datetime.time):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray)):
        return value.hex()
    if isinstance(value, (list, tuple)):
        return [_coerce(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _coerce(v) for k, v in value.items()}
    return str(value)


def _field_key(field: Any) -> str:
    """Key for a field: its name, or ``unknown_<def_num>`` when unnamed."""
    if field.is_named and field.name:
        return field.name
    return f"unknown_{field.def_num}"


def _decode_message(frame: "fitdecode.FitDataMessage", field_units: Dict[str, str]) -> Dict[str, Any]:
    """Decode one FIT data message into a field->value dict, updating the unit legend."""
    record: Dict[str, Any] = {}
    for field in frame.fields:
        key = _field_key(field)
        value = _coerce(field.value)

        if key in record:
            # Preserve repeated field names losslessly.
            if isinstance(record[key], _MultiValue):
                record[key].append(value)
            else:
                record[key] = _MultiValue([record[key], value])
        else:
            record[key] = value

        if field.units and key not in field_units:
            field_units[key] = field.units

    return {k: (list(v) if isinstance(v, _MultiValue) else v) for k, v in record.items()}


def decode_fit_file(filepath: str | Path) -> DecodedActivity:
    """Decode a single .fit file into a lossless :class:`DecodedActivity`.

    Args:
        filepath: Path to a .fit file.

    Returns:
        A DecodedActivity holding every message and field.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"FIT file not found: {filepath}")

    messages: Dict[str, List[Dict[str, Any]]] = {}
    field_units: Dict[str, str] = {}

    with fitdecode.FitReader(str(filepath)) as fit:
        for frame in fit:
            if not isinstance(frame, fitdecode.FitDataMessage):
                continue
            record = _decode_message(frame, field_units)
            messages.setdefault(frame.name, []).append(record)

    return DecodedActivity(
        source_file=filepath.name,
        messages=messages,
        field_units=field_units,
    )
