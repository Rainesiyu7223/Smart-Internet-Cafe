from __future__ import annotations

import json
import math
import os
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

from .telemetry import normalize_seat_code


DEFAULT_TELEMETRY_API_URL = "http://172.20.10.2:5001/api/seat_data"


def get_remote_telemetry_url() -> str:
    return os.getenv("TELEMETRY_API_URL", DEFAULT_TELEMETRY_API_URL)


def fetch_remote_telemetry() -> tuple[list[dict[str, Any]], str | None, str | None]:
    url = get_remote_telemetry_url()
    timeout = float(os.getenv("TELEMETRY_API_TIMEOUT", "3"))
    request = urllib.request.Request(url, headers={"Accept": "application/json"})

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return [], f"Computer A API unavailable: {exc}", None

    records = _extract_records(payload)
    recommended_seat = _recommended_seat(payload)
    return [_normalize_remote_record(record) for record in records], None, recommended_seat


def merge_remote_with_seats(
    seat_rows: list[dict[str, Any]],
    telemetry_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    telemetry_by_code = {
        row["code"]: row
        for row in reversed(telemetry_rows)
        if row.get("code")
    }
    merged_rows = []
    for seat in seat_rows:
        code = seat["code"]
        merged = {
            "client_id": None,
            "temperature": None,
            "humidity": None,
            "noise_level": None,
            "occupied": None,
            "rotary_raw_value": None,
            "received_at": None,
            "source_timestamp": None,
            **seat,
        }
        if code in telemetry_by_code:
            merged.update(telemetry_by_code[code])
        merged_rows.append(merged)

    known_codes = {seat["code"] for seat in seat_rows}
    for telemetry in telemetry_rows:
        if telemetry.get("code") not in known_codes:
            merged_rows.append(
                {
                    "area": "Remote Seat",
                    "pc_level": "Unknown",
                    "status": "available",
                    **telemetry,
                }
            )
    return merged_rows


def _extract_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return _telemetry_records(payload)
    if not isinstance(payload, dict):
        return []

    data = payload.get("data")
    if isinstance(data, list):
        return _telemetry_records(data)
    if isinstance(data, dict):
        nested = data.get("records") or data.get("seats") or data.get("result")
        if isinstance(nested, list):
            return _telemetry_records(nested)
        return [data]

    seats = payload.get("seats") or payload.get("records") or payload.get("result")
    if isinstance(seats, list):
        return _telemetry_records(seats)

    if payload.get("status") == "empty":
        return []
    return [payload]


def _recommended_seat(payload: Any) -> str | None:
    for item in _recommendation_sources(payload):
        value = _first_value(
            item,
            "recommended_seat",
            "recommendation_seat",
            "recommended",
            default=None,
        )
        if value is not None:
            return normalize_seat_code(str(value))
    return None


def _telemetry_records(items: list[Any]) -> list[dict[str, Any]]:
    """Exclude recommendation metadata when the API returns it in the data list."""
    return [
        item
        for item in items
        if isinstance(item, dict) and not _is_recommendation_only_record(item)
    ]


def _is_recommendation_only_record(record: dict[str, Any]) -> bool:
    recommendation_keys = {"recommended_seat", "recommendation_seat", "recommended"}
    seat_keys = {"seat_code", "code", "seat", "seat_id", "client_id"}
    return bool(recommendation_keys.intersection(record)) and not bool(seat_keys.intersection(record))


def _recommendation_sources(payload: Any) -> list[dict[str, Any]]:
    """Accept recommendation metadata at the response root or as a list entry."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []

    sources = [payload]
    for key in ("data", "records", "seats", "result"):
        value = payload.get(key)
        if isinstance(value, dict):
            sources.append(value)
        elif isinstance(value, list):
            sources.extend(item for item in value if isinstance(item, dict))
    return sources


def _normalize_remote_record(record: dict[str, Any]) -> dict[str, Any]:
    environment = _dict_value(record, "environment")
    seat_interact = _dict_value(record, "seat_interact")
    button_pressed = _optional_bool(
        _first_value(
            record,
            "button_pressed",
            "button_state",
            "button",
            "seat_button",
            "is_pressed",
            default=seat_interact.get("button_pressed"),
        )
    )
    code = _first_value(
        record,
        "seat_code",
        "code",
        "seat",
        "seat_id",
        "client_id",
        default="A01",
    )
    received_at = _first_value(
        record,
        "received_at",
        "time",
        "_time",
        "created_at",
        "timestamp",
        default=None,
    )
    source_timestamp = _optional_int(_first_value(record, "timestamp", "source_timestamp", "time", default=None))
    return {
        "code": normalize_seat_code(str(code)),
        "client_id": _first_value(record, "client_id", default=None),
        "temperature": _optional_float(
            _first_value(record, "temperature", "temp", default=environment.get("temperature"))
        ),
        "humidity": _optional_float(
            _first_value(record, "humidity", default=environment.get("humidity"))
        ),
        "noise_level": _optional_float(
            _first_value(record, "noise_level", "noise", default=environment.get("noise_level"))
        ),
        "button_pressed": button_pressed,
        # Occupancy is controlled by checked-in reservations in the web app.
        "occupied": None,
        "rotary_raw_value": _optional_float(
            _first_value(record, "rotary_raw_value", default=seat_interact.get("rotary_raw_value"))
        ),
        "received_at": _format_received_at(received_at) or datetime.utcnow().isoformat(timespec="seconds"),
        "source_timestamp": source_timestamp,
    }


def _dict_value(record: dict[str, Any], key: str) -> dict[str, Any]:
    value = record.get(key)
    return value if isinstance(value, dict) else {}


def _first_value(record: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in record and _has_value(record[key]):
            return record[key]
    return default


def _has_value(value: Any) -> bool:
    if value in (None, ""):
        return False
    return not _is_nan(value)


def _is_nan(value: Any) -> bool:
    return isinstance(value, float) and math.isnan(value)


def _format_received_at(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if value > 10_000_000_000:
            value = value / 1000
        return datetime.utcfromtimestamp(value).isoformat(timespec="seconds")
    return str(value)


def _optional_float(value: Any) -> float | None:
    if value is None or _is_nan(value):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(parsed) else parsed


def _optional_int(value: Any) -> int | None:
    if value is None or _is_nan(value):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(parsed) else int(parsed)


def _optional_bool(value: Any) -> bool | None:
    if value is None or _is_nan(value):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on", "pressed", "down", "occupied"}:
            return True
        if normalized in {"0", "false", "no", "off", "released", "up", "vacant"}:
            return False
    return None
