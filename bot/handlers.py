# bot/handlers.py
import logging
import os  
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
import httpx
import html
import time #for simple caching if u wish to implement later
import re  # Added for escape_markdown_v2
from typing import List, Dict, Optional

# Import constants used in this file
from constants import (
    # Main search flow
    SELECTING_ACTION, TYPING_COURSE, TYPING_PROF,
    SELECTING_COURSE_RESULTS, SELECTING_PROF_RESULTS, SELECTING_COURSE_FOR_PROF,
    SELECTING_YEAR_SEMESTER, SHOWING_FINAL_GRADES,
    COURSE_SEARCH_MODE, PROF_SEARCH_MODE, CANCEL, BACK_TO_MAIN,
    COURSE_SELECT_PREFIX, PROF_SELECT_PREFIX, YEAR_SEM_SELECT_PREFIX,
    BACK_TO_TYPING_COURSE, BACK_TO_TYPING_PROF,
    BACK_TO_PROF_COURSE_LIST_PREFIX,
    BACK_TO_COURSE_SEARCH_LIST,
    BACK_TO_PROF_SEARCH_LIST,
    BACK_TO_YEAR_SEM_SELECT_PREFIX,
    ITEMS_PER_PAGE,
    PAGE_COURSE_SEARCH_RESULTS_PREFIX,
    PAGE_PROF_SEARCH_RESULTS_PREFIX,
    PAGE_PROF_COURSE_LIST_PREFIX,
    PAGE_YEAR_SEMESTER_PREFIX,
    # Feedback flow
    ASK_FEEDBACK_TYPE, TYPING_FEEDBACK_MESSAGE, CONFIRM_FEEDBACK_SUBMISSION,
    FEEDBACK_TYPE_BUG, FEEDBACK_TYPE_SUGGESTION, FEEDBACK_TYPE_GENERAL,
    CONFIRM_SEND_FEEDBACK, CANCEL_FEEDBACK
)
# API client
from api_client import (
    search_items_api,
    get_offerings_for_course_api,
    get_offerings_for_prof_api,
    get_offering_details_api,
    get_grades_distribution_api,
    subscribe_user_api,
    unsubscribe_user_api,
    submit_feedback_api,
    # API client functions for admin commands
    set_user_block_status_api,
    get_user_status_api,
    initiate_broadcast_api
)
# Keyboards
from keyboards import (
    get_start_keyboard,
    create_search_results_keyboard,
    get_cancel_keyboard,
    create_prof_course_selection_keyboard,
    create_year_semester_keyboard,
    get_final_options_keyboard,
    get_feedback_type_keyboard,
    get_feedback_confirmation_keyboard,
    get_feedback_entry_cancel_keyboard
)

logger = logging.getLogger(__name__)

# This cache is very basic. For production, consider a proper expiring cache like cachetools.
BLOCKED_USER_CACHE = {} # {user_id: {"is_blocked": bool, "timestamp": float}}
CACHE_DURATION_SECONDS = 300 # Cache block status for 5 minutes (5 * 60)
# bot/handlers.py
# ... (after BLOCKED_USER_CACHE and other helpers) ...

async def pre_process_blocked_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Checks if the user is blocked.
    Returns True if user is blocked (and further processing should stop), False otherwise.
    """
    if not update.effective_user:
        logger.debug("pre_process_blocked_user: No effective_user in update, allowing.")
        return False # Don't block system updates or those without a clear user

    user_id = update.effective_user.id

    # --- 1. Admins are NEVER blocked by this system check ---
    # Access ADMIN_USER_IDS from application.bot_data
    admin_ids_list = context.application.bot_data.get('ADMIN_USER_IDS', [])
    if user_id in admin_ids_list:
        logger.debug(f"User {user_id} is an admin. Skipping block check.")
        return False # Allow admins

   
    is_user_blocked_api = False
    try:
        
        # This implies the API endpoint should allow a user to fetch their own status
        # when the X-Telegram-User-ID header matches the user ID in the path.
        # If your API's /admin/users/{id} endpoint is strictly for admins to check *other* users
        # and requires an *admin's* ID in the X-Telegram-User-ID header,
        # you might need a new API endpoint like /users/me/status or adjust the existing one.
        user_status_response = await get_user_status_api(str(user_id), admin_user_id=user_id)

        if user_status_response and user_status_response.get('is_blocked'):
            is_user_blocked_api = True

        # Update cache (optional - currently commented out)
        # BLOCKED_USER_CACHE[user_id] = {'is_blocked': is_user_blocked_api, 'timestamp': time.time()}

    except Exception as e:
        # If API call fails, default to NOT blocking the user to prevent accidental lockout.
        logger.error(f"Failed to check block status for user {user_id} via API: {e}. Allowing update as a precaution.", exc_info=True)
        return False # Do not block if status check fails

    if is_user_blocked_api:
        logger.info(f"User {user_id} IS blocked (API check). Update will be ignored.")
        # Optionally send a "You are blocked" message (consider rate limiting or one-time message)
        # (Example sending logic was in the commented-out cache section)
        return True # Block further processing

    return False # User is not blocked, allow processing




# --- Helper Functions ---
def _clear_list_context(context: ContextTypes.DEFAULT_TYPE, list_type: str) -> None:
    """Clears stored list, page number, and related query/context for pagination/back actions."""
    prefix = f"all_{list_type}"
    page_key = f"current_{list_type}_page"
    unique_kb_key = f"unique_{list_type}_kb"

    context.user_data.pop(f"{prefix}_results", None)
    context.user_data.pop(page_key, None)
    context.user_data.pop(unique_kb_key, None)

    if list_type == "course_search":
        context.user_data.pop('last_search_query_course', None)
    elif list_type == "prof_search":
        context.user_data.pop('last_search_query_prof', None)
    elif list_type == "prof_course_list":
        context.user_data.pop('unique_courses_for_selected_prof_kb', None)
    elif list_type == "year_semester_list":
        pass


# --- MarkdownV2 Escaping Function ---
def escape_markdown_v2(text: str) -> str:
    """Escapes special characters for Telegram MarkdownV2."""
    if not isinstance(text, str):
        text = str(text)
    # Order of escaping matters for backslash itself.
    # Escape backslashes first (should be `\\` -> `\\\\` in a raw string, or `\` -> `\\` if not)
    # Then escape other special characters.
    # The `escape_chars` string should list characters that need a \ before them.
    escape_chars = r'_*[]()~`>#+-=|{}.!'  # . ! - = are common culprits if not escaped

 

    escaped_text = text
    for char_to_escape in escape_chars:
        escaped_text = escaped_text.replace(char_to_escape, f'\\{char_to_escape}')

    
    # escaped_text = escaped_text.replace('<TEMP_BACKSLASH_PLACEHOLDER>', '\\\\')
    return escaped_text


def get_restart_keyboard() -> InlineKeyboardMarkup:
    """Returns a simple keyboard with a Restart Search button linked to BACK_TO_MAIN."""
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Restart Search", callback_data=BACK_TO_MAIN)]])


async def _handle_api_error_async(error_source: str, error: Exception, context: ContextTypes.DEFAULT_TYPE,
                                  message_id_to_edit: Optional[int] = None, chat_id: Optional[int] = None) -> None:
    """Internal async helper to send standardized error messages using MarkdownV2."""
    user_message = "An unexpected error occurred\\."  # Escaped period
    log_level = logging.ERROR
    exc_info_flag = True

    if isinstance(error, httpx.HTTPStatusError):
        log_level = logging.WARNING
        exc_info_flag = False
        error_detail = ""
        try:
            error_detail = error.response.json().get("detail", "")
        except:
            pass
        user_message = f"Backend error ({error.response.status_code}) contacting service\\."  # Escaped period
        if error_detail: user_message += f"\nDetails: {escape_markdown_v2(error_detail[:100])}"
        logger.log(log_level,
                   f"API HTTP Error ({error_source}): Status {error.response.status_code} for {error.request.url}. Response: {error.response.text[:150]}",
                   exc_info=exc_info_flag)
    elif isinstance(error, httpx.RequestError):
        log_level = logging.WARNING
        exc_info_flag = False
        user_message = "Network error contacting backend service\\. Please check connection or try again later\\."  # Escaped period
        logger.log(log_level,
                   f"API Network/Request Error ({error_source}): {error.__class__.__name__} for {error.request.url} - {error}",
                   exc_info=exc_info_flag)
    elif isinstance(error, ValueError):
        log_level = logging.WARNING
        exc_info_flag = True
        user_message = f"Data processing error: {escape_markdown_v2(str(error)[:150])}\\. Please restart\\."  # Escaped period
        logger.log(log_level, f"ValueError ({error_source}): {error}", exc_info=exc_info_flag)
    else:
        logger.log(log_level, f"Unexpected error ({error_source}): {error}", exc_info=exc_info_flag)
        user_message = "An unexpected internal error occurred\\. Please restart\\."  # Escaped period

    user_message = f"❌ {user_message}"  # No period here, so no escape needed for this part
    error_keyboard = get_restart_keyboard()

    effective_chat_id = chat_id
    if not effective_chat_id and hasattr(context, '_chat_id') and context._chat_id:
        effective_chat_id = context._chat_id
    if not effective_chat_id and hasattr(context, '_user_id') and context._user_id:
        effective_chat_id = context._user_id

    if message_id_to_edit and effective_chat_id:
        try:
            await context.bot.edit_message_text(chat_id=effective_chat_id, message_id=message_id_to_edit,
                                                text=user_message, reply_markup=error_keyboard,
                                                parse_mode=ParseMode.MARKDOWN_V2)
            return
        except Exception as e_edit:
            logger.warning(f"Failed to edit message {message_id_to_edit} with API error: {e_edit}")

    if effective_chat_id:
        logger.debug(f"Sending new error message to chat_id: {effective_chat_id}")
        await context.bot.send_message(chat_id=effective_chat_id, text=user_message, reply_markup=error_keyboard,
                                       parse_mode=ParseMode.MARKDOWN_V2)
    else:
        logger.error("Cannot send API error message: effective_chat_id could not be determined.")


def handle_api_error(error_source: str, error: Exception, context: ContextTypes.DEFAULT_TYPE,
                     message_id_to_edit: Optional[int] = None, chat_id: Optional[int] = None) -> None:
    """Synchronous wrapper to schedule the async error handler task."""
    context.application.create_task(
        _handle_api_error_async(error_source, error, context, message_id_to_edit, chat_id)
    )


# --- Text Templates for Pagination ---
# These continue to use ParseMode.MARKDOWN and html.escape as per original design
# unless a full switch to MARKDOWN_V2 is planned for the entire bot.
def _get_search_list_text_template(item_type: str, count: int, query: str, current_page_num: int) -> str:
    query_part = f" for '*{html.escape(query)}*'" if query else ""
    count_text = f"Found {count} {item_type}" if count != 1 else f"Found 1 {item_type.rstrip('s')}"
    return f"✅ {count_text}{query_part}.\nPage {current_page_num}. Select one or browse:"


def _get_prof_course_list_text_template(prof_name: str, count: int, current_page_num: int) -> str:
    count_text = f" ({count} found)" if count != 1 else f" (1 found)"
    return f"Courses taught by **{html.escape(prof_name)}**{count_text}.\nPage {current_page_num}. Which course?"


def _get_year_semester_list_text_template(course_code: str, count: int, current_page_num: int,
                                          prof_name: Optional[str] = None) -> str:
    prof_part = f" by Prof. **{html.escape(prof_name)}**" if prof_name else ""
    count_text = f" ({count} offerings found)" if count != 1 else f" (1 offering found)"
    return f"Offerings for **{html.escape(course_code)}**{prof_part}{count_text}.\nPage {current_page_num}. Select Year (Semester):"


# --- HELPER: Display Final Grades & Plot ---
# Uses ParseMode.HTML
async def display_grades_and_plot(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                  grade_data_api_response: Dict) -> None:
    effective_chat_id = update.effective_chat.id
    message_to_edit = None

    if update.callback_query and update.callback_query.message:
        message_to_edit = update.callback_query.message
    elif 'last_bot_message_obj' in context.user_data and context.user_data['last_bot_message_obj']:
        message_to_edit = context.user_data['last_bot_message_obj']
    elif 'original_message_id_for_edit' in context.user_data and context.user_data['original_message_id_for_edit']:
        if update.callback_query:
            message_to_edit = update.callback_query.message
        else:
            logger.warning(
                "display_grades_and_plot: update.callback_query is None, trying to use original_message_id_for_edit directly (might be stale).")

    if not message_to_edit:
        logger.error("display_grades_and_plot: message_to_edit could not be determined even after fallbacks.")
        # _handle_api_error_async sends V2
        handle_api_error("display_grades_pre_check", ValueError("Cannot determine message to edit for grades display."),
                         context, chat_id=effective_chat_id)
        return

    try:
        offering_api = grade_data_api_response.get('offering', {})
        if not offering_api: raise ValueError("Offering details missing in grade data")

        grades_list_api = grade_data_api_response.get('grades', [])
        total_graded_students_api = grade_data_api_response.get('total_graded_students', 0)
        course_info = offering_api.get('course', {})
        course_code = course_info.get('code', 'N/A')
        course_title = course_info.get('name', course_code)
        year = offering_api.get('academic_year', 'N/A')
        sem = offering_api.get('semester', 'N/A')
        current_reg_val = offering_api.get('current_registered')
        plot_file_id = offering_api.get('plot_file_id')
        offering_id_db = offering_api.get('id')
        instructors_api_list = offering_api.get('instructors', [])
        inst_names = ", ".join(sorted([html.escape(i.get('name', 'N/A')) for i in instructors_api_list])) or "N/A"

        title_line = f"📊 <b>{html.escape(course_code)} - {html.escape(course_title)}</b>\n ({html.escape(year)} - {html.escape(sem)})"
        prof_line = f"🧑‍🏫 <i>Instructor(s):</i> {inst_names}"

        students_display_count = total_graded_students_api
        if not students_display_count and isinstance(current_reg_val, int) and current_reg_val > 0:
            students_display_count = current_reg_val
        elif not students_display_count and not grades_list_api:
            students_display_count = current_reg_val if current_reg_val is not None else "?"
        students_display_count_str = str(students_display_count) if students_display_count is not None else "?"

        #students_line = f"👥 <i>Students Graded:</i> {students_display_count_str} (Registered: {current_reg_val if current_reg_val is not None else 'N/A'})"
        students_line = f"👥 <i>Students Graded:</i> {students_display_count_str}"
        message_text_parts = [title_line, prof_line, students_line]

        if not grades_list_api:
            message_text_parts.append("\n🤷 <i>No specific grade counts found.</i>")
        else:
            actual_sum_of_counts_from_grades = sum(
                g.get('count', 0) for g in grades_list_api if isinstance(g.get('count'), int))
            base_for_percentage = 0
            if isinstance(current_reg_val, int) and current_reg_val > 0:
                base_for_percentage = current_reg_val
            elif total_graded_students_api > 0:
                base_for_percentage = total_graded_students_api
            elif actual_sum_of_counts_from_grades > 0:
                base_for_percentage = actual_sum_of_counts_from_grades

            grade_lines = []
            for g_data in grades_list_api:
                gt, gc = g_data.get('grade_type', '??'), g_data.get('count', 0)
                perc = g_data.get('percentage')
                if perc is None and base_for_percentage > 0 and isinstance(gc, int) and gc >= 0:
                    perc = round((gc / base_for_percentage) * 100, 1)
                perc_str = f" ({perc:.1f}%)" if perc is not None else ""
                safe_gt = html.escape(str(gt))
                grade_lines.append(f"<code>{safe_gt:<4}</code> : {gc}{perc_str}")
            message_text_parts.append("\n<b>Grade Distribution:</b>\n" + "\n".join(grade_lines))

        final_text_message = "\n".join(message_text_parts)
        final_keyboard = get_final_options_keyboard(course_code_for_back_to_ys=course_code)

        await message_to_edit.edit_text(final_text_message, reply_markup=final_keyboard, parse_mode=ParseMode.HTML)

        context.user_data.pop('last_plot_message_id', None)
        if plot_file_id:
            logger.info(f"Sending plot for offering {offering_id_db}, file_id: {plot_file_id}")
            try:
                sent_photo_msg = await context.bot.send_photo(
                    chat_id=effective_chat_id,
                    photo=plot_file_id,
                    caption=f"Plot: {html.escape(course_code)} - {html.escape(course_title)} ({html.escape(year)} - {html.escape(sem)})"
                )
                context.user_data['last_plot_message_id'] = sent_photo_msg.message_id
            except Exception as e_plot:
                logger.error(f"Failed to send plot photo with file_id '{plot_file_id}': {e_plot}", exc_info=True)
                await context.bot.send_message(effective_chat_id,
                                               "ℹ️ Grades displayed. Note: Could not send the plot image at this time.")
        else:
            logger.info(f"No plot_file_id for offering {offering_id_db}.")

    except Exception as e:
        logger.error(
            f"Error in display_grades_and_plot for msg_id {message_to_edit.message_id if message_to_edit else 'unknown'}: {e}",
            exc_info=True)
        msg_id_for_err_handling = message_to_edit.message_id if message_to_edit else None
        handle_api_error("display_grades", e, context, message_id_to_edit=msg_id_for_err_handling,  # Uses V2 for error
                         chat_id=effective_chat_id)


# --- CORE CONVERSATION HANDLERS ---
# These mostly use ParseMode.MARKDOWN as per original file.
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info(
        f"--- start_command EXECUTED by user {update.effective_user.id if update.effective_user else 'Unknown'} ---")  # <<< ADD THIS LOG
    user = update.effective_user
    is_callback = bool(update.callback_query)
    effective_chat_id = update.effective_chat.id

    user_details = f"ID: {user.id if user else 'Unknown'}"
    if user:
        if user.full_name: user_details += f", Name: {user.full_name}"
        if user.username: user_details += f", Username: @{user.username}"
    logger.info(f"start_command {'(Callback)' if is_callback else '(Direct)'} from user ({user_details}).")

    if is_callback and update.callback_query:
        pass

    if user:
        try:
            api_response = await subscribe_user_api(
                tg_user_id=user.id,
                first_name=user.first_name,
                last_name=user.last_name,
                username=user.username
            )
            if api_response:
                logger.info(f"User {user.id} subscribed/activity updated via API. Response: {api_response}")
            else:
                logger.info(f"Subscription API call for user {user.id} processed (no detailed response or None).")
        except Exception as e_sub:
            logger.error(f"Failed to call subscribe API for user {user.id} in start_command: {e_sub}", exc_info=True)
    else:
        logger.warning("start_command: update.effective_user is None, cannot call subscribe API.")

    context.user_data.clear()
    logger.debug("User data cleared by start_command.")

    welcome_text = f"👋 Hi {user.first_name if user and user.first_name else 'there'}!\nHow would you like to search?"
    keyboard = get_start_keyboard()
    try:
        sent_message = await context.bot.send_message(
            chat_id=effective_chat_id,
            text=welcome_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        if sent_message:
            context.user_data['original_message_id_for_edit'] = sent_message.message_id
            logger.debug(
                f"start_command sent new message {sent_message.message_id} and set as original_message_id_for_edit.")
            return SELECTING_ACTION
        else:
            raise ValueError("Failed to send start message (send_message returned None).")
    except Exception as e:
        logger.error(f"Failed in start_command when sending message: {e}", exc_info=True)
        if effective_chat_id:
            try:
                # This will be sent by _handle_api_error_async using MARKDOWN_V2 if it were to call it.
                # For direct send, let's keep it simple without V2 unless other direct errors use V2.
                await context.bot.send_message(effective_chat_id,
                                               "An error occurred starting the bot. Please try /start again later.")
            except Exception as e_report:
                logger.error(f"Failed to send error report in start_command: {e_report}")
        return ConversationHandler.END



async def select_search_mode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    logger.info(
        f"select_search_mode_callback triggered. CB Data: {query.data}. Message ID to edit: {context.user_data.get('original_message_id_for_edit')}")
    await query.answer()
    callback_data = query.data
    message_id_to_edit = context.user_data.get('original_message_id_for_edit')
    chat_id = query.message.chat_id

    original_message_id = context.user_data.get('original_message_id_for_edit')
    context.user_data.clear()
    if original_message_id:
        context.user_data['original_message_id_for_edit'] = original_message_id
    else:
        logger.error("CRITICAL: original_message_id_for_edit missing in select_search_mode_callback after clear!")

    next_state = ConversationHandler.END
    prompt_text = "Error selecting mode."
    cancel_kb = get_cancel_keyboard()

    try:
        if not message_id_to_edit:
            logger.error("select_search_mode_callback: No message_id_to_edit. Sending new prompt.")
            raise ValueError("Message ID for editing unavailable in select_search_mode_callback")

        if callback_data == COURSE_SEARCH_MODE:
            context.user_data['search_mode'] = 'course'
            prompt_text = "📚 OK. Enter **course code OR full/partial title**:";
            next_state = TYPING_COURSE
        elif callback_data == PROF_SEARCH_MODE:
            context.user_data['search_mode'] = 'prof'
            prompt_text = "🧑‍🏫 OK. Enter **professor's name**:";
            next_state = TYPING_PROF
        else:
            raise ValueError(f"Unknown search mode callback: {callback_data}")

        await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id_to_edit, text=prompt_text,
                                            reply_markup=cancel_kb, parse_mode=ParseMode.MARKDOWN)
        return next_state
    except Exception as e:
        logger.error(f"Error in select_search_mode_callback: {e}", exc_info=True)
        handle_api_error("select_search_mode", e, context, message_id_to_edit=message_id_to_edit,
                         chat_id=chat_id)  # Uses V2 for error
        return ConversationHandler.END


async def _handle_search_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE, search_type: str) -> int:
    user = update.effective_user
    query_text = update.message.text.strip()
    min_len = 2 if search_type == 'course' else 3
    current_typing_state = TYPING_COURSE if search_type == 'course' else TYPING_PROF
    success_listing_state = SELECTING_COURSE_RESULTS if search_type == 'course' else SELECTING_PROF_RESULTS
    item_name_plural = "courses" if search_type == 'course' else "professors"
    chat_id = update.effective_chat.id
    bot_prompt_message_id = context.user_data.get('original_message_id_for_edit')

    try:
        if update.message: await context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
    except Exception:
        pass

    if len(query_text) < min_len:
        error_text = (
            f"⚠️ Min {min_len} characters required for {search_type} search.\nPlease re-enter {search_type} name/code:")
        if bot_prompt_message_id:
            try:
                await context.bot.edit_message_text(chat_id=chat_id, message_id=bot_prompt_message_id, text=error_text,
                                                    reply_markup=get_cancel_keyboard(), parse_mode=ParseMode.MARKDOWN)
            except Exception:
                logger.info(f"_handle_search_text_input: Edit failed for len error. Sending new prompt.")
                sent_msg = await context.bot.send_message(chat_id, text=error_text, reply_markup=get_cancel_keyboard(),
                                                          parse_mode=ParseMode.MARKDOWN)
                context.user_data['original_message_id_for_edit'] = sent_msg.message_id
        else:
            logger.info(f"_handle_search_text_input: No bot_prompt_message_id for len error. Sending new prompt.")
            sent_msg = await context.bot.send_message(chat_id, text=error_text, reply_markup=get_cancel_keyboard(),
                                                      parse_mode=ParseMode.MARKDOWN)
            context.user_data['original_message_id_for_edit'] = sent_msg.message_id
        return current_typing_state

    status_text = f"⏳ Searching {item_name_plural} for '*{html.escape(query_text)}*'..."
    if not bot_prompt_message_id:
        logger.warning(
            "_handle_search_text_input: bot_prompt_message_id is missing before status update. Sending new status message.")
        sent_msg = await context.bot.send_message(chat_id, status_text, parse_mode=ParseMode.MARKDOWN)
        context.user_data['original_message_id_for_edit'] = sent_msg.message_id
        bot_prompt_message_id = sent_msg.message_id
    else:
        try:
            await context.bot.edit_message_text(chat_id=chat_id, message_id=bot_prompt_message_id, text=status_text,
                                                reply_markup=None, parse_mode=ParseMode.MARKDOWN)
        except Exception as e_edit_status:
            logger.warning(
                f"Failed to edit status message {bot_prompt_message_id}, sending new. Error: {e_edit_status}")
            sent_msg = await context.bot.send_message(chat_id, status_text, parse_mode=ParseMode.MARKDOWN)
            context.user_data['original_message_id_for_edit'] = sent_msg.message_id
            bot_prompt_message_id = sent_msg.message_id

    if not bot_prompt_message_id:
        logger.error("_handle_search_text_input: CRITICAL - No message ID to update with results.")
        await context.bot.send_message(chat_id, "A critical error occurred. Please try /start again.",
                                       reply_markup=None)
        return ConversationHandler.END

    try:
        results = await search_items_api(query=query_text, search_type=search_type, user_id=user.id if user else None)
        if not results:
            await context.bot.edit_message_text(chat_id=chat_id, message_id=bot_prompt_message_id,
                                                text=f"🤷 No {item_name_plural} matching '*{html.escape(query_text)}*'. Try again:",
                                                reply_markup=get_cancel_keyboard(), parse_mode=ParseMode.MARKDOWN)
            return current_typing_state

        list_type_key = "course_search" if search_type == 'course' else "prof_search"
        _clear_list_context(context, list_type_key)
        context.user_data[f'all_{list_type_key}_results'] = results
        context.user_data[f'current_{list_type_key}_page'] = 0
        context.user_data[f'last_search_query_{search_type}'] = query_text

        keyboard = create_search_results_keyboard(results, search_type, current_page=0)
        message_text = _get_search_list_text_template(item_name_plural, len(results), query_text, 1)
        await context.bot.edit_message_text(chat_id=chat_id, message_id=bot_prompt_message_id, text=message_text,
                                            reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        return success_listing_state
    except Exception as e:
        logger.error(f"Error during {search_type} search for '{query_text}': {e}", exc_info=True)
        handle_api_error(f"{search_type}_search", e, context, message_id_to_edit=bot_prompt_message_id,
                         chat_id=chat_id)  # Uses V2 for error
        _clear_list_context(context, "course_search" if search_type == 'course' else "prof_search")
        return ConversationHandler.END


async def handle_course_search_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _handle_search_text_input(update, context, 'course')


async def handle_prof_search_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _handle_search_text_input(update, context, 'prof')


async def select_item_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    callback_data = query.data
    user_id = update.effective_user.id if update.effective_user else None
    message_id_being_edited = query.message.message_id
    chat_id = query.message.chat_id
    logger.debug(f"select_item_callback: CB={callback_data}, MsgID={message_id_being_edited}")

    context.user_data.pop('selected_year', None);
    context.user_data.pop('selected_semester', None)
    _clear_list_context(context, 'year_semester_list')
    context.user_data.pop('last_plot_message_id', None);
    context.user_data.pop('last_bot_message_obj', None)

    if callback_data.startswith(PROF_SELECT_PREFIX):
        context.user_data.pop('selected_course', None)
        _clear_list_context(context, 'prof_course_list')

    context.user_data['original_message_id_for_edit'] = message_id_being_edited

    try:
        if callback_data.startswith(COURSE_SELECT_PREFIX):
            parts = callback_data[len(COURSE_SELECT_PREFIX):].split('|')
            selected_course_code = parts[0].strip()
            context.user_data['selected_course'] = selected_course_code
            is_prof_flow = (len(parts) > 2 and parts[1] == 'prof')
            search_mode = context.user_data.get('search_mode')

            if is_prof_flow:
                if search_mode != 'prof':
                    logger.warning(
                        f"Course selection for prof flow, but search_mode is '{search_mode}'. Expected 'prof'.")
                prof_id_str_cb = parts[2]
                if str(context.user_data.get('selected_prof_id')) != prof_id_str_cb:
                    raise ValueError("Professor ID mismatch when selecting course for a professor.")
            elif search_mode != 'course':
                logger.warning(f"Direct course selection, but search_mode is '{search_mode}'. Expected 'course'.")

            logger.info(f"User {user_id} selected COURSE '{selected_course_code}' (Search Mode: '{search_mode}')")
            prompt_msg = f"Course: **{html.escape(selected_course_code)}**.\n⏳ Fetching Year/Semester options..."
            identifier_for_ys_back_button = selected_course_code
            if search_mode == 'prof':
                prof_name = context.user_data.get('selected_prof_name', 'Selected Prof')
                prof_id = context.user_data.get('selected_prof_id')
                if not prof_id: raise ValueError("Prof ID missing in prof mode context for course selection.")
                identifier_for_ys_back_button = str(prof_id)
                prompt_msg = f"Prof: **{html.escape(prof_name)}**\nCourse: **{html.escape(selected_course_code)}**.\n⏳ Fetching offerings..."

            await query.edit_message_text(prompt_msg, reply_markup=None, parse_mode=ParseMode.MARKDOWN)

            terms_data_list = []
            if search_mode == 'prof':
                all_offerings_for_prof = context.user_data.get('all_prof_course_list_results')
                if not all_offerings_for_prof: raise ValueError(
                    "Full prof offering list ('all_prof_course_list_results') missing.")
                terms_data_list = [o for o in all_offerings_for_prof if
                                   o.get('course', {}).get('code') == selected_course_code]
            else:
                terms_data_list = await get_offerings_for_course_api(selected_course_code, user_id)

            if not terms_data_list:
                back_button_cb_data_no_terms = None
                back_button_text_no_terms = "⬅️ Back"
                target_back_state_no_terms = SELECTING_COURSE_RESULTS

                if search_mode == 'prof' and 'selected_prof_id' in context.user_data:
                    back_button_cb_data_no_terms = f"{BACK_TO_PROF_COURSE_LIST_PREFIX}{context.user_data['selected_prof_id']}"
                    back_button_text_no_terms = "⬅️ Back to Prof's Courses"
                    target_back_state_no_terms = SELECTING_COURSE_FOR_PROF
                elif search_mode == 'course':
                    back_button_cb_data_no_terms = BACK_TO_COURSE_SEARCH_LIST
                    back_button_text_no_terms = "⬅️ Back to Course Search"
                    target_back_state_no_terms = SELECTING_COURSE_RESULTS

                buttons_for_no_terms_kb = []
                if back_button_cb_data_no_terms:
                    buttons_for_no_terms_kb.append(
                        [InlineKeyboardButton(back_button_text_no_terms, callback_data=back_button_cb_data_no_terms)])
                buttons_for_no_terms_kb.append([InlineKeyboardButton("🔄 New Search", callback_data=BACK_TO_MAIN)])
                no_results_kb = InlineKeyboardMarkup(buttons_for_no_terms_kb)

                prof_msg_part = f" by Prof. {html.escape(context.user_data.get('selected_prof_name', ''))}" if search_mode == 'prof' else ""
                await query.edit_message_text(
                    f"🤷 No offerings found for **{html.escape(selected_course_code)}**{prof_msg_part}.",
                    reply_markup=no_results_kb, parse_mode=ParseMode.MARKDOWN)
                return target_back_state_no_terms

            context.user_data['all_year_semester_list_results'] = terms_data_list
            context.user_data['current_year_semester_list_page'] = 0
            context.user_data['current_ys_list_mode'] = search_mode
            context.user_data['current_ys_list_identifier'] = identifier_for_ys_back_button

            keyboard = create_year_semester_keyboard(terms_data_list, identifier_for_ys_back_button, mode=search_mode,
                                                     current_page=0)
            prof_name_text_for_template = context.user_data.get("selected_prof_name") if search_mode == 'prof' else None
            message_text = _get_year_semester_list_text_template(selected_course_code, len(terms_data_list), 1,
                                                                 prof_name_text_for_template)
            await query.edit_message_text(message_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
            return SELECTING_YEAR_SEMESTER

        elif callback_data.startswith(PROF_SELECT_PREFIX):
            selected_prof_id = int(callback_data[len(PROF_SELECT_PREFIX):])
            context.user_data['selected_prof_id'] = selected_prof_id
            context.user_data['search_mode'] = 'prof'
            prof_name = f"ID {selected_prof_id}"
            all_prof_results = context.user_data.get('all_prof_search_results', [])
            for item in all_prof_results:
                if item.get('id') == selected_prof_id: prof_name = item.get('name', prof_name); break
            context.user_data['selected_prof_name'] = prof_name
            logger.info(f"User {user_id} selected PROF: {prof_name} ({selected_prof_id})")

            await query.edit_message_text(f"Selected: **{html.escape(prof_name)}**.\n⏳ Fetching courses...",
                                          reply_markup=None, parse_mode=ParseMode.MARKDOWN)

            prof_offerings_raw = await get_offerings_for_prof_api(selected_prof_id, user_id)
            context.user_data['all_prof_course_list_results'] = prof_offerings_raw

            if not prof_offerings_raw:
                kb_no_offerings = InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back to Prof Search", callback_data=BACK_TO_PROF_SEARCH_LIST)],
                    [InlineKeyboardButton("🔄 New Search", callback_data=BACK_TO_MAIN)]
                ])
                await query.edit_message_text(f"🤷 No offerings recorded for **{html.escape(prof_name)}**.",
                                              reply_markup=kb_no_offerings, parse_mode=ParseMode.MARKDOWN)
                return SELECTING_PROF_RESULTS

            unique_courses_for_kb = []
            seen_course_codes = set()
            for offering in prof_offerings_raw:
                course = offering.get('course', {});
                course_code, course_name_val = course.get('code'), course.get('name')
                if course_code and isinstance(course_code, str) and (
                        course_code_stripped := course_code.strip()) and course_code_stripped not in seen_course_codes:
                    unique_courses_for_kb.append({'course_code': course_code_stripped, 'course_name': (
                        course_name_val.strip() if course_name_val and isinstance(course_name_val, str) else None)})
                    seen_course_codes.add(course_code_stripped)

            context.user_data['unique_courses_for_selected_prof_kb'] = unique_courses_for_kb

            if not unique_courses_for_kb:
                kb_no_distinct_courses = InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back to Prof Search", callback_data=BACK_TO_PROF_SEARCH_LIST)],
                    [InlineKeyboardButton("🔄 New Search", callback_data=BACK_TO_MAIN)]
                ])
                await query.edit_message_text(
                    f"🤷 Offerings found for **{html.escape(prof_name)}**, but couldn't identify distinct courses.",
                    reply_markup=kb_no_distinct_courses, parse_mode=ParseMode.MARKDOWN)
                return SELECTING_PROF_RESULTS

            context.user_data['current_prof_course_list_page'] = 0
            keyboard = create_prof_course_selection_keyboard(unique_courses_for_kb, str(selected_prof_id), 0)
            message_text = _get_prof_course_list_text_template(prof_name, len(unique_courses_for_kb), 1)
            await query.edit_message_text(message_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
            return SELECTING_COURSE_FOR_PROF
        else:
            raise ValueError(f"Unknown selection prefix in select_item_callback: {callback_data}")
    except Exception as e:
        logger.error(f"Error processing selection {callback_data}: {e}", exc_info=True)
        handle_api_error("select_item", e, context,  # Uses V2 for error
                         message_id_to_edit=context.user_data.get('original_message_id_for_edit'), chat_id=chat_id)
        return ConversationHandler.END


async def select_year_semester_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    logger.info(
        f"select_year_semester_callback: CB={query.data}, MsgID={query.message.message_id if query.message else 'N/A'}")
    await query.answer()
    user_id = update.effective_user.id if update.effective_user else None

    if not query.message:
        logger.error("select_year_semester_callback: query.message is None. Cannot proceed.")
        return ConversationHandler.END

    message_to_edit = query.message
    context.user_data['last_bot_message_obj'] = message_to_edit
    context.user_data['original_message_id_for_edit'] = message_to_edit.message_id

    try:
        if not query.data.startswith(YEAR_SEM_SELECT_PREFIX):
            raise ValueError(f"Invalid CB prefix for Y/S selection: {query.data}")
        payload = query.data[len(YEAR_SEM_SELECT_PREFIX):]
        parts = payload.split('|')
        if len(parts) != 4:
            raise ValueError(f"Incorrect CB parts for Y/S selection: {parts}, data: {query.data}")

        year_selected, semester_selected = parts[0], parts[1]
        context.user_data['selected_year'] = year_selected
        context.user_data['selected_semester'] = semester_selected
        course_code = context.user_data.get('selected_course')
        if not course_code:
            raise ValueError("'selected_course' missing from context for Y/S selection")

        logger.info(
            f"User {user_id} final selection: Crs:'{course_code}', Yr:'{year_selected}', Sem:'{semester_selected}'")

        await message_to_edit.edit_text(
            f"Selected: **{html.escape(course_code)} / {html.escape(year_selected)} ({html.escape(semester_selected)})**\n⏳ Fetching details...",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=None
        )

        offering_details = await get_offering_details_api(course_code, year_selected, semester_selected, user_id)
        if not offering_details or 'id' not in offering_details:
            logger.warning(f"Offering details 404/missing for {course_code}/{year_selected}/{semester_selected}.")
            current_ys_list_mode = context.user_data.get('current_ys_list_mode', 'course')
            current_ys_list_identifier = context.user_data.get('current_ys_list_identifier', course_code)
            all_terms_data_for_retry = context.user_data.get('all_year_semester_list_results', [])
            current_page_for_retry = context.user_data.get('current_year_semester_list_page', 0)

            retry_keyboard = create_year_semester_keyboard(
                all_terms_data_for_retry,
                identifier_for_back_button=current_ys_list_identifier,
                mode=current_ys_list_mode,
                current_page=current_page_for_retry
            )
            await message_to_edit.edit_text(
                f"❌ Could not find specific record for **{html.escape(course_code)} / {html.escape(year_selected)} ({html.escape(semester_selected)})**. Please select another from the list below, or go back.",
                reply_markup=retry_keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
            return SELECTING_YEAR_SEMESTER

        offering_id = offering_details['id']
        grade_payload = await get_grades_distribution_api(offering_id, user_id)
        if not grade_payload:
            logger.warning(f"Grade data 404/missing for offering {offering_id}.")
            current_ys_list_mode = context.user_data.get('current_ys_list_mode', 'course')
            current_ys_list_identifier = context.user_data.get('current_ys_list_identifier', course_code)
            all_terms_data_for_retry = context.user_data.get('all_year_semester_list_results', [])
            current_page_for_retry = context.user_data.get('current_year_semester_list_page', 0)

            retry_keyboard = create_year_semester_keyboard(
                all_terms_data_for_retry,
                identifier_for_back_button=current_ys_list_identifier,
                mode=current_ys_list_mode,
                current_page=current_page_for_retry
            )
            await message_to_edit.edit_text(
                f"❌ No grade data found for **{html.escape(course_code)} ({html.escape(year_selected)}-{html.escape(semester_selected)})**. Please select another from the list below, or go back.",
                reply_markup=retry_keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
            return SELECTING_YEAR_SEMESTER

        await display_grades_and_plot(update, context, grade_payload)  # Uses HTML
        return SHOWING_FINAL_GRADES

    except Exception as e:
        logger.error(f"Error processing Y/S selection '{query.data if query else 'N/A'}': {e}", exc_info=True)
        msg_id_for_err = context.user_data.get('original_message_id_for_edit',
                                               message_to_edit.message_id if message_to_edit else None)
        chat_id_for_err = update.effective_chat.id if update.effective_chat else None
        handle_api_error("select_year_semester", e, context, message_id_to_edit=msg_id_for_err,
                         chat_id=chat_id_for_err)  # Uses V2 for error
        return ConversationHandler.END


async def _handle_pagination_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, list_type_key: str,
                                      page_data_parts: List[str], keyboard_creation_func, text_template_func,
                                      current_listing_state: int, expected_cb_parts_len: int):
    query = update.callback_query
    await query.answer()
    logger.debug(f"Pagination CB: {query.data}, list_type: {list_type_key}, parts: {page_data_parts}")
    message_to_edit_id = query.message.message_id
    chat_id = query.message.chat_id
    context.user_data['original_message_id_for_edit'] = message_to_edit_id

    try:
        if len(page_data_parts) != expected_cb_parts_len:
            raise ValueError(
                f"Incorrect CB parts {len(page_data_parts)}, expected {expected_cb_parts_len} for {query.data}")

        new_page = int(page_data_parts[-1])
        current_page_for_display = new_page + 1

        all_results_primary_key = f'all_{list_type_key}_results'
        all_results_primary = context.user_data.get(all_results_primary_key)

        all_results_for_keyboard = all_results_primary
        kb_list_key_specific = None
        if list_type_key == "prof_course_list":
            kb_list_key_specific = 'unique_courses_for_selected_prof_kb'
            all_results_for_keyboard = context.user_data.get(kb_list_key_specific, all_results_primary)

        if all_results_primary is None:
            raise ValueError(f"Missing primary data '{all_results_primary_key}' for pagination of {list_type_key}")
        if kb_list_key_specific and all_results_for_keyboard is None:
            raise ValueError(f"Missing keyboard data '{kb_list_key_specific}' for pagination of {list_type_key}")

        context.user_data[f'current_{list_type_key}_page'] = new_page
        kb_args = []
        text_args_for_template = {'current_page_num': current_page_for_display}

        data_for_kb_creation = all_results_for_keyboard if all_results_for_keyboard is not None else all_results_primary

        if list_type_key == "course_search":
            kb_args = [data_for_kb_creation, 'course', new_page]
            text_args_for_template.update({'item_type': 'courses', 'count': len(all_results_primary),
                                           'query': context.user_data.get('last_search_query_course', '')})
        elif list_type_key == "prof_search":
            kb_args = [data_for_kb_creation, 'prof', new_page]
            text_args_for_template.update({'item_type': 'professors', 'count': len(all_results_primary),
                                           'query': context.user_data.get('last_search_query_prof', '')})
        elif list_type_key == "prof_course_list":
            prof_id_str = page_data_parts[0]
            kb_args = [data_for_kb_creation, prof_id_str, new_page]
            prof_name = context.user_data.get('selected_prof_name', f"ID {prof_id_str}")
            text_args_for_template.update({'prof_name': prof_name, 'count': len(data_for_kb_creation)})
        elif list_type_key == "year_semester_list":
            mode, identifier = page_data_parts[0], page_data_parts[1]
            kb_args = [all_results_primary, identifier, mode, new_page]
            course_code = context.user_data.get('selected_course', '?Crs?')
            prof_name_text = context.user_data.get("selected_prof_name") if mode == 'prof' else None
            text_args_for_template.update(
                {'course_code': course_code, 'count': len(all_results_primary), 'prof_name': prof_name_text})
        else:
            raise ValueError(f"Unknown list_type_key for pagination: {list_type_key}")

        new_keyboard = keyboard_creation_func(*kb_args)
        message_text = text_template_func(**text_args_for_template)

        await query.edit_message_text(text=message_text, reply_markup=new_keyboard, parse_mode=ParseMode.MARKDOWN)
        return current_listing_state
    except Exception as e:
        logger.error(f"Error handling pagination CB '{query.data}': {e}", exc_info=True)
        handle_api_error(f"pagination_{list_type_key}", e, context, message_id_to_edit=message_to_edit_id,
                         # Uses V2 for error
                         chat_id=chat_id)
        return ConversationHandler.END


# ... (All pagination callback handlers: page_course_search_results_callback, etc. would be here)
async def page_course_search_results_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        page_num_str = update.callback_query.data.split(PAGE_COURSE_SEARCH_RESULTS_PREFIX, 1)[1]
    except IndexError:
        logger.error(
            f"Bad CB data for page_course_search_results_callback: {update.callback_query.data}");
        return ConversationHandler.END
    return await _handle_pagination_callback(update, context, "course_search", [page_num_str],
                                             create_search_results_keyboard, _get_search_list_text_template,
                                             SELECTING_COURSE_RESULTS, 1)


async def page_prof_search_results_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        page_num_str = update.callback_query.data.split(PAGE_PROF_SEARCH_RESULTS_PREFIX, 1)[1]
    except IndexError:
        logger.error(
            f"Bad CB data for page_prof_search_results_callback: {update.callback_query.data}");
        return ConversationHandler.END
    return await _handle_pagination_callback(update, context, "prof_search", [page_num_str],
                                             create_search_results_keyboard, _get_search_list_text_template,
                                             SELECTING_PROF_RESULTS, 1)


async def page_prof_course_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        payload = update.callback_query.data.split(PAGE_PROF_COURSE_LIST_PREFIX, 1)[1]
        parts = payload.rsplit('_', 1)
        if len(parts) != 2: raise ValueError("Incorrect parts for prof course list pagination")
        prof_id_str, page_num_str = parts[0], parts[1]
    except (IndexError, ValueError) as e:
        logger.error(f"Bad CB data for page_prof_course_list_callback: {update.callback_query.data}. Error: {e}");
        return ConversationHandler.END
    return await _handle_pagination_callback(update, context, "prof_course_list", [prof_id_str, page_num_str],
                                             create_prof_course_selection_keyboard, _get_prof_course_list_text_template,
                                             SELECTING_COURSE_FOR_PROF, 2)


async def page_year_semester_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        payload = update.callback_query.data.split(PAGE_YEAR_SEMESTER_PREFIX, 1)[1]
        parts = payload.split('_')
        if len(parts) != 3: raise ValueError("Incorrect parts for Y/S list pagination")
    except (IndexError, ValueError) as e:
        logger.error(f"Bad CB data for page_year_semester_list_callback: {update.callback_query.data}. Error: {e}");
        return ConversationHandler.END
    return await _handle_pagination_callback(update, context, "year_semester_list", parts,
                                             create_year_semester_keyboard, _get_year_semester_list_text_template,
                                             SELECTING_YEAR_SEMESTER, 3)


# ... (All back button handlers: back_to_main_callback, etc. would be here)
async def back_to_main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info(
        f"--- back_to_main_callback EXECUTED by user {update.effective_user.id if update.effective_user else 'Unknown'} ---")  # <<< ADD THIS LOG
    query = update.callback_query
    user = update.effective_user
    chat_id = update.effective_chat.id

    logger.info(
        f"back_to_main_callback: User {user.id if user else 'Unknown'} triggered 'New Search' from chat {chat_id}.")

    if query:
        await query.answer("Starting new search...")
        try:
            if query.message and query.message.reply_markup:
                await query.edit_message_reply_markup(reply_markup=None)
                logger.debug(f"Removed keyboard from message {query.message.message_id} in back_to_main_callback.")
            elif query.message:
                logger.debug(
                    f"No reply_markup to remove from message {query.message.message_id} in back_to_main_callback.")
        except Exception as e_edit_markup:
            logger.warning(f"Could not remove keyboard from previous message in back_to_main_callback: {e_edit_markup}",
                           exc_info=True)

    context.user_data.clear()
    logger.debug("User data cleared by back_to_main_callback for new search.")

    user_first_name = user.first_name if user and user.first_name else "there"
    welcome_text = f"👋 Hi {user_first_name}!\nHow would you like to search?"
    start_keyboard = get_start_keyboard()

    try:
        sent_message = await context.bot.send_message(
            chat_id=chat_id,
            text=welcome_text,
            reply_markup=start_keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        context.user_data['original_message_id_for_edit'] = sent_message.message_id
        logger.debug(
            f"Sent new start message {sent_message.message_id} via back_to_main_callback, set as original_message_id_for_edit.")
    except Exception as e_send_start:
        logger.error(f"Failed to send new start message in back_to_main_callback: {e_send_start}", exc_info=True)
        return ConversationHandler.END  # error message via handle_api_error if that's how it's structured, or a direct message

    return SELECTING_ACTION


async def back_to_typing_course_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query;
    await query.answer("⬅️ Back")
    logger.info(f"User {update.effective_user.id if update.effective_user else 'Unknown'}: Back to typing course.")
    _clear_list_context(context, 'course_search')
    context.user_data.pop('selected_course', None);
    _clear_list_context(context, 'year_semester_list')
    context.user_data.pop('selected_year', None);
    context.user_data.pop('selected_semester', None)
    context.user_data.pop('last_plot_message_id', None);
    context.user_data.pop('last_bot_message_obj', None)
    context.user_data.pop('current_ys_list_mode', None);
    context.user_data.pop('current_ys_list_identifier', None)
    context.user_data['search_mode'] = 'course'
    prompt_text = "📚 OK. Re-enter **course code OR full/partial title**:"
    msg_id = query.message.message_id;
    chat_id = query.message.chat_id
    context.user_data['original_message_id_for_edit'] = msg_id
    try:
        await query.edit_message_text(prompt_text, reply_markup=get_cancel_keyboard(), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Error edit msg back_to_typing_course: {e}", exc_info=True)
        handle_api_error("back_to_typing_course", e, context, msg_id, chat_id)  # Uses V2 for error
        return ConversationHandler.END
    return TYPING_COURSE


async def back_to_typing_prof_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query;
    await query.answer("⬅️ Back")
    logger.info(f"User {update.effective_user.id if update.effective_user else 'Unknown'}: Back to typing professor.")
    _clear_list_context(context, 'prof_search');
    _clear_list_context(context, 'prof_course_list')
    context.user_data.pop('selected_prof_id', None);
    context.user_data.pop('selected_prof_name', None)
    context.user_data.pop('selected_course', None);
    _clear_list_context(context, 'year_semester_list')
    context.user_data.pop('selected_year', None);
    context.user_data.pop('selected_semester', None)
    context.user_data.pop('last_plot_message_id', None);
    context.user_data.pop('last_bot_message_obj', None)
    context.user_data.pop('current_ys_list_mode', None);
    context.user_data.pop('current_ys_list_identifier', None)
    context.user_data['search_mode'] = 'prof'
    prompt_text = "🧑‍🏫 OK. Re-enter **professor's name**:"
    msg_id = query.message.message_id;
    chat_id = query.message.chat_id
    context.user_data['original_message_id_for_edit'] = msg_id
    try:
        await query.edit_message_text(prompt_text, reply_markup=get_cancel_keyboard(), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Error edit msg back_to_typing_prof: {e}", exc_info=True)
        handle_api_error("back_to_typing_prof", e, context, msg_id, chat_id)  # Uses V2 for error
        return ConversationHandler.END
    return TYPING_PROF


async def back_to_prof_search_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query;
    await query.answer("⬅️ Back")
    logger.info(
        f"User {update.effective_user.id if update.effective_user else 'Unknown'}: Back to prof search results.")
    all_results = context.user_data.get('all_prof_search_results')
    page = context.user_data.get('current_prof_search_page', 0)
    query_text = context.user_data.get('last_search_query_prof', '')
    msg_id = query.message.message_id;
    chat_id = query.message.chat_id
    context.user_data['original_message_id_for_edit'] = msg_id

    if all_results is None:
        logger.warning("Prof search results context lost for back_to_prof_search_list. Re-prompting for prof name.");
        return await back_to_typing_prof_callback(update, context)

    context.user_data.pop('selected_prof_id', None);
    context.user_data.pop('selected_prof_name', None)
    _clear_list_context(context, 'prof_course_list')
    context.user_data.pop('selected_course', None);
    _clear_list_context(context, 'year_semester_list')
    context.user_data.pop('last_plot_message_id', None);
    context.user_data.pop('last_bot_message_obj', None)
    context.user_data.pop('current_ys_list_mode', None);
    context.user_data.pop('current_ys_list_identifier', None)
    try:
        keyboard = create_search_results_keyboard(all_results, 'prof', page)
        text = f"⬅️ Back to Prof Search Results for '*{html.escape(query_text)}*'.\nPage {page + 1}. Select:"
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Error edit msg back_to_prof_search_list: {e}", exc_info=True)
        handle_api_error("back_to_prof_search_list", e, context, msg_id, chat_id)  # Uses V2 for error
        return ConversationHandler.END
    return SELECTING_PROF_RESULTS


async def back_to_course_search_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query;
    await query.answer("⬅️ Back")
    logger.info(
        f"User {update.effective_user.id if update.effective_user else 'Unknown'}: Back to course search results.")
    all_results = context.user_data.get('all_course_search_results')
    page = context.user_data.get('current_course_search_page', 0)
    query_text = context.user_data.get('last_search_query_course', '')
    msg_id = query.message.message_id;
    chat_id = query.message.chat_id
    context.user_data['original_message_id_for_edit'] = msg_id

    if all_results is None:
        logger.warning(
            "Course search results context lost for back_to_course_search_list. Re-prompting for course name.");
        return await back_to_typing_course_callback(update, context)
    context.user_data.pop('selected_course', None);
    _clear_list_context(context, 'year_semester_list')
    context.user_data.pop('last_plot_message_id', None);
    context.user_data.pop('last_bot_message_obj', None)
    context.user_data.pop('current_ys_list_mode', None);
    context.user_data.pop('current_ys_list_identifier', None)
    try:
        keyboard = create_search_results_keyboard(all_results, 'course', page)
        text = f"⬅️ Back to Course Search Results for '*{html.escape(query_text)}*'.\nPage {page + 1}. Select:"
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Error edit msg back_to_course_search_list: {e}", exc_info=True)
        handle_api_error("back_to_course_search_list", e, context, msg_id, chat_id)  # Uses V2 for error
        return ConversationHandler.END
    return SELECTING_COURSE_RESULTS


async def back_to_prof_courses_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query;
    await query.answer("⬅️ Back")
    msg_id = query.message.message_id;
    chat_id = query.message.chat_id
    context.user_data['original_message_id_for_edit'] = msg_id
    try:
        prof_id_str = query.data.split(BACK_TO_PROF_COURSE_LIST_PREFIX, 1)[1];
        prof_id = int(prof_id_str)
    except (IndexError, ValueError) as e_parse_prof_id:
        logger.error(f"Invalid CB data for back_to_prof_courses: {query.data}. Error: {e_parse_prof_id}");
        return await back_to_main_callback(update, context)

    logger.info(
        f"User {update.effective_user.id if update.effective_user else 'Unknown'}: Back to course list for Prof ID {prof_id}.")

    selected_prof_id_ctx = context.user_data.get('selected_prof_id')
    if selected_prof_id_ctx != prof_id:
        logger.warning(
            f"Context mismatch in back_to_prof_courses. CB ProfID:{prof_id}, Ctx ProfID:{selected_prof_id_ctx}. Re-prompting for prof name.");
        return await back_to_typing_prof_callback(update, context)

    all_unique_courses = context.user_data.get('unique_courses_for_selected_prof_kb')
    page = context.user_data.get('current_prof_course_list_page', 0)
    prof_name = context.user_data.get('selected_prof_name', f"ID {prof_id}")

    if not all_unique_courses:
        logger.warning(
            f"Prof's course list (unique_courses_for_selected_prof_kb) missing for {prof_name}. Attempting to go back to prof search list.");
        return await back_to_prof_search_list_callback(update, context)

    context.user_data.pop('selected_course', None);
    _clear_list_context(context, 'year_semester_list')
    context.user_data.pop('last_plot_message_id', None);
    context.user_data.pop('last_bot_message_obj', None)
    context.user_data.pop('current_ys_list_mode', None);
    context.user_data.pop('current_ys_list_identifier', None)
    try:
        keyboard = create_prof_course_selection_keyboard(all_unique_courses, prof_id_str, page)
        text = f"⬅️ Back. Courses for **{html.escape(prof_name)}**.\nPage {page + 1}. Select:"
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Error edit msg back_to_prof_courses: {e}", exc_info=True)
        handle_api_error("back_to_prof_courses", e, context, msg_id, chat_id)  # Uses V2 for error
        return ConversationHandler.END
    return SELECTING_COURSE_FOR_PROF


async def back_to_year_sem_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    user = update.effective_user
    logger.info(
        f"back_to_year_sem_select_callback (CONVERSATION_HANDLER) for user {user.id if user else 'Unknown'}. CB: {query.data}")
    await query.answer("⬅️ Going back...")

    if not query.message:
        logger.error("back_to_year_sem_select_callback: query.message is None. Cannot proceed.")
        return ConversationHandler.END

    msg_id_to_edit = query.message.message_id
    chat_id = query.message.chat_id
    context.user_data['original_message_id_for_edit'] = msg_id_to_edit

    try:
        course_code_from_cb = query.data.split(BACK_TO_YEAR_SEM_SELECT_PREFIX, 1)[1]
        if not course_code_from_cb.strip():
            raise ValueError("Empty course code from callback in back_to_year_sem_select_callback.")
    except (IndexError, ValueError) as e_cb_parse:
        logger.error(f"Invalid CB for back_to_year_sem_select_callback: {query.data}. Error: {e_cb_parse}")
        await query.edit_message_text("Error: Invalid request data. Restarting...", reply_markup=get_restart_keyboard(),
                                      parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    selected_course_context = context.user_data.get('selected_course')
    all_terms_data = context.user_data.get('all_year_semester_list_results')
    overall_search_mode = context.user_data.get('current_ys_list_mode')
    identifier_for_ys_kb_back = context.user_data.get('current_ys_list_identifier')
    current_page = context.user_data.get('current_year_semester_list_page', 0)

    logger.debug(
        f"back_to_year_sem_select_callback (CONVO): CB_Crs='{course_code_from_cb}', Ctx_Crs='{selected_course_context}', "
        f"Ctx_Terms_Exist={all_terms_data is not None}, Original_Search_Mode='{overall_search_mode}', "
        f"IdentifierForYSBack='{identifier_for_ys_kb_back}', Ctx_Page={current_page}")

    if not (selected_course_context == course_code_from_cb and
            all_terms_data is not None and
            overall_search_mode is not None and
            identifier_for_ys_kb_back is not None):
        logger.warning(
            f"back_to_year_sem_select_callback (CONVO): Context seems stale/missing for {course_code_from_cb}. Sending new message to use /start.")
        await context.bot.send_message(chat_id,
                                       "Session data is incomplete for this action. Please use /start for a new search.",
                                       reply_markup=None, parse_mode=ParseMode.MARKDOWN)
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except:
            pass
        return ConversationHandler.END

    last_plot_msg_id = context.user_data.pop('last_plot_message_id', None)
    if last_plot_msg_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=last_plot_msg_id)
        except Exception as e_del:
            logger.warning(f"Failed to delete plot in back_to_year_sem_select_callback: {e_del}")

    keyboard = create_year_semester_keyboard(all_terms_data, identifier_for_ys_kb_back, overall_search_mode,
                                             current_page)

    prof_name_for_text = None
    if overall_search_mode == 'prof':
        prof_name_for_text = context.user_data.get('selected_prof_name')

    num_terms_for_text = len(all_terms_data) if isinstance(all_terms_data, list) else 0
    message_text = _get_year_semester_list_text_template(course_code_from_cb, num_terms_for_text, current_page + 1,
                                                         prof_name_for_text)

    try:
        await query.edit_message_text(
            f"⬅️ Returning to Year/Semester selection for **{html.escape(course_code_from_cb)}**.\n{message_text}",
            reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        logger.debug(f"back_to_year_sem_select_callback (CONVO) updated message {msg_id_to_edit} to show Y/S list.")
    except Exception as e:
        logger.error(f"Error editing message in back_to_year_sem_select_callback (CONVO): {e}", exc_info=True)
        await context.bot.send_message(chat_id, "Error returning to selection. Please use /start.",
                                       reply_markup=get_restart_keyboard(), parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END  # error message via handle_api_error if that's how it's structured, or a direct message

    return SELECTING_YEAR_SEMESTER


async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user;
    logger.info(f"User {user.id if user else 'Unknown'} canceled a conversation.")
    text = "✅ Process cancelled.\nUse /start for a new search\n\n or /feedback to leave feedback."
    last_plot_msg_id = context.user_data.pop('last_plot_message_id', None)
    if last_plot_msg_id and update.effective_chat:
        try:
            await context.bot.delete_message(update.effective_chat.id, last_plot_msg_id)
        except Exception:
            pass

    if update.callback_query:
        await update.callback_query.answer("Cancelled.")
        try:
            await update.callback_query.edit_message_text(text, reply_markup=None, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            if update.effective_chat:
                await update.effective_chat.send_message(text, reply_markup=None, parse_mode=ParseMode.MARKDOWN)
    elif update.message:
        await update.message.reply_text(text, reply_markup=None, parse_mode=ParseMode.MARKDOWN)

    context.user_data.clear()
    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message: return
    help_text = (
        "ℹ️ **IITK GRADIATOR BOT**\n\n"
        "Use /start to begin searching for course or professor grades.\n"
        "Use /feedback to inform admins about any bugs/errors/suggestions.\n\n"
        "🔄 New Search / Restart starts over.\n\n"
        "/help - This message\n"
        "/cancel - Stop current operation"
        
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)


async def simple_close_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query: return
    logger.info(
        f"simple_close_callback (global) triggered user:{update.effective_user.id if update.effective_user else 'Unknown'}")
    await query.answer("Session closed.")

    new_text_for_closed_message = "<i>This interaction has been closed. Use /start for a new search.</i>"  # HTML

    try:
        if query.message and query.message.reply_markup:
            await query.edit_message_text(text=new_text_for_closed_message, reply_markup=None,
                                          parse_mode=ParseMode.HTML)
        elif query.message:
            await query.edit_message_text(text=new_text_for_closed_message, parse_mode=ParseMode.HTML)
        else:
            logger.warning("simple_close_callback: query.message is None.")
    except Exception as e_edit:
        logger.warning(
            f"Could not edit message in simple_close_callback: {e_edit}. Original text might remain with buttons.")

    context.user_data.clear()


async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not update.message:
        if update.message: await update.message.reply_text("Could not identify user. Please try again.")
        logger.warning("/subscribe command received without user or message context.")
        return

    logger.info(f"/subscribe command from user {user.id}")
    try:
        api_response = await subscribe_user_api(
            tg_user_id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            username=user.username
        )
        if api_response and api_response.get('is_subscribed'):
            await update.message.reply_text("✅ You are now subscribed for updates!")
        elif api_response:
            logger.warning(
                f"Subscription for user {user.id} processed by API but 'is_subscribed' not true or missing. Response: {api_response}")
            await update.message.reply_text("✅ Your subscription status has been updated.")
        else:
            logger.error(f"Subscription API call failed or returned None for user {user.id}.")
            await update.message.reply_text(
                "⚠️ Could not process your subscription at this time. Please try again later.")
    except Exception as e:
        logger.error(f"Error in /subscribe command for user {user.id}: {e}", exc_info=True)
        # Error message via handle_api_error (which uses V2) or direct like this.
        # For consistency, if direct error messages are simple, this is okay.
        await update.message.reply_text("❌ An error occurred while trying to subscribe. Please try again later.")


async def unsubscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not update.message:
        if update.message: await update.message.reply_text("Could not identify user. Please try again.")
        logger.warning("/unsubscribe command received without user or message context.")
        return

    logger.info(f"/unsubscribe command from user {user.id}")
    try:
        api_response = await unsubscribe_user_api(tg_user_id=user.id)
        if api_response and api_response.get('is_subscribed') is False:
            await update.message.reply_text("🚫 You have been unsubscribed from updates.")
        elif api_response and "unsubscribed" in api_response.get("detail", "").lower():  # Check detail from API
            await update.message.reply_text("🚫 You have been unsubscribed from updates.")
        elif api_response:  # API responded but maybe status was already unsubscribed or other detail
            logger.warning(
                f"Unsubscription for user {user.id} processed by API but confirmation unclear. Response: {api_response}")
            await update.message.reply_text(
                api_response.get('detail',
                                 "⚠️ Could not confirm unsubscription. You might already be unsubscribed or an issue occurred."))
        else:  # No response from API
            logger.error(f"Unsubscription API call failed or returned None for user {user.id}.")
            await update.message.reply_text(
                "⚠️ Could not process your unsubscription at this time. Please try again later.")
    except Exception as e:
        logger.error(f"Error in /unsubscribe command for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text("❌ An error occurred while trying to unsubscribe. Please try again later.")


async def feedback_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    if not user or not update.message:
        logger.warning("feedback_start_command called without user or message.")
        return ConversationHandler.END

    logger.info(f"User {user.id} initiated /feedback command.")
    context.user_data.pop('feedback_message', None)
    context.user_data.pop('feedback_type', None)

    text = "Thank you for offering to provide feedback! 🙏\nWhat kind of feedback would you like to give?"
    await update.message.reply_text(text, reply_markup=get_feedback_type_keyboard())  # Standard Markdown
    return ASK_FEEDBACK_TYPE


async def feedback_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query or not query.data or not query.message:
        logger.warning("feedback_type_callback received invalid update or query object.")
        return ConversationHandler.END

    await query.answer()
    feedback_type = query.data
    context.user_data['feedback_type'] = feedback_type

    type_str_map = {
        FEEDBACK_TYPE_BUG: "bug report 🐛",
        FEEDBACK_TYPE_SUGGESTION: "suggestion 💡",
        FEEDBACK_TYPE_GENERAL: "general feedback 🗣️"
    }
    type_display = type_str_map.get(feedback_type, "feedback")

    await query.edit_message_text(
        f"Great! You've selected: **{type_display}**.\nPlease type out your message now.",  # Standard Markdown
        reply_markup=get_feedback_entry_cancel_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )
    return TYPING_FEEDBACK_MESSAGE


async def feedback_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        logger.warning("feedback_message_handler received update without message text.")
        return TYPING_FEEDBACK_MESSAGE

    feedback_text = update.message.text.strip()
    if not feedback_text:
        await update.message.reply_text(
            "Feedback message cannot be empty. Please type your feedback, or use the button to cancel and change type.",
            reply_markup=get_feedback_entry_cancel_keyboard()  # Standard Markdown
        )
        return TYPING_FEEDBACK_MESSAGE

    context.user_data['feedback_message'] = feedback_text
    feedback_type_val = context.user_data.get('feedback_type')

    type_str_map = {
        FEEDBACK_TYPE_BUG: "Bug Report",
        FEEDBACK_TYPE_SUGGESTION: "Suggestion",
        FEEDBACK_TYPE_GENERAL: "General Feedback"
    }
    type_display = type_str_map.get(feedback_type_val, "Feedback")

    # Using html.escape for the preview inside code block
    escaped_feedback_preview = html.escape(feedback_text[:1000])

    confirmation_text = (
        f"Thanks! Here's your **{type_display}**:\n\n"
        f"```\n{escaped_feedback_preview}\n```\n\n"  # Markdown for code block
        f"Shall I send this?"
    )
    await update.message.reply_text(
        confirmation_text,
        reply_markup=get_feedback_confirmation_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )
    return CONFIRM_FEEDBACK_SUBMISSION


async def feedback_confirm_send_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    user = update.effective_user

    if not query or not user:
        logger.warning("feedback_confirm_send_callback: Missing query or user object.")
        if query and query.message:  # Simple text, no special parsing needed for this error
            await query.edit_message_text("An error occurred. Please try /feedback again.")
        return ConversationHandler.END

    await query.answer()

    feedback_type = context.user_data.get('feedback_type', 'general')
    message_text = context.user_data.get('feedback_message')

    if not message_text:
        logger.error(f"User {user.id}: feedback_message missing from context in feedback_confirm_send_callback.")
        await query.edit_message_text(  # Simple text
            "Could not retrieve your feedback message. Please try starting the /feedback process again.",
            reply_markup=None
        )
        context.user_data.clear()
        return ConversationHandler.END

    await query.edit_message_text("⏳ Submitting your feedback...", reply_markup=None)  # Simple text
    api_response = None
    try:
        api_response = await submit_feedback_api(
            tg_user_id=user.id,
            feedback_type=feedback_type,
            message_text=message_text,
            username=user.username
        )
        if api_response:
            await query.edit_message_text("✅ Thank you! Your feedback has been submitted successfully.",  # Simple text
                                          reply_markup=None)
            logger.info(
                f"Feedback from user {user.id} (type: {feedback_type}) submitted successfully. API Response: {api_response}")

            ADMIN_CHANNEL_ID = os.getenv("TELEGRAM_ADMIN_CHANNEL_ID")
            if ADMIN_CHANNEL_ID:
                user_identifier = f"@{user.username}" if user.username else f"ID: {user.id}"
                # Critical: This message uses MARKDOWN_V2 and escapes user content
                admin_message = (
                    f"📝 *New Feedback Received*\n\n"
                    f"*User:* {escape_markdown_v2(user.full_name or '')} \\({escape_markdown_v2(user_identifier)}\\)\n"
                    f"*Type:* `{escape_markdown_v2(feedback_type)}`\n\n"
                    f"*Message:*\n{escape_markdown_v2(message_text)}"
                )
                try:
                    await context.bot.send_message(chat_id=ADMIN_CHANNEL_ID, text=admin_message,
                                                   parse_mode=ParseMode.MARKDOWN_V2)
                    logger.info(f"Feedback from {user.id} sent to admin channel {ADMIN_CHANNEL_ID}.")
                except Exception as e_admin:
                    logger.error(f"Failed to send feedback to admin channel {ADMIN_CHANNEL_ID}: {e_admin}",
                                 exc_info=True)
            else:
                logger.warning(
                    "TELEGRAM_ADMIN_CHANNEL_ID not set in .env. Cannot send admin notification for feedback.")
        else:  # API call returned None or non-truthy
            logger.error(f"Feedback submission API call failed or returned None for user {user.id}.")
            await query.edit_message_text(
                "❌ Could not submit feedback due to an API error\\. Please try again later\\.",  # Using V2 escape
                reply_markup=None, parse_mode=ParseMode.MARKDOWN_V2)
    except Exception as e:  # Exception during the API call itself
        logger.error(f"Error during feedback submission API call for user {user.id}: {e}", exc_info=True)
        await query.edit_message_text(
            "❌ An unexpected error occurred while submitting your feedback\\. Please try again\\.",  # Using V2 escape
            reply_markup=None, parse_mode=ParseMode.MARKDOWN_V2)

    context.user_data.pop('feedback_message', None)
    context.user_data.pop('feedback_type', None)
    return ConversationHandler.END


async def feedback_cancel_or_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query or not query.message:
        logger.warning("feedback_cancel_or_edit_callback: Missing query or message.")
        return ConversationHandler.END

    await query.answer()
    user_id = update.effective_user.id if update.effective_user else "Unknown"

    logger.info(f"User {user_id} triggered CANCEL_FEEDBACK (data: {query.data}). Resetting to ask feedback type.")
    await query.edit_message_text(  # Standard Markdown
        "Okay, let's restart the feedback process.\nWhat kind of feedback would you like to provide?",
        reply_markup=get_feedback_type_keyboard()
    )
    context.user_data.pop('feedback_message', None)
    context.user_data.pop('feedback_type', None)
    return ASK_FEEDBACK_TYPE


# logger = logging.getLogger(__name__)

# --- ADMIN IDS SETUP ---
ADMIN_USER_IDS_STR = os.getenv("TELEGRAM_ADMIN_IDS", "")
# === START DEBUG LINES ===
logger.info(f"HANDLERS.PY: Raw TELEGRAM_ADMIN_IDS from os.getenv: '{ADMIN_USER_IDS_STR}' (Type: {type(ADMIN_USER_IDS_STR)})")

parsed_ids = []
if ADMIN_USER_IDS_STR:
    try:
        parsed_ids = [int(admin_id.strip()) for admin_id in ADMIN_USER_IDS_STR.split(',') if admin_id.strip()]
    except ValueError as e:
        logger.error(f"HANDLERS.PY: ValueError converting admin ID to int. String was '{ADMIN_USER_IDS_STR}'. Error: {e}")

ADMIN_USER_IDS = parsed_ids
logger.info(f"HANDLERS.PY: Parsed ADMIN_USER_IDS list: {ADMIN_USER_IDS} (Type: {type(ADMIN_USER_IDS)})")

if not ADMIN_USER_IDS and ADMIN_USER_IDS_STR:
    logger.warning(f"HANDLERS.PY: TELEGRAM_ADMIN_IDS was '{ADMIN_USER_IDS_STR}' but parsed ADMIN_USER_IDS is empty. Check comma separation and ensure IDs are numeric.")
elif not ADMIN_USER_IDS_STR: # String itself was empty
    logger.warning("HANDLERS.PY: TELEGRAM_ADMIN_IDS environment variable is not set or is empty. Admin commands will not be restricted by user ID.")
# === END DEBUG LINES ===


def is_admin(user_id: int) -> bool:
    """Checks if the user ID belongs to an admin."""
    if not ADMIN_USER_IDS:  # If the list is empty, effectively no one is admin by ID check.
        return False
    return user_id in ADMIN_USER_IDS


async def block_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /block command for admins."""
    user = update.effective_user
    if not user or not is_admin(user.id):
        await update.message.reply_text("❌ You are not authorized to use this command\\.",  # Escaped .
                                        parse_mode=ParseMode.MARKDOWN_V2)
        return

    if not context.args or len(context.args) < 1:
        await update.message.reply_text("Usage: `/block <user_id_or_username> \\[reason\\]`",  # Escaped []
                                        parse_mode=ParseMode.MARKDOWN_V2)
        return

    target_user_identifier = context.args[0]
    reason = " ".join(context.args[1:]) if len(context.args) > 1 else None

    logger.info(f"Admin {user.id} attempting to block {target_user_identifier} with reason: {reason}")
    try:
        response = await set_user_block_status_api(target_user_identifier, block=True, reason=reason,
                                                   admin_user_id=user.id)
        if response and response.get('is_blocked'):
            blocked_reason = response.get('block_reason', 'N/A')
            await update.message.reply_text(
                f"✅ User `{escape_markdown_v2(target_user_identifier)}` has been blocked\\. Reason: {escape_markdown_v2(blocked_reason)}",
                # Escaped .
                parse_mode=ParseMode.MARKDOWN_V2)
        elif response:
            detail = response.get('detail', 'Unknown error')
            await update.message.reply_text(f"⚠️ Could not block user\\. API response: {escape_markdown_v2(detail)}",
                                            # Escaped .
                                            parse_mode=ParseMode.MARKDOWN_V2)
        else:
            await update.message.reply_text(
                "❌ Error blocking user via API\\. No response or failed response from API\\.",  # Escaped .
                parse_mode=ParseMode.MARKDOWN_V2)
    except Exception as e:
        logger.error(f"Error in block_user_command: {e}", exc_info=True)
        await update.message.reply_text("❌ An internal error occurred while trying to block the user\\.",  # Escaped .
                                        parse_mode=ParseMode.MARKDOWN_V2)


async def unblock_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /unblock command for admins."""
    user = update.effective_user
    if not user or not is_admin(user.id):
        await update.message.reply_text("❌ You are not authorized to use this command\\.",  # Escaped .
                                        parse_mode=ParseMode.MARKDOWN_V2)
        return

    if not context.args or len(context.args) != 1:
        await update.message.reply_text("Usage: `/unblock <user_id_or_username>`",
                                        parse_mode=ParseMode.MARKDOWN_V2)
        return

    target_user_identifier = context.args[0]
    logger.info(f"Admin {user.id} attempting to unblock {target_user_identifier}")
    try:
        response = await set_user_block_status_api(target_user_identifier, block=False, reason=None,
                                                   admin_user_id=user.id)
        if response and response.get('is_blocked') is False:
            await update.message.reply_text(
                f"✅ User `{escape_markdown_v2(target_user_identifier)}` has been unblocked\\.",  # Escaped .
                parse_mode=ParseMode.MARKDOWN_V2)
        elif response:
            detail = response.get('detail', 'Unknown error or user not found/already unblocked')
            await update.message.reply_text(f"⚠️ Could not unblock user\\. API response: {escape_markdown_v2(detail)}",
                                            # Escaped .
                                            parse_mode=ParseMode.MARKDOWN_V2)
        else:
            await update.message.reply_text(
                "❌ Error unblocking user via API\\. No response or failed response from API\\.",  # Escaped .
                parse_mode=ParseMode.MARKDOWN_V2)
    except Exception as e:
        logger.error(f"Error in unblock_user_command: {e}", exc_info=True)
        await update.message.reply_text("❌ An internal error occurred while trying to unblock the user\\.",  # Escaped .
                                        parse_mode=ParseMode.MARKDOWN_V2)


async def user_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /userstatus command for admins."""
    user = update.effective_user
    if not user or not is_admin(user.id):
        await update.message.reply_text("❌ You are not authorized to use this command\\.",  # Escaped .
                                        parse_mode=ParseMode.MARKDOWN_V2)
        return

    if not context.args or len(context.args) != 1:
        await update.message.reply_text("Usage: `/userstatus <user_id_or_username>`", parse_mode=ParseMode.MARKDOWN_V2)
        return

    target_user_identifier = context.args[0]
    logger.info(f"Admin {user.id} requesting status for {target_user_identifier}")
    try:
        status = await get_user_status_api(target_user_identifier, admin_user_id=user.id)
        if status:
            # Ensure all dynamic parts are escaped using escape_markdown_v2
            # Ensure static parts like 'N/A' or 'Yes'/'No' don't need escaping unless they contain special chars
            # Parentheses for username also need escaping
            reply = (
                f"Status for User: `{escape_markdown_v2(status.get('telegram_user_id', target_user_identifier))}` \\(@{escape_markdown_v2(status.get('username', 'N/A'))}\\)\n"
                f"Subscribed: {escape_markdown_v2('Yes' if status.get('is_subscribed') else 'No')}\n"
                f"Blocked: {escape_markdown_v2('Yes' if status.get('is_blocked') else 'No')}\n")
            if status.get('is_blocked'):
                reply += f"Reason: {escape_markdown_v2(status.get('block_reason', 'N/A'))}\nBlocked At: {escape_markdown_v2(status.get('blocked_at', 'N/A'))}"
            await update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN_V2)
        else:
            await update.message.reply_text(
                f"User `{escape_markdown_v2(target_user_identifier)}` not found or API error fetching status\\.",
                # Escaped .
                parse_mode=ParseMode.MARKDOWN_V2)
    except Exception as e:
        logger.error(f"Error in user_status_command: {e}", exc_info=True)
        await update.message.reply_text("❌ An internal error occurred while fetching user status\\.",  # Escaped .
                                        parse_mode=ParseMode.MARKDOWN_V2)



async def broadcast_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not is_admin(user.id):
        await update.message.reply_text("❌ You are not authorized for this command\\.", parse_mode=ParseMode.MARKDOWN_V2)
        return

    if not context.args:
        usage_text = "Usage: `/broadcast_admin <Your message here...>`\nUse HTML for formatting messages in the broadcast itself (e\\.g\\. `<b>bold</b>`)\\.\nTo create newlines in your broadcast message when typing this command, use `\\n` literally\\."
        await update.message.reply_text(usage_text, parse_mode=ParseMode.MARKDOWN_V2)
        return

    # Get the raw message string from the arguments
    message_to_broadcast_raw = " ".join(context.args)

    # Process typed '\n' (as literal backslash + n) into actual newline characters
    # This allows admins to type "\n" in their command to signify a newline.
    message_to_broadcast_processed = message_to_broadcast_raw.replace("\\n", "\n")

    # Simple validation for message length using the processed message
    if len(message_to_broadcast_processed) < 5: # Adjusted min length slightly
        await update.message.reply_text("⚠️ Broadcast message seems too short\\. Please provide a meaningful message\\.",
                                        parse_mode=ParseMode.MARKDOWN_V2)
        return

    logger.info(f"Admin {user.id} initiated /broadcast_admin. Processed msg: '{message_to_broadcast_processed[:50]}...'")

    # Preview for the "Queuing broadcast" message (using the processed message)
    preview_text_raw = message_to_broadcast_processed[:30].split('\n')[0] # Show only first line of preview if multi-line
    escaped_preview_for_mdv2 = escape_markdown_v2(preview_text_raw)
    ellipsis_mdv2 = "\\.\\.\\." if len(message_to_broadcast_processed) > 30 or '\n' in message_to_broadcast_processed[:30] else ""
    
    queuing_message = f"⏳ Queuing broadcast: \"_{escaped_preview_for_mdv2}{ellipsis_mdv2}_\""

    try:
        await update.message.reply_text(queuing_message, parse_mode=ParseMode.MARKDOWN_V2)
    except Exception as e_reply:
        logger.error(f"Error sending 'Queuing broadcast' message: {e_reply}", exc_info=True)
        await update.message.reply_text("Processing broadcast request...") # Fallback

    try:
        # Use the processed message when calling the API
        response = await initiate_broadcast_api(message_text=message_to_broadcast_processed, admin_user_id=user.id)
        
        if response and response.get('task_id'):
            await update.message.reply_text(f"✅ Broadcast successfully queued\\.\nTask ID: `{escape_markdown_v2(str(response['task_id']))}`",
                                            parse_mode=ParseMode.MARKDOWN_V2)
        else:
            api_error_detail_raw = response.get('detail', 'No specific detail from API.') if response else 'No response from API.'
            escaped_api_error_detail = escape_markdown_v2(api_error_detail_raw)
            await update.message.reply_text(
                f"⚠️ Could not queue broadcast via API\\. Error: {escaped_api_error_detail}",
                parse_mode=ParseMode.MARKDOWN_V2)
    except httpx.RequestError as e_req: # Catch network errors specifically
        logger.error(f"Network error calling initiate_broadcast_api from bot: {e_req}", exc_info=True)
        await update.message.reply_text("❌ Failed to send broadcast request due to a network connection error with the API\\.",
                                        parse_mode=ParseMode.MARKDOWN_V2)
    except Exception as e: # Catch other exceptions
        logger.error(f"Error calling initiate_broadcast_api from bot: {e}", exc_info=True)
        await update.message.reply_text("❌ Failed to send broadcast request due to an internal error\\.",
                                        parse_mode=ParseMode.MARKDOWN_V2)

