from datetime import timedelta
import json
from config import supabase, TZ
from datetime import datetime as dt

def parse_duration(duration_text):
    parts = duration_text.split(":")
    hours = int(parts[0])
    minutes = int(parts[1])
    return timedelta(hours=hours, minutes=minutes)

def get_all_venues():
    response = supabase.table("venues").select("*").execute()
    return response.data if response.data else []

def get_all_users():
    response = supabase.table("users").select("*").execute()
    return response.data if response.data else []

def get_user_info(user_id):
    response = supabase.table("users").select("*").eq("user_id", user_id).execute()
    if response.data and len(response.data) > 0:
        return response.data[0]
    return None

def get_venue_ids_for(names):
    """
    Returns a list of venue_ids for venues whose names match any name in the provided list.
    The comparison is done case-insensitively.
    """
    venues = get_all_venues()
    lower_names = [n.lower() for n in names]
    return [v["venue_id"] for v in venues if v["name"].strip().lower() in lower_names]

def get_user_bookings(user_id, is_admin=False):
    """
    Returns all bookings for the given user.
    If is_admin is True, returns all non-cancelled bookings;
    otherwise, only bookings made by the given user.
    """
    query = supabase.table("bookings").select("*").neq("status", "cancelled")
    if not is_admin:
        query = query.eq("user_id", user_id)
    result = query.execute()
    return result.data if result.data else []

def user_can_access_venue(user, venue):
    """Check if user can access a venue based on database permissions"""
    # Get instant booking permissions from venue
    instant_book_permissions = venue.get("instant_book", {})
    
    user_role = user.get("role", "").strip().lower() if user.get("role") else ""
    user_cca = user.get("cca", "").strip().lower() if user.get("cca") else ""
    user_block = user.get("block", "").strip().lower() if user.get("block") else ""
    venue_name = venue["name"].strip().lower()
    
    # Special handling for block lounges - users can only access their own block's lounge
    if "blk lounge" in venue_name:
        # Extract block from venue name (e.g., "A Blk Lounge" -> "a blk")
        venue_block = venue_name.replace(" lounge", "").strip().lower()
        
        # Block heads can only access their own block's lounge
        if user_role == "block head":
            return user_block and user_block == venue_block
        
        # Other users can request bookings for their own block's lounge
        # (but will need approval unless they have instant booking access)
        return user_block and user_block == venue_block
    
    # Check if user has instant booking access
    for role, values in instant_book_permissions.items():
        if user_role == role.strip().lower():
            # For other roles, check CCA
            if user_cca and user_cca in [v.strip().lower() for v in values]:
                return True
    
    # If no instant booking access, check if they can at least request bookings
    # Band Room is restricted to specific chairmen only
    if venue_name == "band room":
        return (user_role == "chairman" and 
                user_cca and user_cca in ["rockers", "inspire"])
    
    # All other venues (Reading Room, Dining Hall, MPSH) allow booking requests
    return True

def has_instant_booking_access(user, venue):
    """Check if user has instant booking access to a venue"""
    instant_book_permissions = venue.get("instant_book", {})
    
    user_role = user.get("role", "").strip().lower() if user.get("role") else ""
    user_cca = user.get("cca", "").strip().lower() if user.get("cca") else ""
    user_block = user.get("block", "").strip().lower() if user.get("block") else ""
    
    # Check if user has instant booking access
    for role, values in instant_book_permissions.items():
        if user_role == role.strip().lower():
            # For block lounges, check block instead of CCA
            if role.strip().lower() == "block head":
                if user_block and user_block in [v.strip().lower() for v in values]:
                    return True
            else:
                # For other roles, check CCA
                if user_cca and user_cca in [v.strip().lower() for v in values]:
                    return True
    
    return False

def has_bypass_limit_access(user, venue):
    """Check if user can bypass booking limits for a venue"""
    bypass_limit_permissions = venue.get("bypass_limit", {})
    
    user_role = user.get("role", "").strip().lower() if user.get("role") else ""
    user_cca = user.get("cca", "").strip().lower() if user.get("cca") else ""
    user_block = user.get("block", "").strip().lower() if user.get("block") else ""
    
    # Check if user has bypass limit access
    for role, values in bypass_limit_permissions.items():
        if user_role == role.strip().lower():
            # For block lounges, check block instead of CCA
            if role.strip().lower() == "block head":
                if user_block and user_block in [v.strip().lower() for v in values]:
                    return True
            else:
                # For other roles, check CCA
                if user_cca and user_cca in [v.strip().lower() for v in values]:
                    return True
    
    return False

def within_booking_limit(user_id, venues, max_bookings= 1):
    """
    Checks if the user has reached the maximum number of active bookings allowed for the specific venues(veneus is array of venue_id).
    Returns True if they can book, False otherwise.
    """
    bookings = get_user_bookings(user_id)
    confirmed_pending_bookings = [b for b in bookings if (b["status"] == "confirmed" or b["status"] == "pending approval") and b["venue_id"] in venues]
    
    def is_active_booking(booking_date, duration):
        hours, minutes = map(int, duration.split(":"))
        delta = timedelta(hours=hours, minutes=minutes)
        booking_start_time = dt.strptime(booking_date, "%Y-%m-%dT%H:%M:%S")
        booking_end_time = booking_start_time + delta
        booking_end_time = TZ.localize(booking_end_time)

        return dt.now(TZ) <= booking_end_time
    
    active_bookings = [b for b in confirmed_pending_bookings if is_active_booking(b["booking_date"], b["duration"])]
    return len(active_bookings) < max_bookings