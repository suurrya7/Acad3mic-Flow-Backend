
import asyncio
import os
from app.db.supabase import get_supabase_admin
from app.config import get_settings
from app.services.ai_service import get_ai_service

async def test_assignment_solver():
    ai = get_ai_service()
    
    print("--- ASSIGNMENT SOLVER TEST START ---")
    
    topic = "The Impact of Quantum Computing on Modern Cryptography"
    instructions = "Write a 1500-word academic paper on the topic. Include introduction, methodology, and conclusion. Use APA format."
    
    print(f"Generating assignment for topic: {topic}")
    try:
        # We test the core method used in the background task
        # Note: This might take a few minutes as it's chunked
        result = await ai.generate_assignment(
            topic=topic,
            instructions=instructions,
            files_content="Testing content. Quantum computing is fast. Cryptography is hard."
        )
        
        print("\nSUCCESS! Assignment generated.")
        print(f"Content Length: {len(result)} characters")
        print(f"Word Count: {len(result.split())}")
        print("-" * 50)
        print(result[:500] + "...")
        print("-" * 50)
        
    except Exception as e:
        print(f"ASSIGNMENT GENERATION FAILED: {str(e)}")
        import traceback
        traceback.print_exc()

    print("\n--- ASSIGNMENT SOLVER TEST END ---")

if __name__ == "__main__":
    asyncio.run(test_assignment_solver())
