import hashlib
from app.config import get_settings

settings = get_settings()

class PaymentService:
    def __init__(self):
        self.merchant_key = settings.PAYU_MERCHANT_KEY
        self.salt = settings.PAYU_SALT
        
    def generate_hash(self, data: dict) -> str:
        # Sequence: key|txnid|amount|productinfo|firstname|email|udf1|udf2|udf3|udf4|udf5|udf6|udf7|udf8|udf9|udf10|salt
        udfs = [data.get(f'udf{i}', '') for i in range(1, 11)]
        hash_string = f"{self.merchant_key}|{data['txnid']}|{data['amount']}|{data['productinfo']}|{data['firstname']}|{data['email']}|{'|'.join(udfs)}|{self.salt}"
        return hashlib.sha512(hash_string.encode('utf-8')).hexdigest()
        
    def verify_hash(self, data: dict, status: str) -> bool:
        # Sequence for verification: salt|status|udf10|udf9|udf8|udf7|udf6|udf5|udf4|udf3|udf2|udf1|email|firstname|productinfo|amount|txnid|key
        
        # Extract fields safely
        txnid = data.get('txnid', '')
        amount = data.get('amount', '')
        productinfo = data.get('productinfo', '')
        firstname = data.get('firstname', '')
        email = data.get('email', '')
        
        # Reverse UDF sequence for verification
        udfs_rev = [data.get(f'udf{i}', '') for i in range(10, 0, -1)]
        
        # salt|status|udf10|udf9|...|udf1|email|firstname|productinfo|amount|txnid|key
        hash_string = f"{self.salt}|{status}|{'|'.join(udfs_rev)}|{email}|{firstname}|{productinfo}|{amount}|{txnid}|{self.merchant_key}"
        
        calculated_hash = hashlib.sha512(hash_string.encode('utf-8')).hexdigest()
        received_hash = data.get('hash', '')
        
        # Use constant time comparison if possible, or just standard for now
        return calculated_hash.lower() == received_hash.lower()

payment_service = PaymentService()
