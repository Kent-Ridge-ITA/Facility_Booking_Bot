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
    is_admin = (user["role"].strip().lower() == "admin")
    bookings = get_user_bookings(user["user_id"], is_admin=is_admin)
    if not bookings:
        bot.send_message(user["user_id"], "You have no active bookings to cancel. Press /start to restart.")
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
        start_str = booking_start.strftime("%Y-%m-%d %H:%M")
        end_str   = end_dt.strftime("%Y-%m-%d %H:%M")
        venue_name = venue_dict.get(str(b["venue_id"]), "Unknown Venue")
        user_name  = users_dict.get(str(b["user_id"]), "Unknown User")
        line = (
            f"Booking ID: {b['booking_id']}\n"
            f"Venue: {venue_name}\n"
            f"Name: {user_name}\n"
            f"Start: {start_str}\n"
            f"End: {end_str}\n"
            f"Status: {b['status']}\n"
            f"Reason: {b.get('reason','')}\n"
            "----------------------"
        )
        response_lines.append(line)
    final_msg = "\n".join(response_lines)
    final_msg += "\nPlease enter the Booking ID to cancel:"
    bot.send_message(user["user_id"], final_msg)
    bot.register_next_step_handler(message, process_cancel)

def process_cancel(message):
    try:
        booking_id = int(message.text.strip())
        user_id = message.from_user.id
        user = get_user_info(user_id)
        is_admin = (user and user["role"].strip().lower() == "admin")
        if cancel_booking(booking_id, user_id, is_admin=is_admin):
            bot.send_message(message.from_user.id, f"Booking {booking_id} cancelled successfully. Press /start to restart.")
        else:
            bot.send_message(message.from_user.id, "Unable to cancel booking. Please check the Booking ID. Press /start to restart.")
    except ValueError:
        bot.send_message(message.from_user.id, "Invalid Booking ID. Press /start to restart.")

@bot.message_handler(commands=['view'])
def view_command(message):
    user = get_user_info(message.from_user.id)
    if not user:
        return
    user_role = user["role"].strip().lower()
    if user_role == "jcrc":
        venue_ids = get_venue_ids_for(["Dining Hall", "Reading Room", "MPSH"])
        data = supabase.table("bookings").select("*").in_("venue_id", venue_ids).eq("status", "confirmed").execute()
        bookings = data.data if data.data else []
    elif user_role == "block head":
        # Block Head can view their block's lounge bookings + their own bookings
        user_block = user.get("block", "").strip()
        lounge_name = f"{user_block} Lounge"
        lounge_venue_ids = get_venue_ids_for([lounge_name])
        
        # Get confirmed bookings for their block's lounge
        lounge_bookings = supabase.table("bookings").select("*") \
            .in_("venue_id", lounge_venue_ids) \
            .eq("status", "confirmed") \
            .execute()
        
        # Get all their personal bookings
        personal_bookings = get_user_bookings(user["user_id"], is_admin=False)
        
        # Combine and deduplicate
        all_bookings = (lounge_bookings.data if lounge_bookings.data else []) + personal_bookings
        booking_ids = set()
        bookings = []
        for b in all_bookings:
            if b["booking_id"] not in booking_ids:
                bookings.append(b)
                booking_ids.add(b["booking_id"])
    else:
        is_admin = (user["role"].strip().lower() == "admin")
        bookings = get_user_bookings(user["user_id"], is_admin=is_admin)
    if not bookings:
        bot.send_message(user["user_id"], "No active bookings found.")
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
        line = (
            f"Booking ID: {b['booking_id']}\n"
            f"Venue: {venue_name}\n"
            f"Name: {user_name}\n"
            f"Start: {start_time}\n"
            f"End: {end_time}\n"
            f"Status: {b['status']}\n"
            f"Reason: {b.get('reason','')}\n"
            "----------------------"
        )
        response_lines.append(line)
    bot.send_message(user["user_id"], "\n".join(response_lines))

