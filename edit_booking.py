from datetime import datetime as dt, timedelta
from telebot import types
from config import bot, supabase, TZ
from db_helpers import get_user_info, get_all_venues, parse_duration, get_venue_ids_for
from booking_utils import check_conflict, check_start_conflict
from calendar_helpers import add_event_to_calendar, remove_event_from_calendar

# Global dictionaries to track active edit sessions
active_edit_sessions = {}
edit_booking_message_ids = {}
edit_flow_data = {}

def can_user_edit_venue(user, venue_name):
    """Check if user can edit bookings for a specific venue (only venues they have instant booking for)"""
    user_role = user["role"].strip().lower()
    venue_name = venue_name.strip().lower()
    user_cca = user.get("cca", "").strip()
    
    # JCRC can edit Reading Room and Dining Hall (they have instant booking)
    if user_role == "jcrc" and venue_name in ["reading room", "dining hall"]:
        return True
    # Captains (all CCAs) and Chairman of Dance can edit MPSH (they have instant booking)
    elif venue_name == "mpsh":
        if user_role == "captain":
            return True
        elif user_role == "chairman" and user_cca == "Dance":
            return True
    # Only Chairman of Rockers or Inspire can edit Band Room (they have instant booking)
    elif venue_name == "band room":
        if user_role == "chairman" and user_cca in ["Rockers", "Inspire"]:
            return True
    # Block Head can edit their own block's lounge (they have instant booking for their own block)
    elif user_role == "block head":
        user_block = user.get("block", "").strip().lower()
        if "blk lounge" in venue_name:
            venue_block = venue_name.replace(" lounge", "")
            return user_block == venue_block
    
    return False

def is_booking_ongoing_or_future(booking_date_str, duration_str, current_time):
    """Check if a booking is ongoing or in the future"""
    booking_start = dt.fromisoformat(booking_date_str)
    if booking_start.tzinfo is None:
        booking_start = TZ.localize(booking_start)
    
    duration = parse_duration(duration_str)
    booking_end = booking_start + duration
    
    return current_time < booking_end

@bot.message_handler(commands=['edit'])
def edit_command(message):
    user = get_user_info(message.from_user.id)
    if not user:
        bot.send_message(message.from_user.id, "Please /start first to register.")
        return
    
    user_role = user["role"].strip().lower()
    
    # Check if user has edit privileges
    if user_role not in ["jcrc", "captain", "chairman", "block head"]:
        bot.send_message(user["user_id"], "You do not have permission to edit bookings. Press /start to restart.")
        return
    
    # Get current time for filtering past bookings
    current_time = dt.now(TZ)
    
    # Get user's confirmed bookings that they can edit
    user_bookings_data = supabase.table("bookings").select("*") \
        .eq("user_id", user["user_id"]) \
        .eq("status", "confirmed") \
        .order("booking_date", desc=False) \
        .execute()
    all_bookings = user_bookings_data.data if user_bookings_data.data else []
    
    # Filter to only ongoing/future bookings at venues they can edit
    venues = get_all_venues()
    venue_dict = {str(v["venue_id"]): v["name"] for v in venues}
    
    editable_bookings = []
    for booking in all_bookings:
        if is_booking_ongoing_or_future(booking["booking_date"], booking["duration"], current_time):
            venue_name = venue_dict.get(str(booking["venue_id"]), "")
            if can_user_edit_venue(user, venue_name):
                editable_bookings.append(booking)
    
    if not editable_bookings:
        bot.send_message(user["user_id"], f"No editable bookings found. Press /start to restart.")
        return
    
    # Create new edit session
    session_id = str(int(dt.now().timestamp()))
    active_edit_sessions[user["user_id"]] = session_id
    edit_booking_message_ids[user["user_id"]] = []
    
    # Send exit button keyboard
    exit_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    exit_markup.add(types.KeyboardButton("/exit_edit"))
    bot.send_message(user["user_id"], "Use /exit_edit to exit the editing process at any time.", reply_markup=exit_markup)
    
    # Send each editable booking with inline edit button
    for booking in editable_bookings:
        booking_start = dt.fromisoformat(booking["booking_date"])
        if booking_start.tzinfo is None:
            booking_start = TZ.localize(booking_start)
        
        dur = parse_duration(booking["duration"])
        end_dt = booking_start + dur
        start_time = booking_start.strftime("%Y-%m-%d %H:%M")
        end_time = end_dt.strftime("%Y-%m-%d %H:%M")
        venue_name = venue_dict.get(str(booking["venue_id"]), "Unknown Venue")
        
        # Add booking type display for MPSH
        booking_type_display = ""
        if venue_name.lower() == "mpsh":
            booking_type = booking.get('booking_type', 'full')
            booking_type_display = f" [{booking_type.upper()}]"
        
        msg = (
            f"📋 Booking ID: {booking['booking_id']}\n"
            f"🏢 Venue: {venue_name}{booking_type_display}\n"
            f"📅 Start: {start_time}\n"
            f"⏰ End: {end_time}\n"
            f"📝 Reason: {booking.get('reason', '')}\n"
        )
        
        # Create inline keyboard with edit button
        inline_markup = types.InlineKeyboardMarkup()
        inline_markup.add(
            types.InlineKeyboardButton("✏️ Edit", callback_data=f"edit_booking_{booking['booking_id']}_{session_id}")
        )
        
        sent_message = bot.send_message(user["user_id"], msg, reply_markup=inline_markup)
        edit_booking_message_ids[user["user_id"]].append(sent_message.message_id)

@bot.message_handler(commands=['exit_edit'])
def exit_edit_command(message):
    user = get_user_info(message.from_user.id)
    if not user:
        return
    
    # Delete all booking messages
    if user["user_id"] in edit_booking_message_ids:
        for message_id in edit_booking_message_ids[user["user_id"]]:
            try:
                bot.delete_message(user["user_id"], message_id)
            except Exception:
                pass
        edit_booking_message_ids.pop(user["user_id"], None)
    
    # Clear session data
    active_edit_sessions.pop(user["user_id"], None)
    edit_flow_data.pop(user["user_id"], None)
    
    # Send main menu
    from registration import send_main_menu
    bot.send_message(user["user_id"], "Exited editing process. All booking messages have been removed.")
    send_main_menu(user["user_id"])

@bot.callback_query_handler(func=lambda call: call.data.startswith("edit_booking_"))
def handle_edit_action(call):
    user = get_user_info(call.from_user.id)
    if not user:
        bot.answer_callback_query(call.id, "Access denied.")
        return
    
    # Parse callback data
    callback_parts = call.data.split("_")
    if len(callback_parts) < 4:
        bot.answer_callback_query(call.id, "Invalid callback data.")
        return
    
    booking_id = int(callback_parts[2])
    session_id = callback_parts[3]
    
    # Check if edit session is still active
    current_session = active_edit_sessions.get(user["user_id"])
    if current_session != session_id:
        bot.answer_callback_query(call.id, "This editing session has expired. Please start a new /edit process.")
        try:
            bot.edit_message_text("⚠️ Editing session expired. Please use /edit to start a new session.", 
                                 call.message.chat.id, call.message.message_id, reply_markup=None)
        except Exception:
            pass
        return
    
    # Get booking details
    res = supabase.table("bookings").select("*").eq("booking_id", booking_id).execute()
    if not res.data:
        bot.answer_callback_query(call.id, "Booking not found.")
        return
    
    booking = res.data[0]
    
    # Verify this is user's booking and it's confirmed
    if booking["user_id"] != user["user_id"] or booking["status"] != "confirmed":
        bot.answer_callback_query(call.id, "Cannot edit this booking.")
        return
    
    # Get venue info
    venue_data = supabase.table("venues").select("*").eq("venue_id", booking["venue_id"]).execute()
    if not venue_data.data:
        bot.answer_callback_query(call.id, "Venue not found.")
        return
    
    venue = venue_data.data[0]
    
    # Check if user can edit this venue
    if not can_user_edit_venue(user, venue["name"]):
        bot.answer_callback_query(call.id, "You cannot edit bookings for this venue.")
        return
    
    # Delete all other booking messages, keep only this one
    if user["user_id"] in edit_booking_message_ids:
        for message_id in edit_booking_message_ids[user["user_id"]]:
            if message_id != call.message.message_id:
                try:
                    bot.delete_message(user["user_id"], message_id)
                except Exception:
                    pass
        edit_booking_message_ids[user["user_id"]] = [call.message.message_id]
    
    # Store booking data for editing
    edit_flow_data[user["user_id"]] = {
        "booking": booking,
        "venue": venue,
        "step": "booking_type" if venue["name"].strip().lower() == "mpsh" else "start_time"
    }
    
    # Check if venue is MPSH to ask for booking type first
    if venue["name"].strip().lower() == "mpsh":
        current_booking_type = booking.get('booking_type', 'full')
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("Full", callback_data=f"edit_mpsh_full_{session_id}"),
            types.InlineKeyboardButton("Half", callback_data=f"edit_mpsh_half_{session_id}")
        )
        
        bot.edit_message_text(
            f"✏️ Editing Booking {booking_id}\n"
            f"🏢 Venue: {venue['name']}\n"
            f"Current booking type: {current_booking_type.upper()}\n\n"
            f"Select new MPSH booking type:",
            call.message.chat.id, call.message.message_id, reply_markup=markup
        )
    else:
        # For non-MPSH venues, go directly to start time
        current_start = dt.fromisoformat(booking["booking_date"])
        if current_start.tzinfo is None:
            current_start = TZ.localize(current_start)
        
        bot.edit_message_text(
            f"✏️ Editing Booking {booking_id}\n"
            f"🏢 Venue: {venue['name']}\n"
            f"Current start time: {current_start.strftime('%Y-%m-%d %H:%M')}\n\n"
            f"⏰ Enter new start time (HH:MM in 24-hr format):",
            call.message.chat.id, call.message.message_id, reply_markup=None
        )
        
        bot.register_next_step_handler(call.message, handle_edit_start_time)
    
    bot.answer_callback_query(call.id, "Starting edit process...")

@bot.callback_query_handler(func=lambda call: call.data.startswith("edit_mpsh_"))
def handle_edit_mpsh_type_selection(call):
    user_id = call.from_user.id
    if user_id not in edit_flow_data:
        bot.answer_callback_query(call.id, "Edit flow expired.")
        return
    
    # Parse callback data
    callback_parts = call.data.split("_")
    if len(callback_parts) < 4:
        bot.answer_callback_query(call.id, "Invalid callback data.")
        return
    
    booking_type = callback_parts[2]  # "full" or "half"
    session_id = callback_parts[3]
    
    # Check if edit session is still active
    current_session = active_edit_sessions.get(user_id)
    if current_session != session_id:
        bot.answer_callback_query(call.id, "This editing session has expired.")
        return
    
    flow_data = edit_flow_data[user_id]
    booking = flow_data["booking"]
    venue = flow_data["venue"]
    
    # Store the selected booking type
    flow_data["new_booking_type"] = booking_type
    flow_data["step"] = "start_time"
    
    # Show current start time and ask for new one
    current_start = dt.fromisoformat(booking["booking_date"])
    if current_start.tzinfo is None:
        current_start = TZ.localize(current_start)
    
    bot.edit_message_text(
        f"✏️ Editing Booking {booking['booking_id']}\n"
        f"🏢 Venue: {venue['name']} [{booking_type.upper()}]\n"
        f"Current start time: {current_start.strftime('%Y-%m-%d %H:%M')}\n\n"
        f"⏰ Enter new start time (HH:MM in 24-hr format):",
        call.message.chat.id, call.message.message_id, reply_markup=None
    )
    
    bot.register_next_step_handler(call.message, handle_edit_start_time)
    bot.answer_callback_query(call.id, f"MPSH {booking_type.title()} selected.")

def handle_edit_start_time(message):
    user_id = message.from_user.id
    
    # Check if user wants to exit
    if message.text.strip() == "/exit_edit":
        cleanup_edit_session(user_id)
        bot.send_message(user_id, "Exited editing process.")
        return
    
    if user_id not in edit_flow_data:
        bot.send_message(user_id, "Edit flow expired. Please try /edit again.")
        return
    
    flow_data = edit_flow_data[user_id]
    booking = flow_data["booking"]
    venue = flow_data["venue"]
    time_str = message.text.strip()
    
    try:
        proposed_start = dt.strptime(time_str, "%H:%M").time()
        if proposed_start.minute % 15 != 0:
            bot.send_message(user_id, "⚠️ Start time must be in 15-minute increments.")
            bot.register_next_step_handler(message, handle_edit_start_time)
            return
        
        # Use the same date as original booking
        original_start = dt.fromisoformat(booking["booking_date"])
        proposed_dt = dt.combine(original_start.date(), proposed_start)
        proposed_dt = TZ.localize(proposed_dt)
        
        # Safety check: prevent booking times in the past
        current_time = dt.now(TZ)
        if proposed_dt <= current_time:
            bot.send_message(user_id, "⚠️ Cannot set times in the past. Exiting edit process.")
            cleanup_edit_session(user_id)
            return
        
        # Get booking type (new one for MPSH, or existing for other venues)
        if venue["name"].strip().lower() == "mpsh":
            booking_type = flow_data.get("new_booking_type", booking.get("booking_type", "full"))
        else:
            booking_type = booking.get("booking_type", "full")
        
        # Check for conflicts with other bookings (exclude current booking)
        if check_start_conflict_excluding_booking(venue, proposed_dt, booking["booking_id"], booking_type):
            bot.send_message(user_id, "⚠️ The specified start time conflicts with an existing booking. Exiting edit process.")
            cleanup_edit_session(user_id)
            return
        
        flow_data["new_start_time"] = proposed_start
        flow_data["step"] = "duration"
        
        # Ask for new duration
        current_duration = booking["duration"]
        bot.send_message(user_id, f"⏱️ Current duration: {current_duration}\nEnter new duration (H:MM):")
        bot.register_next_step_handler(message, handle_edit_duration)
        
    except ValueError:
        bot.send_message(user_id, "❌ Invalid start time format. Please try again (HH:MM).")
        bot.register_next_step_handler(message, handle_edit_start_time)

def handle_edit_duration(message):
    user_id = message.from_user.id
    
    # Check if user wants to exit
    if message.text.strip() == "/exit_edit":
        cleanup_edit_session(user_id)
        bot.send_message(user_id, "Exited editing process.")
        return
    
    if user_id not in edit_flow_data:
        bot.send_message(user_id, "Edit flow expired. Please try /edit again.")
        return
    
    flow_data = edit_flow_data[user_id]
    booking = flow_data["booking"]
    venue = flow_data["venue"]
    duration_str = message.text.strip()
    
    try:
        parts = duration_str.split(":")
        if len(parts) != 2:
            raise ValueError("Invalid format")
        hours = int(parts[0])
        minutes = int(parts[1])
        total_minutes = hours * 60 + minutes
        if total_minutes <= 0 or total_minutes % 15 != 0:
            raise ValueError("Duration must be positive and in 15-minute increments")
        if total_minutes > 1440:
            raise ValueError("Duration cannot exceed 24 hours")
        
        # Create new booking datetime with timezone
        original_start = dt.fromisoformat(booking["booking_date"])
        new_start_dt = dt.combine(original_start.date(), flow_data["new_start_time"])
        new_start_dt = TZ.localize(new_start_dt)
        
        # Get booking type (new one for MPSH, or existing for other venues)
        if venue["name"].strip().lower() == "mpsh":
            booking_type = flow_data.get("new_booking_type", booking.get("booking_type", "full"))
        else:
            booking_type = booking.get("booking_type", "full")
        
        # Check for conflicts with the new duration (exclude current booking)
        if check_conflict_excluding_booking(venue, new_start_dt, duration_str, booking["booking_id"], booking_type):
            bot.send_message(user_id, "⚠️ This time slot overlaps with an existing booking. Exiting edit process.")
            cleanup_edit_session(user_id)
            return
        
        # Remove old calendar event if exists
        if booking.get("calendar_event_id"):
            remove_event_from_calendar(booking["calendar_event_id"])
        
        # Prepare update data
        update_data = {
            "booking_date": new_start_dt.replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S"),
            "duration": duration_str,
            "calendar_event_id": None  # Will be set below
        }
        
        # Add booking type for MPSH
        if venue["name"].strip().lower() == "mpsh":
            update_data["booking_type"] = booking_type
        
        # Update booking in database
        supabase.table("bookings").update(update_data).eq("booking_id", booking["booking_id"]).execute()
        
        # Get updated booking data
        updated_res = supabase.table("bookings").select("*").eq("booking_id", booking["booking_id"]).execute()
        updated_booking = updated_res.data[0] if updated_res.data else None
        
        # Add new calendar event
        if updated_booking:
            event_id = add_event_to_calendar(updated_booking, venue)
            supabase.table("bookings").update({"calendar_event_id": event_id}).eq("booking_id", booking["booking_id"]).execute()
        
        # Success message
        new_end_dt = new_start_dt + parse_duration(duration_str)
        start_str = new_start_dt.strftime("%Y-%m-%d %H:%M")
        end_str = new_end_dt.strftime("%Y-%m-%d %H:%M")
        
        # Add booking type display for MPSH
        booking_type_display = ""
        if venue["name"].lower() == "mpsh":
            booking_type_display = f" [{booking_type.upper()}]"
        
        success_msg = (
            f"✅ Booking {booking['booking_id']} updated successfully!\n\n"
            f"🏢 Venue: {venue['name']}{booking_type_display}\n"
            f"📅 New Start: {start_str}\n"
            f"⏰ New End: {end_str}\n"
            f"📝 Reason: {booking.get('reason', '')}\n\n"
            f"🔄 Press /start to restart the process."
        )
        
        bot.send_message(user_id, success_msg)
        cleanup_edit_session(user_id)
        
    except ValueError as ve:
        bot.send_message(user_id, f"❌ Invalid duration format: {ve}. Please try again.")
        bot.register_next_step_handler(message, handle_edit_duration)

def cleanup_edit_session(user_id):
    """Clean up edit session data and return to main menu"""
    # Delete booking message
    if user_id in edit_booking_message_ids:
        for message_id in edit_booking_message_ids[user_id]:
            try:
                bot.delete_message(user_id, message_id)
            except Exception:
                pass
        edit_booking_message_ids.pop(user_id, None)
    
    # Clear session data
    active_edit_sessions.pop(user_id, None)
    edit_flow_data.pop(user_id, None)
    
    # Send main menu
    from registration import send_main_menu
    send_main_menu(user_id)

def check_start_conflict_excluding_booking(venue, proposed_start, exclude_booking_id, booking_type="full"):
    """Check for start time conflicts, excluding a specific booking"""
    response = supabase.table("bookings").select("*") \
        .eq("venue_id", venue["venue_id"]) \
        .eq("status", "confirmed") \
        .neq("booking_id", exclude_booking_id) \
        .execute()
    bookings = response.data if response.data else []
    
    venue_name = venue["name"].strip().lower()
    
    for b in bookings:
        confirmed_start = dt.fromisoformat(b["booking_date"])
        if confirmed_start.tzinfo is None:
            confirmed_start = TZ.localize(confirmed_start)
        
        try:
            confirmed_duration = parse_duration(b["duration"])
        except Exception:
            confirmed_duration = timedelta(0)
        confirmed_end = confirmed_start + confirmed_duration
        
        if proposed_start.tzinfo is None:
            proposed_start = TZ.localize(proposed_start)
        
        if confirmed_start <= proposed_start < confirmed_end:
            # For MPSH, check booking type conflicts
            if venue_name == "mpsh":
                existing_booking_type = b.get("booking_type", "full")
                if booking_type == "full" or existing_booking_type == "full":
                    return True
                # Both are half bookings - no conflict
                else:
                    continue
            else:
                return True
    return False

def check_conflict_excluding_booking(venue, new_booking_start, duration_text, exclude_booking_id, booking_type="full"):
    """Check for booking conflicts, excluding a specific booking"""
    new_duration = parse_duration(duration_text)
    
    if new_booking_start.tzinfo is None:
        new_booking_start = TZ.localize(new_booking_start)
    
    new_booking_end = new_booking_start + new_duration
    
    response = supabase.table("bookings").select("*") \
        .eq("venue_id", venue["venue_id"]) \
        .eq("status", "confirmed") \
        .neq("booking_id", exclude_booking_id) \
        .execute()
    bookings = response.data if response.data else []
    
    venue_name = venue["name"].strip().lower()
    
    for b in bookings:
        confirmed_start = dt.fromisoformat(b["booking_date"])
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
                if booking_type == "full" or existing_booking_type == "full":
                    return True
                # Both are half bookings - no conflict
                else:
                    continue
            else:
                return True
    return False