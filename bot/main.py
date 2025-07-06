import logging
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters,
    ConversationHandler, TypeHandler, ApplicationHandlerStop
)

# Import local modules cleanly
from . import handlers
from . import constants

# --- Configuration & Setup ---

# Load environment variables from a .env file in the project root
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Set up logging for the bot
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
# Reduce noise from underlying HTTP library
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Fetch bot token and parse admin IDs from environment
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_IDS_STR = os.getenv("TELEGRAM_ADMIN_IDS", "")
try:
    ADMIN_USER_IDS = [int(admin_id) for admin_id in ADMIN_IDS_STR.split(',') if admin_id.strip()]
    logger.info(f"Admin IDs loaded: {ADMIN_USER_IDS}")
except ValueError:
    ADMIN_USER_IDS = []
    logger.error(f"Could not parse ADMIN_USER_IDS. Check your .env file. Value was: '{ADMIN_IDS_STR}'")

if not BOT_TOKEN:
    logger.error("FATAL: TELEGRAM_BOT_TOKEN not found in environment! Bot cannot start.")
    exit(1)


# --- Pre-processing Handler ---

async def block_check(update: Update, context) -> None:
    """A high-priority handler to check if a user is blocked before processing any command."""
    if await handlers.pre_process_blocked_user(update, context):
        # Stop processing any other handlers for this update if user is blocked
        raise ApplicationHandlerStop

# --- Main Bot Application ---

def main() -> None:
    """Initializes and runs the Telegram bot."""
    logger.info("Starting bot...")

    # Create the bot application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Share admin IDs with all handlers via bot_data
    application.bot_data['ADMIN_USER_IDS'] = ADMIN_USER_IDS

    # --- Handler Definitions ---
    # Define the conversation handlers directly inside main()

    # 1. Main Search Conversation
    search_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', handlers.start_command)],
        states={
            constants.SELECTING_ACTION: [
                CallbackQueryHandler(handlers.select_search_mode_callback, pattern=f"^({constants.COURSE_SEARCH_MODE}|{constants.PROF_SEARCH_MODE})$")
            ],
            constants.TYPING_COURSE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_course_search_input)
            ],
            # (Your other states go here...)
        },
        fallbacks=[
            CommandHandler('start', handlers.start_command),
            CommandHandler('cancel', handlers.cancel_conversation),
        ],
        conversation_timeout=600,
        allow_reentry=True,
    )

    # 2. Feedback Conversation
    feedback_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('feedback', handlers.feedback_start_command)],
        states={
            constants.ASK_FEEDBACK_TYPE: [
                CallbackQueryHandler(handlers.feedback_type_callback, pattern=f"^({constants.FEEDBACK_TYPE_BUG}|{constants.FEEDBACK_TYPE_SUGGESTION}|{constants.FEEDBACK_TYPE_GENERAL})$")
            ],
            constants.TYPING_FEEDBACK_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.feedback_message_handler)
            ],
            constants.CONFIRM_FEEDBACK_SUBMISSION: [
                CallbackQueryHandler(handlers.feedback_confirm_send_callback, pattern=f"^{constants.CONFIRM_SEND_FEEDBACK}$"),
                CallbackQueryHandler(handlers.feedback_cancel_or_edit_callback, pattern=f"^{constants.CANCEL_FEEDBACK}$")
            ]
        },
        fallbacks=[
            CommandHandler('cancel', handlers.cancel_conversation),
        ],
        conversation_timeout=300,
        allow_reentry=True,
    )

    # --- Handler Registration ---
    # Register handlers in groups. Lower group numbers run first.
    
    # Group -1: The block checker runs before anything else.
    application.add_handler(TypeHandler(Update, block_check), group=-1)

    # Group 0: Main conversation and command handlers.
    application.add_handler(search_conv_handler)
    application.add_handler(feedback_conv_handler)
    
    # Add standalone command handlers
    application.add_handler(CommandHandler("subscribe", handlers.subscribe_command))
    application.add_handler(CommandHandler("unsubscribe", handlers.unsubscribe_command))
    application.add_handler(CommandHandler("help", handlers.help_command))
    
    # Add admin command handlers
    application.add_handler(CommandHandler("block", handlers.block_user_command))
    application.add_handler(CommandHandler("unblock", handlers.unblock_user_command))
    application.add_handler(CommandHandler("userstatus", handlers.user_status_command))
    application.add_handler(CommandHandler("broadcast", handlers.broadcast_admin_command))

    # --- Run the Bot ---
    logger.info("Bot is configured. Starting polling...")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()