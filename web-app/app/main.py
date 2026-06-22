from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from .database import (
    check_in_reservation,
    create_reservation,
    find_pending_reservation_by_name,
    get_reservation,
    init_db,
    list_latest_telemetry,
    list_available_seats,
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
def reservation_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/checkin", response_class=HTMLResponse)
def checkin_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("checkin.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request) -> HTMLResponse:
    dashboard = load_dashboard_data()
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            **dashboard,
        },
    )


@app.get("/seats", response_class=HTMLResponse)
def seats_page(request: Request, reservation_id: int) -> HTMLResponse:
    reservation = get_reservation(reservation_id)
    if reservation is None or reservation["checked_in_at"] is None:
        raise HTTPException(status_code=404, detail="Reservation is not checked in")

    seats = list_available_seats()
    recommended = seats[0] if seats else None
    return templates.TemplateResponse(
        "seats.html",
        {
            "request": request,
            "reservation": reservation,
            "recommended": recommended,
            "seats": seats,
        },
    )


@app.post("/api/reservations")
def reserve(payload: ReservationCreate) -> dict[str, object]:
    reservation = create_reservation(payload.name, payload.phone)
    return {
        "message": "Reservation created",
        "reservation": dict(reservation),
    }


@app.post("/api/checkin")
def checkin(payload: CheckInRequest) -> dict[str, object]:
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
def dashboard_data() -> dict[str, object]:
    return {"message": "Dashboard data loaded", **load_dashboard_data()}


@app.post("/api/telemetry")
def ingest_telemetry(payload: TelemetryPayload) -> dict[str, object]:
    row = save_telemetry_payload(payload.model_dump())
    return {
        "message": "Telemetry stored",
        "telemetry": row,
    }


def load_dashboard_data() -> dict[str, object]:
    seat_rows = [dict(row) for row in list_latest_telemetry()]
    remote_rows, error = fetch_remote_telemetry()
    rows = merge_remote_with_seats(seat_rows, remote_rows)
    online_count = sum(1 for row in rows if row["received_at"] is not None)
    return {
        "online_count": online_count,
        "seats": rows,
        "data_source": get_remote_telemetry_url(),
        "data_source_error": error,
    }
