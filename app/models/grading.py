from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID

class RubricCriterion(BaseModel):
    name: str
    weight: float
    description: Optional[str] = None
    descriptors: Optional[Dict[str, str]] = None # e.g. {"First": "Excellent criticality...", "Pass": "Basic understanding..."}

class GradingRubric(BaseModel):
    criteria: List[RubricCriterion]
    total_weight: float = 100.0

class GradingRequest(BaseModel):
    assignment_id: Optional[UUID] = None
    brief_text: str = Field(..., description="Assignment brief content")
    assignment_text: str = Field(..., description="Student's assignment content")
    country: str = Field("UK", description="University marking style (UK, Australia, India, etc.)")
    strictness: str = Field("Standard", description="Lenient, Standard, Very Strict")
    document_ids: Optional[List[UUID]] = [] # Legacy
    brief_document_ids: Optional[List[UUID]] = []
    assignment_document_ids: Optional[List[UUID]] = []

class GradingCriterionResult(BaseModel):
    criterion_name: str
    score: float
    max_score: float
    feedback: str
    strengths: List[str]
    weaknesses: List[str]

class GradingReport(BaseModel):
    id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    assignment_id: Optional[UUID] = None
    title: str
    
    # Input data reflected in report
    country: Optional[str] = None
    strictness: Optional[str] = None
    brief_text: Optional[str] = None
    assignment_text: Optional[str] = None
    rubric_json: Optional[Dict[str, Any]] = None
    brief_document_ids: Optional[List[UUID]] = []
    assignment_document_ids: Optional[List[UUID]] = []
    
    overall_score: float
    grade_classification: str
    criterion_results: List[GradingCriterionResult]
    examiner_comments: str
    improvement_suggestions: List[str]
    
    # Metadata/Stats
    word_count: int
    referencing_style_detected: str
    citation_count: int
    
    created_at: Optional[datetime] = None

class GradingResponse(BaseModel):
    report: GradingReport
    status: str = "completed"
