# bot/constants.py

# Conversation States for main search flow
(SELECTING_ACTION, TYPING_COURSE, TYPING_PROF,
 SELECTING_COURSE_RESULTS,
 SELECTING_PROF_RESULTS,
 SELECTING_COURSE_FOR_PROF,
 SELECTING_YEAR_SEMESTER,
 SHOWING_FINAL_GRADES # This was state 7 (0-indexed)
 ) = range(8)

# --- NEW: Conversation States for feedback ---
# Continue numbering from the last state of the main flow
_last_main_flow_state = SHOWING_FINAL_GRADES # This is 7
(ASK_FEEDBACK_TYPE, TYPING_FEEDBACK_MESSAGE, CONFIRM_FEEDBACK_SUBMISSION
 ) = range(_last_main_flow_state + 1, _last_main_flow_state + 1 + 3) # States 8, 9, 10

# Callback Data for Inline Buttons (Main Flow)
COURSE_SEARCH_MODE = "mode_course"
PROF_SEARCH_MODE = "mode_prof"

CANCEL = "cancel" # General cancel, typically ends the current conversation
BACK_TO_MAIN = "back_main"

BACK_TO_TYPING_COURSE = "back_type_crs"
BACK_TO_TYPING_PROF = "back_type_prof"
BACK_TO_PROF_COURSE_LIST_PREFIX = "back_prof_crs_list_"
BACK_TO_COURSE_SEARCH_LIST = "back_crs_srch_list"
BACK_TO_PROF_SEARCH_LIST = "back_prof_srch_list"
BACK_TO_YEAR_SEM_SELECT_PREFIX = "back_ys_sel_"

COURSE_SELECT_PREFIX = "cs_"
PROF_SELECT_PREFIX = "ps_"
YEAR_SEM_SELECT_PREFIX = "ysel_"

ITEMS_PER_PAGE = 8

PAGE_COURSE_SEARCH_RESULTS_PREFIX = "p_csr_"
PAGE_PROF_SEARCH_RESULTS_PREFIX = "p_psr_"
PAGE_PROF_COURSE_LIST_PREFIX = "p_pcl_"
PAGE_YEAR_SEMESTER_PREFIX = "p_ys_"

# --- NEW: Callback Data for Feedback ---
FEEDBACK_TYPE_BUG = "fb_bug"
FEEDBACK_TYPE_SUGGESTION = "fb_suggestion"
FEEDBACK_TYPE_GENERAL = "fb_general"
CONFIRM_SEND_FEEDBACK = "fb_confirm_send"
CANCEL_FEEDBACK = "fb_cancel" # Specific cancel for feedback flow, usually to restart feedback type selection
