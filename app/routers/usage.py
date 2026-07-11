from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.database import get_database
from app.routers.auth import get_current_user
from app.schemas.usage import (
    AdminStatsResponse,
    ModelUsageStats,
    PaginatedUsageResponse,
    UsageRecordResponse,
)

router = APIRouter(tags=["usage & analytics"])


def _doc_to_usage_response(doc: dict) -> UsageRecordResponse:
    """Convert raw MongoDB usage log doc to UsageRecordResponse schema."""
    return UsageRecordResponse(
        id=str(doc.get("_id", "")),
        user_id=doc["user_id"],
        provider=doc["provider"],
        model=doc["model"],
        prompt_tokens=doc["prompt_tokens"],
        completion_tokens=doc["completion_tokens"],
        total_tokens=doc["total_tokens"],
        latency_ms=doc["latency_ms"],
        status_code=doc["status_code"],
        error_message=doc.get("error_message"),
        created_at=doc["created_at"]
    )


@router.get("/usage", response_model=PaginatedUsageResponse, summary="Paginated usage history for current user")
async def get_usage(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    current_user = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Returns a paginated list of the caller's own usage records from MongoDB.
    """
    user_id_str = str(current_user["_id"])
    
    # Query logs with pagination
    cursor = db.usage_logs.find({"user_id": user_id_str}).sort("created_at", -1).skip((page - 1) * limit).limit(limit)
    records = await cursor.to_list(length=limit)
    
    # Count total documents
    total = await db.usage_logs.count_documents({"user_id": user_id_str})

    records_response = [_doc_to_usage_response(r) for r in records]

    return PaginatedUsageResponse(
        records=records_response,
        total=total,
        page=page,
        limit=limit
    )


@router.get("/admin/usage/stats", response_model=AdminStatsResponse, summary="Aggregated usage stats (all users)")
async def get_admin_stats(
    current_user = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Aggregated stats breakdown across all users. Admin role required.
    Uses MongoDB aggregation framework.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    # 1. Global statistics aggregation
    pipeline_global = [
        {
            "$group": {
                "_id": None,
                "total_requests": {"$sum": 1},
                "total_tokens": {"$sum": "$total_tokens"},
                "avg_latency": {"$avg": "$latency_ms"}
            }
        }
    ]
    
    cursor_global = db.usage_logs.aggregate(pipeline_global)
    global_results = await cursor_global.to_list(length=1)
    
    if global_results:
        g = global_results[0]
        total_requests = g.get("total_requests", 0)
        total_tokens = g.get("total_tokens", 0)
        avg_latency_ms = float(g.get("avg_latency", 0.0))
    else:
        total_requests = 0
        total_tokens = 0
        avg_latency_ms = 0.0

    # 2. Model/Provider breakdown aggregation
    pipeline_breakdown = [
        {
            "$group": {
                "_id": {"model": "$model", "provider": "$provider"},
                "request_count": {"$sum": 1},
                "total_tokens": {"$sum": "$total_tokens"},
                "avg_latency": {"$avg": "$latency_ms"}
            }
        }
    ]
    
    cursor_breakdown = db.usage_logs.aggregate(pipeline_breakdown)
    breakdown_results = await cursor_breakdown.to_list(length=100)
    
    breakdown = []
    for b in breakdown_results:
        grp = b["_id"]
        breakdown.append(
            ModelUsageStats(
                model=grp["model"],
                provider=grp["provider"],
                request_count=b["request_count"],
                total_tokens=b["total_tokens"],
                avg_latency_ms=float(b["avg_latency"])
            )
        )

    return AdminStatsResponse(
        total_requests=total_requests,
        total_tokens=total_tokens,
        avg_latency_ms=avg_latency_ms,
        breakdown=breakdown
    )
