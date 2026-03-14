"""
Admin Blog Router
Endpoints for Admins to trigger AI generations and approve blog topics.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from app.middleware.admin_auth import require_admin
from app.services.blog_service import BlogService
from pydantic import BaseModel, Field
from typing import List

from app.utils.logger import logger

router = APIRouter(prefix="/admin/blog", tags=["admin-blog"])

class SuggestionRequest(BaseModel):
    title: str = Field(..., min_length=5, max_length=200)

class ApprovalRequest(BaseModel):
    topic_ids: List[str] = Field(..., min_items=1)

@router.post("/generate-topics")
async def generate_topics(admin=Depends(require_admin)):
    """Ask AI to generate 4 new blog topics"""
    blog_service = BlogService()
    topics = await blog_service.generate_topics()
    return {"message": "Generated new topics", "topics": topics}

@router.get("/topics")
async def get_all_topics(status: str = None, admin=Depends(require_admin)):
    """List all blog topics (filters optional)"""
    blog_service = BlogService()
    topics = await blog_service.list_topics(status)
    return topics

@router.post("/suggest")
async def suggest_topic(
    data: SuggestionRequest, 
    admin=Depends(require_admin)
):
    import asyncio
    blog_service = BlogService()
    topic = await blog_service.suggest_topic(data.title)
    # Generate instantly in background for immediate feedback
    asyncio.create_task(blog_service.generate_blog_post(topic["id"], topic["title"]))
    return {"message": "Topic suggested and generation started", "topic": topic}

@router.post("/topics/approve")
async def approve_topics(
    data: ApprovalRequest,
    admin=Depends(require_admin)
):
    """Approve selected topics and reject the rest, then trigger generation"""
    blog_service = BlogService()
    await blog_service.approve_topics(data.topic_ids)
    
    # Start generation for approved topics in background
    import asyncio
    topics = await blog_service.list_topics(status="approved")
    for t in topics:
        if t["id"] in data.topic_ids:
            asyncio.create_task(blog_service.generate_blog_post(t["id"], t["title"]))
            
    return {"message": f"Approved {len(data.topic_ids)} topics and started generation"}

@router.post("/{topic_id}/generate")
async def generate_post_admin(
    topic_id: str,
    admin=Depends(require_admin)
):
    """Manually trigger AI generation for an existing pending/approved topic"""
    import asyncio
    blog_service = BlogService()
    
    # Need to get title first
    topics = await blog_service.list_topics()
    target_topic = next((t for t in topics if t["id"] == topic_id), None)
    
    if not target_topic:
        raise HTTPException(status_code=404, detail="Topic not found")
        
    asyncio.create_task(blog_service.generate_blog_post(topic_id, target_topic["title"]))
    return {"message": "Generation started in background"}

@router.get("/posts")
async def list_posts_admin(admin=Depends(require_admin)):
    """List all published posts for admin view"""
    blog_service = BlogService()
    return await blog_service.list_published_posts()
