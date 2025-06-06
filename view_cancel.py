from datetime import datetime as dt
from telebot import types
from config import bot, supabase
from db_helpers import get_user_info, get_all_venues, get_all_users, parse_duration, get_user_bookings, get_venue_ids_for
from booking_utils import cancel_booking

@bot.message_handler(commands=['cancel'])
def cancel_command(message):
    user = get_user_info(message.from_user.id)
    if not user:
        return
    
    # Get current time for filtering past bookings
    from config import TZ
    current_time = dt.now(TZ)
    
    is_admin = (user["role"].strip().lower() == "admin")
    if is_admin:
        # Admin can cancel all future bookings
        admin_bookings_data = supabase.table("bookings").select("*") \
            .neq("status", "cancelled") \
            .gte("booking_date", current_time.strftime("%Y-%m-%d %H:%M:%S")) \
            .order("booking_id", desc=False) \
            .execute()
        bookings = admin_bookings_data.data if admin_bookings_data.data else []
    else:
        # Regular user can cancel only their future bookings
        user_bookings_data = supabase.table("bookings").select("*") \
            .eq("user_id", user["user_id"]) \
            .neq("status", "cancelled") \
            .gte("booking_date", current_time.strftime("%Y-%m-%d %H:%M:%S")) \
            .order("booking_id", desc=False) \
            .execute()
        bookings = user_bookings_data.data if user_bookings_data.data else []
    
    if not bookings:
        bot.send_message(user["user_id"], "You have no future bookings to cancel. Press /start to restart.")
        return
    
    venues = get_all_venues()
    users = get_all_users()
    venue_dict = {str(v["venue_id"]): v["name"] for v in venues}
    users_dict = {str(u["user_id"]): u["name"] for u in users}
    response_lines = []
    for b in bookings:
        booking_start = dt.fromisoformat(b["booking_date"])
        dur = parse_duration(b["duration"])
        end_dt = booking_start + dur
        start_time = booking_start.strftime("%Y-%m-%d %H:%M")
        end_time = end_dt.strftime("%Y-%m-%d %H:%M")
        venue_name = venue_dict.get(str(b["venue_id"]), "Unknown Venue")
        user_name = users_dict.get(str(b["user_id"]), "Unknown User")
        
        # Add booking type display for MPSH
        booking_type_display = ""
        if venue_name.lower() == "mpsh":
            booking_type = b.get('booking_type', 'full')
            booking_type_display = f" [{booking_type.upper()}]"
        
        line = (
            f"📋 Booking ID: {b['booking_id']}\n"
            f"🏢 Venue: {venue_name}{booking_type_display}\n"
            f"👤 Name: {user_name}\n"
            f"📅 Start: {start_time}\n"
            f"⏰ End: {end_time}\n"
            f"📊 Status: {b['status']}\n"
            f"📝 Reason: {b.get('reason','')}\n"
            "----------------------"
        )
        response_lines.append(line)
    final_msg = "\n".join(response_lines)
    final_msg += "\n❓ Please enter the Booking ID to cancel:"
    bot.send_message(user["user_id"], final_msg)
    bot.register_next_step_handler(message, process_cancel)

def process_cancel(message):
    try:
        booking_id = int(message.text.strip())
        user_id = message.from_user.id
        user = get_user_info(user_id)
        is_admin = (user and user["role"].strip().lower() == "admin")
        if cancel_booking(booking_id, user_id, is_admin=is_admin):
            bot.send_message(message.from_user.id, f"✅ Booking {booking_id} cancelled successfully. Press /start to restart.")
        else:
            bot.send_message(message.from_user.id, "❌ Unable to cancel booking. Please check the Booking ID. Press /start to restart.")
    except ValueError:
        bot.send_message(message.from_user.id, "Invalid Booking ID. Press /start to restart.")

@bot.message_handler(commands=['view'])
def view_command(message):
    user = get_user_info(message.from_user.id)
    if not user:
        return
    
    # Get current time for filtering past bookings
    from config import TZ
    current_time = dt.now(TZ)
    
    user_role = user["role"].strip().lower()
    if user_role == "jcrc":
        # JCRC can view Dining Hall, Reading Room, MPSH bookings + their own bookings
        venue_ids = get_venue_ids_for(["Dining Hall", "Reading Room", "MPSH"])
        
        # Get confirmed bookings for JCRC venues (future only)
        jcrc_venue_bookings = supabase.table("bookings").select("*") \
            .in_("venue_id", venue_ids) \
            .eq("status", "confirmed") \
            .gte("booking_date", current_time.strftime("%Y-%m-%d %H:%M:%S")) \
            .order("booking_id", desc=False) \
            .execute()
        
        # Get all their personal bookings (future only)
        personal_bookings_data = supabase.table("bookings").select("*") \
            .eq("user_id", user["user_id"]) \
            .neq("status", "cancelled") \
            .gte("booking_date", current_time.strftime("%Y-%m-%d %H:%M:%S")) \
            .order("booking_id", desc=False) \
            .execute()
        personal_bookings = personal_bookings_data.data if personal_bookings_data.data else []
        
        # Combine and sort by booking_id
        all_bookings = (jcrc_venue_bookings.data if jcrc_venue_bookings.data else []) + personal_bookings
        booking_ids = set()
        bookings = []
        for b in all_bookings:
            if b["booking_id"] not in booking_ids:
                bookings.append(b)
                booking_ids.add(b["booking_id"])
        # Sort combined bookings by booking_id
        bookings = sorted(bookings, key=lambda x: x["booking_id"])
    elif user_role == "block head":
        # Block Head can view their block's lounge bookings + their own bookings
        user_block = user.get("block", "").strip()
        lounge_name = f"{user_block} Lounge"
        lounge_venue_ids = get_venue_ids_for([lounge_name])
        
        # Get confirmed bookings for their block's lounge (future only)
        lounge_bookings = supabase.table("bookings").select("*") \
            .in_("venue_id", lounge_venue_ids) \
            .eq("status", "confirmed") \
            .gte("booking_date", current_time.strftime("%Y-%m-%d %H:%M:%S")) \
            .order("booking_id", desc=False) \
            .execute()
        
        # Get all their personal bookings (future only)
        personal_bookings_data = supabase.table("bookings").select("*") \
            .eq("user_id", user["user_id"]) \
            .neq("status", "cancelled") \
            .gte("booking_date", current_time.strftime("%Y-%m-%d %H:%M:%S")) \
            .order("booking_id", desc=False) \
            .execute()
        personal_bookings = personal_bookings_data.data if personal_bookings_data.data else []
        
        # Combine and sort by booking_id
        all_bookings = (lounge_bookings.data if lounge_bookings.data else []) + personal_bookings
        booking_ids = set()
        bookings = []
        for b in all_bookings:
            if b["booking_id"] not in booking_ids:
                bookings.append(b)
                booking_ids.add(b["booking_id"])
        # Sort combined bookings by booking_id
        bookings = sorted(bookings, key=lambda x: x["booking_id"])
    else:
        is_admin = (user["role"].strip().lower() == "admin")
        if is_admin:
            # Admin sees all future bookings
            admin_bookings_data = supabase.table("bookings").select("*") \
                .neq("status", "cancelled") \
                .gte("booking_date", current_time.strftime("%Y-%m-%d %H:%M:%S")) \
                .order("booking_id", desc=False) \
                .execute()
            bookings = admin_bookings_data.data if admin_bookings_data.data else []
        else:
            # Regular user sees only their future bookings
            user_bookings_data = supabase.table("bookings").select("*") \
                .eq("user_id", user["user_id"]) \
                .neq("status", "cancelled") \
                .gte("booking_date", current_time.strftime("%Y-%m-%d %H:%M:%S")) \
                .order("booking_id", desc=False) \
                .execute()
            bookings = user_bookings_data.data if user_bookings_data.data else []
    
    if not bookings:
        bot.send_message(user["user_id"], "📭 No future bookings found.")
        return
    
    venues = get_all_venues()
    users = get_all_users()
    venue_dict = {str(v["venue_id"]): v["name"] for v in venues}
    users_dict = {str(u["user_id"]): u["name"] for u in users}
    response_lines = []
    for b in bookings:
        booking_start = dt.fromisoformat(b["booking_date"])
        dur = parse_duration(b["duration"])
        end_dt = booking_start + dur
        start_time = booking_start.strftime("%Y-%m-%d %H:%M")
        end_time = end_dt.strftime("%Y-%m-%d %H:%M")
        venue_name = venue_dict.get(str(b["venue_id"]), "Unknown Venue")
        user_name = users_dict.get(str(b["user_id"]), "Unknown User")
        
        # Add booking type display for MPSH
        booking_type_display = ""
        if venue_name.lower() == "mpsh":
            booking_type = b.get('booking_type', 'full')
            booking_type_display = f" [{booking_type.upper()}]"
        
        line = (
            f"📋 Booking ID: {b['booking_id']}\n"
            f"🏢 Venue: {venue_name}{booking_type_display}\n"
            f"👤 Name: {user_name}\n"
            f"📅 Start: {start_time}\n"
            f"⏰ End: {end_time}\n"
            f"📊 Status: {b['status']}\n"
            f"📝 Reason: {b.get('reason','')}\n"
            "----------------------"
        )
        response_lines.append(line)
    bot.send_message(user["user_id"], "\n".join(response_lines))