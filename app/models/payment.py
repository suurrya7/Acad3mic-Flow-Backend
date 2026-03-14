from pydantic import BaseModel
from typing import Optional

class PaymentInitiateRequest(BaseModel):
    amount: float
    productinfo: str
    firstname: str
    email: str
    phone: Optional[str] = None

class PaymentInitiateResponse(BaseModel):
    txnid: str
    hash: str
    amount: float
    productinfo: str
    firstname: str
    email: str
    key: str
    surl: str
    furl: str

class UsageResponse(BaseModel):
    word_balance: int
    grading_balance: int = 0
    subscription_tier: str
