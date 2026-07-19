from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from .database import (
    assign_seat_to_reservation,
    check_in_reservation,
    check_out_reservation,
    create_reservation,
    find_pending_reservation_by_name,
    get_reservation,
    init_db,
    list_active_seat_assignments,
    release_active_seat,
)
from .remote_telemetry import fetch_remote_telemetry, get_remote_telemetry_url, merge_remote_with_seats
from .telemetry import save_telemetry_payload, start_mqtt_subscriber, stop_mqtt_subscriber


APP_DIR = Path(__file__).resolve().parent


def humidity_label(value: object) -> str:
    """Return a concise user-facing assessment for relative humidity."""
    try:
        humidity = float(value)
    except (TypeError, ValueError):
        return "--"
    if humidity < 30:
        return "Dry"
    if humidity <= 60:
        return "Comfortable"
    return "Humid"

app = FastAPI(title="Smart Internet Cafe Reservation")
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")
templates.env.globals["humidity_label"] = humidity_label
mqtt_client: Any | None = None
MANAGED_SEAT_CODES = {"A01", "A02", "A03", "A04"}


class ReservationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    phone: Optional[str] = Field(default=None, max_length=40)


class CheckInRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class SeatSelectionRequest(BaseModel):
    seat_code: str = Field(min_length=1, max_length=20)


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
def root_login_page(request: Request):
    """The root URL is always the login landing page."""
    return templates.TemplateResponse("login.html", {"request": request, "role": None})


@app.get("/reservation", response_class=HTMLResponse)
def reservation_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "role": "user"})


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if has_admin_access(request):
        return RedirectResponse(url="/admin", status_code=303)
    if has_user_access(request):
        return RedirectResponse(url="/reservation", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "role": None})


@app.get("/login/{role}")
def login_as(role: str) -> RedirectResponse:
    if role not in {"user", "admin"}:
        return RedirectResponse(url="/login", status_code=303)

    response = RedirectResponse(url="/admin" if role == "admin" else "/reservation", status_code=303)
    response.set_cookie(f"{role}_access", "1", httponly=True, samesite="lax")
    return response


@app.get("/logout")
def logout() -> RedirectResponse:
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("role")
    response.delete_cookie("user_access")
    response.delete_cookie("admin_access")
    return response


@app.get("/checkin", response_class=HTMLResponse)
def checkin_page(request: Request):
    return templates.TemplateResponse("checkin.html", {"request": request, "role": "user"})


@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    if not has_admin_access(request):
        return RedirectResponse(url="/login", status_code=303)
    dashboard = load_dashboard_data()
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "role": "admin",
            **dashboard,
        },
    )


@app.get("/seats", response_class=HTMLResponse)
def seats_page(request: Request, reservation_id: int):
    reservation = get_reservation(reservation_id)
    if reservation is None or reservation["checked_in_at"] is None:
        raise HTTPException(status_code=404, detail="Reservation is not checked in")

    dashboard = load_dashboard_data()
    seats = dashboard["seats"]
    recommended = dashboard["recommended_seat"]
    return templates.TemplateResponse(
        "seats.html",
        {
            "request": request,
            "role": "user",
            "reservation": reservation,
            "recommended": recommended,
            "seats": seats,
            "data_source_error": dashboard["data_source_error"],
        },
    )


@app.get("/seat/{seat_code}", response_class=HTMLResponse)
def seat_detail_page(
    request: Request,
    seat_code: str,
    snapshot: bool = False,
    temperature: Optional[float] = None,
    humidity: Optional[float] = None,
    noise_level: Optional[float] = None,
    occupied: Optional[bool] = None,
    reservation_id: Optional[int] = None,
):
    normalized_code = seat_code.upper()
    if snapshot:
        seat = snapshot_seat(
            normalized_code,
            temperature=temperature,
            humidity=humidity,
            noise_level=noise_level,
            occupied=occupied,
        )
        data_source_error = None
    else:
        dashboard = load_dashboard_data()
        seat = find_seat_row(dashboard["seats"], normalized_code)
        if seat is None:
            if normalized_code not in MANAGED_SEAT_CODES:
                raise HTTPException(status_code=404, detail="Seat not found")
            seat = placeholder_seat(normalized_code)
        data_source_error = dashboard["data_source_error"]

    return templates.TemplateResponse(
        "seat_detail.html",
        {
            "request": request,
            "role": "user",
            "seat": seat,
            "data_source_error": data_source_error,
            "has_snapshot": snapshot,
            "reservation_id": reservation_id,
        },
    )


@app.post("/api/reservations")
def reserve(request: Request, payload: ReservationCreate) -> dict[str, object]:
    reservation = create_reservation(payload.name, payload.phone)
    return {
        "message": "Reservation created",
        "reservation": dict(reservation),
    }


@app.post("/api/checkin")
def checkin(request: Request, payload: CheckInRequest) -> dict[str, object]:
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


@app.post("/api/reservations/{reservation_id}/seat")
def select_seat(
    request: Request,
    reservation_id: int,
    payload: SeatSelectionRequest,
) -> dict[str, object]:
    reservation = get_reservation(reservation_id)
    if reservation is None or reservation["checked_in_at"] is None:
        raise HTTPException(status_code=404, detail="Reservation is not checked in")

    seat_code = payload.seat_code.upper()
    if seat_code not in MANAGED_SEAT_CODES:
        raise HTTPException(status_code=404, detail="Seat not found")
    try:
        assignment = assign_seat_to_reservation(reservation_id, seat_code)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"message": "Seat selected", "assignment": dict(assignment)}


@app.post("/api/reservations/{reservation_id}/checkout")
def checkout(request: Request, reservation_id: int) -> dict[str, object]:
    reservation = get_reservation(reservation_id)
    if reservation is None or reservation["checked_in_at"] is None:
        raise HTTPException(status_code=404, detail="Reservation is not checked in")
    if reservation["checked_out_at"] is not None:
        raise HTTPException(status_code=409, detail="Reservation has already checked out")

    checked_out = check_out_reservation(reservation_id)
    return {"message": "Check-out successful", "reservation": dict(checked_out)}


@app.post("/api/seats/{seat_code}/release")
def release_seat(request: Request, seat_code: str) -> dict[str, object]:
    if not has_admin_access(request):
        raise HTTPException(status_code=403, detail="Admin login required")
    normalized_code = seat_code.upper()
    released_reservation = release_active_seat(normalized_code)
    if released_reservation is None:
        raise HTTPException(status_code=404, detail="Seat is not occupied")
    return {
        "message": f"Seat {normalized_code} released",
        "reservation": dict(released_reservation),
    }


@app.get("/api/dashboard")
def dashboard_data(request: Request) -> dict[str, object]:
    if not has_admin_access(request):
        raise HTTPException(status_code=403, detail="Admin login required")
    return {"message": "Dashboard data loaded", **load_dashboard_data()}


@app.get("/api/seats/{seat_code}/telemetry")
def seat_telemetry_data(request: Request, seat_code: str) -> dict[str, object]:
    dashboard = load_dashboard_data()
    seat = find_seat_row(dashboard["seats"], seat_code.upper())
    if seat is None:
        normalized_code = seat_code.upper()
        if normalized_code not in MANAGED_SEAT_CODES:
            raise HTTPException(status_code=404, detail="Seat not found")
        seat = placeholder_seat(normalized_code)

    return {
        "message": "Seat telemetry loaded",
        "seat": seat,
        "data_source_error": dashboard["data_source_error"],
    }


@app.get("/api/recommendations/{reservation_id}")
def recommendation_data(request: Request, reservation_id: int) -> dict[str, object]:
    reservation = get_reservation(reservation_id)
    if reservation is None or reservation["checked_in_at"] is None:
        raise HTTPException(status_code=404, detail="Reservation is not checked in")

    return {"message": "Recommendation data loaded", **load_dashboard_data()}


@app.post("/api/telemetry")
def ingest_telemetry(payload: TelemetryPayload) -> dict[str, object]:
    row = save_telemetry_payload(payload.model_dump())
    return {
        "message": "Telemetry stored",
        "telemetry": row,
    }


def load_dashboard_data() -> dict[str, object]:
    remote_rows, error, recommended_code = fetch_remote_telemetry()
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
    seat_rows = build_admin_seat_layout(remote_rows)
    rows = merge_remote_with_seats(seat_rows, remote_rows)
    apply_reservation_occupancy(rows)
    apply_admin_call_state(rows, remote_rows)
    recommended_seat = find_seat_row(rows, recommended_code) if recommended_code else None
    online_count = sum(1 for row in rows if row["received_at"] is not None)
    return {
        "online_count": online_count,
        "seats": rows,
        "recommended_seat": recommended_seat,
        "recommended_seat_code": recommended_code,
        "data_source": get_remote_telemetry_url(),
        "data_source_error": error,
    }


def has_user_access(request: Request) -> bool:
    return request.cookies.get("user_access") == "1" or request.cookies.get("role") == "user"


def has_admin_access(request: Request) -> bool:
    return request.cookies.get("admin_access") == "1" or request.cookies.get("role") == "admin"


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


def build_admin_seat_layout(remote_rows: list[dict[str, object]] | None = None) -> list[dict[str, object]]:
    if remote_rows:
        seat_defs = [
            (str(row["code"]), seat_area(str(row["code"])), "API data", "live")
            for row in sorted(remote_rows, key=lambda row: str(row.get("code", "")))
            if row.get("code")
        ]
    else:
        # Do not show invented seats while the upstream API is unavailable.
        seat_defs = []
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


def seat_area(code: str) -> str:
    areas = {
        "A01": "Sensor Seat",
        "A02": "Quiet Focus",
        "A03": "Balanced",
        "A04": "Warm / Busy",
    }
    return areas.get(code, "Remote Seat")


def placeholder_seat(code: str) -> dict[str, object]:
    """Keep a selected managed seat available while its live API data reconnects."""
    return {
        "code": code,
        "area": seat_area(code),
        "pc_level": "RTX 4070",
        "status": "available",
        "quality_label": "Waiting",
        "quality_level": "unknown",
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


def snapshot_seat(
    code: str,
    *,
    temperature: float | None,
    humidity: float | None,
    noise_level: float | None,
    occupied: bool | None,
) -> dict[str, object]:
    seat = placeholder_seat(code)
    seat.update(
        {
            "temperature": temperature,
            "humidity": humidity,
            "noise_level": noise_level,
            "occupied": occupied,
            "received_at": "snapshot",
        }
    )
    return seat


def apply_reservation_occupancy(rows: list[dict[str, object]]) -> None:
    assigned_codes = {
        str(assignment["seat_code"]).upper()
        for assignment in list_active_seat_assignments()
    }
    for row in rows:
        is_occupied = str(row.get("code", "")).upper() in assigned_codes
        row["occupied"] = is_occupied
        row["status"] = "occupied" if is_occupied else "available"


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
