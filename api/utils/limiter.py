from slowapi import Limiter
from starlette.requests import Request

def get_identifier(request: Request) -> str:
    """
    Determines the unique identifier for a request for rate limiting.

    It prioritizes the custom 'X-Telegram-User-ID' header, which should be
    sent by the bot. If that's not present, it falls back to the user's IP address,
    handling cases where the app is behind a proxy.
    """
    # The bot should send the user's ID in this header
    telegram_user_id = request.headers.get("x-telegram-user-id")
    if telegram_user_id:
        return telegram_user_id

    # If the app is behind a proxy (like Nginx), the real IP is in this header
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # The header can contain a list of IPs; the first one is the client's
        return forwarded_for.split(",")[0].strip()

    # As a last resort, get the direct client IP from the request
    return request.client.host

# Limiter Initialization 

# Create the rate limiter instance that will be used by the app.
# It uses our custom function to identify each user.
# Note: By default, this stores rate limits in memory. For a real multi-worker
# setup, you would point this to a Redis instance.
# e.g., storage_uri="redis://redis:6379"
limiter = Limiter(key_func=get_identifier)