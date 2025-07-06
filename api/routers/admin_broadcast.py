import logging
from fastapi import APIRouter, Depends, HTTPException, status

from ..tasks import send_broadcast_message
from ..schemas import BroadcastMessageRequest # Assuming you create this schema

# This router handles sending broadcast messages to all users.
# It should be protected by an admin-only API key in production.
router = APIRouter(
    prefix="/admin/broadcast",
    tags=["Admin - Broadcast"],
    # dependencies=[Depends(get_admin_api_key)], # TODO: Implement and enable security
)

logger = logging.getLogger(__name__)

@router.post("/", status_code=status.HTTP_202_ACCEPTED)
async def enqueue_broadcast(broadcast_data: BroadcastMessageRequest):
    """
    Accepts a message from an admin and queues it for broadcasting to all users.
    
    This endpoint returns immediately with a task ID, while the actual messages
    are sent in the background by a Celery worker.
    """
    logger.info(f"Admin request to enqueue broadcast: '{broadcast_data.message_text[:50]}...'")
    try:
        # .delay() sends the task to the Celery queue
        task = send_broadcast_message.delay(broadcast_data.message_text)
        logger.info(f"Broadcast message enqueued. Celery Task ID: {task.id}")
        return {"message": "Broadcast task successfully queued.", "task_id": task.id}
    except Exception as e:
        logger.error(f"Failed to enqueue broadcast task: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to connect to the message broker."
        )