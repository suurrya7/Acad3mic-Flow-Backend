from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Dict
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(BASE_DIR, ".env")

class SubscriptionTier:
    FREE = "Free"
    BASIC = "Basic"
    STANDARD = "Standard"
    PREMIUM = "Premium"
    ULTIMATE = "Ultimate"

class TierAllocation:
    WORD_LIMITS = {
        SubscriptionTier.FREE: 3000,
        SubscriptionTier.BASIC: 20000,
        SubscriptionTier.STANDARD: 60000,
        SubscriptionTier.PREMIUM: 150000,
        SubscriptionTier.ULTIMATE: 500000
    }

    GRADING_LIMITS = {
        SubscriptionTier.FREE: 2,
        SubscriptionTier.BASIC: 7,
        SubscriptionTier.STANDARD: 15,
        SubscriptionTier.PREMIUM: 40,
        SubscriptionTier.ULTIMATE: 100
    }

    # Marking Classifications by Country
    MARKING_CLASSIFICATIONS = {
        "UK": {
            "First (1st)": (70, 100),
            "Upper Second (2:1)": (60, 69),
            "Lower Second (2:2)": (50, 59),
            "Third (3rd)": (40, 49),
            "Fail": (0, 39)
        },
        "Australia": {
            "High Distinction (HD)": (80, 100),
            "Distinction (D)": (70, 79),
            "Credit (C)": (60, 69),
            "Pass (P)": (50, 59),
            "Fail (N)": (0, 49)
        },
        "India": {
            "First Class with Distinction": (75, 100),
            "First Class": (60, 74),
            "Second Class": (50, 59),
            "Pass": (35, 49),
            "Fail": (0, 34)
        }
    }

class Settings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str
    SUPABASE_JWT_SECRET: str
    
    GEMINI_API_KEY: str
    GEMINI_MODEL_NAME: str = "models/gemini-3.1-flash-lite-preview"
    
    # Payment Conversion
    USD_TO_INR: float = 85.0 # Conversion rate for PayU
    
    PAYU_MERCHANT_KEY: str
    PAYU_SALT: str
    
    ENV: str = "development"
    PROD_ORIGINS: str = "http://localhost:5173,https://acad3micflow.space" # Comma separated origins for CORS
    API_BASE_URL: str = "http://localhost:8000"  # Base URL for webhooks and callbacks
    FRONTEND_URL: str = "http://localhost:5173"  # Used for password reset redirect links

    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

@lru_cache()
def get_settings():
    return Settings()
