from datetime import datetime
from typing import List, Optional
import uuid
from pydantic import BaseModel

class UsageRecordResponse(BaseModel):
    id: str
    user_id: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: int
    status_code: int
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class PaginatedUsageResponse(BaseModel):
    records: List[UsageRecordResponse]
    total: int
    page: int
    limit: int

class ModelUsageStats(BaseModel):
    model: str
    provider: str
    request_count: int
    total_tokens: int
    avg_latency_ms: float

class AdminStatsResponse(BaseModel):
    total_requests: int
    total_tokens: int
    avg_latency_ms: float
    breakdown: List[ModelUsageStats]
