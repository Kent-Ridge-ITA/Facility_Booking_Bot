from datetime import datetime as dt, timedelta
import re
from telebot import types
from config import bot, TZ, supabase
from db_helpers import get_user_info, get_all_venues, user_can_access_venue
from booking_utils import check_conflict, create_booking
from registration import send_main_menu

@bot.message_handler(commands=['mass_book'])
def mass_book_command(message):
    user = get_user_info(message.from_user.id)
    if not user:
        bot.send_message(message.from_user.id, "Please /start first to register.")
        return
    
    user_role = user["role"].strip().lower()
    user_cca = user.get("cca", "").strip()
    
    # Check if user has permission (Captain, Chairman, or JCRC with Sports D/Culture D)
    has_permission = False
    if user_role in ["captain", "chairman"]:
        has_permission = True
    elif user_role == "jcrc" and user_cca in ["Sports D", "Culture D"]:
        has_permission = True
    
    if not has_permission:
        bot.send_message(user["user_id"], "You do not have permission to use mass booking. Only Captains, Chairmen, and JCRC (Sports D/Culture D) can use this feature. Press /start to restart.")
        return
    
    # Get MPSH venue and check if user has access
    venues = get_all_venues()
    mpsh_venue = next((v for v in venues if v["name"].strip().lower() == "mpsh"), None)
    
    if not mpsh_venue:
        bot.send_message(user["user_id"], "❌ MPSH venue not found. Please contact an administrator.")
        return
    
    # Check if user can access MPSH venue based on database permissions
    if not user_can_access_venue(user, mpsh_venue):
        user_cca = user.get("cca", "")
        user_role = user["role"]
        # Don't show "No CCA"
        if user_cca and user_cca.lower() != "no cca":
            role_display = f"{user_role} ({user_cca})"
        else:
            role_display = user_role
        bot.send_message(user["user_id"], f"❌ You do not have access to MPSH. Your current role is {role_display}. Please contact an administrator if you believe this is an error. Press /start to restart.")
        return
    
    # Send example message
    example_message = (
        "🏟️ **MPSH Mass Booking**\n\n"
        "📝 **Format for each booking (one per line):**\n"
        "`Full/Half, YYYY-MM-DD, HH:MM, H:MM, Reason`\n\n"
        "📊 **Column Explanation:**\n"
        "`Type, Date, Start Time, Duration, Reason`\n\n"
        "📋 **Example:**\n"
        "```\n"
        "Full, 2025-06-15, 14:00, 2:00, Training\n"
        "Half, 2025-06-16, 10:00, 1:30, Practice\n"
        "Full, 2025-06-17, 16:00, 3:00, Tech Run\n"
        "```\n\n"
        "`Click the example above to copy it.`\n\n"
        "⚠️ **Important Notes:**\n"
        "• You can book up to 1 month in advance\n"
        "• Times must be in 15-minute increments\n"
        "• Duration format: H:MM (e.g., 1:30 for 1 hour 30 minutes)\n"
        "• If conflicts exist, those bookings will be skipped\n"
        "• All successful bookings will be automatically confirmed\n"
        "📤 **Please enter your bookings below:**"
    )
    
    bot.send_message(user["user_id"], example_message, parse_mode='Markdown')
    bot.register_next_step_handler(message, handle_mass_booking_input)

def handle_mass_booking_input(message):
    user_id = message.from_user.id
    user = get_user_info(user_id)
    
    if not user:
        bot.send_message(user_id, "Session expired. Please try /start again.")
        return
    
    # Check permission again
    user_role = user["role"].strip().lower()
    user_cca = user.get("cca", "").strip()
    
    has_permission = False
    if user_role in ["captain", "chairman"]:
        has_permission = True
    elif user_role == "jcrc" and user_cca in ["Sports D", "Culture D"]:
        has_permission = True
    
    if not has_permission:
        bot.send_message(user_id, "Permission denied. Press /start to restart.")
        return
    
    # Get MPSH venue and re-check access
    venues = get_all_venues()
    mpsh_venue = next((v for v in venues if v["name"].strip().lower() == "mpsh"), None)
    
    if not mpsh_venue:
        bot.send_message(user_id, "❌ MPSH venue not found. Please contact an administrator.")
        return
    
    # Re-check if user can access MPSH venue
    if not user_can_access_venue(user, mpsh_venue):
        user_cca = user.get("cca", "")
        user_role = user["role"]
        # Don't show "No CCA"
        if user_cca and user_cca.lower() != "no cca":
            role_display = f"{user_role} ({user_cca})"
        else:
            role_display = user_role
        bot.send_message(user_id, f"❌ You do not have access to MPSH. Your current role is {role_display}. Please contact an administrator if you believe this is an error. Press /start to restart.")
        return
    
    input_text = message.text.strip()
    # More tolerant line splitting - handle multiple newlines and whitespace
    lines = []
    for line in input_text.split('\n'):
        cleaned_line = line.strip()
        if cleaned_line:  # Only add non-empty lines
            lines.append(cleaned_line)
    
    if not lines:
        bot.send_message(user_id, "❌ No booking data provided. Press /start to restart.")
        return
    
    successful_bookings = []
    failed_bookings = []
    current_time = dt.now(TZ)
    one_month_later = current_time + timedelta(days=30)
    
    for line_num, line in enumerate(lines, 1):
        try:
            # More tolerant parsing - handle extra spaces and normalize commas
            # Replace multiple spaces with single space and normalize comma spacing
            normalized_line = re.sub(r'\s+', ' ', line.strip())
            normalized_line = re.sub(r'\s*,\s*', ',', normalized_line)
            
            # Parse the line
            parts = normalized_line.split(',')
            if len(parts) != 5:
                failed_bookings.append({
                    'line': line_num,
                    'data': line,
                    'reason': 'Invalid format - expected 5 parts separated by commas'
                })
                continue
            
            # Strip and clean each part
            booking_type_str = parts[0].strip()
            date_str = parts[1].strip()
            time_str = parts[2].strip()
            duration_str = parts[3].strip()
            reason = parts[4].strip()
            
            # Validate booking type (more tolerant)
            booking_type = booking_type_str.lower()
            if booking_type not in ['full', 'half']:
                failed_bookings.append({
                    'line': line_num,
                    'data': line,
                    'reason': 'Booking type must be "Full" or "Half"'
                })
                continue
            
            # Parse date (remove any extra spaces)
            date_str = re.sub(r'\s+', '', date_str)  # Remove all spaces from date
            try:
                booking_date = dt.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                failed_bookings.append({
                    'line': line_num,
                    'data': line,
                    'reason': 'Invalid date format - use YYYY-MM-DD'
                })
                continue
            
            # Check if date is within allowed range
            if booking_date < current_time.date():
                failed_bookings.append({
                    'line': line_num,
                    'data': line,
                    'reason': 'Cannot book dates in the past'
                })
                continue
            
            if booking_date > one_month_later.date():
                failed_bookings.append({
                    'line': line_num,
                    'data': line,
                    'reason': 'Cannot book more than 1 month in advance'
                })
                continue
            
            # Parse time (remove spaces and be more tolerant)
            time_str = re.sub(r'\s+', '', time_str)  # Remove all spaces from time
            try:
                start_time = dt.strptime(time_str, "%H:%M").time()
                if start_time.minute % 15 != 0:
                    failed_bookings.append({
                        'line': line_num,
                        'data': line,
                        'reason': 'Start time must be in 15-minute increments'
                    })
                    continue
            except ValueError:
                failed_bookings.append({
                    'line': line_num,
                    'data': line,
                    'reason': 'Invalid time format - use HH:MM'
                })
                continue
            
            # Parse duration (remove spaces and be more tolerant)
            duration_str = re.sub(r'\s+', '', duration_str)  # Remove all spaces from duration
            try:
                duration_parts = duration_str.split(":")
                if len(duration_parts) != 2:
                    raise ValueError("Invalid format")
                hours = int(duration_parts[0])
                minutes = int(duration_parts[1])
                total_minutes = hours * 60 + minutes
                if total_minutes <= 0 or total_minutes % 15 != 0:
                    raise ValueError("Duration must be positive and in 15-minute increments")
                if total_minutes > 1440:
                    raise ValueError("Duration cannot exceed 24 hours")
            except ValueError as ve:
                failed_bookings.append({
                    'line': line_num,
                    'data': line,
                    'reason': f'Invalid duration: {ve}'
                })
                continue
            
            # Create booking datetime
            booking_start = dt.combine(booking_date, start_time)
            booking_start = TZ.localize(booking_start)
            
            # Check if booking time is in the past
            if booking_start <= current_time:
                failed_bookings.append({
                    'line': line_num,
                    'data': line,
                    'reason': 'Booking time is in the past'
                })
                continue
            
            # Check for conflicts
            if check_conflict(mpsh_venue, booking_start, duration_str, user_id, booking_type):
                failed_bookings.append({
                    'line': line_num,
                    'data': line,
                    'reason': 'Time slot conflicts with existing booking'
                })
                continue
            
            # Create the booking
            booking_created = create_booking(
                user_id=user_id,
                venue=mpsh_venue,
                booking_start=booking_start,
                duration_text=duration_str,
                user_role=user["role"],
                reason=reason,
                booking_type=booking_type
            )
            
            if booking_created:
                end_time = (booking_start + timedelta(hours=hours, minutes=minutes)).strftime("%H:%M")
                successful_bookings.append({
                    'line': line_num,
                    'type': booking_type.title(),
                    'date': booking_date.strftime("%Y-%m-%d"),
                    'start': start_time.strftime("%H:%M"),
                    'end': end_time,
                    'duration': duration_str,
                    'reason': reason
                })
            else:
                failed_bookings.append({
                    'line': line_num,
                    'data': line,
                    'reason': 'Failed to create booking (unknown error)'
                })
                
        except Exception as e:
            failed_bookings.append({
                'line': line_num,
                'data': line,
                'reason': f'Unexpected error: {str(e)}'
            })
    
    # Generate summary message
    summary_lines = ["🏟️ **MPSH Mass Booking Results**\n"]
    
    if successful_bookings:
        summary_lines.append(f"✅ **Successfully booked {len(successful_bookings)} slots:**")
        for booking in successful_bookings:
            summary_lines.append(
                f"📋 Line {booking['line']}: {booking['type']} - {booking['date']} "
                f"{booking['start']}-{booking['end']} ({booking['duration']}) - {booking['reason']}"
            )
        summary_lines.append("")
    
    if failed_bookings:
        summary_lines.append(f"❌ **Failed to book {len(failed_bookings)} slots:**")
        for failed in failed_bookings:
            summary_lines.append(f"🚫 Line {failed['line']}: {failed['reason']}")
            summary_lines.append(f"   Data: `{failed['data']}`")
        summary_lines.append("")
    
    if not successful_bookings and not failed_bookings:
        summary_lines.append("❌ No bookings processed.")
    
    summary_lines.append("🔄 Press /start to restart the process.")
    
    summary_message = "\n".join(summary_lines)
    
    # Split message if too long (Telegram has a 4096 character limit)
    if len(summary_message) > 4000:
        # Send successful bookings first
        if successful_bookings:
            success_msg = ["🏟️ **MPSH Mass Booking - Successful Bookings**\n"]
            success_msg.append(f"✅ **Successfully booked {len(successful_bookings)} slots:**")
            for booking in successful_bookings:
                success_msg.append(
                    f"📋 Line {booking['line']}: {booking['type']} - {booking['date']} "
                    f"{booking['start']}-{booking['end']} ({booking['duration']}) - {booking['reason']}"
                )
            bot.send_message(user_id, "\n".join(success_msg), parse_mode='Markdown')
        
        # Send failed bookings separately
        if failed_bookings:
            failed_msg = ["🏟️ **MPSH Mass Booking - Failed Bookings**\n"]
            failed_msg.append(f"❌ **Failed to book {len(failed_bookings)} slots:**")
            for failed in failed_bookings:
                failed_msg.append(f"🚫 Line {failed['line']}: {failed['reason']}")
                failed_msg.append(f"   Data: `{failed['data']}`")
            bot.send_message(user_id, "\n".join(failed_msg), parse_mode='Markdown')
        
        bot.send_message(user_id, "🔄 Press /start to restart the process.")
    else:
        bot.send_message(user_id, summary_message, parse_mode='Markdown')
    
    # Send main menu
    send_main_menu(user_id)