from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from uuid import UUID

class ChatCreate(BaseModel):
    title: Optional[str] = "New Chat"

class MessageCreate(BaseModel):
    content: str
    document_ids: Optional[List[UUID]] = None  # File attachments

class MessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime

class ChatResponse(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime

class ChatHistoryResponse(ChatResponse):
    messages: List[MessageResponse]
