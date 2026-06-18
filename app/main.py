from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.database import connect_to_mongo, close_mongo_connection
from app.core.rate_limiter import limiter
from app.routers import auth, health, chat, template, usage


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logging or prep
    print(f"Starting {settings.PROJECT_NAME} backend...")
    await connect_to_mongo()
    yield
    # Shutdown logging or cleanup
    print(f"Stopping {settings.PROJECT_NAME} backend...")
    await close_mongo_connection()


async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Custom rate limit handler matching BRD AC-05 requirements."""
    retry_after = getattr(exc, "retry_after", 60)
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "retry_after_seconds": retry_after
        },
        headers={"Retry-After": str(retry_after)}
    )


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

# Register slowapi rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, custom_rate_limit_handler)

# Include API Routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(template.router)
app.include_router(usage.router)


@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.PROJECT_NAME}"}
