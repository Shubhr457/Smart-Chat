from datetime import datetime
from typing import Dict, Optional
import uuid
from pydantic import BaseModel

class TemplateCreate(BaseModel):
    name: str
    body: str

class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    body: Optional[str] = None

class TemplateResponse(BaseModel):
    id: str
    owner_id: str
    name: str
    body: str
    is_deleted: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class TemplateRenderRequest(BaseModel):
    variables: Dict[str, str]

class TemplateRenderResponse(BaseModel):
    rendered: str
