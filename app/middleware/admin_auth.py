"""
Admin Authentication Middleware
Verifies admin role from JWT token.
"""

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.db.supabase import get_supabase_admin
from app.dependencies import get_current_user
import logging

logger = logging.getLogger(__name__)
security = HTTPBearer()

async def require_admin(current_user: dict = Depends(get_current_user)):
    """
    Verify that the current user has admin privileges.
    Raises 403 if user is not an admin.
    """
    try:
        user_id = current_user.get("id")
        user_profile = current_user.get("profile")
        
        if not user_id or not user_profile:
            logger.error(f"require_admin: Missing user_id or profile in current_user context")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        
        # Check if user has admin flag from the profile already fetched by get_current_user
        is_admin = user_profile.get("is_admin", False)
        
        if not is_admin:
            logger.warning(f"Unauthorized admin access attempt by {user_id} ({current_user.get('email')})")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
        
        # Return user data with admin confirmation
        return {
            **current_user,
            "is_admin": True,
            "admin_email": user_profile.get("email")
        }

        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin auth verification failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify admin status"
        )

async def get_request_ip(request: Request) -> str:
    """Extract client IP from request"""
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
