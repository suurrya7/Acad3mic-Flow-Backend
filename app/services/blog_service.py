"""
Blog Service
Handles the AI generation of blog topics, writing articles, and managing publications.
"""

from app.db.supabase import get_supabase_admin
from app.services.ai_service import AIService
from fastapi import HTTPException
import logging
from typing import Dict, List, Optional
import json
import re

logger = logging.getLogger(__name__)

class BlogService:
    def __init__(self):
        self.supabase = get_supabase_admin()
        self.ai = AIService()

    def _generate_slug(self, title: str) -> str:
        """Create a URL friendly slug from title"""
        slug = title.lower().strip()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[\s_-]+', '-', slug)
        return slug

    async def generate_topics(self) -> List[Dict]:
        """Ask AI to generate 4 new academic writing blog topics"""
        prompt = (
            "You are an expert SEO content strategist for an AI Academic Writing Assistant called Acad3micFlow. "
            "Generate 4 highly engaging, SEO-optimized blog topics designed to attract college students, PhD candidates, and researchers. "
            "Topics should cover things like: writing better literature reviews, avoiding plagiarism, structuring essays, or academic research methodologies. "
            "Return ONLY a JSON array of strings containing the 4 titles, with no markdown formatting or extra text."
        )
        
        try:
            logger.info("Requesting 4 new blog topics from AI")
            response_text = await self.ai.generate_content(prompt, timeout=60)
            
            # Use centralized robust extraction
            json_str = self.ai.extract_json_from_text(response_text)
            titles = json.loads(json_str)
            
            if not isinstance(titles, list) or len(titles) == 0:
                raise ValueError("AI did not return a valid list of titles")

            # Insert into database
            inserted_topics = []
            for title_str in titles[:4]:  # Ensure max 4
                res = self.supabase.table("blog_topics").insert({
                    "title": title_str,
                    "status": "pending",
                    "source": "ai_generated"
                }).execute()
                if res.data:
                    inserted_topics.append(res.data[0])
                    
            return inserted_topics

        except Exception as e:
            logger.error(f"Failed to generate blog topics: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500, 
                detail=f"AI Generation Failed: {str(e)}"
            )

    async def suggest_topic(self, title: str) -> Dict:
        """Admin manually suggests a topic to be written immediately"""
        try:
            res = self.supabase.table("blog_topics").insert({
                "title": title,
                "status": "approved", # Instantly approved
                "source": "admin_suggested"
            }).execute()
            
            if not res.data:
                raise HTTPException(status_code=500, detail="Failed to save suggested topic")
                
            return res.data[0]
        except Exception as e:
            logger.error(f"Failed to suggest topic: {str(e)}")
            raise HTTPException(status_code=500, detail="Database error suggesting topic")

    async def list_topics(self, status: Optional[str] = None) -> List[Dict]:
        """List topics, optionally filtered by status (pending, approved, etc)"""
        try:
            query = self.supabase.table("blog_topics").select("*").order("created_at", desc=True)
            if status:
                query = query.eq("status", status)
                
            res = query.execute()
            return res.data
        except Exception as e:
            logger.error(f"Failed to list topics: {str(e)}")
            raise HTTPException(status_code=500, detail="Database error retrieving topics")

    async def approve_topics(self, topic_ids: List[str]) -> bool:
        """Approve a list of topics. Rejects all pending topics that were not approved."""
        try:
            # 1. Reject all currently pending topics first
            self.supabase.table("blog_topics")\
                .update({"status": "rejected"})\
                .eq("status", "pending")\
                .execute()
                
            # 2. Approve the selected ones
            self.supabase.table("blog_topics")\
                .update({"status": "approved"})\
                .in_("id", topic_ids)\
                .execute()
                
            return True
        except Exception as e:
            logger.error(f"Failed to approve topics: {str(e)}")
            raise HTTPException(status_code=500, detail="Database error approving topics")

    async def generate_blog_post(self, topic_id: str, title: str) -> str:
        """Background Task: Ask AI to write the complete article, then save to DB"""
        prompt = (
            f"You are the Lead Content Strategist and Senior SEO Expert for Acad3micFlow, a premium AI-powered academic writing platform.\n\n"
            f"GOAL: Write a definitive, high-authority, and SEO-optimized masterclass article about: '{title}'.\n\n"
            f"SEO & QUALITY REQUIREMENTS:\n"
            f"1. STRATEGIC STRUCTURE: Use a clear hierarchy with H1 (title), H2 (major sections), and H3 (sub-points). "
            f"Ensure the title and headings contain high-intent academic keywords.\n"
            f"2. RICH FORMATTING: Use tables for comparisons, blockquotes for expert insights, and deeply nested bullet points for process steps. "
            f"The article must look 'visually broken up' and easy to scan.\n"
            f"3. SEO KEYWORDS: Naturally weave in keywords like 'academic rigor', 'AI supervision', 'research methodology', 'literature review optimization', and 'scholarly writing'.\n"
            f"4. DEPTH: Minimum 1000 words. Provide actionable 'Step-by-Step' or 'Best Practice' sections.\n"
            f"5. APP INTEGRATION: Position Acad3micFlow as the 'Digital Supervisor' that handles the heavy lifting of structure/formatting while the researcher focuses on original thought.\n"
            f"6. TONE: Authoritative yet inspiring. Write for PhD candidates and ambitious students.\n\n"
            f"CONTENT STRUCTURE:\n"
            f"- Hook: Start with a powerful problem statement.\n"
            f"- Comparative Analysis: Include a Markdown Table comparing 'Traditional Research' vs 'AI-Supervised Research' via Acad3micFlow. "
            f"Use strict Markdown table syntax (| Header 1 | Header 2 |) and ensure no empty columns or trailing pipes at the ends of rows.\n"
            f"- Deep Dive: 3-4 major H2 sections with H3 sub-sections with clear paragraph separation.\n"
            f"- The Acad3micFlow Advantage: A dedicated section on how our platform specifically solves the mentioned problems.\n"
            f"- Final Synthesis: A strong summary with a CTA to start a research session.\n\n"
            f"OUTPUT: Return ONLY the raw Markdown. No introductory chat, no JSON, no wrapping."
        )

        meta_prompt = (
            f"As an SEO manager, write a high-CTR meta description (150-160 characters) for an article titled: '{title}'.\n"
            f"Include a strong call-to-action and primary keywords. Return ONLY the raw string."
        )

        try:
            logger.info(f"Generating full blog article for topic: {topic_id} - '{title}'")
            
            # Step 1: Generate Content
            content = await self.ai.generate_content(prompt, timeout=180)
            
            # Step 2: Generate Meta Description
            meta_desc = await self.ai.generate_content(meta_prompt, timeout=30)
            
            # Make sure slug is unique
            base_slug = self._generate_slug(title)
            slug = base_slug
            counter = 1
            while True:
                # check slug exists
                existing = self.supabase.table("blog_posts").select("id").eq("slug", slug).execute()
                if not existing.data:
                    break
                slug = f"{base_slug}-{counter}"
                counter += 1

            # Step 3: Insert into blog_posts
            self.supabase.table("blog_posts").insert({
                "topic_id": topic_id,
                "title": title,
                "slug": slug,
                "content": content.strip().strip("```markdown").strip("```"),
                "meta_description": meta_desc.strip(),
                "is_published": True,
                "published_at": "now()"
            }).execute()

            logger.info(f"Successfully generated and published blog: '{title}'")
            return slug
            
        except Exception as e:
            logger.error(f"Failed to generate article for '{title}': {str(e)}")
            # Even if it fails, we keep the topic as "approved" so it can be retried later
            raise

    async def list_published_posts(self, search: Optional[str] = None, page: int = 1, page_size: int = 9) -> Dict:
        """Fetch published posts with search, pagination and total count"""
        try:
            query = self.supabase.table("blog_posts")\
                .select("slug, title, meta_description, published_at", count="exact")\
                .eq("is_published", True)
            
            if search:
                # Simple search on title and meta_description
                query = query.or_(f"title.ilike.%{search}%,meta_description.ilike.%{search}%")
            
            # Pagination
            start = (page - 1) * page_size
            end = start + page_size - 1
            
            res = query.order("published_at", desc=True)\
                .range(start, end)\
                .execute()
            
            return {
                "blogs": res.data,
                "total": res.count,
                "page": page,
                "page_size": page_size
            }
        except Exception as e:
            logger.error(f"Failed to list published posts: {str(e)}")
            return {"blogs": [], "total": 0, "page": page, "page_size": page_size}

    async def get_related_posts(self, current_slug: str, limit: int = 3) -> List[Dict]:
        """Fetch other published posts for recommendations"""
        try:
            res = self.supabase.table("blog_posts")\
                .select("slug, title, meta_description, published_at")\
                .eq("is_published", True)\
                .neq("slug", current_slug)\
                .order("published_at", desc=True)\
                .limit(limit)\
                .execute()
            return res.data
        except Exception as e:
            logger.error(f"Failed to get related posts: {str(e)}")
            return []

    async def get_post_by_slug(self, slug: str) -> Dict:
        """Fetch a specific published post by slug for the frontend website"""
        try:
            res = self.supabase.table("blog_posts")\
                .select("*")\
                .eq("slug", slug)\
                .eq("is_published", True)\
                .single()\
                .execute()
            if not res.data:
                raise HTTPException(status_code=404, detail="Blog post not found")
            return res.data
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get post {slug}: {str(e)}")
            raise HTTPException(status_code=500, detail="Database error retrieving post")
