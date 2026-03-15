from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from app.routers import auth, chats, assignments, documents, payments, usage, admin, admin_blog, blog
from app.config import get_settings
from fastapi.responses import JSONResponse
from app.limiter import limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from contextvars import ContextVar
import logging
import uuid
import asyncio

settings = get_settings()
logger = logging.getLogger("main")

# Request ID context for tracing
request_id_contextvar = ContextVar("request_id", default=None)

app = FastAPI(
    title="Acad3mic-Flow AI",
    version="1.0.0",
    docs_url="/docs" if settings.ENV == "development" else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.ENV == "development" else None
)

# Attach limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Configuration
origins = []
if settings.ENV == "development":
    # Explicit localhost and 127.0.0.1 origins for development
    origins = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]
else:
    # Parse valid origins from config
    origins = [origin.strip() for origin in settings.PROD_ORIGINS.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Trusted host middleware for production
if settings.ENV == "production":
    # Base allowed hosts from CORS origins
    allowed_hosts = [origin.replace("https://", "").replace("http://", "").split(":")[0] for origin in origins]
    
    # Add common cloud and local hosts to prevent lockout
    allowed_hosts.extend([
        "localhost",
        "127.0.0.1",
        ".onrender.com",  # Allows all subdomains on Render
        "*.onrender.com"
    ])
    
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

# Request logging middleware for debugging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Incoming request: {request.method} {request.url}")
    try:
        response = await call_next(request)
        logger.info(f"Response status: {response.status_code} for {request.method} {request.url}")
        return response
    except Exception as e:
        logger.error(f"Request failed: {str(e)} for {request.method} {request.url}")
        raise

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

    if settings.ENV == "production":
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
            "img-src 'self' data: https:; "
            "connect-src 'self' https://*.supabase.co; "
            "object-src 'none'; "
            "frame-ancestors 'none';"
        )
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    
    return response

# Correlation ID middleware
@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request_id_contextvar.set(request_id)
    
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

# Exception Handler for generic error masking
from fastapi import HTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # If it's an HTTPException, let it through so we see the actual detail
    if isinstance(exc, (HTTPException, StarletteHTTPException)):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail}
        )
    
    # Log the real error (sanitized by our logger)
    logger.error(f"Global Exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred."}
    )

app.include_router(auth.router)
app.include_router(usage.router)
app.include_router(chats.router)
app.include_router(assignments.router)
app.include_router(documents.router)
app.include_router(payments.router)
app.include_router(admin.router)
app.include_router(admin_blog.router)
app.include_router(blog.router)

@app.get("/")
def root():
    return {"message": "Acad3mic-Flow AI Service is running."}

@app.get("/health")
async def health_check():
    """
    Health check endpoint for load balancers and monitoring.
    Checks database connectivity.
    """
    from app.db.supabase import get_supabase_admin
    
    try:
        supabase = get_supabase_admin()
        # Simple query to verify database connection
        supabase.table("user_profiles").select("id").limit(1).execute()
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        db_status = "unhealthy"
    
    status = "healthy" if db_status == "healthy" else "degraded"
    
    return {
        "status": status,
        "database": db_status,
        "version": "1.0.0",
        "environment": settings.ENV
    }

# Graceful shutdown handler
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down gracefully...")
    # Give in-flight requests time to complete
    await asyncio.sleep(5)
    logger.info("Shutdown complete")


