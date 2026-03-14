from app.db.supabase import get_supabase_admin
import json

def test_insert_and_fetch():
    supabase = get_supabase_admin()
    try:
        # Minimal data payload that avoids NOT NULL constraint on id and created_at
        data = {
            "title": "Schema Test Report",
            "overall_score": 85.5,
            "grade_classification": "Distinction",
            "criterion_results": [{"criterion_name": "Test", "score": 1, "max_score": 1, "feedback": "Good", "strengths": [], "weaknesses": []}],
            "examiner_comments": "Looks good.",
            "improvement_suggestions": [],
            "word_count": 50,
            "referencing_style_detected": "None",
            "citation_count": 0
        }
        print("Attempting insert...")
        res = supabase.table("grading_reports").insert(data).execute()
        
        if res.data:
            print("Successfully inserted and fetched row!")
            print(json.dumps(res.data[0], indent=2))
            
            # Now let's delete the test row
            report_id = res.data[0]["id"]
            supabase.table("grading_reports").delete().eq("id", report_id).execute()
            print("Test row deleted.")
        else:
            print("No data returned on insert.")
    except Exception as e:
        print(f"Error during insert: {e}")

if __name__ == "__main__":
    test_insert_and_fetch()
