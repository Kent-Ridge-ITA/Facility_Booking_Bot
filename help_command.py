from config import bot

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = (
        "📖 Available Commands:\n"
        "🏁 /start - Register or login\n"
        "🆔 /getid - Get your Telegram User ID\n"
        "📋 /book - Start a venue booking\n"
        "❌ /cancel - Cancel an existing booking\n"
        "👀 /view - View your active bookings\n"
        "\n💬 For further assistance, contact: @winstonzzk or @Jaredee"
    )
    bot.send_message(message.chat.id, help_text)
