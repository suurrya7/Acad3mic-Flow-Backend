import logging
import sys
from logging.handlers import RotatingFileHandler
from pythonjsonlogger import jsonlogger
from app.config import get_settings

settings = get_settings()

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter to add standard fields"""
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        log_record['environment'] = settings.ENV

class SanitizedLogger(logging.Logger):
    """Logger that sanitizes sensitive AI model information"""
    def _log(self, level, msg, args, exc_info=None, extra=None, stack_info=False, stacklevel=1):
        # List of forbidden terms to mask
        forbidden_terms = ["Gemini", "Google", "Flash", "gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.5-flash", "gemini-flash"]
        
        if isinstance(msg, str):
            for term in forbidden_terms:
                msg = msg.replace(term, "***AI_MODEL***")
                
        super()._log(level, msg, args, exc_info, extra, stack_info, stacklevel)

# Configure handlers
handlers = []

# Console handler (always present)
console_handler = logging.StreamHandler(sys.stdout)
if settings.ENV == "production":
    console_handler.setFormatter(CustomJsonFormatter())
else:
    console_handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ))
handlers.append(console_handler)

# File handler for production (with rotation)
if settings.ENV == "production":
    try:
        import os
        os.makedirs('logs', exist_ok=True)
        file_handler = RotatingFileHandler(
            'logs/app.log',
            maxBytes=50*1024*1024,  # 50MB
            backupCount=5
        )
        file_handler.setFormatter(CustomJsonFormatter())
        handlers.append(file_handler)
    except Exception as e:
        print(f"Warning: Could not create file handler: {e}")

# Configure logging
logging.basicConfig(
    level=logging.INFO if settings.ENV == "production" else logging.DEBUG,
    handlers=handlers
)

# Replace default logger class
logging.setLoggerClass(SanitizedLogger)
logger = logging.getLogger("acad3mic-flow")
