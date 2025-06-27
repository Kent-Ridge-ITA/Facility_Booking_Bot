from datetime import timedelta, datetime as dt
from config import supabase
from calendar_helpers import add_event_to_calendar, remove_event_from_calendar
from db_helpers import parse_duration

def create_booking(user_id, venue, booking_start, duration_text, user_role, reason, booking_type="full"):
    # Safety check: prevent creating bookings in the past
    from config import TZ
    current_time = dt.now(TZ)
    if booking_start <= current_time:
        print(f"Attempted to create booking in the past: {booking_start} <= {current_time}")
        return False
    
    # Get user info to determine booking status
    from db_helpers import get_user_info, has_instant_booking_access
    user_info = get_user_info(user_id)
    
    # Determine booking status based on venue's instant booking permissions
    if has_instant_booking_access(user_info, venue):
        status = "confirmed"
    else:
        status = "pending approval"
    
    booking_start_naive = booking_start.replace(tzinfo=None) if booking_start.tzinfo else booking_start
    booking_start_str = booking_start_naive.strftime("%Y-%m-%d %H:%M:%S")
    data = {
        "user_id": user_id,
        "venue_id": venue["venue_id"],
        "booking_date": booking_start_str,
        "duration": duration_text,
        "status": status,
        "reason": reason,
        "booking_type": booking_type
    }
    
    supabase.table("bookings").insert(data).execute()
    result = supabase.table("bookings").select("*") \
        .eq("user_id", user_id) \
        .eq("venue_id", venue["venue_id"]) \
        .eq("booking_date", booking_start_str) \
        .eq("duration", duration_text) \
        .eq("reason", reason) \
        .eq("booking_type", booking_type) \
        .execute()
    new_booking_data = result.data[0] if result.data else None
    
    if new_booking_data and status == "confirmed":
        event_id = add_event_to_calendar(new_booking_data, venue)
        supabase.table("bookings").update({"calendar_event_id": event_id}).eq("booking_id", new_booking_data["booking_id"]).execute()

    # Send notifications for pending approvals
    venue_name = venue["name"].strip().lower()
    if status == "pending approval" and new_booking_data:
        if venue_name in ["reading room", "dining hall"]:
            from notifications import notify_jcrc_welfare_d_of_new_request
            notify_jcrc_welfare_d_of_new_request(new_booking_data)
        elif "blk lounge" in venue_name:
            from notifications import notify_block_head_of_new_request
            notify_block_head_of_new_request(new_booking_data)
    
    # Send GC notifications for instantly confirmed venues
    if status == "confirmed" and new_booking_data:
        if venue_name in ["reading room", "dining hall", "a blk lounge", "b blk lounge", "c blk lounge", "d blk lounge", "e blk lounge"]:
            from notifications import notify_gc
            notify_gc(new_booking_data)

    return True

def check_conflict(venue, new_booking_start, duration_text, user_id, booking_type="full"):
    from config import TZ
    new_duration = parse_duration(duration_text)
    
    # Ensure new_booking_start is timezone-aware
    if new_booking_start.tzinfo is None:
        new_booking_start = TZ.localize(new_booking_start)
    
    new_booking_end = new_booking_start + new_duration
    
    response = supabase.table("bookings").select("*") \
        .eq("venue_id", venue["venue_id"]) \
        .eq("status", "confirmed") \
        .execute()
    bookings = response.data if response.data else []
    
    venue_name = venue["name"].strip().lower()
    
    for b in bookings:
        confirmed_start = dt.fromisoformat(b["booking_date"])
        # Make confirmed_start timezone-aware for comparison
        if confirmed_start.tzinfo is None:
            confirmed_start = TZ.localize(confirmed_start)
        
        try:
            confirmed_duration = parse_duration(b["duration"])
        except Exception:
            confirmed_duration = timedelta(0)
        confirmed_end = confirmed_start + confirmed_duration
        
        # Check for time overlap
        if new_booking_start < confirmed_end and new_booking_end > confirmed_start:
            # For MPSH, check booking type conflicts
            if venue_name == "mpsh":
                existing_booking_type = b.get("booking_type", "full")
                # Full booking conflicts with any other booking
                # Half booking conflicts with full booking
                # Half booking can coexist with another half booking
                if booking_type == "full" or existing_booking_type == "full":
                    return True
                # Both are half bookings - no conflict
                else:
                    continue
            else:
                # For other venues, any time overlap is a conflict
                return True
    return False

def check_start_conflict(venue, proposed_start, booking_type="full"):
    from config import TZ
    response = supabase.table("bookings").select("*") \
        .eq("venue_id", venue["venue_id"]) \
        .eq("status", "confirmed") \
        .execute()
    bookings = response.data if response.data else []
    
    venue_name = venue["name"].strip().lower()
    
    for b in bookings:
        confirmed_start = dt.fromisoformat(b["booking_date"])
        # Make confirmed_start timezone-aware for comparison
        if confirmed_start.tzinfo is None:
            confirmed_start = TZ.localize(confirmed_start)
        
        try:
            confirmed_duration = parse_duration(b["duration"])
        except Exception:
            confirmed_duration = timedelta(0)
        confirmed_end = confirmed_start + confirmed_duration
        
        # Ensure proposed_start is also timezone-aware
        if proposed_start.tzinfo is None:
            proposed_start = TZ.localize(proposed_start)
        
        if confirmed_start <= proposed_start < confirmed_end:
            # For MPSH, check booking type conflicts
            if venue_name == "mpsh":
                existing_booking_type = b.get("booking_type", "full")
                # Full booking conflicts with any other booking
                # Half booking conflicts with full booking
                if booking_type == "full" or existing_booking_type == "full":
                    return True
                # Both are half bookings - no conflict
                else:
                    continue
            else:
                # For other venues, any overlap is a conflict
                return True
    return False

def cancel_booking(booking_id, user_id, is_allowed=False):
    query = supabase.table("bookings").select("*").eq("booking_id", booking_id)
    if not is_allowed:
        query = query.eq("user_id", user_id)
    result = query.execute()
    if not result.data:
        return False
    booking = result.data[0]
    
    # Get venue information before cancelling
    venue_result = supabase.table("venues").select("*").eq("venue_id", booking["venue_id"]).execute()
    venue = venue_result.data[0] if venue_result.data else None
    
    # Store original booker ID before cancelling
    original_booker_id = booking["user_id"]
    
    # Cancel the booking
    supabase.table("bookings").update({"status": "cancelled"}).eq("booking_id", booking_id).execute()
    
    # Remove calendar event if exists
    if booking.get("calendar_event_id"):
        remove_event_from_calendar(booking["calendar_event_id"])
    
    # Send MPSH-specific notifications
    if venue and venue["name"].strip().lower() == "mpsh":
        from notifications import notify_mpsh_cancellation, notify_booking_cancelled_by_jcrc
        
        # If someone else cancelled the booking (JCRC), notify the original booker
        if user_id != original_booker_id:
            notify_booking_cancelled_by_jcrc(booking, user_id)
        
        # Always notify other eligible users about the available slot
        notify_mpsh_cancellation(booking, user_id)
    
    return True

def validate_booking_request(user_id, venue, booking_start, duration_text):
    """Validate if a booking request is allowed"""
    from db_helpers import get_user_info, has_bypass_limit_access
    from config import TZ
    
    user_info = get_user_info(user_id)
    
    # Check if user can bypass booking limits
    if has_bypass_limit_access(user_info, venue):
        return True, "Booking limit bypassed"
    
    # Apply normal booking limit (1 active booking per venue)
    # Check if user already has an active booking for this venue
    current_time = dt.now(TZ)
    
    existing_bookings = supabase.table("bookings").select("*") \
        .eq("user_id", user_id) \
        .eq("venue_id", venue["venue_id"]) \
        .neq("status", "cancelled") \
        .neq("status", "rejected") \
        .execute()
    
    # Check if any existing booking is still active (ongoing or future)
    for booking in existing_bookings.data:
        booking_start_time = dt.fromisoformat(booking["booking_date"])
        if booking_start_time.tzinfo is None:
            booking_start_time = TZ.localize(booking_start_time)
        
        # Parse duration and calculate end time
        try:
            duration = parse_duration(booking["duration"])
            booking_end_time = booking_start_time + duration
            
            # If current time is before booking ends, it's still active
            if current_time < booking_end_time:
                return False, f"You already have an active booking for {venue['name']}. Limit: 1 active booking per venue."
        except Exception:
            # If duration parsing fails, skip this booking
            continue
    
    return True, "Booking allowed"