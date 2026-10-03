#!/usr/bin/env python3
"""
End-to-End Live Assignment Solver Test
Executes the full pipeline:
Requirement Check -> Academic Research -> Parallel Chunk Generation -> CrossRef Citation Validation -> Similarity Scoring -> DB Persistence.
"""

import os
import sys
import asyncio
import time
from uuid import uuid4

os.environ.setdefault("ENVIRONMENT", "testing")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.supabase import SupabaseClient
from app.routers.assignments import process_assignment_task

async def main():
    sb = SupabaseClient.get_admin_instance()
    test_user_id = "0b54c226-9f42-4df9-ba16-447b3e70e0a0"
    asg_id = str(uuid4())
    topic = "E2E Test: Quantum Computing Fault-Tolerance and Surface Codes"
    instructions = "Provide a concise academic evaluation (approx 400-600 words) discussing error thresholds, physical vs logical qubits, and 2024-2026 experimental milestones. Include verified references."
    brief_text = "Brief: Must include introduction, core analysis of surface codes, and formal reference list."

    print(f"Creating test assignment {asg_id}...")
    insert_data = {
        "id": asg_id,
        "user_id": test_user_id,
        "title": topic,
        "status": "processing",
        "progress_stage": "queued"
    }
    sb.table("assignments").insert(insert_data).execute()

    start_time = time.perf_counter()
    try:
        print("Executing process_assignment_task in background...")
        await process_assignment_task(
            assignment_id=asg_id,
            user_id=test_user_id,
            topic=topic,
            instructions=instructions,
            combined_docs_text=brief_text,
            file_uris=[]
        )
        elapsed = time.perf_counter() - start_time

        # Verify DB state
        res = sb.table("assignments").select("*").eq("id", asg_id).single().execute()
        asg = res.data
        assert asg is not None, "Assignment record missing"
        
        status = asg.get("status")
        stage = asg.get("progress_stage")
        output = asg.get("output_text") or ""
        words = asg.get("words_used") or 0
        similarity = asg.get("self_similarity_score")
        
        print("\n" + "=" * 60)
        print("  END-TO-END PIPELINE EXECUTION SUMMARY")
        print("=" * 60)
        print(f"  Assignment ID:       {asg_id}")
        print(f"  Total Duration:      {round(elapsed, 2)}s")
        print(f"  Final Status:        {status}")
        print(f"  Progress Stage:      {stage}")
        print(f"  Words Generated:     {words} words ({len(output)} chars)")
        print(f"  Self-Similarity:     {similarity}")
        print(f"  References Included: {'# References' in output or 'References' in output}")
        print("=" * 60)

        assert status == "completed", f"Expected completed, got {status}"
        assert words > 200, f"Expected > 200 words, got {words}"
        assert len(output) > 1000, "Generated text too short"

        print("✅ FULL END-TO-END PIPELINE VALIDATED SUCCESSFULLY!")

    finally:
        # Clean up test record
        print(f"Cleaning up test assignment {asg_id}...")
        sb.table("assignments").delete().eq("id", asg_id).execute()
        sb.table("assignment_chunks").delete().eq("assignment_id", asg_id).execute()
        print("Cleanup complete.")

if __name__ == "__main__":
    asyncio.run(main())
