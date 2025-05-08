# bot/keyboards.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from .constants import COURSE_SEARCH_MODE, PROF_SEARCH_MODE

def get_start_keyboard() -> InlineKeyboardMarkup:
    """Returns the initial keyboard for selecting search mode."""
    keyboard = [
        [
            InlineKeyboardButton("📚 Search by Course", callback_data=COURSE_SEARCH_MODE),
        ],
        [
            InlineKeyboardButton("🧑‍🏫 Search by Professor", callback_data=PROF_SEARCH_MODE),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)