from __future__ import annotations

from pathlib import Path
from typing import Optional

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
    list_available_seats,
)


APP_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Smart Internet Cafe Reservation")
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")


class ReservationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    phone: Optional[str] = Field(default=None, max_length=40)


class CheckInRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/", response_class=HTMLResponse)
def reservation_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/checkin", response_class=HTMLResponse)
def checkin_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("checkin.html", {"request": request})


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
