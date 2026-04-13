import asyncio
from app.services.blog_service import BlogService
async def test():
    s = BlogService()
    try:
        res = await s.generate_topics()
        print("Success:", res)
    except Exception as e:
        print("Error:", str(e))
asyncio.run(test())
