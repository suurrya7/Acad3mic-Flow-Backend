from supabase import create_client, Client
from supabase.lib.client_options import SyncClientOptions
import httpx
from app.config import get_settings

# Force HTTP/1.1 to avoid ConnectionTerminated and StreamReset (HTTP/2 race) errors.
# We use a shared client (with pooling) to avoid resource leaks.
_shared_httpx_client = httpx.Client(http2=False)

class SupabaseClient:
    _admin_instance: Client = None
    _admin_key_used: str = None

    @classmethod
    def get_admin_instance(cls) -> Client:
        """
        Returns a Supabase client with SERVICE_ROLE_KEY for admin tasks.
        Bypasses RLS.
        """
        from app.config import get_settings
        settings = get_settings()
        target_key = settings.SUPABASE_SERVICE_ROLE_KEY
        
        # Defensive: If instance exists but keys don't match (poisoned singleton), re-init.
        if cls._admin_instance and cls._admin_key_used != target_key:
            import logging
            logging.getLogger("supabase").warning("Admin singleton key mismatch detected. Re-initializing...")
            cls._admin_instance = None

        if cls._admin_instance is None:
            if not target_key or target_key == settings.SUPABASE_KEY:
                import logging
                logging.getLogger("supabase").warning("CRITICAL: SUPABASE_SERVICE_ROLE_KEY not found or same as ANON_KEY.")
            
            # Inject our HTTP/1.1 client via SyncClientOptions
            from supabase.lib.client_options import SyncClientOptions
            options = SyncClientOptions(httpx_client=_shared_httpx_client)
            
            cls._admin_instance = create_client(settings.SUPABASE_URL, target_key, options=options)
            cls._admin_key_used = target_key
            
            import logging
            logging.getLogger("supabase").info(f"Initialized Admin Supabase Client (HTTP/1.1, RLS Bypass)")
            
        return cls._admin_instance

def get_supabase_admin() -> Client:
    return SupabaseClient.get_admin_instance()

# Helper to create a client with user context
def get_supabase_user_client(access_token: str) -> Client:
    """
    Creates a new Supabase client and sets the Auth header for RLS.
    """
    from app.config import get_settings
    current_settings = get_settings()
    
    # Inject our HTTP/1.1 client via SyncClientOptions
    options = SyncClientOptions(httpx_client=_shared_httpx_client)
    client = create_client(current_settings.SUPABASE_URL, current_settings.SUPABASE_KEY, options=options)
    
    # Set the Authorization header for PostgREST (Database) requests
    client.postgrest.auth(access_token)
    
    # Try to set session for Auth client to avoid "Auth session missing!" errors.
    try:
        client.auth.set_session(access_token, "")
    except Exception:
        pass
        
    return client
