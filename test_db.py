import asyncio
from app.db.supabase import get_supabase_admin
sb = get_supabase_admin()
res = sb.table('blog_topics').select('id').limit(1).execute()
print("Success:", res.data)
