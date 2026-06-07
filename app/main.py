from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.core.database import close_mongo_connection, connect_to_mongo
from app.routers import auth, health, protected


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect_to_mongo()
    yield
    # Shutdown
    await close_mongo_connection()


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(protected.router)


@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.PROJECT_NAME}"}
