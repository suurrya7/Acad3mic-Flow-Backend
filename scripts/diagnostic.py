
import asyncio
import os
from app.db.supabase import get_supabase_admin
from app.config import get_settings
from app.services.ai_service import get_ai_service
from app.services.prompt_manager import prompt_manager

async def diagnostic():
    supabase = get_supabase_admin()
    settings = get_settings()
    ai = get_ai_service()
    
    print("--- EXTENDED DIAGNOSTIC START ---")
    
    # 1. Test AI Streaming
    print("\n1. Testing AI Streaming (chat_with_memory_stream)...")
    try:
        new_message = "Write a short poem about coding."
        print(f"Streaming request for: '{new_message}'")
        chunk_count = 0
        async for chunk in ai.chat_with_memory_stream("", [], new_message):
            if chunk_count == 0:
                print("Received first chunk!")
            chunk_count += 1
            # print(chunk, end="", flush=True)
        print(f"\nSuccess! Received {chunk_count} chunks.")
    except Exception as e:
        print(f"STREAMING FAILED: {str(e)}")

    # 2. Test Humanizer Prompt Activation
    print("\n2. Testing Humanizer Prompt Activation...")
    try:
        # Get first available prompt
        prompts = await prompt_manager.list_prompts()
        valid_prompts = [p for p in prompts if p["id"] != "default"]
        
        if not valid_prompts:
            print("No database prompts found to test activation. Creating one...")
            admin = supabase.table("user_profiles").select("id").eq("is_admin", True).limit(1).execute()
            if not admin.data:
                print("No admin user for prompt creation test.")
            else:
                new_p = await prompt_manager.create_prompt("Test prompt", "Diagnostic test", admin.data[0]["id"])
                prompt_id = new_p["id"]
                admin_id = admin.data[0]["id"]
        else:
            prompt_id = valid_prompts[0]["id"]
            admin = supabase.table("user_profiles").select("id").eq("is_admin", True).limit(1).execute()
            admin_id = admin.data[0]["id"]

        if 'prompt_id' in locals():
            print(f"Attempting to activate prompt: {prompt_id} with admin: {admin_id}")
            res = await prompt_manager.activate_prompt(prompt_id, admin_id)
            print(f"Success! Activated prompt version: {res.get('version')}")
        else:
            print("Skipping activation test (no prompt found/created).")
            
    except Exception as e:
        print(f"PROMPT ACTIVATION FAILED: {str(e)}")

    # 3. Test Blog Topic Generation (Same as user's failing one)
    print("\n3. Testing Blog Topic Generation...")
    from app.services.blog_service import BlogService
    blog_service = BlogService()
    try:
        topics = await blog_service.generate_topics()
        print(f"Success! Generated {len(topics)} topics.")
    except Exception as e:
        print(f"BLOG GENERATION FAILED: {str(e)}")

    print("\n--- EXTENDED DIAGNOSTIC END ---")

if __name__ == "__main__":
    asyncio.run(diagnostic())
