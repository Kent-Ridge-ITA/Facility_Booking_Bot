from datetime import datetime as dt
from telebot import types
from config import bot, supabase
from db_helpers import get_user_info, get_all_venues, get_all_users, parse_duration, get_user_bookings, get_venue_ids_for
from booking_utils import cancel_booking

# Add global dictionaries to track active cancel sessions
active_cancel_sessions = {}
cancel_booking_message_ids = {}

def is_booking_ongoing_or_future(booking_date_str, duration_str, current_time):
    """Check if a booking is ongoing or in the future"""
    booking_start = dt.fromisoformat(booking_date_str)
    # Make booking_start timezone-aware if needed
    if booking_start.tzinfo is None:
        from config import TZ
        booking_start = TZ.localize(booking_start)
    
    duration = parse_duration(duration_str)
    booking_end = booking_start + duration
    
    # Return True if current time is before the booking ends
    return current_time < booking_end

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
        # Admin can cancel all ongoing and future bookings (exclude rejected and cancelled)
        admin_bookings_data = supabase.table("bookings").select("*") \
            .not_.in_("status", ["cancelled", "rejected"]) \
            .order("booking_date", desc=False) \
            .execute()
        all_bookings = admin_bookings_data.data if admin_bookings_data.data else []
        # Filter to only ongoing and future bookings
        bookings = [b for b in all_bookings if is_booking_ongoing_or_future(b["booking_date"], b["duration"], current_time)]
    else:
        # Regular user can cancel only their ongoing and future bookings (exclude rejected and cancelled)
        user_bookings_data = supabase.table("bookings").select("*") \
            .eq("user_id", user["user_id"]) \
            .not_.in_("status", ["cancelled", "rejected"]) \
            .order("booking_date", desc=False) \
            .execute()
        all_bookings = user_bookings_data.data if user_bookings_data.data else []
        # Filter to only ongoing and future bookings
        bookings = [b for b in all_bookings if is_booking_ongoing_or_future(b["booking_date"], b["duration"], current_time)]
    
    if not bookings:
        bot.send_message(user["user_id"], "You have no ongoing or future bookings to cancel. Press /start to restart.")
        return
    
    # Create new cancel session - use integer timestamp to avoid precision issues
    session_id = str(int(dt.now().timestamp()))
    active_cancel_sessions[user["user_id"]] = session_id
    # Initialize message IDs tracking for this session
    cancel_booking_message_ids[user["user_id"]] = []
    
    venues = get_all_venues()
    users = get_all_users()
    venue_dict = {str(v["venue_id"]): v["name"] for v in venues}
    users_dict = {str(u["user_id"]): u["name"] for u in users}
    
    # Send exit button keyboard
    exit_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    exit_markup.add(types.KeyboardButton("/exit_cancel"))
    bot.send_message(user["user_id"], "Use /exit_cancel to exit the cancellation process at any time.", reply_markup=exit_markup)
    
    # Send each booking with inline cancel button (include session_id in callback data)
    for b in bookings:
        booking_start = dt.fromisoformat(b["booking_date"])
        # Make booking_start timezone-aware if needed
        if booking_start.tzinfo is None:
            from config import TZ
            booking_start = TZ.localize(booking_start)
        
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
        
        msg = (
            f"📋 Booking ID: {b['booking_id']}\n"
            f"🏢 Venue: {venue_name}{booking_type_display}\n"
            f"👤 Name: {user_name}\n"
            f"📅 Start: {start_time}\n"
            f"⏰ End: {end_time}\n"
            f"📊 Status: {b['status']}\n"
            f"📝 Reason: {b.get('reason','')}\n"
        )
        
        # Create inline keyboard with cancel button (include session_id)
        inline_markup = types.InlineKeyboardMarkup()
        inline_markup.add(
            types.InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_booking_{b['booking_id']}_{session_id}")
        )
        
        sent_message = bot.send_message(user["user_id"], msg, reply_markup=inline_markup)
        # Track this booking message ID
        cancel_booking_message_ids[user["user_id"]].append(sent_message.message_id)

@bot.message_handler(commands=['exit_cancel'])
def exit_cancel_command(message):
    user = get_user_info(message.from_user.id)
    if not user:
        return
    
    # Delete all booking messages with inline buttons
    if user["user_id"] in cancel_booking_message_ids:
        for message_id in cancel_booking_message_ids[user["user_id"]]:
            try:
                bot.delete_message(user["user_id"], message_id)
            except Exception as e:
                # If message deletion fails (already deleted/modified), just continue
                pass
        # Clear the message IDs for this user
        cancel_booking_message_ids.pop(user["user_id"], None)
    
    # Mark the cancel session as inactive
    if user["user_id"] in active_cancel_sessions:
        active_cancel_sessions.pop(user["user_id"], None)
    
    # Remove the exit keyboard and send main menu
    from registration import send_main_menu
    bot.send_message(user["user_id"], "Exited cancellation process. All booking messages have been removed.")
    send_main_menu(user["user_id"])

@bot.callback_query_handler(func=lambda call: call.data.startswith("cancel_booking_"))
def handle_cancel_action(call):
    user = get_user_info(call.from_user.id)
    if not user:
        bot.answer_callback_query(call.id, "Access denied.")
        return
    
    # Parse callback data to extract session_id
    callback_parts = call.data.split("_")
    if len(callback_parts) < 4:
        bot.answer_callback_query(call.id, "Invalid callback data.")
        return
    
    booking_id = int(callback_parts[2])
    session_id = callback_parts[3]
    
    # Check if the cancel session is still active
    current_session = active_cancel_sessions.get(user["user_id"])
    if current_session != session_id:
        bot.answer_callback_query(call.id, "This cancellation session has expired. Please start a new /cancel process.")
        try:
            bot.edit_message_text("⚠️ Cancellation session expired. Please use /cancel to start a new session.", 
                                 call.message.chat.id, call.message.message_id, reply_markup=None)
        except Exception:
            # If message edit fails (already modified), just ignore
            pass
        return
    
    # Get the booking details
    res = supabase.table("bookings").select("*").eq("booking_id", booking_id).execute()
    if not res.data:
        bot.answer_callback_query(call.id, "Booking not found.")
        try:
            bot.edit_message_text("❌ Booking not found.", call.message.chat.id, call.message.message_id, reply_markup=None)
        except Exception:
            pass
        return
    
    booking = res.data[0]
    
    # Check if booking can be cancelled
    if booking["status"] in ["cancelled", "rejected"]:
        bot.answer_callback_query(call.id, "Booking cannot be cancelled.")
        try:
            bot.edit_message_text("⚠️ Booking cannot be cancelled.", call.message.chat.id, call.message.message_id, reply_markup=None)
        except Exception:
            pass
        return
    
    # Check permission - regular users can only cancel their own bookings
    is_admin = user["role"].strip().lower() == "admin"
    if not is_admin and booking["user_id"] != user["user_id"]:
        bot.answer_callback_query(call.id, "You can only cancel your own bookings.")
        return
    
    # Remove this message ID from tracking since it will become a confirmation message
    if user["user_id"] in cancel_booking_message_ids and call.message.message_id in cancel_booking_message_ids[user["user_id"]]:
        cancel_booking_message_ids[user["user_id"]].remove(call.message.message_id)
    
    # Cancel the booking
    if cancel_booking(booking_id, user["user_id"], is_admin=is_admin):
        bot.answer_callback_query(call.id, "Booking cancelled!")
        try:
            bot.edit_message_text(f"✅ Booking {booking_id} has been cancelled.", 
                                 call.message.chat.id, call.message.message_id, reply_markup=None)
        except Exception:
            pass
    else:
        bot.answer_callback_query(call.id, "Failed to cancel booking.")
        try:
            bot.edit_message_text(f"❌ Failed to cancel booking {booking_id}.", 
                                 call.message.chat.id, call.message.message_id, reply_markup=None)
        except Exception:
            pass

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
        
        # Get confirmed bookings for JCRC venues
        jcrc_venue_bookings = supabase.table("bookings").select("*") \
            .in_("venue_id", venue_ids) \
            .eq("status", "confirmed") \
            .order("booking_date", desc=False) \
            .execute()
        
        # Get all their personal bookings (exclude rejected and cancelled)
        personal_bookings_data = supabase.table("bookings").select("*") \
            .eq("user_id", user["user_id"]) \
            .not_.in_("status", ["cancelled", "rejected"]) \
            .order("booking_date", desc=False) \
            .execute()
        personal_bookings = personal_bookings_data.data if personal_bookings_data.data else []
        
        # Combine and filter for ongoing/future bookings
        all_bookings = (jcrc_venue_bookings.data if jcrc_venue_bookings.data else []) + personal_bookings
        booking_ids = set()
        combined_bookings = []
        for b in all_bookings:
            if b["booking_id"] not in booking_ids:
                combined_bookings.append(b)
                booking_ids.add(b["booking_id"])
        # Filter to only ongoing and future bookings
        bookings = [b for b in combined_bookings if is_booking_ongoing_or_future(b["booking_date"], b["duration"], current_time)]
        # Sort by booking_date (time start ascending)
        bookings = sorted(bookings, key=lambda x: x["booking_date"])
    elif user_role == "block head":
        # Block Head can view their block's lounge bookings + their own bookings
        user_block = user.get("block", "").strip()
        lounge_name = f"{user_block} Lounge"
        lounge_venue_ids = get_venue_ids_for([lounge_name])
        
        # Get confirmed bookings for their block's lounge
        lounge_bookings = supabase.table("bookings").select("*") \
            .in_("venue_id", lounge_venue_ids) \
            .eq("status", "confirmed") \
            .order("booking_date", desc=False) \
            .execute()
        
        # Get all their personal bookings (exclude rejected and cancelled)
        personal_bookings_data = supabase.table("bookings").select("*") \
            .eq("user_id", user["user_id"]) \
            .not_.in_("status", ["cancelled", "rejected"]) \
            .order("booking_date", desc=False) \
            .execute()
        personal_bookings = personal_bookings_data.data if personal_bookings_data.data else []
        
        # Combine and filter for ongoing/future bookings
        all_bookings = (lounge_bookings.data if lounge_bookings.data else []) + personal_bookings
        booking_ids = set()
        combined_bookings = []
        for b in all_bookings:
            if b["booking_id"] not in booking_ids:
                combined_bookings.append(b)
                booking_ids.add(b["booking_id"])
        # Filter to only ongoing and future bookings
        bookings = [b for b in combined_bookings if is_booking_ongoing_or_future(b["booking_date"], b["duration"], current_time)]
        # Sort by booking_date (time start ascending)
        bookings = sorted(bookings, key=lambda x: x["booking_date"])
    else:
        is_admin = (user["role"].strip().lower() == "admin")
        if is_admin:
            # Admin sees all ongoing and future bookings (exclude rejected and cancelled)
            admin_bookings_data = supabase.table("bookings").select("*") \
                .not_.in_("status", ["cancelled", "rejected"]) \
                .order("booking_date", desc=False) \
                .execute()
            all_bookings = admin_bookings_data.data if admin_bookings_data.data else []
            # Filter to only ongoing and future bookings
            bookings = [b for b in all_bookings if is_booking_ongoing_or_future(b["booking_date"], b["duration"], current_time)]
        else:
            # Regular user sees only their ongoing and future bookings (exclude rejected and cancelled)
            user_bookings_data = supabase.table("bookings").select("*") \
                .eq("user_id", user["user_id"]) \
                .not_.in_("status", ["cancelled", "rejected"]) \
                .order("booking_date", desc=False) \
                .execute()
            all_bookings = user_bookings_data.data if user_bookings_data.data else []
            # Filter to only ongoing and future bookings
            bookings = [b for b in all_bookings if is_booking_ongoing_or_future(b["booking_date"], b["duration"], current_time)]
    
    if not bookings:
        bot.send_message(user["user_id"], "📭 No ongoing or future bookings found.")
        return
    
    venues = get_all_venues()
    users = get_all_users()
    venue_dict = {str(v["venue_id"]): v["name"] for v in venues}
    users_dict = {str(u["user_id"]): u["name"] for u in users}
    response_lines = []
    for b in bookings:
        booking_start = dt.fromisoformat(b["booking_date"])
        if booking_start.tzinfo is None:
            from config import TZ
            booking_start = TZ.localize(booking_start)
        
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