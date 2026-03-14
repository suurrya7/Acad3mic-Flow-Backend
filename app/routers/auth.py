from fastapi import APIRouter, Depends, HTTPException, Body
from app.dependencies import get_current_user
from app.db.supabase import get_supabase_admin, get_supabase_user_client
from app.config import get_settings
from pydantic import BaseModel
import logging

logger = logging.getLogger("auth")
settings = get_settings()

router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)

class LoginRequest(BaseModel):
    email: str
    password: str

class PasswordChangeRequest(BaseModel):
    new_password: str

class PasswordResetRequest(BaseModel):
    email: str

@router.post("/signup")
async def signup(credentials: LoginRequest):
    """
    Developer Helper: Sign up a new user.
    """
    supabase = get_supabase_admin()
    try:
        res = supabase.auth.sign_up({
            "email": credentials.email,
            "password": credentials.password
        })
        return {
            "message": "User created successfully. Check your email for confirmation if enabled, or just login if auto-confirm is on.",
            "user": res.user
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/login")
async def login(credentials: LoginRequest):
    """
    Developer Helper: Login to get Access Token for Swagger UI testing.
    PROD NOTE: Frontend should use Supabase JS SDK directly.
    """
    import time
    start_time = time.time()
    supabase = get_supabase_admin()
    try:
        logger.info(f"Attempting login for user: {credentials.email}")
        res = supabase.auth.sign_in_with_password({
            "email": credentials.email,
            "password": credentials.password
        })
        duration = time.time() - start_time
        logger.info(f"Login successful for {credentials.email} in {duration:.2f}s")
        return {
            "access_token": res.session.access_token,
            "token_type": "bearer",
            "user": res.user
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/me")
async def get_my_profile(current_user: dict = Depends(get_current_user)):
    """
    Returns the current authenticated user's profile.
    """
    return {
        "id": current_user["id"],
        "email": current_user["email"],
        "profile": current_user["profile"]
    }

@router.post("/change-password")
async def change_password(
    request: PasswordChangeRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Authenticated users can change their own password.
    Note: In production, Supabase JS SDK handles this client-side.
    This serves as a server-side alternative.
    """
    try:
        # Use the user's own client for password updates to avoid "User not allowed" admin errors.
        # get_supabase_user_client now initializes the auth session to avoid "Auth session missing!".
        user_client = get_supabase_user_client(current_user["token"])
        user_client.auth.update_user(
            {"password": request.new_password}
        )
        logger.info(f"Password successfully updated for user {current_user.get('id')}")
        return {"message": "Password updated successfully."}
    except Exception as e:
        logger.error(f"Password change failed for user {current_user.get('id')}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/reset-password")
async def reset_password(request: PasswordResetRequest):
    """
    Triggers a password reset email for the given email address.
    """
    supabase = get_supabase_admin()
    try:
        redirect_url = f"{settings.FRONTEND_URL}/reset-password"
        supabase.auth.reset_password_for_email(
            request.email,
            options={"redirect_to": redirect_url}
        )
        return {"message": "Password reset email sent."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


