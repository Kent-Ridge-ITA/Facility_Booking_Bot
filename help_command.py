from config import bot
from db_helpers import get_user_info

@bot.message_handler(commands=['help'])
def help_command(message):
    user = get_user_info(message.from_user.id)
    if not user:
        help_text = (
            "📖 Available Commands:\n"
            "🏁 /start - Register or login\n"
            "🆔 /getid - Get your Telegram User ID\n"
            "\n💬 For further assistance, contact: @winstonzzk or @Jaredee"
        )
        bot.send_message(message.chat.id, help_text)
        return

    user_role = user["role"].strip().lower()
    user_cca = user.get("cca", "").strip().lower()
    user_block = user.get("block", "").strip().lower()

    # Base commands available to all users
    help_text = "📖 Available Commands:\n🏁 /start - Register or login\n🆔 /getid - Get your Telegram User ID\n"

    if user_role == "admin":
        help_text += (
            "📋 /book - Start a venue booking\n"
            "👀 /view - View all bookings across all venues\n"
            "❌ /cancel - Cancel any booking\n"
            "✏️ /edit - Edit your own bookings\n"
            "⚙️ /admin_update - Update user roles and CCAs\n"
            "🔄 /restart - Restart the bot\n"
        )
    
    elif user_role == "jcrc":
        help_text += "📋 /book - Start a venue booking\n"
        
        if user_cca == "welfare d":
            help_text += (
                "✅ /approve - Approve/reject Reading Room & Dining Hall bookings\n"
                "👀 /view - View all Reading Room & Dining Hall bookings + your own\n"
                "❌ /cancel - Cancel your own bookings + any Reading Room/Dining Hall bookings\n"
                "✏️ /edit - Edit your own Reading Room & Dining Hall bookings\n"
            )
        elif user_cca in ["sports d", "culture d"]:
            help_text += (
                "📦 /mass_book - Submit multiple MPSH bookings at once\n"
                "👀 /view - View all MPSH bookings + your own bookings\n"
                "❌ /cancel - Cancel your own bookings + any MPSH bookings\n"
                "✏️ /edit - Edit your own Reading Room, Dining Hall & MPSH bookings\n"
            )
        else:
            help_text += (
                "👀 /view - View your own bookings\n"
                "❌ /cancel - Cancel your own bookings\n"
                "✏️ /edit - Edit your own Reading Room & Dining Hall bookings\n"
            )
    
    elif user_role == "captain":
        help_text += (
            "📋 /book - Start a venue booking\n"
            "📦 /mass_book - Submit multiple MPSH bookings at once\n"
            "👀 /view - View your own bookings\n"
            "❌ /cancel - Cancel your own bookings\n"
            "✏️ /edit - Edit your own MPSH bookings\n"
        )
    
    elif user_role == "chairman":
        if user_cca == "dance":
            help_text += (
                "📋 /book - Start a venue booking\n"
                "📦 /mass_book - Submit multiple MPSH bookings at once\n"
                "👀 /view - View your own bookings\n"
                "❌ /cancel - Cancel your own bookings\n"
                "✏️ /edit - Edit your own MPSH bookings\n"
            )
        elif user_cca in ["rockers", "inspire"]:
            help_text += (
                "📋 /book - Start a venue booking\n"
                "👀 /view - View your own bookings\n"
                "❌ /cancel - Cancel your own bookings\n"
                "✏️ /edit - Edit your own Band Room bookings\n"
            )
        else:
            help_text += (
                "📋 /book - Start a venue booking\n"
                "👀 /view - View your own bookings\n"
                "❌ /cancel - Cancel your own bookings\n"
            )
    
    elif user_role == "block head":
        block_display = user_block.title() if user_block else "Your Block"
        help_text += (
            "📋 /book - Start a venue booking\n"
            f"✅ /approve - Approve/reject {block_display} Lounge bookings\n"
            f"👀 /view - View all {block_display} Lounge bookings + your own\n"
            f"❌ /cancel - Cancel your own bookings + any {block_display} Lounge bookings\n"
            "✏️ /edit - Edit your own bookings\n"
        )
    
    else:  # Regular residents
        help_text += (
            "📋 /book - Start a venue booking (requires approval)\n"
            "👀 /view - View your own bookings only\n"
            "❌ /cancel - Cancel your own bookings only\n"
        )

    help_text += "\n💬 For further assistance, contact: @winstonzzk or @Jaredee"
    bot.send_message(message.chat.id, help_text)
