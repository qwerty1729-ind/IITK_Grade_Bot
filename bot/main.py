# bot/main.py
import logging
import os
from dotenv import load_dotenv

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    # ConversationHandler, # Add later
    # MessageHandler, # Add later
    # filters, # Add later
)
# Import handlers and constants
from .handlers import start_command, help_command, select_search_mode_callback
from .constants import COURSE_SEARCH_MODE, PROF_SEARCH_MODE

# --- Logging Setup ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- Environment Variables ---
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env')) # Load .env from root
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN not found in .env file!")
    exit(1)

def main() -> None:
    """Start the bot."""
    logger.info("Starting bot...")

    # --- Create the Application and pass it your bot's token ---
    # Use default settings for persistence, rate limits etc. for now
    application = Application.builder().token(BOT_TOKEN).build()

    # --- Register Handlers ---
    # Basic commands
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))

    # Callback Query Handler for the start menu buttons
    application.add_handler(CallbackQueryHandler(select_search_mode_callback, pattern=f"^({COURSE_SEARCH_MODE}|{PROF_SEARCH_MODE})$"))

    # Add ConversationHandler later for search flow
    # Add MessageHandlers later for text input
    # Add Error handler later

    # --- Run the bot ---
    logger.info("Bot starting polling...")
    # Run the bot until the user presses Ctrl-C
    application.run_polling()
    logger.info("Bot stopped.")

if __name__ == "__main__":
    main()