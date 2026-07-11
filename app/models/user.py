from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field

class UserModel(BaseModel):
    """Represents a User document stored in MongoDB."""

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    id: Optional[str] = Field(default=None, alias="_id")
    username: str
    email: EmailStr
    hashed_password: str
    role: str = "user"
    is_active: bool = True
    refresh_tokens: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @classmethod
    def from_mongo(cls, doc: dict) -> "UserModel":
        if doc is None:
            return None  # type: ignore[return-value]
        doc = dict(doc)
        oid = doc.pop("_id", None)
        if oid is not None:
            doc["_id"] = str(oid)
        return cls(**doc)
