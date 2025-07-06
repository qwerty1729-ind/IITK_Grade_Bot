import os
from celery import Celery
from dotenv import load_dotenv

#        Celery App Configuration 

# Load environment variables from the .env file in the project root.
# This is mainly for local development. In production, variables
# are usually set directly in the environment (e.g., by Docker Compose).
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Fetch the Redis URL from the environment. This is critical for Celery.
REDIS_URL = os.getenv("REDIS_URL")
if not REDIS_URL:
    # If the URL isn't set, the app can't connect to the broker.
    # It's better to fail loudly than to silently use a bad default.
    raise RuntimeError("CELERY_BROKER_URL is not set in the environment.")

# Create the Celery application instance.
# The name 'app' is important, as Celery's command-line tool looks for it by default.
app = Celery(
    'grade_bot_tasks',
    broker=REDIS_URL,
    backend=REDIS_URL,
    # Tell Celery where to find our task modules.
    include=['api.tasks']
)

#  Celery Settings 
# Configure Celery with settings for serialization, timezones, and task routing.
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Kolkata', # Set to your local timezone
    enable_utc=True,
    result_expires=3600, # Expire results after 1 hour
    broker_connection_retry_on_startup=True, # Important for robust startup in Docker
    
    # Route specific tasks to specific queues.
    task_routes={
        'api.tasks.send_broadcast_message': {'queue': 'broadcasts'},
    }
)

# This block allows the worker to be started directly for testing,
# though it's typically run via the Celery CLI.
if __name__ == '__main__':
    app.start()