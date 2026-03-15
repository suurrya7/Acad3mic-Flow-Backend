
import asyncio
import os
from app.db.supabase import get_supabase_admin
from app.config import get_settings

async def diagnostic():
    supabase = get_supabase_admin()
    settings = get_settings()
    
    print("--- DATABASE DIAGNOSTIC START ---")
    
    # 1. Test get_dashboard_stats
    print("\n1. Testing 'get_dashboard_stats' RPC...")
    try:
        res = supabase.rpc('get_dashboard_stats').execute()
        print(f"Success! Stats: {res.data}")
    except Exception as e:
        print(f"FAILED: {str(e)}")

    # 2. Check if admin_logs table exists
    print("\n2. Checking 'admin_logs' table...")
    try:
        # Try a simple select
        res = supabase.table("admin_logs").select("id").limit(1).execute()
        print("Success! 'admin_logs' table exists.")
    except Exception as e:
        print(f"FAILED: 'admin_logs' table might be missing or inaccessible: {str(e)}")

    # 3. Test log_admin_action RPC
    print("\n3. Testing 'log_admin_action' RPC...")
    try:
        # Get a real user ID to use as admin (the first one)
        user = supabase.table("user_profiles").select("id").eq("is_admin", True).limit(1).execute()
        if not user.data:
            print("No admin user found to test with.")
        else:
            admin_id = user.data[0]["id"]
            res = supabase.rpc('log_admin_action', {
                'admin_uuid': admin_id,
                'action_name': 'diagnostic_test',
                'target_type_val': 'system',
                'target_id_val': 'test',
                'details_val': {'message': 'testing diagnostic script'}
            }).execute()
            print("Success! Action logged.")
    except Exception as e:
        print(f"FAILED 'log_admin_action': {str(e)}")

    # 4. Check Gemini Model availability
    print("\n4. Checking Gemini Model via AI SDK...")
    from app.services.ai_service import get_ai_service
    ai = get_ai_service()
    print(f"Current Configured Model: {settings.GEMINI_MODEL_NAME}")
    try:
        res = await ai.generate_content("Hello, this is a diagnostic test. Reply with 'OK'.")
        print(f"AI Success! Response: {res}")
    except Exception as e:
        print(f"AI FAILED: {str(e)}")

    print("\n--- DIAGNOSTIC END ---")

if __name__ == "__main__":
    asyncio.run(diagnostic())
