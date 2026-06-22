from __future__ import annotations

import json
import os
import re
from typing import Any

from .database import upsert_seat_telemetry


SEAT_CODE_PATTERN = re.compile(r"^([A-Za-z])0?(\d+)$")


def normalize_seat_code(value: str | None) -> str:
    if not value:
        return "A01"

    cleaned = value.strip()
    cleaned = cleaned.removeprefix("pi_node_").removeprefix("seat_")
    match = SEAT_CODE_PATTERN.match(cleaned)
    if match:
        return f"{match.group(1).upper()}{int(match.group(2)):02d}"
    return cleaned.upper()


def seat_code_from_payload(payload: dict[str, Any], topic: str | None = None) -> str:
    if payload.get("seat_code"):
        return normalize_seat_code(str(payload["seat_code"]))
    if payload.get("seat_id"):
        return normalize_seat_code(str(payload["seat_id"]))
    if topic:
        return normalize_seat_code(topic.rsplit("/", 1)[-1])
    return normalize_seat_code(str(payload.get("client_id", "")))


def save_telemetry_payload(payload: dict[str, Any], topic: str | None = None) -> dict[str, Any]:
    environment = payload.get("environment") or {}
    seat_interact = payload.get("seat_interact") or {}
    row = upsert_seat_telemetry(
        seat_code=seat_code_from_payload(payload, topic),
        client_id=payload.get("client_id"),
        temperature=_optional_float(environment.get("temperature")),
        humidity=_optional_float(environment.get("humidity")),
        noise_level=_optional_float(environment.get("noise_level")),
        motion_detected=_optional_bool(seat_interact.get("motion_detected")),
        rotary_raw_value=_optional_float(seat_interact.get("rotary_raw_value")),
        source_timestamp=_optional_int(payload.get("timestamp")),
    )
    return dict(row)


def start_mqtt_subscriber() -> Any | None:
    if os.getenv("ENABLE_MQTT_SUBSCRIBER", "0") == "0":
        return None

    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        print("[MQTT] paho-mqtt is not installed; dashboard API still works.")
        return None

    broker = os.getenv("MQTT_BROKER", "localhost")
    port = int(os.getenv("MQTT_PORT", "1883"))
    topic = os.getenv("MQTT_TOPIC", "cybercafe/#")

    client = _create_mqtt_client(mqtt)

    def on_connect(client_obj: Any, _userdata: Any, _flags: Any, result_code: int) -> None:
        if result_code == 0:
            client_obj.subscribe(topic)
            print(f"[MQTT] Dashboard subscribed to {topic} on {broker}:{port}")
        else:
            print(f"[MQTT] Dashboard connection failed with code {result_code}")

    def on_message(_client_obj: Any, _userdata: Any, message: Any) -> None:
        try:
            payload = json.loads(message.payload.decode("utf-8"))
            save_telemetry_payload(payload, message.topic)
        except Exception as exc:
            print(f"[MQTT] Failed to store telemetry: {exc}")

    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect_async(broker, port, 60)
        client.loop_start()
    except Exception as exc:
        print(f"[MQTT] Dashboard subscriber disabled: {exc}")
        return None
    return client


def stop_mqtt_subscriber(client: Any | None) -> None:
    if client is None:
        return
    client.loop_stop()
    client.disconnect()


def _create_mqtt_client(mqtt: Any) -> Any:
    if hasattr(mqtt, "CallbackAPIVersion"):
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id="web_app_dashboard")
    return mqtt.Client(client_id="web_app_dashboard")


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
        return int(value)
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
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return None
