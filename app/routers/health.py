import logging
from fastapi import APIRouter, HTTPException
from app.core.database import db_instance

router = APIRouter(tags=["Health"])
logger = logging.getLogger(__name__)

@router.get("/health")
async def health_check():
    health_status = {"status": "ok", "db": "disconnected"}
    
    try:
        if db_instance.client is not None:
            # Ping MongoDB database to verify connectivity
            await db_instance.client.admin.command('ping')
            health_status["db"] = "connected"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        health_status["status"] = "degraded"
        health_status["db"] = "error"
        raise HTTPException(status_code=503, detail=health_status)

    return health_status
