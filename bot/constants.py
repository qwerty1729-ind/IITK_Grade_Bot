# bot/constants.py

# Conversation States (We'll use these later)
(SELECTING_ACTION, SELECTING_COURSE, SELECTING_PROF,
SELECTING_YEAR, SELECTING_SEMESTER, TYPING_COURSE, TYPING_PROF) = range(7)

# Callback Data for Inline Buttons (Strings are safer)
# Initial Actions
COURSE_SEARCH_MODE = "mode_course"
PROF_SEARCH_MODE = "mode_prof"

# Generic Navigation / Controls
CANCEL = "cancel"
BACK_TO_MAIN = "back_main"
# Add more 'BACK_TO_...' as needed for conversation steps
# BACK_TO_PROF_SELECT = "back_prof_select"
# BACK_TO_COURSE_SELECT = "back_course_select"
# BACK_TO_YEAR_SELECT = "back_year_select"

# Dynamic Callback Prefixes (Used later for selecting specific items)
COURSE_SELECT_PREFIX = "cs_"  # e.g., "cs_MTH101A"
PROF_SELECT_PREFIX = "ps_"    # e.g., "ps_123" (instructor ID)
YEAR_SELECT_PREFIX = "ys_"    # e.g., "ys_2023-2024"
SEMESTER_SELECT_PREFIX = "ss_" # e.g., "ss_Odd"