from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Dict, Any

# Import the constants module cleanly
from . import constants

# --- Static Keyboards ---

def get_start_keyboard() -> InlineKeyboardMarkup:
    """Returns the initial keyboard for choosing a search mode."""
    keyboard = [
        [InlineKeyboardButton("📚 Search by Course", callback_data=constants.COURSE_SEARCH_MODE)],
        [InlineKeyboardButton("🧑‍🏫 Search by Professor", callback_data=constants.PROF_SEARCH_MODE)]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_feedback_type_keyboard() -> InlineKeyboardMarkup:
    """Returns a keyboard for selecting the type of feedback."""
    keyboard = [
        [InlineKeyboardButton("🐛 Bug Report", callback_data=constants.FEEDBACK_TYPE_BUG)],
        [InlineKeyboardButton("💡 Suggestion", callback_data=constants.FEEDBACK_TYPE_SUGGESTION)],
        [InlineKeyboardButton("🗣️ General Feedback", callback_data=constants.FEEDBACK_TYPE_GENERAL)],
        [InlineKeyboardButton("❌ Cancel", callback_data=constants.CANCEL)]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_feedback_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Returns a keyboard for confirming or editing feedback."""
    keyboard = [
        [InlineKeyboardButton("✅ Yes, send it", callback_data=constants.CONFIRM_SEND_FEEDBACK)],
        [InlineKeyboardButton("✏️ Edit / Re-type", callback_data=constants.CANCEL_FEEDBACK)],
        [InlineKeyboardButton("🗑️ Discard Feedback", callback_data=constants.CANCEL)]
    ]
    return InlineKeyboardMarkup(keyboard)


# --- Dynamic & Paginated Keyboards ---

def create_paginated_keyboard(
    items: List[Dict[str, Any]],
    page: int,
    item_callback_prefix: str,
    page_callback_prefix: str,
    back_button: InlineKeyboardButton,
    item_display_key: str = 'display_text',
    item_id_key: str = 'id',
) -> InlineKeyboardMarkup:
    """
    A generic function to create a paginated list of buttons.
    The calling handler is responsible for providing the pre-processed items.
    """
    keyboard: List[List[InlineKeyboardButton]] = []
    
    # Create a button for each item on the current page
    start_index = page * constants.ITEMS_PER_PAGE
    end_index = start_index + constants.ITEMS_PER_PAGE
    for item in items[start_index:end_index]:
        keyboard.append([
            InlineKeyboardButton(
                text=item[item_display_key][:60], # Truncate long text
                callback_data=f"{item_callback_prefix}{item[item_id_key]}"
            )
        ])

    # Add pagination controls if needed
    total_pages = (len(items) + constants.ITEMS_PER_PAGE - 1) // constants.ITEMS_PER_PAGE
    pagination_row = []
    if page > 0:
        pagination_row.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"{page_callback_prefix}{page - 1}"))
    if page < total_pages - 1:
        pagination_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"{page_callback_prefix}{page + 1}"))
    
    if pagination_row:
        keyboard.append(pagination_row)

    # Add the final navigation buttons
    keyboard.append([back_button, InlineKeyboardButton("❌ Cancel", callback_data=constants.CANCEL)])
    
    return InlineKeyboardMarkup(keyboard)

def get_final_options_keyboard(back_to_select_term_payload: str) -> InlineKeyboardMarkup:
    """
    Returns the final keyboard after viewing grades, allowing the user
    to go back or start a new search.
    """
    keyboard = [
        [InlineKeyboardButton("⬅️ Select Diff. Year/Sem", callback_data=back_to_select_term_payload)],
        [InlineKeyboardButton("🔄 New Search", callback_data=constants.BACK_TO_MAIN)]
    ]
    return InlineKeyboardMarkup(keyboard)