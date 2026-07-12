from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator


BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BASE_DIR / "cafe.db"


def normalize_name(name: str) -> str:
    return " ".join(name.strip().lower().split())


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_db() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS reservations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                normalized_name TEXT NOT NULL,
                phone TEXT,
                reserved_at TEXT NOT NULL,
                checked_in_at TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS seats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                area TEXT NOT NULL,
                pc_level TEXT NOT NULL,
                noise_level TEXT NOT NULL,
                has_window INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'available'
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS seat_telemetry (
                seat_code TEXT PRIMARY KEY,
                client_id TEXT,
                temperature REAL,
                humidity REAL,
                noise_level REAL,
                button_pressed INTEGER,
                rotary_raw_value REAL,
                received_at TEXT NOT NULL,
                source_timestamp INTEGER
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS telemetry_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seat_code TEXT NOT NULL,
                client_id TEXT,
                temperature REAL,
                humidity REAL,
                noise_level REAL,
                button_pressed INTEGER,
                rotary_raw_value REAL,
                received_at TEXT NOT NULL,
                source_timestamp INTEGER
            )
            """
        )
        existing_seats = connection.execute("SELECT COUNT(*) FROM seats").fetchone()[0]
        if existing_seats == 0:
            connection.executemany(
                """
                INSERT INTO seats (code, area, pc_level, noise_level, has_window, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    ("A01", "Quiet Zone", "RTX 4070", "low", 1, "available"),
                    ("A02", "Quiet Zone", "RTX 4060", "low", 0, "available"),
                    ("B05", "Team Zone", "RTX 4070", "medium", 0, "available"),
                    ("B06", "Team Zone", "RTX 4060", "medium", 0, "occupied"),
                    ("C03", "Streaming Zone", "RTX 4080", "medium", 1, "available"),
                    ("D08", "Budget Zone", "GTX 1660", "low", 0, "available"),
                ],
            )
        ensure_column(connection, "seat_telemetry", "button_pressed", "INTEGER")
        ensure_column(connection, "telemetry_history", "button_pressed", "INTEGER")


def ensure_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_type: str,
) -> None:
    columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name not in columns:
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


def upsert_seat_telemetry(
    *,
    seat_code: str,
    client_id: str | None,
    temperature: float | None,
    humidity: float | None,
    noise_level: float | None,
    button_pressed: bool | None,
    rotary_raw_value: float | None,
    source_timestamp: int | None,
) -> sqlite3.Row:
    received_at = datetime.utcnow().isoformat(timespec="seconds")
    button_value = None if button_pressed is None else int(button_pressed)
    values: tuple[Any, ...] = (
        seat_code,
        client_id,
        temperature,
        humidity,
        noise_level,
        button_value,
        rotary_raw_value,
        received_at,
        source_timestamp,
    )
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO seat_telemetry (
                seat_code, client_id, temperature, humidity, noise_level,
                button_pressed, rotary_raw_value, received_at, source_timestamp
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(seat_code) DO UPDATE SET
                client_id = excluded.client_id,
                temperature = excluded.temperature,
                humidity = excluded.humidity,
                noise_level = excluded.noise_level,
                button_pressed = excluded.button_pressed,
                rotary_raw_value = excluded.rotary_raw_value,
                received_at = excluded.received_at,
                source_timestamp = excluded.source_timestamp
            """,
            values,
        )
        connection.execute(
            """
            INSERT INTO telemetry_history (
                seat_code, client_id, temperature, humidity, noise_level,
                button_pressed, rotary_raw_value, received_at, source_timestamp
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )
        return connection.execute(
            "SELECT * FROM seat_telemetry WHERE seat_code = ?",
            (seat_code,),
        ).fetchone()


def list_latest_telemetry() -> list[sqlite3.Row]:
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT
                s.code,
                s.area,
                s.pc_level,
                s.status,
                t.client_id,
                t.temperature,
                t.humidity,
                t.noise_level,
                t.button_pressed,
                t.rotary_raw_value,
                t.received_at,
                t.source_timestamp
            FROM seats s
            LEFT JOIN seat_telemetry t ON t.seat_code = s.code
            ORDER BY s.code ASC
            """
        ).fetchall()


def create_reservation(name: str, phone: str | None = None) -> sqlite3.Row:
    normalized_name = normalize_name(name)
    now = datetime.utcnow().isoformat(timespec="seconds")
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO reservations (name, normalized_name, phone, reserved_at)
            VALUES (?, ?, ?, ?)
            """,
            (name.strip(), normalized_name, phone.strip() if phone else None, now),
        )
        reservation_id = cursor.lastrowid
        return connection.execute(
            "SELECT * FROM reservations WHERE id = ?",
            (reservation_id,),
        ).fetchone()


def find_pending_reservation_by_name(name: str) -> sqlite3.Row | None:
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT *
            FROM reservations
            WHERE normalized_name = ?
              AND checked_in_at IS NULL
            ORDER BY reserved_at DESC
            LIMIT 1
            """,
            (normalize_name(name),),
        ).fetchone()


def check_in_reservation(reservation_id: int) -> sqlite3.Row:
    now = datetime.utcnow().isoformat(timespec="seconds")
    with get_connection() as connection:
        connection.execute(
            "UPDATE reservations SET checked_in_at = ? WHERE id = ?",
            (now, reservation_id),
        )
        return connection.execute(
            "SELECT * FROM reservations WHERE id = ?",
            (reservation_id,),
        ).fetchone()


def get_reservation(reservation_id: int) -> sqlite3.Row | None:
    with get_connection() as connection:
        return connection.execute(
            "SELECT * FROM reservations WHERE id = ?",
            (reservation_id,),
        ).fetchone()


def list_available_seats() -> list[sqlite3.Row]:
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT *
            FROM seats
            WHERE status = 'available'
            ORDER BY
                CASE noise_level WHEN 'low' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                has_window DESC,
                code ASC
            """
        ).fetchall()
