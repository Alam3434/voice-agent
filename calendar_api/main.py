from fastapi import FastAPI
from pydantic import BaseModel
import zoneinfo
from datetime import datetime
from calendar_api.calendar_backend import find_free_slots, book_event

app = FastAPI()

LOCAL_TZ = zoneinfo.ZoneInfo("America/Los_Angeles")


class CheckAvailabilityRequest(BaseModel):
    date: str  # e.g. "2025-11-15" or "2025-11-15T00:00:00Z"
    durationMinutes: int = 30
    workStartHour: int = 9
    workEndHour: int = 17


class BookEventRequest(BaseModel):
    start: str  # ISO string
    end: str    # ISO string
    summary: str
    description: str = ""


def parse_as_local(dt_str: str) -> datetime:
    """
    Treat whatever datetime string the agent sends as LOCAL wall time.
    - Strip any 'Z' or timezone offset.
    - Parse 'YYYY-MM-DDTHH:MM:SS'.
    - Attach America/Los_Angeles tzinfo.
    """
    # Remove trailing 'Z'
    if dt_str.endswith("Z"):
        dt_str = dt_str[:-1]

    # If there is a timezone offset like +00:00 or -08:00, strip it.
    # Keep only the first 19 chars: 'YYYY-MM-DDTHH:MM:SS'
    if len(dt_str) > 19:
        dt_str = dt_str[:19]

    # Now dt_str should look like '2025-11-14T16:30:00'
    naive = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
    return naive.replace(tzinfo=LOCAL_TZ)


@app.get("/")
def root():
    return {"status": "ok", "message": "Calendar API is running"}


# Support BOTH /calendar/check and /calendar/checkAvailability
@app.post("/calendar/check")
@app.post("/calendar/checkAvailability")
def check_availability(req: CheckAvailabilityRequest):
    print("CHECK PAYLOAD:", req)

    raw = req.date

    # Allow either "YYYY-MM-DD" or full ISO string
    if "T" in raw:
        # e.g. "2025-11-15T00:00:00Z"
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=LOCAL_TZ)
        else:
            dt = dt.astimezone(LOCAL_TZ)
    else:
        # "YYYY-MM-DD"
        dt = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=LOCAL_TZ)

    # IMPORTANT: call find_free_slots with the correct arguments
    slots = find_free_slots(
        dt,
        work_start_hour=req.workStartHour,
        work_end_hour=req.workEndHour,
        duration_minutes=req.durationMinutes,
    )
    return {"slots": slots}


@app.post("/calendar/book")
def book(req: BookEventRequest):
    print("BOOK RAW PAYLOAD:", req)

    start_local = parse_as_local(req.start)
    end_local = parse_as_local(req.end)

    start_iso = start_local.isoformat()
    end_iso = end_local.isoformat()

    result = book_event(start_iso, end_iso, req.summary, req.description)
    return {"status": "confirmed", "event": result}

