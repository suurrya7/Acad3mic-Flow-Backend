"""
Prompt Manager Service
Handles humanizer prompt versioning, testing, and activation.
"""

from app.db.supabase import get_supabase_admin
from app.services.ai_service import AIService
from fastapi import HTTPException
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class PromptManager:
    def __init__(self):
        self.supabase = get_supabase_admin()
        self.ai_service = AIService()
    
    async def get_active_prompt(self) -> Dict:
        """Get currently active humanizer prompt"""
        try:
            result = self.supabase.table("humanizer_prompts")\
                .select("*")\
                .eq("is_active", True)\
                .single()\
                .execute()
            
            if result.data:
                return result.data
            
            # If no active prompt in database, return default from humanizer_prompts.py
            from app.services.humanizer_prompts import HUMANIZER_SYSTEM_PROMPT
            return {
                "id": "default",
                "version": 1,
                "prompt_text": HUMANIZER_SYSTEM_PROMPT,
                "is_active": True,
                "created_at": datetime.utcnow().isoformat(),
                "notes": "Default prompt from code"
            }
        except Exception as e:
            # If query fails (e.g., no active prompt), return default
            from app.services.humanizer_prompts import HUMANIZER_SYSTEM_PROMPT
            return {
                "id": "default",
                "version": 1,
                "prompt_text": HUMANIZER_SYSTEM_PROMPT,
                "is_active": True,
                "created_at": datetime.utcnow().isoformat(),
                "notes": "Default prompt from code"
            }
    
    async def list_prompts(self) -> List[Dict]:
        """List all prompt versions"""
        try:
            result = self.supabase.table("humanizer_prompts")\
                .select("id, version, is_active, created_at, created_by, notes")\
                .order("version", desc=True)\
                .execute()
            
            # Also include the default prompt if database is empty
            prompts = result.data if result.data else []
            
            # Add default prompt indicator
            if not any(p.get("is_active") for p in prompts):
                from app.services.humanizer_prompts import HUMANIZER_SYSTEM_PROMPT
                prompts.insert(0, {
                    "id": "default",
                    "version": 0,
                    "is_active": True,
                    "created_at": "2024-01-01T00:00:00Z",
                    "notes": "Default prompt (hardcoded)"
                })
            
            return prompts
        except Exception as e:
            logger.error(f"Failed to list prompts: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch prompts")
    
    async def get_prompt_by_id(self, prompt_id: str) -> Dict:
        """Get specific prompt by ID"""
        try:
            if prompt_id == "default":
                from app.services.humanizer_prompts import HUMANIZER_SYSTEM_PROMPT
                return {
                    "id": "default",
                    "version": 0,
                    "prompt_text": HUMANIZER_SYSTEM_PROMPT,
                    "is_active": True,
                    "notes": "Default hardcoded prompt"
                }
            
            result = self.supabase.table("humanizer_prompts")\
                .select("*")\
                .eq("id", prompt_id)\
                .single()\
                .execute()
            
            if not result.data:
                raise HTTPException(status_code=404, detail="Prompt not found")
            
            return result.data
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get prompt: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch prompt")
    
    async def create_prompt(
        self, 
        prompt_text: str, 
        notes: Optional[str],
        admin_id: str
    ) -> Dict:
        """Create new prompt version"""
        try:
            # Get next version number
            latest = self.supabase.table("humanizer_prompts")\
                .select("version")\
                .order("version", desc=True)\
                .limit(1)\
                .execute()
            
            next_version = (latest.data[0]["version"] + 1) if latest.data else 1
            
            # Insert new prompt
            result = self.supabase.table("humanizer_prompts").insert({
                "version": next_version,
                "prompt_text": prompt_text,
                "is_active": False,
                "created_by": admin_id,
                "notes": notes
            }).execute()
            
            # Log action
            self.supabase.rpc('log_admin_action', {
                'admin_uuid': admin_id,
                'action_name': 'create_prompt',
                'target_type_val': 'prompt',
                'target_id_val': result.data[0]["id"],
                'details_val': {
                    'version': next_version,
                    'notes': notes
                }
            }).execute()
            
            logger.info(f"Created prompt version {next_version}")
            return result.data[0]
        except Exception as e:
            logger.error(f"Failed to create prompt: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to create prompt")
    
    async def activate_prompt(self, prompt_id: str, admin_id: str) -> Dict:
        """Set a prompt as active, deactivate all others"""
        try:
            # Deactivate all prompts
            self.supabase.table("humanizer_prompts")\
                .update({"is_active": False})\
                .neq("id", "00000000-0000-0000-0000-000000000000")\
                .execute()
            
            # Activate selected prompt
            result = self.supabase.table("humanizer_prompts")\
                .update({"is_active": True})\
                .eq("id", prompt_id)\
                .execute()
            
            if not result.data:
                raise HTTPException(status_code=404, detail="Prompt not found")
            
            # Log action
            self.supabase.rpc('log_admin_action', {
                'admin_uuid': admin_id,
                'action_name': 'activate_prompt',
                'target_type_val': 'prompt',
                'target_id_val': prompt_id
            }).execute()
            
            logger.info(f"Activated prompt {prompt_id}")
            return result.data[0]
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to activate prompt: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to activate prompt")
    
    async def test_prompt(self, prompt_text: str, sample_text: str) -> Dict:
        """Test prompt with sample text (doesn't save)"""
        try:
            # Use AI service to test the prompt
            result = await self.ai_service.generate_content(
                prompt=sample_text,
                system_instruction=prompt_text,
                timeout=30  # Shorter timeout for testing
            )
            
            return {
                "success": True,
                "output": result,
                "input_length": len(sample_text),
                "output_length": len(result)
            }
        except Exception as e:
            logger.error(f"Prompt test failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "input_length": len(sample_text)
            }
    
    async def delete_prompt(self, prompt_id: str, admin_id: str) -> Dict:
        """Delete a prompt version (only if not active)"""
        try:
            # Check if prompt is active
            prompt = await self.get_prompt_by_id(prompt_id)
            
            if prompt.get("is_active"):
                raise HTTPException(
                    status_code=400,
                    detail="Cannot delete active prompt. Activate another prompt first."
                )
            
            # Delete prompt
            self.supabase.table("humanizer_prompts")\
                .delete()\
                .eq("id", prompt_id)\
                .execute()
            
            # Log action
            self.supabase.rpc('log_admin_action', {
                'admin_uuid': admin_id,
                'action_name': 'delete_prompt',
                'target_type_val': 'prompt',
                'target_id_val': prompt_id,
                'details_val': {'version': prompt.get('version')}
            }).execute()
            
            logger.info(f"Deleted prompt {prompt_id}")
            return {"success": True, "message": "Prompt deleted"}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to delete prompt: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to delete prompt")
    
    async def get_prompt_history(self, limit: int = 20) -> List[Dict]:
        """Get prompt version history"""
        try:
            result = self.supabase.table("humanizer_prompts")\
                .select("id, version, is_active, created_at, created_by, notes")\
                .order("created_at", desc=True)\
                .limit(limit)\
                .execute()
            
            return result.data
        except Exception as e:
            logger.error(f"Failed to get prompt history: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch prompt history")

# Singleton instance
prompt_manager = PromptManager()
