from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator


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
