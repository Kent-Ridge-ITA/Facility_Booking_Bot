from datetime import datetime as dt
from telebot import types
from config import bot, supabase, TZ
from db_helpers import get_user_info, get_all_venues, get_all_users, parse_duration
from notifications import notify_approval, notify_gc

# Add a global dictionary to track active approval sessions
active_approval_sessions = {}
# Add a dictionary to track booking message IDs for each user session
booking_message_ids = {}
# Add a dictionary to map booking IDs to message IDs for each user
booking_to_message_map = {}

def check_booking_overlap(booking1, booking2):
    """Check if two bookings overlap in time"""
    start1 = dt.fromisoformat(booking1["booking_date"])
    start2 = dt.fromisoformat(booking2["booking_date"])
    
    dur1 = parse_duration(booking1["duration"])
    dur2 = parse_duration(booking2["duration"])
    
    end1 = start1 + dur1
    end2 = start2 + dur2
    
    # Check for time overlap
    return start1 < end2 and end1 > start2

def find_overlapping_bookings(pending_bookings):
    """Find groups of overlapping bookings"""
    overlap_groups = {}
    
    for i, booking in enumerate(pending_bookings):
        booking_id = booking["booking_id"]
        venue_id = booking["venue_id"]
        venue_name = booking.get("venue_name", "").lower()
        booking_type = booking.get("booking_type", "full")
        
        overlapping_ids = set()
        
        for j, other_booking in enumerate(pending_bookings):
            if i != j and other_booking["venue_id"] == venue_id:
                other_booking_type = other_booking.get("booking_type", "full")
                
                # Check if bookings overlap in time
                if check_booking_overlap(booking, other_booking):
                    # For MPSH, check booking type conflicts
                    if venue_name == "mpsh":
                        # Full booking conflicts with any other booking
                        # Half booking conflicts with full booking
                        # Half booking can coexist with another half booking
                        if booking_type == "full" or other_booking_type == "full":
                            overlapping_ids.add(other_booking["booking_id"])
                        # Both are half bookings - no conflict
                    else:
                        # For other venues, any time overlap is a conflict
                        overlapping_ids.add(other_booking["booking_id"])
        
        if overlapping_ids:
            overlap_groups[booking_id] = overlapping_ids
    
    return overlap_groups

def reject_overlapping_bookings(approved_booking_id, overlap_groups):
    """Reject all bookings that overlap with the approved booking"""
    if approved_booking_id not in overlap_groups:
        return []
    
    overlapping_ids = overlap_groups[approved_booking_id]
    rejected_bookings = []
    
    for booking_id in overlapping_ids:
        # Update booking status to rejected
        supabase.table("bookings").update({"status": "rejected"}).eq("booking_id", booking_id).execute()
        
        # Get booking details for notification
        booking_res = supabase.table("bookings").select("*").eq("booking_id", booking_id).execute()
        if booking_res.data:
            booking = booking_res.data[0]
            rejected_bookings.append(booking)
            
            # Notify user of rejection
            try:
                user_info = get_user_info(booking["user_id"])
                user_name = user_info.get("name", "Unknown User") if user_info else "Unknown User"
                
                venue_data = supabase.table("venues").select("*").eq("venue_id", booking["venue_id"]).execute()
                venue = venue_data.data[0] if venue_data.data else {}
                
                booking_start = dt.fromisoformat(booking["booking_date"])
                dur = parse_duration(booking["duration"])
                end_dt = booking_start + dur
                start_str = booking_start.strftime("%Y-%m-%d %H:%M")
                end_str = end_dt.strftime("%Y-%m-%d %H:%M")
                
                rejection_msg = (
                    f"Your booking has been automatically rejected due to a conflicting approved booking.\n\n"
                    f"📋 Booking ID: {booking_id}\n"
                    f"🏢 Venue: {venue.get('name', 'Unknown Venue')}\n"
                    f"📅 Start: {start_str}\n"
                    f"⏰ End: {end_str}\n"
                    f"📝 Reason: {booking.get('reason', 'No reason provided')}\n"
                )
                
                bot.send_message(booking["user_id"], rejection_msg)
            except Exception as e:
                print(f"Failed to notify user of automatic rejection: {e}")
    
    return rejected_bookings

@bot.message_handler(commands=['approve'])
def approve_command(message):
    user = get_user_info(message.from_user.id)
    if not user:
        return
    
    user_role = user["role"].strip().lower()
    user_cca = user.get("cca", "").strip().lower()
    
    if user_role == "jcrc" and user_cca == "welfare d":
        # JCRC Welfare D can approve Reading Room and Dining Hall
        venue_ids = get_venue_ids_for(["Reading Room", "Dining Hall"])
    elif user_role == "block head":
        # Block Head can approve their own block's lounge
        user_block = user.get("block", "").strip()
        lounge_name = f"{user_block} Lounge"
        venue_ids = get_venue_ids_for([lounge_name])
    else:
        if user_role == "jcrc" and user_cca != "welfare d":
            bot.send_message(user["user_id"], "You do not have permission to approve bookings. Only JCRC (Welfare D) can approve Reading Room and Dining Hall bookings. Press /start to restart.")
        else:
            bot.send_message(user["user_id"], "You do not have permission to approve bookings. Press /start to restart.")
        return
    
    # Get current time to filter out past bookings
    current_time = dt.now(TZ)
    
    response = supabase.table("bookings").select("*") \
        .eq("status", "pending approval") \
        .in_("venue_id", venue_ids) \
        .gte("booking_date", current_time.strftime("%Y-%m-%d %H:%M:%S")) \
        .order("booking_date", desc=False) \
        .execute()
    pending = response.data if response.data else []
    
    if not pending:
        if user_role == "jcrc":
            approval_type = "Reading Room/Dining Hall"
        else:
            approval_type = f"{user.get('block', 'your block')} Lounge"
        bot.send_message(user["user_id"], f"No pending {approval_type} bookings for approval. Press /start to restart.")
        return
    
    # Create new approval session - use integer timestamp to avoid precision issues
    session_id = str(int(dt.now(TZ).timestamp()))
    active_approval_sessions[user["user_id"]] = session_id
    # Initialize message IDs tracking for this session
    booking_message_ids[user["user_id"]] = []
    booking_to_message_map[user["user_id"]] = {}
    
    venues = get_all_venues()
    users = get_all_users()
    venue_dict = {str(v["venue_id"]): v["name"] for v in venues}
    users_dict = {str(u["user_id"]): u["name"] for u in users}
    
    # Add venue names to bookings for overlap detection
    for booking in pending:
        venue_name = venue_dict.get(str(booking["venue_id"]), "Unknown Venue")
        booking["venue_name"] = venue_name
    
    # Find overlapping bookings
    overlap_groups = find_overlapping_bookings(pending)
    
    # Send exit button keyboard
    exit_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    exit_markup.add(types.KeyboardButton("/exit_approve"))
    bot.send_message(user["user_id"], "Use /exit_approve to exit the approval process at any time.", reply_markup=exit_markup)
    
    # Send overlap warning if any conflicts exist
    if overlap_groups:
        warning_msg = "⚠️ WARNING: Some bookings have overlapping times. Approving one will automatically reject the conflicting ones.\n\n"
        bot.send_message(user["user_id"], warning_msg)
    
    # Send each booking with inline approve/reject buttons (include session_id in callback data)
    for b in pending:
        booking_start = dt.fromisoformat(b["booking_date"])
        dur = parse_duration(b["duration"])
        end_dt = booking_start + dur
        start_str = booking_start.strftime("%Y-%m-%d %H:%M")
        end_str = end_dt.strftime("%Y-%m-%d %H:%M")
        venue_name = venue_dict.get(str(b["venue_id"]), "Unknown Venue")
        user_name = users_dict.get(str(b["user_id"]), "Unknown User")
        
        # Add booking type display for MPSH
        booking_type_display = ""
        if venue_name.lower() == "mpsh":
            booking_type = b.get('booking_type', 'full')
            booking_type_display = f" [{booking_type.upper()}]"
        
        # Add overlap indicator
        overlap_indicator = ""
        if b["booking_id"] in overlap_groups:
            overlapping_count = len(overlap_groups[b["booking_id"]])
            overlap_indicator = f"⚠️ CONFLICTS WITH {overlapping_count} OTHER BOOKING(S)\n"
        
        msg = (
            f"{overlap_indicator}"
            f"📋 Booking ID: {b['booking_id']}\n"
            f"🏢 Venue: {venue_name}{booking_type_display}\n"
            f"👤 Name: {user_name}\n"
            f"📅 Start: {start_str}\n"
            f"⏰ End: {end_str}\n"
            f"📝 Reason: {b.get('reason', 'No reason provided')}\n"
        )
        
        # Create inline keyboard with approve/reject buttons (include session_id)
        inline_markup = types.InlineKeyboardMarkup()
        inline_markup.add(
            types.InlineKeyboardButton("✅ Approve", callback_data=f"approve_{b['booking_id']}_{session_id}"),
            types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_{b['booking_id']}_{session_id}")
        )
        
        sent_message = bot.send_message(user["user_id"], msg, reply_markup=inline_markup)
        # Track this booking message ID
        booking_message_ids[user["user_id"]].append(sent_message.message_id)
        # Map booking ID to message ID
        booking_to_message_map[user["user_id"]][b["booking_id"]] = sent_message.message_id

@bot.message_handler(commands=['exit_approve'])
def exit_approve_command(message):
    user = get_user_info(message.from_user.id)
    if not user:
        return
    
    # Delete all booking messages with inline buttons
    if user["user_id"] in booking_message_ids:
        for message_id in booking_message_ids[user["user_id"]]:
            try:
                bot.delete_message(user["user_id"], message_id)
            except Exception as e:
                # If message deletion fails (already deleted/modified), just continue
                pass
        # Clear the message IDs for this user
        booking_message_ids.pop(user["user_id"], None)
        booking_to_message_map.pop(user["user_id"], None)
    
    # Mark the approval session as inactive
    if user["user_id"] in active_approval_sessions:
        active_approval_sessions.pop(user["user_id"], None)
    
    # Remove the exit keyboard and send main menu
    from registration import send_main_menu
    bot.send_message(user["user_id"], "Exited approval process. All booking messages have been removed.")
    send_main_menu(user["user_id"])

@bot.callback_query_handler(func=lambda call: call.data.startswith("approve_") or call.data.startswith("reject_"))
def handle_approval_action(call):
    user = get_user_info(call.from_user.id)
    if not user:
        bot.answer_callback_query(call.id, "Access denied.")
        return
    
    user_role = user["role"].strip().lower()
    user_cca = user.get("cca", "").strip().lower()
    
    # Check permission based on role and CCA
    if not ((user_role == "jcrc" and user_cca == "welfare d") or user_role == "block head"):
        bot.answer_callback_query(call.id, "You do not have permission to approve bookings.")
        return
    
    # Parse callback data to extract session_id
    callback_parts = call.data.split("_")
    if len(callback_parts) < 3:
        bot.answer_callback_query(call.id, "Invalid callback data.")
        return
    
    action = callback_parts[0]
    booking_id = int(callback_parts[1])
    session_id = callback_parts[2]
    
    # Check if the approval session is still active
    current_session = active_approval_sessions.get(user["user_id"])
    if current_session != session_id:
        bot.answer_callback_query(call.id, "This approval session has expired. Please start a new /approve process.")
        try:
            bot.edit_message_text("⚠️ Approval session expired. Please use /approve to start a new session.", 
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
    
    # Check if booking is still pending
    if booking["status"] != "pending approval":
        bot.answer_callback_query(call.id, "Booking is no longer pending approval.")
        try:
            bot.edit_message_text("⚠️ Booking is no longer pending approval.", call.message.chat.id, call.message.message_id, reply_markup=None)
        except Exception:
            pass
        return
    
    # Verify user has permission for this specific booking
    venue_data = supabase.table("venues").select("*").eq("venue_id", booking["venue_id"]).execute()
    if not venue_data.data:
        bot.answer_callback_query(call.id, "Venue not found.")
        return
    
    venue = venue_data.data[0]
    venue_name = venue["name"].strip().lower()
    
    # Check permission based on user role and venue
    has_permission = False
    if user_role == "jcrc" and user_cca == "welfare d" and venue_name in ["reading room", "dining hall"]:
        has_permission = True
    elif user_role == "block head":
        user_block = user.get("block", "").strip()
        if "blk lounge" in venue_name:
            venue_block = venue_name.replace(" lounge", "")
            if user_block.lower() == venue_block:
                has_permission = True
    
    if not has_permission:
        bot.answer_callback_query(call.id, "You don't have permission for this venue.")
        return
    
    # Remove this message ID from tracking since it will become a confirmation message
    if user["user_id"] in booking_message_ids and call.message.message_id in booking_message_ids[user["user_id"]]:
        booking_message_ids[user["user_id"]].remove(call.message.message_id)
    
    if action == "approve":
        # Get all pending bookings for overlap detection
        if user_role == "jcrc" and user_cca == "welfare d":
            venue_ids = get_venue_ids_for(["Reading Room", "Dining Hall"])
        else:  # block head
            user_block = user.get("block", "").strip()
            lounge_name = f"{user_block} Lounge"
            venue_ids = get_venue_ids_for([lounge_name])
        
        current_time = dt.now(TZ)
        
        pending_response = supabase.table("bookings").select("*") \
            .eq("status", "pending approval") \
            .in_("venue_id", venue_ids) \
            .gte("booking_date", current_time.strftime("%Y-%m-%d %H:%M:%S")) \
            .execute()
        all_pending = pending_response.data if pending_response.data else []
        
        # Add venue names for overlap detection
        venues = get_all_venues()
        venue_dict = {str(v["venue_id"]): v["name"] for v in venues}
        users = get_all_users()
        users_dict = {str(u["user_id"]): u["name"] for u in users}
        
        for b in all_pending:
            b["venue_name"] = venue_dict.get(str(b["venue_id"]), "Unknown Venue")
        
        # Find overlapping bookings BEFORE any changes
        overlap_groups = find_overlapping_bookings(all_pending)
        
        # Get list of booking IDs that will be rejected BEFORE approving
        rejected_booking_ids = overlap_groups.get(booking_id, set())
        
        # Remove booking messages for bookings that will be automatically rejected
        if user["user_id"] in booking_to_message_map and rejected_booking_ids:
            for rejected_id in rejected_booking_ids:
                if rejected_id in booking_to_message_map[user["user_id"]]:
                    message_id = booking_to_message_map[user["user_id"]][rejected_id]
                    try:
                        bot.delete_message(user["user_id"], message_id)
                    except Exception:
                        # Message might have already been deleted or modified
                        pass
                    # Remove from both tracking dictionaries
                    if message_id in booking_message_ids[user["user_id"]]:
                        booking_message_ids[user["user_id"]].remove(message_id)
                    del booking_to_message_map[user["user_id"]][rejected_id]
        
        # Approve the booking
        supabase.table("bookings").update({"status": "confirmed"}).eq("booking_id", booking_id).execute()
        
        # Reject overlapping bookings
        rejected_bookings = reject_overlapping_bookings(booking_id, overlap_groups)
        
        # After rejecting overlapping bookings, update remaining booking messages
        # to reflect the new conflict status
        if rejected_booking_ids:
            # Get updated list of pending bookings (after rejections)
            updated_pending_response = supabase.table("bookings").select("*") \
                .eq("status", "pending approval") \
                .in_("venue_id", venue_ids) \
                .gte("booking_date", current_time.strftime("%Y-%m-%d %H:%M:%S")) \
                .execute()
            updated_pending = updated_pending_response.data if updated_pending_response.data else []
            
            # Add venue names
            for b in updated_pending:
                b["venue_name"] = venue_dict.get(str(b["venue_id"]), "Unknown Venue")
            
            # Find new overlap groups after rejections
            updated_overlap_groups = find_overlapping_bookings(updated_pending)
            
            # Update messages for bookings that were previously conflicting but no longer are
            bookings_to_update = set()
            for old_booking_id, old_conflicts in overlap_groups.items():
                # Skip the approved booking and rejected bookings
                if old_booking_id == booking_id or old_booking_id in rejected_booking_ids:
                    continue
                
                # Check if this booking had conflicts that were rejected
                if old_conflicts.intersection(rejected_booking_ids):
                    bookings_to_update.add(old_booking_id)
            
            # Update the messages for affected bookings
            for update_booking_id in bookings_to_update:
                if update_booking_id in booking_to_message_map[user["user_id"]]:
                    message_id = booking_to_message_map[user["user_id"]][update_booking_id]
                    
                    # Find the booking data
                    booking_data = next((b for b in updated_pending if b["booking_id"] == update_booking_id), None)
                    if booking_data:
                        # Recreate the message content with updated conflict status
                        booking_start = dt.fromisoformat(booking_data["booking_date"])
                        dur = parse_duration(booking_data["duration"])
                        end_dt = booking_start + dur
                        start_str = booking_start.strftime("%Y-%m-%d %H:%M")
                        end_str = end_dt.strftime("%Y-%m-%d %H:%M")
                        venue_name = venue_dict.get(str(booking_data["venue_id"]), "Unknown Venue")
                        user_name = users_dict.get(str(booking_data["user_id"]), "Unknown User")
                        
                        # Add booking type display for MPSH
                        booking_type_display = ""
                        if venue_name.lower() == "mpsh":
                            booking_type = booking_data.get('booking_type', 'full')
                            booking_type_display = f" [{booking_type.upper()}]"
                        
                        # Add updated overlap indicator
                        overlap_indicator = ""
                        if update_booking_id in updated_overlap_groups:
                            overlapping_count = len(updated_overlap_groups[update_booking_id])
                            overlap_indicator = f"⚠️ CONFLICTS WITH {overlapping_count} OTHER BOOKING(S)\n"
                        
                        updated_msg = (
                            f"{overlap_indicator}"
                            f"📋 Booking ID: {booking_data['booking_id']}\n"
                            f"🏢 Venue: {venue_name}{booking_type_display}\n"
                            f"👤 Name: {user_name}\n"
                            f"📅 Start: {start_str}\n"
                            f"⏰ End: {end_str}\n"
                            f"📝 Reason: {booking_data.get('reason', 'No reason provided')}\n"
                        )
                        
                        # Keep the same inline keyboard
                        inline_markup = types.InlineKeyboardMarkup()
                        inline_markup.add(
                            types.InlineKeyboardButton("✅ Approve", callback_data=f"approve_{booking_data['booking_id']}_{session_id}"),
                            types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_{booking_data['booking_id']}_{session_id}")
                        )
                        
                        try:
                            bot.edit_message_text(updated_msg, user["user_id"], message_id, reply_markup=inline_markup)
                        except Exception:
                            # If edit fails, the message might have been deleted or modified elsewhere
                            pass
        
        # Get updated booking data
        updated_res = supabase.table("bookings").select("*").eq("booking_id", booking_id).execute()
        updated_booking = updated_res.data[0] if updated_res.data else None
        
        if updated_booking:
            # Add to calendar if not already added
            if not updated_booking.get("calendar_event_id"):
                from calendar_helpers import add_event_to_calendar
                event_id = add_event_to_calendar(updated_booking, venue)
                supabase.table("bookings").update({"calendar_event_id": event_id}).eq("booking_id", booking_id).execute()
            
            # Send notification
            notify_approval(updated_booking)
            notify_gc(updated_booking)
            
        
        # Prepare response message
        response_msg = f"✅ Booking {booking_id} has been approved."
        if rejected_bookings:
            rejected_ids = [str(b["booking_id"]) for b in rejected_bookings]
            response_msg += f"\n⚠️ Automatically rejected conflicting bookings: {', '.join(rejected_ids)}"
            response_msg += f"\n📝 Conflicting booking messages have been updated."
        
        bot.answer_callback_query(call.id, "Booking approved!")
        try:
            bot.edit_message_text(response_msg, call.message.chat.id, call.message.message_id, reply_markup=None)
        except Exception:
            pass
        
    else:  # reject
        # Reject the booking
        supabase.table("bookings").update({"status": "rejected"}).eq("booking_id", booking_id).execute()
        
        # Notify user of rejection
        try:
            user_info = get_user_info(booking["user_id"])
            user_name = user_info.get("name", "Unknown User") if user_info else "Unknown User"
            
            booking_start = dt.fromisoformat(booking["booking_date"])
            dur = parse_duration(booking["duration"])
            end_dt = booking_start + dur
            start_str = booking_start.strftime("%Y-%m-%d %H:%M")
            end_str = end_dt.strftime("%Y-%m-%d %H:%M")
            
            rejection_msg = (
                f"Your booking has been rejected.\n\n"
                f"📋 Booking ID: {booking_id}\n"
                f"🏢 Venue: {venue['name']}\n"
                f"📅 Start: {start_str}\n"
                f"⏰ End: {end_str}\n"
                f"📝 Reason: {booking.get('reason', 'No reason provided')}\n"
            )
            
            bot.send_message(booking["user_id"], rejection_msg)
        except Exception as e:
            print(f"Failed to notify user of rejection: {e}")
        
        bot.answer_callback_query(call.id, "Booking rejected!")
        try:
            bot.edit_message_text(f"❌ Booking {booking_id} has been rejected.", call.message.chat.id, call.message.message_id, reply_markup=None)
        except Exception:
            pass

def get_venue_ids_for(names):
    from db_helpers import get_all_venues
    venues = get_all_venues()
    return [v["venue_id"] for v in venues if v["name"].strip().lower() in [n.lower() for n in names]]