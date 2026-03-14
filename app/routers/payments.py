from fastapi import APIRouter, Depends, HTTPException, Request, Form
from app.dependencies import get_current_user
from app.services.payment_service import payment_service
from app.db.supabase import get_supabase_admin
from app.models.payment import PaymentInitiateRequest, PaymentInitiateResponse
from app.config import get_settings, SubscriptionTier, TierAllocation
from uuid import uuid4
import logging

logger = logging.getLogger("payments")
settings = get_settings()

router = APIRouter(
    prefix="/payments",
    tags=["Payments"]
)

@router.post("/payu/create-order", response_model=PaymentInitiateResponse)
async def create_payu_order(
    request: PaymentInitiateRequest,
    current_user: dict = Depends(get_current_user)
):
    supabase = get_supabase_admin()
    user_id = current_user["id"]
    
    # 1. Generate Transaction ID
    txnid = str(uuid4().hex)[:20] # PayU txnids are usually strings
    
    # 2. Validate payment amount (strict validation for security)
    VALID_PLANS = {
        699: TierAllocation.WORD_LIMITS[SubscriptionTier.BASIC],
        1499: TierAllocation.WORD_LIMITS[SubscriptionTier.STANDARD],
        2999: TierAllocation.WORD_LIMITS[SubscriptionTier.PREMIUM],
        5999: TierAllocation.WORD_LIMITS[SubscriptionTier.ULTIMATE]
    }
    
    amount = float(request.amount)
    if amount not in VALID_PLANS:
        raise HTTPException(
            status_code=400,
            detail="Invalid plan amount. Valid amounts: 699, 1499, 2999"
        )
    
    words_to_add = VALID_PLANS[amount]
    
    # 3. Create Transaction Record (Pending)
    data = {
        "user_id": user_id,
        "amount": amount,
        "words_purchased": words_to_add,
        "status": "pending",
        "provider_ref": txnid
    }
    supabase.table("transactions").insert(data).execute()
    
    # 4. Generate Hash
    hash_data = {
        "txnid": txnid,
        "amount": str(int(amount)),
        "productinfo": request.productinfo,
        "firstname": request.firstname,
        "email": request.email
    }
    
    payment_hash = payment_service.generate_hash(hash_data)
    
    # 5. Return params for frontend form submission
    return {
        "txnid": txnid,
        "hash": payment_hash,
        "amount": request.amount,
        "productinfo": request.productinfo,
        "firstname": request.firstname,
        "email": request.email,
        "key": settings.PAYU_MERCHANT_KEY,
        "surl": f"{settings.API_BASE_URL}/payments/payu/webhook",  # Dynamic webhook URL
        "furl": f"{settings.API_BASE_URL}/payments/payu/webhook"
    }

@router.post("/payu/webhook")
async def payu_webhook(request: Request):
    """
    Handle PayU Callback.
    Note: PayU sends data as Form Data.
    """
    form_data = await request.form()
    data = dict(form_data)
    
    status = data.get("status")
    txnid = data.get("txnid")
    
    if not txnid:
        return {"status": "failed", "message": "No txnid"}

    supabase = get_supabase_admin()
    
    # 1. Verify Hash
    if not payment_service.verify_hash(data, status):
        logger.error(f"Hash verification failed for txn {txnid}")
        return {"status": "failed", "message": "Invalid Hash"}
        
    # 2. Get Transaction from DB
    txn_res = supabase.table("transactions").select("*").eq("provider_ref", txnid).single().execute()
    if not txn_res.data:
        logger.error(f"Transaction not found for {txnid}")
        return {"status": "failed", "message": "Transaction not found"}
    
    txn = txn_res.data
    user_id = txn["user_id"]
    words_to_add = txn["words_purchased"]

    # IDEMPOTENCY GUARD: If already processed, return success silently.
    # This prevents double-crediting if PayU retries the webhook.
    if txn.get("status") == "success":
        logger.info(f"Webhook replay detected for already-processed txn {txnid}. Ignoring.")
        return {"status": "success"}

    if status == "success":
        # 3. Update Transaction Status
        supabase.table("transactions").update({"status": "success"}).eq("id", txn["id"]).execute()

        # 4. Credit Words to User — use atomic RPC to prevent race conditions
        try:
            supabase.rpc("add_user_words", {
                "user_uuid": user_id,
                "words_to_add": words_to_add
            }).execute()
        except Exception as e:
            # Fallback: non-atomic update (better than losing the credit)
            logger.error(f"RPC credit failed for {user_id}, falling back to manual update: {e}")
            profile_res = supabase.table("user_profiles").select("word_balance").eq("id", user_id).single().execute()
            current_balance = profile_res.data.get("word_balance", 0)
            supabase.table("user_profiles").update({"word_balance": current_balance + words_to_add}).eq("id", user_id).execute()

        logger.info(f"Credited {words_to_add} words to user {user_id} for txn {txnid}")
        return {"status": "success"}

    else:
        supabase.table("transactions").update({"status": "failed"}).eq("id", txn["id"]).execute()
        return {"status": "failed"}
