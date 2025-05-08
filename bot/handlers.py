# bot/handlers.py
import logging
from telegram import Update, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from .keyboards import get_start_keyboard
from .constants import COURSE_SEARCH_MODE, PROF_SEARCH_MODE # Import button constants

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message and the initial action keyboard."""
    user = update.effective_user
    logger.info(f"User {user.id} ({user.full_name}) started the bot.")

    # Ideally, call API endpoint /users/subscribe here later
    # For now, just send the welcome message

    welcome_text = (
        f"👋 Welcome, {user.first_name}!\n\n"
        "I'm the IITK Grade Explorer Bot. I can help you find grade distributions.\n\n"
        "How would you like to search?"
    )
    keyboard = get_start_keyboard()

    await update.message.reply_text(welcome_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    # Later, we will return a state for ConversationHandler if needed

async def select_search_mode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the user selecting Course or Professor search mode."""
    query = update.callback_query
    await query.answer() # Important to answer callbacks
    callback_data = query.data

    if callback_data == COURSE_SEARCH_MODE:
        logger.info(f"User {update.effective_user.id} chose Course Search Mode.")
        # Placeholder response - In Phase 4, this will ask for course input
        await query.edit_message_text(text="Okay, you chose **Search by Course**.\n\nPlease type the course code or name (e.g., `MTH101A` or `introduction`):", parse_mode=ParseMode.MARKDOWN)
        # Return the state for TYPING_COURSE for ConversationHandler later

    elif callback_data == PROF_SEARCH_MODE:
        logger.info(f"User {update.effective_user.id} chose Professor Search Mode.")
        # Placeholder response - In Phase 4, this will ask for professor input
        await query.edit_message_text(text="Okay, you chose **Search by Professor**.\n\nPlease type the professor's name (partial is okay):", parse_mode=ParseMode.MARKDOWN)
         # Return the state for TYPING_PROF for ConversationHandler later
    else:
         logger.warning(f"Received unknown callback data in select_search_mode: {callback_data}")
         await query.edit_message_text(text="Sorry, something went wrong. Please try /start again.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays help information."""
    help_text = (
        "**How to use this bot:**\n"
        "1. Use /start to begin a search.\n"
        "2. Choose whether to search by Course or Professor.\n"
        "3. Follow the prompts to enter your search query.\n"
        "4. Select the specific item (course/prof) from the results.\n"
        "5. Choose the Academic Year and Semester.\n"
        "6. The bot will display the grade distribution.\n\n"
        "Use /cancel at any time during a search to stop.\n"
        # Add more help as needed
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

# Placeholder for potential error handling
# async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
#     logger.error(msg="Exception while handling an update:", exc_info=context.error)
    # Add more sophisticated error logging/reporting later