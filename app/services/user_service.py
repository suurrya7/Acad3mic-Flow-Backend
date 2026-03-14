from fastapi import HTTPException
from app.db.supabase import get_supabase_admin
from app.utils.logger import logger
from app.config import SubscriptionTier, TierAllocation
import datetime

class UserService:
    def __init__(self):
        self.supabase = get_supabase_admin()

    def get_profile(self, user_id: str):
        response = self.supabase.table("user_profiles").select("*").eq("id", user_id).single().execute()
        return response.data

    def check_balance(self, user_id: str, required_words: int = 1) -> bool:
        # 1. Lazy Monthly Reset Check
        self.ensure_monthly_reset(user_id)
        
        # 2. Check Balance
        profile = self.get_profile(user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="User not found")
        
        balance = profile.get("word_balance", 0)
        return balance >= required_words

    def check_grading_balance(self, user_id: str) -> bool:
        """
        Checks if the user has enough grading checks remaining.
        """
        # 1. Lazy Monthly Reset Check
        self.ensure_monthly_reset(user_id)
        
        # 2. Check Grading Balance
        profile = self.get_profile(user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="User not found")
        
        balance = profile.get("grading_balance", 0)
        return balance > 0

    def ensure_monthly_reset(self, user_id: str):
        profile = self.get_profile(user_id)
        if not profile:
            return

        today = datetime.date.today()
        last_reset = profile.get("last_reset_date")
        
        # If last_reset is string, parse it. It might be returned as str by Supabase python client
        if isinstance(last_reset, str):
            try:
                last_reset = datetime.datetime.strptime(last_reset, "%Y-%m-%d").date()
            except ValueError:
                # Fallback if format is weird
                last_reset = today
        
        # If None, assume today (new user) or handle
        if not last_reset:
            last_reset = today
            
        # Check if month changed
        # Logic: If current year > last year OR (same year AND current month > last month)
        # Actually simpler: just if (today.year, today.month) > (last_reset.year, last_reset.month)
        # But even simpler: if they are different, and today is AFTER last_reset.
        # We assume time moves forward.
        if (today.year > last_reset.year) or (today.year == last_reset.year and today.month > last_reset.month):
            # RESET LOGIC
            tier = profile.get("subscription_tier", SubscriptionTier.FREE)
            base_allocation = TierAllocation.WORD_LIMITS.get(tier, TierAllocation.WORD_LIMITS[SubscriptionTier.FREE])
            grading_allocation = TierAllocation.GRADING_LIMITS.get(tier, TierAllocation.GRADING_LIMITS[SubscriptionTier.FREE])
            
            logger.info(f"Resetting monthly allowance for {user_id} (Tier: {tier})")
            
            self.supabase.table("user_profiles").update({
                "word_balance": base_allocation,
                "grading_balance": grading_allocation,
                "last_reset_date": str(today)
            }).eq("id", user_id).execute()

    def deduct_words(self, user_id: str, amount: int):
        """
        Atomically deduct words using Supabase RPC to prevent race conditions.
        Falls back to manual update if RPC is missing.
        """
        try:
            # Try atomic RPC first
            result = self.supabase.rpc('deduct_user_words', {
                'user_id_uuid': user_id,
                'amount': amount
            }).execute()
            
            return result.data
        except Exception as e:
            # Check if it's a "function not found" error (PGRST202)
            error_str = str(e)
            if "PGRST202" in error_str or "Could not find the function" in error_str:
                logger.warning(f"RPC 'deduct_user_words' not found. Falling back to manual update for user {user_id}")
                try:
                    # Fallback: Manual fetch and update (non-atomic but better than crashing)
                    profile = self.get_profile(user_id)
                    if not profile:
                        raise Exception("User not found during deduction fallback")
                    
                    old_balance = profile.get("word_balance", 0)
                    new_balance = max(0, old_balance - amount)
                    
                    self.supabase.table("user_profiles").update({
                        "word_balance": new_balance
                    }).eq("id", user_id).execute()
                    
                    return new_balance
                except Exception as ex:
                    logger.error(f"Manual deduction fallback failed: {str(ex)}")
            
            logger.error(f"Error deducting words: {error_str}")
            # Still raise to notify system of failure if fallback also fails or it's a different error
            raise HTTPException(status_code=500, detail="Failed to update word balance")

    def add_words(self, user_id: str, amount: int):
        """
        Atomically add words using Supabase RPC.
        Falls back to manual update if RPC is missing.
        """
        try:
            result = self.supabase.rpc('add_user_words', {
                'user_id_uuid': user_id,
                'amount': amount
            }).execute()
            
            return result.data
        except Exception as e:
            error_str = str(e)
            if "PGRST202" in error_str or "Could not find the function" in error_str:
                logger.warning(f"RPC 'add_user_words' not found. Falling back to manual update for user {user_id}")
                try:
                    profile = self.get_profile(user_id)
                    if not profile:
                        raise Exception("User not found during add_words fallback")
                    
                    old_balance = profile.get("word_balance", 0)
                    new_balance = old_balance + amount
                    
                    self.supabase.table("user_profiles").update({
                        "word_balance": new_balance
                    }).eq("id", user_id).execute()
                    
                    return new_balance
                except Exception as ex:
                    logger.error(f"Manual add_words fallback failed: {str(ex)}")
            
            logger.error(f"Error adding words: {error_str}")
            raise HTTPException(status_code=500, detail="Failed to update word balance")

    def deduct_grading_check(self, user_id: str):
        """
        Deducts one grading check from the user's balance.
        """
        try:
            # Try atomic RPC first
            result = self.supabase.rpc('deduct_grading_check', {
                'user_id_uuid': user_id
            }).execute()
            return result.data
        except Exception as e:
            error_str = str(e)
            if "PGRST202" in error_str or "Could not find the function" in error_str:
                logger.warning(f"RPC 'deduct_grading_check' not found for user {user_id}. Falling back to manual update.")
                try:
                    profile = self.get_profile(user_id)
                    old_balance = profile.get("grading_balance", 0)
                    new_balance = max(0, old_balance - 1)
                    self.supabase.table("user_profiles").update({
                        "grading_balance": new_balance
                    }).eq("id", user_id).execute()
                    return new_balance
                except Exception as ex:
                    logger.error(f"Manual grading check deduction fallback failed: {str(ex)}")
            
            logger.error(f"Error deducting grading check: {error_str}")
            # Non-fatal to grading flow if deduction fails but report is generated
            raise HTTPException(status_code=500, detail="Failed to update grading balance")


user_service = UserService()
