from app.db.supabase import get_supabase_admin

def run_migration():
    supabase = get_supabase_admin()
    try:
        # Instead of generic supabase RPC, we have standard RPC exec_sql established for admin usage typically
        # Let's see if we can perform a direct POST or if there's a defined RPC.
        # Often with supabase-py, if `exec_sql` isn't there, you might need to use the dashboard.
        # But we can try the commonly created `execute_sql` RPC or just `execute`
        response = supabase.rpc("exec_sql", {"sql": "ALTER TABLE public.messages ADD COLUMN IF NOT EXISTS document_ids UUID[] DEFAULT '{}';"}).execute()
        print(f"Migration Response: {response}")
    except Exception as e:
        print(f"Migration Error: {e}")

if __name__ == "__main__":
    run_migration()
