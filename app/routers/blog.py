"""
Public Blog Router
Endpoints for the Next.js Frontend to fetch published blog content.
"""

from typing import Optional
from fastapi import APIRouter
from app.services.blog_service import BlogService

router = APIRouter(prefix="/public/blogs", tags=["public-blog"])
blog_service = BlogService()

@router.get("")
async def get_published_blogs(search: Optional[str] = None, page: int = 1, page_size: int = 9):
    """Get a paginated list of all published blogs with search"""
    return await blog_service.list_published_posts(search=search, page=page, page_size=page_size)

@router.get("/{slug}")
async def get_blog_by_slug(slug: str):
    """Get the full content of a specific blog post"""
    return await blog_service.get_post_by_slug(slug)

@router.get("/{slug}/related")
async def get_related_blogs(slug: str, limit: int = 3):
    """Get related blog posts for a specific article"""
    posts = await blog_service.get_related_posts(slug, limit=limit)
    return {"blogs": posts}
