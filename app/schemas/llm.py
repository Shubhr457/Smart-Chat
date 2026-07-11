from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class MessageParam(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str
    provider: str = "openai"
    messages: List[MessageParam]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False

class ChatResponse(BaseModel):
    id: str
    provider: str
    model: str
    content: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    created_at: datetime

class ModelDetail(BaseModel):
    name: str
    provider: str

class ModelListResponse(BaseModel):
    models: List[ModelDetail]
