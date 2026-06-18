from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

class PromptTemplateModel(BaseModel):
    """Represents a Prompt Template document stored in MongoDB."""

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    id: Optional[str] = Field(default=None, alias="_id")
    owner_id: str
    name: str
    body: str
    is_deleted: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @classmethod
    def from_mongo(cls, doc: dict) -> "PromptTemplateModel":
        if doc is None:
            return None  # type: ignore[return-value]
        doc = dict(doc)
        oid = doc.pop("_id", None)
        if oid is not None:
            doc["_id"] = str(oid)
        return cls(**doc)


class UsageLogModel(BaseModel):
    """Represents a Usage Log document stored in MongoDB."""

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    id: Optional[str] = Field(default=None, alias="_id")
    user_id: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: int
    status_code: int
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @classmethod
    def from_mongo(cls, doc: dict) -> "UsageLogModel":
        if doc is None:
            return None  # type: ignore[return-value]
        doc = dict(doc)
        oid = doc.pop("_id", None)
        if oid is not None:
            doc["_id"] = str(oid)
        return cls(**doc)
