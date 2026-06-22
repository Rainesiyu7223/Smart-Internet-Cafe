from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

from .telemetry import normalize_seat_code


DEFAULT_TELEMETRY_API_URL = "http://192.168.0.114:5001/api/seat_data"


def get_remote_telemetry_url() -> str:
    return os.getenv("TELEMETRY_API_URL", DEFAULT_TELEMETRY_API_URL)


def fetch_remote_telemetry() -> tuple[list[dict[str, Any]], str | None]:
    url = get_remote_telemetry_url()
    timeout = float(os.getenv("TELEMETRY_API_TIMEOUT", "5"))
    request = urllib.request.Request(url, headers={"Accept": "application/json"})

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return [], f"Computer A API unavailable: {exc}"

    records = _extract_records(payload)
    return [_normalize_remote_record(record) for record in records], None


def merge_remote_with_seats(
    seat_rows: list[dict[str, Any]],
    telemetry_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    telemetry_by_code = {
        row["code"]: row
        for row in telemetry_rows
        if row.get("code")
    }
    merged_rows = []
    for seat in seat_rows:
        code = seat["code"]
        merged = {
            **seat,
            "client_id": None,
            "temperature": None,
            "humidity": None,
            "noise_level": None,
            "motion_detected": None,
            "rotary_raw_value": None,
            "received_at": None,
            "source_timestamp": None,
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
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []

    data = payload.get("data")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        nested = data.get("records") or data.get("seats") or data.get("result")
        if isinstance(nested, list):
            return [item for item in nested if isinstance(item, dict)]
        return [data]

    seats = payload.get("seats") or payload.get("records") or payload.get("result")
    if isinstance(seats, list):
        return [item for item in seats if isinstance(item, dict)]

    if payload.get("status") == "empty":
        return []
    return [payload]


def _normalize_remote_record(record: dict[str, Any]) -> dict[str, Any]:
    environment = _dict_value(record, "environment")
    seat_interact = _dict_value(record, "seat_interact")
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
    source_timestamp = _optional_int(_first_value(record, "timestamp", "source_timestamp", default=None))

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
        "motion_detected": _optional_bool(
            _first_value(
                record,
                "motion_detected",
                "occupied",
                "is_occupied",
                default=seat_interact.get("motion_detected"),
            )
        ),
        "rotary_raw_value": _optional_float(
            _first_value(record, "rotary_raw_value", default=seat_interact.get("rotary_raw_value"))
        ),
        "received_at": _format_received_at(received_at),
        "source_timestamp": source_timestamp,
    }


def _dict_value(record: dict[str, Any], key: str) -> dict[str, Any]:
    value = record.get(key)
    return value if isinstance(value, dict) else {}


def _first_value(record: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in record and record[key] not in (None, ""):
            return record[key]
    return default


def _format_received_at(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if value > 10_000_000_000:
            value = value / 1000
        return datetime.utcfromtimestamp(value).isoformat(timespec="seconds")
    return str(value)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on", "occupied"}:
            return True
        if normalized in {"0", "false", "no", "off", "vacant"}:
            return False
    return None
