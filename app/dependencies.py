from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.db.supabase import get_supabase_admin, get_supabase_user_client
from app.config import get_settings
from typing import Optional
import logging

settings = get_settings()

logger = logging.getLogger("auth")

security = HTTPBearer(auto_error=False)

from jose import jwt, JWTError

async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """
    Verifies the Supabase JWT locally for speed, then fetches user profile.
    Checks Authorization header first, then 'token' query parameter.
    """
    token = None
    if credentials:
        token = credentials.credentials
    else:
        # Fallback to query parameter (useful for window.open downloads)
        token = request.query_params.get("token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # 1. LOCAL JWT VERIFICATION (Optimized)
        try:
            # Note: Supabase JWTs are typically HS256 with the secret provided in your dashboard
            payload = jwt.decode(
                token, 
                settings.SUPABASE_JWT_SECRET, 
                algorithms=["HS256"],
                options={"verify_aud": False} # Supabase aud defaults to 'authenticated'
            )
            user_id = payload.get("sub")
            user_email = payload.get("email")
            
            if not user_id:
                raise JWTError("Token missing subject (user_id)")
                
        except JWTError as jwt_err:
            logger.warning(f"Local JWT verification failed: {str(jwt_err)}. Falling back to remote check...")
            # 2. FALLBACK TO REMOTE VERIFICATION (Legacy/Safety)
            user_client = get_supabase_user_client(token)
            user_response = user_client.auth.get_user(token)
            
            if not user_response or not user_response.user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication credentials",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            user_id = user_response.user.id
            user_email = user_response.user.email

        # 3. Fetch user profile (Always needed for balance/tier)
        supabase = get_supabase_admin()
        profile_response = supabase.table("user_profiles").select("*").eq("id", user_id).single().execute()
        
        if not profile_response.data:
            logger.warning(f"User profile missing for {user_id}")
            raise HTTPException(status_code=400, detail="User profile not found")

        return {
            "id": user_id,
            "email": user_email,
            "token": token,
            "profile": profile_response.data
        }
        
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        logger.error(f"Auth verification failed: {str(e)}")
        
        # Mask error details in production for security
        if settings.ENV == "production":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Could not validate credentials: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"},
            )

