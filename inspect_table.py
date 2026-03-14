from app.db.supabase import get_supabase_admin
import json

def inspect_table():
    supabase = get_supabase_admin()
    try:
        # Try to insert a row with a garbage column to trigger a "column not found" error
        # which often lists all valid columns in the error message.
        res = supabase.table("grading_reports").insert({"garbage_column_name_test": 1}).execute()
    except Exception as e:
        print(f"Caught expected error:\n{e}")

if __name__ == "__main__":
    inspect_table()

if __name__ == "__main__":
    inspect_table()
