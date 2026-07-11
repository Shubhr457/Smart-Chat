from datetime import datetime
from typing import List

from pydantic import BaseModel, ConfigDict, Field


class ChatRoomCreate(BaseModel):
    name: str


class ChatRoomResponse(BaseModel):
    # validation_alias allows Pydantic to read "_id" from raw MongoDB dicts
    # while the serialized JSON output still uses the field name "id"
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(validation_alias="_id")
    name: str
    participants: List[str]
    created_at: datetime


class MessageResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(validation_alias="_id")
    room_id: str
    sender_email: str
    content: str
    timestamp: datetime
