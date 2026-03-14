from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from uuid import UUID

class DocumentResponse(BaseModel):
    id: UUID
    filename: str
    created_at: datetime

class AssignmentRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=200, description="Assignment topic (max 200 chars)")
    instructions: str = Field(..., min_length=1, max_length=5000, description="Assignment instructions (max 5000 chars)")
    document_ids: Optional[List[UUID]] = Field(default=[], max_items=10, description="Maximum 10 document references")

class AssignmentResponse(BaseModel):
    id: UUID
    title: str
    status: str
    output_text: Optional[str]
    created_at: datetime
