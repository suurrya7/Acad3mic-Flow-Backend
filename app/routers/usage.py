from fastapi import APIRouter, Depends
from app.dependencies import get_current_user
from app.models.payment import UsageResponse

router = APIRouter(
    prefix="/usage",
    tags=["Usage"]
)

@router.get("/words", response_model=UsageResponse)
async def get_word_usage(current_user: dict = Depends(get_current_user)):
    user_profile = current_user["profile"]
    return {
        "word_balance": user_profile.get("word_balance", 0),
        "grading_balance": user_profile.get("grading_balance", 0),
        "subscription_tier": user_profile.get("subscription_tier", "Free")
    }
