import os
import base64
import json
from datetime import datetime as dt
from googleapiclient.discovery import build
import google.oauth2.service_account

from config import VENUE_COLORS
from db_helpers import get_user_info

SCOPES = ['https://www.googleapis.com/auth/calendar']
calendar_id = 'fde2719902f4ca8ada620b4922fa8365a333b2cf79885e048e107dd6d7834b9a@group.calendar.google.com'

def get_calendar_service():
    """Initializes and returns Google Calendar service."""
    encoded_credentials = os.getenv("GOOGLE_CREDENTIALS")

    if not encoded_credentials:
        print("GOOGLE_CREDENTIALS is not set or is empty.")
        raise ValueError("GOOGLE_CREDENTIALS environment variable is not set.")
    else:
        print(f"GOOGLE_CREDENTIALS is set. Length: {len(encoded_credentials)}")

    decoded_credentials = base64.b64decode(encoded_credentials).decode("utf-8")

    # Optional: write to temp file or use from_service_account_info directly
    credentials = google.oauth2.service_account.Credentials.from_service_account_info(
        json.loads(decoded_credentials), scopes=SCOPES)

    service = build('calendar', 'v3', credentials=credentials)
    return service

def add_event_to_calendar(booking, venue):
    calendar_service = get_calendar_service()  # 👈 Service initialized here at runtime

    start_dt = dt.fromisoformat(booking["booking_date"])
    from booking_utils import parse_duration
    duration_td = parse_duration(booking["duration"])
    end_dt = start_dt + duration_td

    venue_name = venue['name']
    booking_type = booking.get('booking_type', 'full')
    
    venue_display = f"{venue_name} [{booking_type.upper()}]" if venue_name.lower() == 'mpsh' else venue_name

    summary = f"{venue_display}: {booking.get('reason', 'No Reason Provided')}"
    user_info = get_user_info(booking["user_id"])
    print(user_info)

    description = f"Booked by: {user_info.get('name', 'Unknown User')}"
    if user_info.get("role", "Resident") != "Resident":
        user_role = user_info.get('role', '')
        user_cca = user_info.get('cca', '')
        if user_cca and user_cca.lower() != "no cca":
            description += f", ({user_role} ({user_cca}))"
        else:
            description += f", ({user_role})"
    description += f" from {user_info.get('block', 'No Block')}"

    color_id = VENUE_COLORS.get(venue["name"], "1")

    event = {
        'summary': summary,
        'description': description,
        'location': venue['name'],
        'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'Asia/Singapore'},
        'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'Asia/Singapore'},
        'colorId': color_id
    }

    created_event = calendar_service.events().insert(calendarId=calendar_id, body=event).execute()
    print('Event created on Calendar: {}'.format(created_event.get('htmlLink')))
    return created_event.get("id")

def remove_event_from_calendar(event_id):
    calendar_service = get_calendar_service()  # 👈 Service initialized here too

    try:
        calendar_service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        print(f"Event {event_id} removed from Google Calendar.")
    except Exception as e:
        print(f"Failed to remove event from calendar: {e}")
