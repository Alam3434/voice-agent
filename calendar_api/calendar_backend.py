# calendar_backend.py
from datetime import datetime, timedelta
from typing import List, Dict
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
import zoneinfo

BASE_DIR = Path(__file__).resolve().parent
SERVICE_ACCOUNT_FILE = BASE_DIR / "service-account-key.json"
SCOPES = ["https://www.googleapis.com/auth/calendar"]

CALENDAR_ID = "mohammadalam2003@gmail.com"  # your real calendar
LOCAL_TZ = zoneinfo.ZoneInfo("America/Los_Angeles") 


def get_calendar_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    service = build("calendar", "v3", credentials=creds)
    return service


def get_events_for_range(start_local: datetime, end_local: datetime) -> List[Dict]:
    """
    Get events between start_local and end_local, both treated as
    America/Los_Angeles time.
    """
    if start_local.tzinfo is None:
        start_local = start_local.replace(tzinfo=LOCAL_TZ)
    else:
        start_local = start_local.astimezone(LOCAL_TZ)

    if end_local.tzinfo is None:
        end_local = end_local.replace(tzinfo=LOCAL_TZ)
    else:
        end_local = end_local.astimezone(LOCAL_TZ)

    service = get_calendar_service()
    events_result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=start_local.isoformat(),  # e.g. 2025-11-15T09:00:00-08:00
        timeMax=end_local.isoformat(),    # RFC3339 with offset
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    return events_result.get("items", [])


def find_free_slots(
    date_local: datetime,
    work_start_hour: int = 9,
    work_end_hour: int = 17,
    duration_minutes: int = 30,
) -> List[Dict]:
    """
    Returns free slots on a given date within [work_start_hour, work_end_hour]
    in America/Los_Angeles time.
    """
    # Normalize incoming date to LOCAL_TZ
    if date_local.tzinfo is None:
        date_local = date_local.replace(tzinfo=LOCAL_TZ)
    else:
        date_local = date_local.astimezone(LOCAL_TZ)

    day_start = date_local.replace(
        hour=work_start_hour, minute=0, second=0, microsecond=0
    )
    day_end = date_local.replace(
        hour=work_end_hour, minute=0, second=0, microsecond=0
    )

    events = get_events_for_range(day_start, day_end)

    busy: List[tuple[datetime, datetime]] = []
    for e in events:
        start = e["start"].get("dateTime") or e["start"].get("date")
        end = e["end"].get("dateTime") or e["end"].get("date")

        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)

        # Convert existing events to LOCAL_TZ for comparison
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=LOCAL_TZ)
        else:
            start_dt = start_dt.astimezone(LOCAL_TZ)

        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=LOCAL_TZ)
        else:
            end_dt = end_dt.astimezone(LOCAL_TZ)

        busy.append((start_dt, end_dt))

    busy.sort(key=lambda x: x[0])

    free_slots: List[Dict] = []
    cursor = day_start

    for b_start, b_end in busy:
        if b_start > cursor:
            slot_start = cursor
            while slot_start + timedelta(minutes=duration_minutes) <= b_start:
                slot_end = slot_start + timedelta(minutes=duration_minutes)
                free_slots.append(
                    {"start": slot_start.isoformat(), "end": slot_end.isoformat()}
                )
                slot_start = slot_end
        cursor = max(cursor, b_end)

    while cursor + timedelta(minutes=duration_minutes) <= day_end:
        slot_end = cursor + timedelta(minutes=duration_minutes)
        free_slots.append(
            {"start": cursor.isoformat(), "end": slot_end.isoformat()}
        )
        cursor = slot_end

    return free_slots


def book_event(start_iso: str, end_iso: str, summary: str, description: str = "") -> Dict:
    service = get_calendar_service()
    event_body = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start_iso},
        "end": {"dateTime": end_iso},
    }
    event = service.events().insert(calendarId=CALENDAR_ID, body=event_body).execute()
    return {"id": event["id"], "htmlLink": event.get("htmlLink")}
