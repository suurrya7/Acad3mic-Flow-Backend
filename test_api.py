import asyncio
from app.services.admin_service import AdminService
async def test():
    s = AdminService()
    res = await s.list_users(1, 50, None, None)
    print(res)
asyncio.run(test())
