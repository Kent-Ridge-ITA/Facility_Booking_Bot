from config import logger, bot
import help_command
import registration
import booking_flow
import booking_utils
import admin
import approval
import view_cancel
import restart
import edit_booking
import mass_booking
from flask import Flask, request
import telebot

app = Flask(__name__)

# Health check endpoint (optional but useful for Fly.io health checks)
@app.route("/health")
def health():
    return "OK", 200

# Webhook endpoint for Telegram updates
@app.route(f"/webhook/{bot.token}", methods=['POST'])
def telegram_webhook():
    if request.method == "POST":
        update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
        bot.process_new_updates([update])
        return "OK", 200

if __name__ == "__main__":
    FLY_URL = "https://facility-booking-bot-bitter-river-8311.fly.dev"
    WEBHOOK_PATH = f"/webhook/{bot.token}"
    WEBHOOK_URL = f"{FLY_URL}{WEBHOOK_PATH}"

    logger.critical(f"Setting webhook to: {WEBHOOK_URL}")
    
    # Remove any existing webhook
    bot.remove_webhook()
    
    # Set the new webhook
    bot.set_webhook(url=WEBHOOK_URL)

    # Start Flask app
    app.run(host="0.0.0.0", port=8080)
