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

class ProfileUpdateRequest(BaseModel):
    writing_profile: dict = None

@router.patch("/me")
async def update_my_profile(
    request: ProfileUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Update the current user's profile settings (like writing_profile).
    """
    supabase = get_supabase_admin()
    user_id = current_user["id"]
    
    update_data = {}
    if request.writing_profile is not None:
        update_data["writing_profile"] = request.writing_profile
        
    if not update_data:
        return {"message": "No fields to update."}
        
    try:
        res = supabase.table("user_profiles").update(update_data).eq("id", user_id).execute()
        if not res.data:
            raise HTTPException(status_code=400, detail="Failed to update profile.")
        return {"message": "Profile updated successfully.", "profile": res.data[0]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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

class ReferralRequest(BaseModel):
    code: str

@router.post("/referral")
async def apply_referral_code(
    request: ReferralRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Applies a referral code.
    If valid, grants 2000 free words to both the referee (current user) and referrer.
    """
    supabase = get_supabase_admin()
    user_id = current_user["id"]
    code = request.code.strip()

    # 1. Check if user already used a referral
    profile_res = supabase.table("user_profiles").select("referred_by, referral_code").eq("id", user_id).single().execute()
    if not profile_res.data:
        raise HTTPException(status_code=404, detail="User profile not found")
        
    my_profile = profile_res.data
    if my_profile.get("referred_by"):
        raise HTTPException(status_code=400, detail="You have already claimed a referral code.")
        
    if my_profile.get("referral_code") == code:
        raise HTTPException(status_code=400, detail="You cannot apply your own referral code.")

    # 2. Find the referrer
    referrer_res = supabase.table("user_profiles").select("id, word_balance, referral_rewards_given").eq("referral_code", code).execute()
    if not referrer_res.data:
        raise HTTPException(status_code=400, detail="Invalid referral code.")
        
    referrer = referrer_res.data[0]
    referrer_id = referrer["id"]
    referrer_rewards = referrer.get("referral_rewards_given") or 0

    if referrer_rewards >= 5:
        raise HTTPException(status_code=400, detail="This referral code has reached its maximum usage limit.")

    # 3. Apply rewards
    from app.services.user_service import user_service
    
    try:
        # Give current user (referee) 2000 words + set referred_by
        user_service.add_words(user_id, 2000)
        supabase.table("user_profiles").update({"referred_by": code}).eq("id", user_id).execute()
        
        # Give referrer 2000 words + increment rewards count
        user_service.add_words(referrer_id, 2000)
        supabase.table("user_profiles").update({"referral_rewards_given": referrer_rewards + 1}).eq("id", referrer_id).execute()
        
    except Exception as e:
        logger.error(f"Error applying referral rewards: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to apply referral code rewards.")

    return {"message": "Referral code applied! You gained 2000 free words."}


