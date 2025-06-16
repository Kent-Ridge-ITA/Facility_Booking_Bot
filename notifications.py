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