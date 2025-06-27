from datetime import datetime as dt
from config import bot, supabase
from db_helpers import parse_duration, get_user_info
from dotenv import load_dotenv
import os

load_dotenv()

KR_EVERYBODY_ID = os.getenv("KR_EVERYBODY_ID")
DBLK_GC_ID = os.getenv("DBLK_GC_ID")

#TO ADD IN THE FUTURE
ABLK_GC_ID = DBLK_GC_ID
BBLK_GC_ID = DBLK_GC_ID
CBLK_GC_ID = DBLK_GC_ID
EBLK_GC_ID = DBLK_GC_ID

def notify_approval(booking):
    booking_id = booking["booking_id"]
    user_id = booking["user_id"]
    user_info = get_user_info(user_id)
    user_name = user_info.get("name", "Unknown User") if user_info else "Unknown User"
    venue_data = supabase.table("venues").select("*").eq("venue_id", booking["venue_id"]).execute()
    venue = venue_data.data[0] if venue_data.data else {}
    venue_name = venue.get("name", "Unknown Venue")
    booking_start = dt.fromisoformat(booking["booking_date"])
    dur = parse_duration(booking["duration"])
    end_dt = booking_start + dur
    start_str = booking_start.strftime("%Y-%m-%d %H:%M")
    end_str = end_dt.strftime("%Y-%m-%d %H:%M")
    detail_message = (
        f"📋 Booking ID: {booking_id}\n"
        f"🏢 Venue: {venue_name}\n"
        f"👤 Name: {user_name}\n"
        f"📅 Start: {start_str}\n"
        f"⏰ End: {end_str}\n"
        f"✅ Status: {booking['status']}\n"
        f"📝 Reason: {booking.get('reason','')}\n"
        "----------------------"
    )
    try:
        bot.send_message(user_id, f"🎉 Your booking has been approved!\n\n{detail_message}")
    except Exception as e:
        print(f"Failed to message user {user_id}: {e}")

def notify_gc(booking):
    booking_id = booking["booking_id"]
    user_id = booking["user_id"]
    user_info = get_user_info(user_id)
    user_name = user_info.get("name", "Unknown User") if user_info else "Unknown User"
    venue_data = supabase.table("venues").select("*").eq("venue_id", booking["venue_id"]).execute()
    venue = venue_data.data[0] if venue_data.data else {}
    venue_name = venue.get("name", "Unknown Venue")
    booking_start = dt.fromisoformat(booking["booking_date"])
    dur = parse_duration(booking["duration"])
    end_dt = booking_start + dur
    start_str = booking_start.strftime("%Y-%m-%d %H:%M")
    end_str = end_dt.strftime("%Y-%m-%d %H:%M")
    gc_message = (
        f"🏢 Venue: {venue_name}\n"
        f"👤 Name: {user_name}\n"
        f"📅 Start: {start_str}\n"
        f"⏰ End: {end_str}\n"
        "----------------------"
    )
    if venue_name in ["Reading Room", "Dining Hall"]:
        chat_id = KR_EVERYBODY_ID
    elif venue_name == "A Blk Lounge":
        chat_id = ABLK_GC_ID
    elif venue_name == "B Blk Lounge":
        chat_id = BBLK_GC_ID
    elif venue_name == "C Blk Lounge":
        chat_id = CBLK_GC_ID
    elif venue_name == "D Blk Lounge":
        chat_id = DBLK_GC_ID
    elif venue_name == "E Blk Lounge":
        chat_id = EBLK_GC_ID
    try:
        bot.send_message(chat_id, f"📢 New Booking Alert!\n\n{gc_message}")
    except Exception as e:
        print(f"Failed to notify group {chat_id}: {e}")


def notify_jcrc_welfare_d_of_new_request(booking):
    # Find JCRC users with Welfare D CCA only
    jcrc_welfare_d_result = supabase.table("users").select("*") \
        .ilike("role", "JCRC") \
        .eq("cca", "Welfare D") \
        .execute()
    jcrc_welfare_d_users = jcrc_welfare_d_result.data if jcrc_welfare_d_result.data else []
    
    if not jcrc_welfare_d_users:
        print("No JCRC Welfare D users found in database")
        return
    
    booking_id = booking["booking_id"]
    user_id = booking["user_id"]
    user_info = get_user_info(user_id)
    user_name = user_info.get("name", "Unknown User") if user_info else "Unknown User"
    venue_data = supabase.table("venues").select("*").eq("venue_id", booking["venue_id"]).execute()
    venue = venue_data.data[0] if venue_data.data else {}
    venue_name = venue.get("name", "Unknown Venue")
    booking_start = dt.fromisoformat(booking["booking_date"])
    dur = parse_duration(booking["duration"])
    end_dt = booking_start + dur
    start_str = booking_start.strftime("%Y-%m-%d %H:%M")
    end_str = end_dt.strftime("%Y-%m-%d %H:%M")
    detail_msg = (
        f"🔔 New booking request (Pending Approval)!\n"
        f"📋 Booking ID: {booking_id}\n"
        f"🏢 Venue: {venue_name}\n"
        f"👤 Name: {user_name}\n"
        f"📅 Start: {start_str}\n"
        f"⏰ End: {end_str}\n"
        f"⏳ Status: {booking['status']}\n"
        f"📝 Reason: {booking.get('reason', '')}\n"
        "----------------------"
    )
    for jcrc_user in jcrc_welfare_d_users:
        jcrc_user_id = jcrc_user["user_id"]
        try:
            bot.send_message(jcrc_user_id, detail_msg)
            print(f"Notification sent to JCRC (Welfare D) user {jcrc_user_id}")
        except Exception as e:
            print(f"Failed to notify JCRC (Welfare D) user {jcrc_user_id}: {e}")

def notify_block_head_of_new_request(booking):
    venue_data = supabase.table("venues").select("*").eq("venue_id", booking["venue_id"]).execute()
    venue = venue_data.data[0] if venue_data.data else {}
    # Extract block from venue name (e.g., "A Blk Lounge" -> "A Blk")
    venue_block = venue["name"].strip().replace(" Lounge", "")
    
    # Find Block Head for this specific block - make sure role comparison is case-insensitive
    block_head_result = supabase.table("users").select("*") \
        .ilike("role", "Block Head") \
        .eq("block", venue_block) \
        .execute()
    block_heads = block_head_result.data if block_head_result.data else []
    
    if not block_heads:
        print(f"No Block Head found for {venue_block}")
        return
    
    booking_id = booking["booking_id"]
    user_id = booking["user_id"]
    user_info = get_user_info(user_id)
    user_name = user_info.get("name", "Unknown User") if user_info else "Unknown User"
    venue_name = venue.get("name", "Unknown Venue")
    
    booking_start = dt.fromisoformat(booking["booking_date"])
    dur = parse_duration(booking["duration"])
    end_dt = booking_start + dur
    start_str = booking_start.strftime("%Y-%m-%d %H:%M")
    end_str = end_dt.strftime("%Y-%m-%d %H:%M")
    
    detail_msg = (
        f"🔔 New {venue_block} booking request (Pending Approval)!\n"
        f"📋 Booking ID: {booking_id}\n"
        f"🏢 Venue: {venue_name}\n"
        f"👤 Name: {user_name}\n"
        f"📅 Start: {start_str}\n"
        f"⏰ End: {end_str}\n"
        f"⏳ Status: {booking['status']}\n"
        f"📝 Reason: {booking.get('reason', '')}\n"
        "----------------------"
    )
    
    for block_head in block_heads:
        block_head_user_id = block_head["user_id"]
        try:
            bot.send_message(block_head_user_id, detail_msg)
            print(f"Notification sent to Block Head {block_head_user_id} for {venue_block}")
        except Exception as e:
            print(f"Failed to notify Block Head {block_head_user_id}: {e}")

def notify_mpsh_cancellation(cancelled_booking, cancelled_by_user_id):
    """Notify all MPSH-eligible users about a cancelled MPSH booking"""
    from db_helpers import get_all_users, get_all_venues, has_instant_booking_access
    
    # Get the MPSH venue
    venues = get_all_venues()
    mpsh_venue = next((v for v in venues if v["name"].strip().lower() == "mpsh"), None)
    
    if not mpsh_venue:
        print("MPSH venue not found for cancellation notification")
        return
    
    # Get all users who can access MPSH
    all_users = get_all_users()
    eligible_users = []
    
    for user in all_users:
        # Skip the user who cancelled the booking
        if user["user_id"] == cancelled_by_user_id:
            continue
        
        # Skip the original booker (they get a separate notification if cancelled by someone else)
        if user["user_id"] == cancelled_booking["user_id"]:
            continue
        
        # Skip users with incomplete data
        if not user.get("role") or not user.get("cca"):
            continue
            
        # Check if user has instant booking access to MPSH
        if has_instant_booking_access(user, mpsh_venue):
            eligible_users.append(user)
    
    if not eligible_users:
        print("No eligible users found for MPSH cancellation notification")
        return
    
    # Get booking details
    booking_start = dt.fromisoformat(cancelled_booking["booking_date"])
    dur = parse_duration(cancelled_booking["duration"])
    end_dt = booking_start + dur
    start_str = booking_start.strftime("%Y-%m-%d %H:%M")
    end_str = end_dt.strftime("%Y-%m-%d %H:%M")
    
    # Get booking type display
    booking_type = cancelled_booking.get('booking_type', 'full')
    booking_type_display = f" [{booking_type.upper()}]"
    
    # Get information about the original booker
    original_booker = get_user_info(cancelled_booking["user_id"])
    if original_booker:
        original_booker_name = original_booker.get("name", "Unknown User")
        original_booker_role = original_booker.get("role", "Unknown Role")
        original_booker_cca = original_booker.get("cca", "Unknown CCA")
        original_booker_info = f"{original_booker_name} ({original_booker_role} - {original_booker_cca})"
    else:
        original_booker_info = "Unknown User"
    
    # Create notification message
    notification_msg = (
        f"🏟️ MPSH Slot is now Available!\n\n"
        f"📅 Date & Time: {start_str} - {end_str}\n"
        f"🏢 Venue: MPSH{booking_type_display}\n"
        f"👤 Previously booked by: {original_booker_info}\n"
        f"📝 Reason: {cancelled_booking.get('reason', 'No reason provided')}\n\n"
        f"💡 This slot is now available for booking!\n"
        f"Use /book to make a reservation."
    )
    
    # Send notification to all eligible users
    successful_notifications = 0
    for user in eligible_users:
        try:
            bot.send_message(user["user_id"], notification_msg)
            successful_notifications += 1
        except Exception as e:
            print(f"Failed to notify user {user['user_id']} of MPSH cancellation: {e}")
    
    print(f"MPSH cancellation notification sent to {successful_notifications}/{len(eligible_users)} eligible users")

def notify_booking_cancelled_by_jcrc(cancelled_booking, cancelled_by_user_id):
    """Notify the original booker that their booking was cancelled by JCRC"""
    original_booker_id = cancelled_booking["user_id"]
    
    # Don't notify if the original booker is the one who cancelled
    if original_booker_id == cancelled_by_user_id:
        return
    
    # Get booking details
    booking_start = dt.fromisoformat(cancelled_booking["booking_date"])
    dur = parse_duration(cancelled_booking["duration"])
    end_dt = booking_start + dur
    start_str = booking_start.strftime("%Y-%m-%d %H:%M")
    end_str = end_dt.strftime("%Y-%m-%d %H:%M")
    
    # Get booking type display
    booking_type = cancelled_booking.get('booking_type', 'full')
    booking_type_display = f" [{booking_type.upper()}]"
    
    # Get venue name
    from db_helpers import get_all_venues
    venues = get_all_venues()
    venue = next((v for v in venues if v["venue_id"] == cancelled_booking["venue_id"]), None)
    venue_name = venue["name"] if venue else "Unknown Venue"
    
    # Get information about who cancelled the booking
    cancelled_by_user = get_user_info(cancelled_by_user_id)
    if cancelled_by_user:
        cancelled_by_name = cancelled_by_user.get("name", "Unknown User")
        cancelled_by_role = cancelled_by_user.get("role", "Unknown Role")
        cancelled_by_cca = cancelled_by_user.get("cca", "Unknown CCA")
        cancelled_by_info = f"{cancelled_by_name} ({cancelled_by_role} - {cancelled_by_cca})"
    else:
        cancelled_by_info = "JCRC"
    
    # Create notification message for original booker
    notification_msg = (
        f"❌ Your Booking Has Been Cancelled\n\n"
        f"📅 Date & Time: {start_str} - {end_str}\n"
        f"🏢 Venue: {venue_name}{booking_type_display}\n"
        f"📝 Your reason: {cancelled_booking.get('reason', 'No reason provided')}\n"
        f"👤 Cancelled by: {cancelled_by_info}\n\n"
        f"💡 You can make a new booking using /book if needed."
    )
    
    try:
        bot.send_message(original_booker_id, notification_msg)
        print(f"Cancellation notification sent to original booker {original_booker_id}")
    except Exception as e:
        print(f"Failed to notify original booker {original_booker_id} of cancellation: {e}")