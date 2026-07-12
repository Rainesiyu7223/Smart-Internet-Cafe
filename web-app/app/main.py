from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from .database import (
    check_in_reservation,
    create_reservation,
    find_pending_reservation_by_name,
    get_reservation,
    init_db,
)
from .remote_telemetry import fetch_remote_telemetry, get_remote_telemetry_url, merge_remote_with_seats
from .telemetry import save_telemetry_payload, start_mqtt_subscriber, stop_mqtt_subscriber


APP_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Smart Internet Cafe Reservation")
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")
mqtt_client: Any | None = None


class ReservationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    phone: Optional[str] = Field(default=None, max_length=40)


class CheckInRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class TelemetryPayload(BaseModel):
    client_id: Optional[str] = None
    timestamp: Optional[int] = None
    seat_code: Optional[str] = None
    seat_id: Optional[str] = None
    button_pressed: Optional[bool] = None
    environment: Dict[str, Any] = Field(default_factory=dict)
    seat_interact: Dict[str, Any] = Field(default_factory=dict)


@app.on_event("startup")
def startup() -> None:
    global mqtt_client
    init_db()
    mqtt_client = start_mqtt_subscriber()


@app.on_event("shutdown")
def shutdown() -> None:
    stop_mqtt_subscriber(mqtt_client)


@app.get("/", response_class=HTMLResponse)
def reservation_page(request: Request):
    role = get_role(request)
    if role == "admin":
        return RedirectResponse(url="/admin", status_code=303)
    if role != "user":
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("index.html", {"request": request, "role": role})


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    role = get_role(request)
    if role == "admin":
        return RedirectResponse(url="/admin", status_code=303)
    if role == "user":
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "role": None})


@app.get("/login/{role}")
def login_as(role: str) -> RedirectResponse:
    if role not in {"user", "admin"}:
        return RedirectResponse(url="/login", status_code=303)

    response = RedirectResponse(url="/admin" if role == "admin" else "/", status_code=303)
    response.set_cookie("role", role, httponly=True, samesite="lax")
    return response


@app.get("/logout")
def logout() -> RedirectResponse:
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("role")
    return response


@app.get("/checkin", response_class=HTMLResponse)
def checkin_page(request: Request):
    role = get_role(request)
    if role == "admin":
        return RedirectResponse(url="/admin", status_code=303)
    if role != "user":
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("checkin.html", {"request": request, "role": role})


@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    role = get_role(request)
    if role != "admin":
        return RedirectResponse(url="/login", status_code=303)
    dashboard = load_dashboard_data()
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "role": role,
            **dashboard,
        },
    )


@app.get("/seats", response_class=HTMLResponse)
def seats_page(request: Request, reservation_id: int):
    role = get_role(request)
    if role == "admin":
        return RedirectResponse(url="/admin", status_code=303)
    if role != "user":
        return RedirectResponse(url="/login", status_code=303)
    reservation = get_reservation(reservation_id)
    if reservation is None or reservation["checked_in_at"] is None:
        raise HTTPException(status_code=404, detail="Reservation is not checked in")

    seats = build_admin_seat_layout()
    recommended = seats[0] if seats else None
    return templates.TemplateResponse(
        "seats.html",
        {
            "request": request,
            "role": role,
            "reservation": reservation,
            "recommended": recommended,
            "seats": seats,
        },
    )


@app.get("/seat/{seat_code}", response_class=HTMLResponse)
def seat_detail_page(request: Request, seat_code: str):
    role = get_role(request)
    if role == "admin":
        return RedirectResponse(url="/admin", status_code=303)
    if role != "user":
        return RedirectResponse(url="/login", status_code=303)

    normalized_code = seat_code.upper()
    dashboard = load_dashboard_data()
    seat = find_seat_row(dashboard["seats"], normalized_code)
    if seat is None:
        raise HTTPException(status_code=404, detail="Seat not found")

    return templates.TemplateResponse(
        "seat_detail.html",
        {
            "request": request,
            "role": role,
            "seat": seat,
            "data_source_error": dashboard["data_source_error"],
        },
    )


@app.post("/api/reservations")
def reserve(request: Request, payload: ReservationCreate) -> dict[str, object]:
    if get_role(request) != "user":
        raise HTTPException(status_code=403, detail="User login required")
    reservation = create_reservation(payload.name, payload.phone)
    return {
        "message": "Reservation created",
        "reservation": dict(reservation),
    }


@app.post("/api/checkin")
def checkin(request: Request, payload: CheckInRequest) -> dict[str, object]:
    if get_role(request) != "user":
        raise HTTPException(status_code=403, detail="User login required")
    reservation = find_pending_reservation_by_name(payload.name)
    if reservation is None:
        raise HTTPException(
            status_code=404,
            detail="No pending reservation found for this name",
        )

    checked_in = check_in_reservation(reservation["id"])
    return {
        "message": "Check-in successful",
        "reservation": dict(checked_in),
        "redirect_url": f"/seats?reservation_id={checked_in['id']}",
    }


@app.get("/api/dashboard")
def dashboard_data(request: Request) -> dict[str, object]:
    if get_role(request) != "admin":
        raise HTTPException(status_code=403, detail="Admin login required")
    return {"message": "Dashboard data loaded", **load_dashboard_data()}


@app.get("/api/seats/{seat_code}/telemetry")
def seat_telemetry_data(request: Request, seat_code: str) -> dict[str, object]:
    if get_role(request) not in {"user", "admin"}:
        raise HTTPException(status_code=403, detail="Login required")

    dashboard = load_dashboard_data()
    seat = find_seat_row(dashboard["seats"], seat_code.upper())
    if seat is None:
        raise HTTPException(status_code=404, detail="Seat not found")

    return {
        "message": "Seat telemetry loaded",
        "seat": seat,
        "data_source_error": dashboard["data_source_error"],
    }


@app.post("/api/telemetry")
def ingest_telemetry(payload: TelemetryPayload) -> dict[str, object]:
    row = save_telemetry_payload(payload.model_dump())
    return {
        "message": "Telemetry stored",
        "telemetry": row,
    }


def load_dashboard_data() -> dict[str, object]:
    remote_rows, error = fetch_remote_telemetry()
    for remote_row in remote_rows:
        save_telemetry_payload(
            {
                "seat_code": remote_row.get("code"),
                "client_id": remote_row.get("client_id"),
                "timestamp": remote_row.get("source_timestamp"),
                "environment": {
                    "temperature": remote_row.get("temperature"),
                    "humidity": remote_row.get("humidity"),
                    "noise_level": remote_row.get("noise_level"),
                },
                "seat_interact": {
                    "button_pressed": remote_row.get("button_pressed"),
                    "rotary_raw_value": remote_row.get("rotary_raw_value"),
                },
            }
        )
    seat_rows = build_admin_seat_layout()
    rows = merge_remote_with_seats(seat_rows, remote_rows)
    apply_admin_call_state(rows, remote_rows)
    rows = apply_virtual_seat_data(rows)
    online_count = sum(1 for row in rows if row["received_at"] is not None)
    return {
        "online_count": online_count,
        "seats": rows,
        "data_source": get_remote_telemetry_url(),
        "data_source_error": error,
    }


def get_role(request: Request) -> str | None:
    role = request.cookies.get("role")
    if role in {"user", "admin"}:
        return role
    return None


def find_seat_row(rows: object, code: str) -> dict[str, object] | None:
    if not isinstance(rows, list):
        return None
    return next(
        (
            row
            for row in rows
            if isinstance(row, dict) and str(row.get("code", "")).upper() == code
        ),
        None,
    )


def build_admin_seat_layout() -> list[dict[str, object]]:
    seat_defs = [
        ("A01", "Sensor Seat", "Button sensor", "live"),
        ("A02", "Quiet Focus", "Waiting", "unknown"),
        ("A03", "Balanced", "Waiting", "unknown"),
        ("A04", "Warm / Busy", "Waiting", "unknown"),
        ("A05", "Noisy Corner", "Waiting", "unknown"),
    ]
    return [
        {
            "code": code,
            "area": area,
            "pc_level": "RTX 4070",
            "status": "available",
            "quality_label": quality_label,
            "quality_level": quality_level,
            "client_id": None,
            "temperature": None,
            "humidity": None,
            "noise_level": None,
            "occupied": None,
            "button_pressed": None,
            "admin_call": False,
            "admin_call_id": None,
            "rotary_raw_value": None,
            "received_at": None,
            "source_timestamp": None,
        }
        for code, area, quality_label, quality_level in seat_defs
    ]


def apply_admin_call_state(
    rows: list[dict[str, object]],
    remote_rows: list[dict[str, object]],
) -> None:
    a01 = find_seat_row(rows, "A01")
    if not a01:
        return
    call_row = next(
        (
            row
            for row in remote_rows
            if row.get("code") == "A01" and row.get("button_pressed") is True
        ),
        None,
    )
    a01["admin_call"] = call_row is not None
    a01["admin_call_id"] = None
    if call_row:
        a01["admin_call_id"] = (
            call_row.get("source_timestamp")
            or call_row.get("received_at")
            or call_row.get("client_id")
        )


def apply_virtual_seat_data(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    a01 = find_seat_row(rows, "A01")
    if not a01 or a01.get("received_at") is None:
        return rows

    profiles = {
        "A02": {
            "temperature": -0.8,
            "humidity": 1.5,
            "noise_level": -18.0,
            "occupied": False,
            "quality_label": "Quiet",
            "quality_level": "good",
        },
        "A03": {
            "temperature": 0.4,
            "humidity": -1.0,
            "noise_level": 8.0,
            "occupied": False,
            "quality_label": "Balanced",
            "quality_level": "good",
        },
        "A04": {
            "temperature": 1.2,
            "humidity": 2.0,
            "noise_level": 22.0,
            "occupied": True,
            "quality_label": "Busy",
            "quality_level": "fair",
        },
        "A05": {
            "temperature": 1.8,
            "humidity": 3.5,
            "noise_level": 35.0,
            "occupied": True,
            "quality_label": "Warm",
            "quality_level": "poor",
        },
    }

    for row in rows:
        profile = profiles.get(str(row.get("code")))
        if not profile:
            continue
        row.update(
            {
                "client_id": "derived_from_A01",
                "temperature": add_metric(a01.get("temperature"), profile["temperature"]),
                "humidity": clamp_metric(
                    add_metric(a01.get("humidity"), profile["humidity"]),
                    0.0,
                    100.0,
                ),
                "noise_level": max_metric(add_metric(a01.get("noise_level"), profile["noise_level"]), 0.0),
                "occupied": profile["occupied"],
                "button_pressed": False,
                "admin_call": False,
                "admin_call_id": None,
                "received_at": a01.get("received_at"),
                "source_timestamp": a01.get("source_timestamp"),
                "quality_label": profile["quality_label"],
                "quality_level": profile["quality_level"],
            }
        )
    return rows


def add_metric(value: object, delta: object) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value) + float(delta), 1)
    except (TypeError, ValueError):
        return None


def clamp_metric(value: float | None, minimum: float, maximum: float) -> float | None:
    if value is None:
        return None
    return min(max(value, minimum), maximum)


def max_metric(value: float | None, minimum: float) -> float | None:
    if value is None:
        return None
    return max(value, minimum)
