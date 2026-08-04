"""Main entry point for the Telegram expense management bot."""

import logging

import telebot

from bot.config import BOT_TOKEN, ensure_directories, msg
from bot.db import init_db
from bot.classifier import get_classifier
from bot.state import set_bot
from bot.handlers import expense, export, admin

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Initialize and start the bot."""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set. Please configure your .env file.")
        return

    # Ensure data directories exist
    ensure_directories()

    # Initialize database
    logger.info("Initializing database...")
    init_db()

    # Initialize classifier
    logger.info("Loading keyword classifier...")
    get_classifier()

    # Create bot instance
    bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

    # Debug: log all incoming messages
    @bot.middleware_handler(update_types=["message"])
    def log_message(bot_instance, message):
        logger.debug(
            "MSG from chat_id=%s user_id=%s type=%s text=%s",
            message.chat.id,
            message.from_user.id if message.from_user else None,
            message.chat.type,
            (message.text or message.caption or "")[:50],
        )

    # Set bot reference for state timeout notifications
    set_bot(bot)

    # Start/help command (registered first so it takes priority)
    @bot.message_handler(commands=["start", "help"])
    def handle_start(message: telebot.types.Message) -> None:
        """Handle /start and /help commands."""
        bot.send_message(message.chat.id, msg("help"))

    # Register handlers (order matters — more specific first)
    admin.register_handlers(bot)
    export.register_handlers(bot)
    expense.register_handlers(bot)

    logger.info("Bot starting... polling for messages.")
    bot.infinity_polling(timeout=60, long_polling_timeout=60)


if __name__ == "__main__":
    main()
