import logging
import os
from typing import List, Optional, Dict, Any
import httpx

logger = logging.getLogger(__name__)

# The base URL for your backend API, loaded from environment variables.
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

async def _make_api_request(
    method: str,
    endpoint: str,
    user_id: Optional[int] = None,
    params: Optional[Dict] = None,
    json_data: Optional[Dict] = None,
) -> Any:
    """
    A central function to make requests to the backend API.
    It handles setting headers, timeouts, and raising exceptions for bad responses.
    """
    headers = {"X-Telegram-User-ID": str(user_id)} if user_id else {}
    full_url = f"{API_BASE_URL}{endpoint}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.request(method, full_url, params=params, json=json_data, headers=headers)
            
            # Raise an exception for 4xx or 5xx status codes.
            # This is caught by the calling function in handlers.py.
            response.raise_for_status()
            
            # For 204 No Content, there's no JSON body.
            if response.status_code == 204:
                return None
            
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"API HTTP Error: {e.response.status_code} for {e.request.url} - Response: {e.response.text}")
            raise  # Re-raise the exception to be handled by the bot handlers
        except httpx.RequestError as e:
            logger.error(f"API Network Error: {e.__class__.__name__} for {e.request.url}")
            raise

# SECTION: Public API Functions

async def search_items(query: str, search_type: str, user_id: int) -> List[Dict]:
    """Searches for courses or professors."""
    endpoint = f"/search/{'course' if search_type == 'course' else 'prof'}"
    return await _make_api_request("GET", endpoint, user_id=user_id, params={"q": query})

async def get_offerings_for_course(course_code: str, user_id: int) -> List[Dict]:
    """Gets all offerings (terms) for a specific course."""
    return await _make_api_request("GET", f"/grades/offering/by_course/{course_code}", user_id=user_id)

async def get_grades_distribution(offering_id: int, user_id: int) -> Dict:
    """Gets the full grade report for a single offering."""
    return await _make_api_request("GET", f"/grades/offering/{offering_id}", user_id=user_id)

async def subscribe_user(tg_user_id: int, first_name: str, username: str) -> Dict:
    """Creates a new user or updates an existing one."""
    payload = {"telegram_user_id": tg_user_id, "first_name": first_name, "username": username}
    return await _make_api_request("POST", "/users/subscribe", user_id=tg_user_id, json_data=payload)

async def submit_feedback(tg_user_id: int, feedback_type: str, message_text: str) -> Dict:
    """Submits feedback from a user."""
    payload = {"telegram_user_id": tg_user_id, "feedback_type": feedback_type, "message_text": message_text}
    return await _make_api_request("POST", "/feedback/", user_id=tg_user_id, json_data=payload)

# SECTION: Admin API Functions

async def get_user_status(user_identifier: str, admin_user_id: int) -> Optional[Dict]:
    """Admin action to get a user's status."""
    return await _make_api_request("GET", f"/admin/users/{user_identifier}", user_id=admin_user_id)

async def set_user_block_status(user_identifier: str, block: bool, reason: str, admin_user_id: int) -> Optional[Dict]:
    """Admin action to block or unblock a user."""
    payload = {"is_blocked": block, "block_reason": reason}
    return await _make_api_request("PUT", f"/admin/users/{user_identifier}/block", user_id=admin_user_id, json_data=payload)

async def initiate_broadcast(message_text: str, admin_user_id: int) -> Optional[Dict]:
    """Admin action to start a broadcast task."""
    return await _make_api_request("POST", "/admin/broadcast/", user_id=admin_user_id, json_data={"message_text": message_text})