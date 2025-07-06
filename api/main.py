from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded

# Local Imports 
# Import the different API endpoint groups (routers)
from .routers import search, grades, users, feedback, admin_users, admin_broadcast

# Import utilities for rate limiting
from .utils.limiter import limiter, _rate_limit_exceeded_handler

# Import the Celery app instance (we alias it to avoid a name conflict with the FastAPI app)
from .celery_app import app as celery_app

#  FastAPI App Initialization 
app = FastAPI(
    title="IITK Grade Explorer API",
    description="API backend for fetching IITK course grade distributions.",
    version="0.1.0",
)

# Middleware & Exception Handlers 
# Set up the rate limiter to prevent abuse
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# API Routers 
# Register the different parts of our API
app.include_router(search.router)
app.include_router(grades.router)
app.include_router(users.router)
app.include_router(feedback.router)
app.include_router(admin_users.router)
app.include_router(admin_broadcast.router)

# Health Check Endpoint 
@app.get("/health", tags=["Health"])
async def health_check():
    """A simple endpoint to check if the API is up and running."""
    return {"status": "ok"}