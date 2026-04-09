"""
Admin Router
All admin-only endpoints for user management, prompts, transactions, and system monitoring.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import StreamingResponse
from app.middleware.admin_auth import require_admin, get_request_ip
from app.services.admin_service import AdminService
from app.services.prompt_manager import PromptManager
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from uuid import UUID

router = APIRouter(prefix="/admin", tags=["admin"])
admin_service = AdminService()
prompt_manager = PromptManager()

# ============ REQUEST MODELS ============

class CreditAdjustment(BaseModel):
    amount: int = Field(..., description="Positive to add, negative to subtract")
    reason: str = Field(..., min_length=1, max_length=500)

class TierChange(BaseModel):
    new_tier: str = Field(..., description="Free, Basic, Standard, or Premium")

class BanRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)

class PromptCreate(BaseModel):
    prompt_text: str = Field(..., min_length=10)
    notes: Optional[str] = Field(None, max_length=1000)

class PromptTest(BaseModel):
    prompt_text: str = Field(..., min_length=10)
    sample_text: str = Field(..., max_length=5000)

class ManualCredit(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)

class DeleteAssignment(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)

class SettingUpdate(BaseModel):
    value: Dict

class UserUpdate(BaseModel):
    """Strict model for admin user updates. Only allow safe, known fields."""
    full_name: Optional[str] = Field(None, max_length=100)
    subscription_tier: Optional[str] = Field(None, description="Free, Basic, Standard, or Premium")
    word_balance: Optional[int] = Field(None, ge=0)
    grading_balance: Optional[int] = Field(None, ge=0)
    is_admin: Optional[bool] = None
    is_banned: Optional[bool] = None
    notes: Optional[str] = Field(None, max_length=500)

# ============ DASHBOARD ============

@router.get("/dashboard/stats")
async def get_dashboard_stats(admin=Depends(require_admin)):
    """Get overview statistics for admin dashboard"""
    return await admin_service.get_dashboard_stats()

# ============ USER MANAGEMENT ============

@router.get("/users")
async def list_users(
    page: int = 1,
    per_page: int = 50,
    search: Optional[str] = None,
    tier: Optional[str] = None,
    admin=Depends(require_admin)
):
    """List all users with pagination and filters"""
    return await admin_service.list_users(page, per_page, search, tier)

@router.get("/users/{user_id}")
async def get_user_details(user_id: UUID, admin=Depends(require_admin)):
    """Get detailed user information with statistics"""
    return await admin_service.get_user_details(str(user_id))

@router.post("/users/{user_id}/credits")
async def adjust_user_credits(
    user_id: UUID,
    data: CreditAdjustment,
    admin=Depends(require_admin)
):
    """Add or subtract word credits from a user"""
    return await admin_service.adjust_credits(
        str(user_id),
        data.amount,
        data.reason,
        admin["id"]
    )

@router.put("/users/{user_id}/tier")
async def change_user_tier(
    user_id: UUID,
    data: TierChange,
    admin=Depends(require_admin)
):
    """Change user's subscription tier"""
    return await admin_service.change_tier(
        str(user_id),
        data.new_tier,
        admin["id"]
    )

@router.post("/users/{user_id}/ban")
async def ban_user(
    user_id: UUID,
    data: BanRequest,
    admin=Depends(require_admin)
):
    """Ban a user from the platform"""
    return await admin_service.ban_user(
        str(user_id),
        data.reason,
        admin["id"]
    )

@router.put("/users/{user_id}")
async def update_user(
    user_id: UUID,
    data: UserUpdate,
    admin=Depends(require_admin)
):
    """Generic user update (for React Admin) — only allowed fields accepted"""
    return await admin_service.update_user(
        str(user_id),
        data.model_dump(exclude_none=True),
        admin["id"]
    )

# ============ HUMANIZER PROMPTS ============

@router.get("/prompts")
async def list_prompts(admin=Depends(require_admin)):
    """List all humanizer prompt versions"""
    return await prompt_manager.list_prompts()

@router.get("/prompts/active")
async def get_active_prompt(admin=Depends(require_admin)):
    """Get currently active humanizer prompt"""
    return await prompt_manager.get_active_prompt()

@router.get("/prompts/{prompt_id}")
async def get_prompt(prompt_id: str, admin=Depends(require_admin)):
    """Get specific prompt by ID"""
    return await prompt_manager.get_prompt_by_id(prompt_id)

@router.post("/prompts")
async def create_prompt(
    data: PromptCreate,
    admin=Depends(require_admin)
):
    """Create new humanizer prompt version"""
    return await prompt_manager.create_prompt(
        data.prompt_text,
        data.notes,
        admin["id"]
    )

@router.post("/prompts/{prompt_id}/activate")
async def activate_prompt(
    prompt_id: str,
    admin=Depends(require_admin)
):
    """Set a prompt as active (deactivates all others)"""
    return await prompt_manager.activate_prompt(prompt_id, admin["id"])

@router.delete("/prompts/{prompt_id}")
async def delete_prompt(
    prompt_id: str,
    admin=Depends(require_admin)
):
    """Delete a prompt version (only if not active)"""
    return await prompt_manager.delete_prompt(prompt_id, admin["id"])

@router.post("/prompts/test")
async def test_prompt(data: PromptTest, admin=Depends(require_admin)):
    """Test a prompt with sample text before saving"""
    return await prompt_manager.test_prompt(data.prompt_text, data.sample_text)

@router.get("/prompts/history")
async def get_prompt_history(
    limit: int = 20,
    admin=Depends(require_admin)
):
    """Get prompt version history"""
    return await prompt_manager.get_prompt_history(limit)

# ============ TRANSACTIONS ============

@router.get("/transactions")
async def list_transactions(
    page: int = 1,
    per_page: int = 50,
    status: Optional[str] = None,
    admin=Depends(require_admin)
):
    """List all payment transactions with filters"""
    return await admin_service.list_transactions(page, per_page, status)

@router.post("/transactions/{txn_id}/credit")
async def manual_credit_transaction(
    txn_id: UUID,
    data: ManualCredit,
    admin=Depends(require_admin)
):
    """Manually credit user for failed transaction"""
    return await admin_service.manual_credit(
        str(txn_id),
        data.reason,
        admin["id"]
    )

# ============ CONTENT MODERATION ============

@router.get("/assignments")
async def list_assignments(
    page: int = 1,
    per_page: int = 50,
    min_score: Optional[float] = None,
    flagged_only: bool = False,
    admin=Depends(require_admin)
):
    """List assignments for content moderation"""
    return await admin_service.list_assignments(page, per_page, min_score, flagged_only)

@router.get("/assignments/download")
async def download_assignments_zip(
    report_ids: List[str] = Query(...),
    admin=Depends(require_admin)
):
    """Download selected grading reports as a ZIP file"""
    zip_bytes = await admin_service.download_grading_reports_zip(report_ids)
    
    return StreamingResponse(
        iter([zip_bytes]), 
        media_type="application/zip",
        headers={
            "Content-Disposition": "attachment; filename=grading_reports_export.zip"
        }
    )

@router.delete("/assignments/{assignment_id}")
async def delete_assignment(
    assignment_id: UUID,
    data: DeleteAssignment,
    admin=Depends(require_admin)
):
    """Delete inappropriate assignment"""
    return await admin_service.delete_assignment(
        str(assignment_id),
        data.reason,
        admin["id"]
    )

# ============ SYSTEM MONITORING ============

@router.get("/system/health")
async def get_system_health(admin=Depends(require_admin)):
    """Get system health metrics"""
    return await admin_service.get_system_health()

@router.get("/system/logs")
async def get_admin_logs(
    level: str = "ERROR",
    limit: int = 100,
    admin=Depends(require_admin)
):
    """Get admin action logs"""
    return await admin_service.get_logs(level, limit)

# ============ SETTINGS ============

@router.get("/settings/{key}")
async def get_setting(key: str, admin=Depends(require_admin)):
    """Get system setting by key"""
    return await admin_service.get_setting(key)

@router.put("/settings/{key}")
async def update_setting(
    key: str,
    data: SettingUpdate,
    admin=Depends(require_admin)
):
    """Update system setting"""
    return await admin_service.update_setting(key, data.value, admin["id"])

@router.get("/settings")
async def list_all_settings(admin=Depends(require_admin)):
    """List all system settings"""
    # Get common settings
    settings = {}
    for key in ["rate_limits", "subscription_plans", "feature_flags"]:
        try:
            setting = await admin_service.get_setting(key)
            settings[key] = setting
        except:
            pass
    return settings
