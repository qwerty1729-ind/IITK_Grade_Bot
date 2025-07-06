import asyncio
import os
import logging
from dataclasses import dataclass, asdict

from celery import shared_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from telegram import Bot as TelegramBot
from telegram.constants import ParseMode
from telegram.error import TelegramError, Forbidden, BadRequest

from .models import User

# --- Configuration ---
# Keep settings in one place, loaded from environment variables
DATABASE_URL = os.getenv("DATABASE_URL")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
logger = logging.getLogger(__name__)

# A simple dataclass to hold the results of our broadcast
@dataclass
class BroadcastReport:
    total_targeted: int = 0
    sent: int = 0
    blocked: int = 0
    failed: int = 0

# --- Helper Functions ---

async def get_subscribed_user_ids(session: AsyncSession) -> list[int]:
    """Fetches all active and subscribed user IDs from the database."""
    stmt = select(User.telegram_user_id).where(User.is_subscribed == True, User.is_blocked == False)
    result = await session.execute(stmt)
    return result.scalars().all()

async def send_message_to_user(bot: TelegramBot, user_id: int, message: str) -> str:
    """
    Tries to send a message to a single user and returns the status.
    Returns: "sent", "blocked", or "failed"
    """
    try:
        await bot.send_message(chat_id=user_id, text=message, parse_mode=ParseMode.HTML)
        return "sent"
    except Forbidden:
        logger.warning(f"User {user_id} has blocked the bot.")
        return "blocked"
    except (BadRequest, TelegramError) as e:
        logger.error(f"Failed to send to {user_id}: {e}")
        return "failed"

# --- Main Celery Task ---

# By making the task async, Celery handles the event loop for us.
@shared_task(bind=True, name="api.tasks.send_broadcast_message", max_retries=2, default_retry_delay=300)
async def send_broadcast_message(self, message_text: str):
    """
    A Celery task to send a message to all subscribed users.
    """
    task_id = self.request.id
    logger.info(f"Starting broadcast task {task_id}...")

    if not TELEGRAM_BOT_TOKEN or not DATABASE_URL:
        logger.error(f"Task {task_id} failed: Bot token or DB URL not configured.")
        return {"status": "error", "message": "Configuration missing."}

    # Create resources for this task run
    engine = create_async_engine(DATABASE_URL, pool_size=5)
    bot = TelegramBot(token=TELEGRAM_BOT_TOKEN)
    report = BroadcastReport()

    try:
        async with sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as session:
            user_ids = await get_subscribed_user_ids(session)
            report.total_targeted = len(user_ids)
            logger.info(f"Task {task_id}: Targeting {report.total_targeted} users.")

            for user_id in user_ids:
                status = await send_message_to_user(bot, user_id, message_text)
                if status == "sent":
                    report.sent += 1
                elif status == "blocked":
                    report.blocked += 1
                else:
                    report.failed += 1
                
                # A small delay to avoid hitting Telegram's rate limits
                await asyncio.sleep(0.05)

    except Exception as e:
        logger.error(f"Task {task_id} failed with a critical error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
    finally:
        # Clean up the database connection pool
        await engine.dispose()

    summary = f"Broadcast complete. Sent: {report.sent}, Blocked: {report.blocked}, Failed: {report.failed}"
    logger.info(f"Task {task_id}: {summary}")
    
    # Return a simple dictionary, which is easy for other services to use
    return asdict(report)