"""
Admin Service
Handles all admin operations including user management, transactions, and system monitoring.
"""

from app.db.supabase import get_supabase_admin
from fastapi import HTTPException
import logging
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import io
import zipfile
import json

logger = logging.getLogger(__name__)

class AdminService:
    def __init__(self):
        self.supabase = get_supabase_admin()
    
    # ============ DASHBOARD ============
    
    async def get_dashboard_stats(self) -> Dict:
        """Get overview statistics for dashboard"""
        try:
            result = self.supabase.rpc('get_dashboard_stats').execute()
            return result.data
        except Exception as e:
            logger.error(f"Failed to get dashboard stats: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch dashboard statistics")
    
    # ============ USER MANAGEMENT ============
    
    async def list_users(
        self, 
        page: int = 1, 
        per_page: int = 50,
        search: Optional[str] = None,
        tier: Optional[str] = None
    ) -> Dict:
        """List all users with pagination and filters"""
        try:
            offset = (page - 1) * per_page
            
            query = self.supabase.table("user_profiles").select(
                "id, email, word_balance, grading_balance, subscription_tier, is_admin, is_banned, created_at, last_reset_date",
                count="exact"
            )
            
            if search:
                query = query.ilike("email", f"%{search}%")
            
            if tier:
                query = query.eq("subscription_tier", tier)
            
            result = query.range(offset, offset + per_page - 1).execute()
            
            return {
                "data": result.data,
                "total": result.count,
                "page": page,
                "per_page": per_page,
                "total_pages": (result.count + per_page - 1) // per_page
            }
        except Exception as e:
            logger.error(f"Failed to list users: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch users")
    
    async def get_user_details(self, user_id: str) -> Dict:
        """Get detailed user information with stats"""
        try:
            # Get user profile
            user = self.supabase.table("user_profiles")\
                .select("*")\
                .eq("id", user_id)\
                .single()\
                .execute()
            
            if not user.data:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Get user stats
            chats = self.supabase.table("chats")\
                .select("id", count="exact")\
                .eq("user_id", user_id)\
                .execute()
            
            assignments = self.supabase.table("assignments")\
                .select("id, status", count="exact")\
                .eq("user_id", user_id)\
                .execute()
            
            transactions = self.supabase.table("transactions")\
                .select("amount, status")\
                .eq("user_id", user_id)\
                .execute()
            
            total_spent = sum(t["amount"] for t in transactions.data if t["status"] == "success")
            
            return {
                **user.data,
                "stats": {
                    "total_chats": chats.count,
                    "total_assignments": assignments.count,
                    "completed_assignments": len([a for a in assignments.data if a["status"] == "completed"]),
                    "total_spent": total_spent
                }
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get user details: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch user details")
    
    async def adjust_credits(
        self, 
        user_id: str, 
        amount: int, 
        reason: str,
        admin_id: str
    ) -> Dict:
        """Add or subtract word credits from user"""
        try:
            # Get current balance
            user = self.supabase.table("user_profiles")\
                .select("word_balance")\
                .eq("id", user_id)\
                .single()\
                .execute()
            
            if not user.data:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Update balance
            new_balance = max(0, user.data["word_balance"] + amount)
            
            self.supabase.table("user_profiles")\
                .update({"word_balance": new_balance})\
                .eq("id", user_id)\
                .execute()
            
            # Log action
            self.supabase.rpc('log_admin_action', {
                'admin_uuid': admin_id,
                'action_name': 'adjust_credits',
                'target_type_val': 'user',
                'target_id_val': user_id,
                'details_val': {
                    'amount': amount,
                    'reason': reason,
                    'old_balance': user.data["word_balance"],
                    'new_balance': new_balance
                }
            }).execute()
            
            logger.info(f"Admin {admin_id} adjusted credits for user {user_id}: {amount} words")
            
            return {
                "success": True,
                "old_balance": user.data["word_balance"],
                "new_balance": new_balance,
                "adjustment": amount
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to adjust credits: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to adjust credits")
    
    async def change_tier(
        self, 
        user_id: str, 
        new_tier: str,
        admin_id: str
    ) -> Dict:
        """Change user subscription tier"""
        valid_tiers = ["Free", "Basic", "Standard", "Premium", "Ultimate"]
        if new_tier not in valid_tiers:
            raise HTTPException(status_code=400, detail=f"Invalid tier. Must be one of: {valid_tiers}")
        
        try:
            # Get old tier
            user = self.supabase.table("user_profiles")\
                .select("subscription_tier")\
                .eq("id", user_id)\
                .single()\
                .execute()
            
            if not user.data:
                raise HTTPException(status_code=404, detail="User not found")
            
            old_tier = user.data["subscription_tier"]
            
            # Update tier
            self.supabase.table("user_profiles")\
                .update({"subscription_tier": new_tier})\
                .eq("id", user_id)\
                .execute()
            
            # Log action
            self.supabase.rpc('log_admin_action', {
                'admin_uuid': admin_id,
                'action_name': 'change_tier',
                'target_type_val': 'user',
                'target_id_val': user_id,
                'details_val': {
                    'old_tier': old_tier,
                    'new_tier': new_tier
                }
            }).execute()
            
            logger.info(f"Admin {admin_id} changed tier for user {user_id}: {old_tier} -> {new_tier}")
            
            return {
                "success": True,
                "old_tier": old_tier,
                "new_tier": new_tier
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to change tier: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to change tier")
    
    async def ban_user(self, user_id: str, reason: str, admin_id: str) -> Dict:
        """Ban a user (mark as inactive)"""
        try:
            # Update user
            self.supabase.table("user_profiles")\
                .update({
                    "is_admin": False,
                    "is_banned": True,
                    "word_balance": 0
                })\
                .eq("id", user_id)\
                .execute()
            
            # Log action
            self.supabase.rpc('log_admin_action', {
                'admin_uuid': admin_id,
                'action_name': 'ban_user',
                'target_type_val': 'user',
                'target_id_val': user_id,
                'details_val': {'reason': reason}
            }).execute()
            
            logger.warning(f"Admin {admin_id} banned user {user_id}: {reason}")
            
            return {"success": True, "message": "User banned successfully"}
        except Exception as e:
            logger.error(f"Failed to ban user: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to ban user")
    
    async def update_user(self, user_id: str, data: Dict, admin_id: str) -> Dict:
        """Generic user update (for React Admin)"""
        try:
            # Filter allowed fields
            allowed_fields = ["subscription_tier", "word_balance", "grading_balance", "is_admin", "is_banned"]
            updates = {k: v for k, v in data.items() if k in allowed_fields}
            
            if not updates:
                return {"success": False, "message": "No valid fields to update"}
            
            # If an admin is manually adjusting limits, set last_reset_date to today.
            # This prevents `ensure_monthly_reset` from immediately wiping these changes upon user login.
            if "word_balance" in updates or "grading_balance" in updates:
                updates["last_reset_date"] = datetime.utcnow().strftime("%Y-%m-%d")
            
            # Update user
            self.supabase.table("user_profiles")\
                .update(updates)\
                .eq("id", user_id)\
                .execute()
            
            # Log action
            self.supabase.rpc('log_admin_action', {
                'admin_uuid': str(admin_id),
                'action_name': 'update_user',
                'target_type_val': 'user',
                'target_id_val': str(user_id),
                'details_val': updates
            }).execute()
            
            logger.info(f"Admin {admin_id} updated user {user_id}: {updates}")
            
            # Fetch and return the fully hydrated updated user to sync React Admin's strict cache
            updated_user = await self.get_user_details(user_id)
            return updated_user

        except Exception as e:
            logger.error(f"Failed to update user: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to update user")

    # ============ TRANSACTIONS ============
    
    async def list_transactions(
        self,
        page: int = 1,
        per_page: int = 50,
        status: Optional[str] = None
    ) -> Dict:
        """List all transactions"""
        try:
            offset = (page - 1) * per_page
            
            query = self.supabase.table("transactions")\
                .select("*, user_profiles!inner(email)", count="exact")
            
            if status:
                query = query.eq("status", status)
            
            result = query.order("created_at", desc=True)\
                .range(offset, offset + per_page - 1)\
                .execute()
            
            return {
                "data": result.data,
                "total": result.count,
                "page": page,
                "per_page": per_page
            }
        except Exception as e:
            logger.error(f"Failed to list transactions: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch transactions")
    
    async def manual_credit(
        self,
        txn_id: str,
        reason: str,
        admin_id: str
    ) -> Dict:
        """Manually credit user for failed transaction"""
        try:
            # Get transaction
            txn = self.supabase.table("transactions")\
                .select("*")\
                .eq("id", txn_id)\
                .single()\
                .execute()
            
            if not txn.data:
                raise HTTPException(status_code=404, detail="Transaction not found")
            
            # Add words to user
            await self.adjust_credits(
                txn.data["user_id"],
                txn.data["words_purchased"],
                f"Manual credit for transaction {txn_id}: {reason}",
                admin_id
            )
            
            # Update transaction status
            self.supabase.table("transactions")\
                .update({"status": "manual_success"})\
                .eq("id", txn_id)\
                .execute()
            
            logger.info(f"Admin {admin_id} manually credited transaction {txn_id}")
            
            return {"success": True, "words_credited": txn.data["words_purchased"]}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to manual credit: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to process manual credit")
    
    # ============ CONTENT MODERATION ============
    
    async def list_assignments(
        self,
        page: int = 1,
        per_page: int = 50,
        min_score: Optional[float] = None,
        flagged_only: bool = False
    ) -> Dict:
        """List assignments for moderation"""
        try:
            offset = (page - 1) * per_page
            
            query = self.supabase.table("grading_reports")\
                .select("*", count="exact")
                
            if min_score is not None:
                query = query.gte("overall_score", min_score)
            
            result = query.order("created_at", desc=True)\
                .range(offset, offset + per_page - 1)\
                .execute()
            
            reports = result.data
            
            if reports:
                user_ids = list(set([r["user_id"] for r in reports if r.get("user_id")]))
                if user_ids:
                    profiles_res = self.supabase.table("user_profiles").select("id, email").in_("id", user_ids).execute()
                    email_map = {p["id"]: {"email": p.get("email")} for p in profiles_res.data}
                    
                    for r in reports:
                        r["user_profiles"] = email_map.get(r.get("user_id"), {"email": "Unknown"})
            
            return {
                "data": reports,
                "total": result.count,
                "page": page,
                "per_page": per_page
            }
        except Exception as e:
            logger.error(f"Failed to list assignments: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch assignments")
    
    async def delete_assignment(
        self,
        assignment_id: str,
        reason: str,
        admin_id: str
    ) -> Dict:
        """Delete inappropriate assignment"""
        try:
            # Delete assignment
            self.supabase.table("assignments")\
                .delete()\
                .eq("id", assignment_id)\
                .execute()
            
            # Log action
            self.supabase.rpc('log_admin_action', {
                'admin_uuid': admin_id,
                'action_name': 'delete_assignment',
                'target_type_val': 'assignment',
                'target_id_val': assignment_id,
                'details_val': {'reason': reason}
            }).execute()
            
            logger.warning(f"Admin {admin_id} deleted assignment {assignment_id}: {reason}")
            
            return {"success": True, "message": "Assignment deleted"}
        except Exception as e:
            logger.error(f"Failed to delete assignment: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to delete assignment")
            
    async def download_grading_reports_zip(self, report_ids: List[str]) -> bytes:
        """Download selected grading reports as a ZIP file"""
        try:
            # Query the required reports
            result = self.supabase.table("grading_reports")\
                .select("*")\
                .in_("id", report_ids)\
                .execute()
                
            reports = result.data
            if not reports:
                raise HTTPException(status_code=404, detail="No valid reports found")
            
            # Fetch emails manually
            user_ids = list(set([r["user_id"] for r in reports if r.get("user_id")]))
            email_map = {}
            if user_ids:
                profiles_res = self.supabase.table("user_profiles").select("id, email").in_("id", user_ids).execute()
                email_map = {p["id"]: p.get("email", "unknown_user") for p in profiles_res.data}
            
            # Collect all attached document IDs
            all_doc_ids = set()
            for r in reports:
                if r.get("brief_document_ids"):
                    all_doc_ids.update(r["brief_document_ids"])
                if r.get("assignment_document_ids"):
                    all_doc_ids.update(r["assignment_document_ids"])
            
            # Fetch metadata for those documents
            doc_meta_map = {}
            if all_doc_ids:
                docs_res = self.supabase.table("documents").select("id, filename, storage_path").in_("id", list(all_doc_ids)).execute()
                doc_meta_map = {d["id"]: d for d in docs_res.data}
                
            # Create an in-memory ZIP file
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                for report in reports:
                    user_email = email_map.get(report.get("user_id"), "unknown_user")
                    report_id = str(report.get("id"))[:8] # short id
                    folder_name = f"{report_id}_{user_email}"
                    
                    # 1. Requirements Text
                    brief_text = report.get("brief_text", "")
                    if brief_text:
                        zip_file.writestr(f"{folder_name}/Requirements.txt", brief_text.encode('utf-8'))
                        
                    # 1b. Brief Document Attachments
                    brief_doc_ids = report.get("brief_document_ids") or []
                    for did in brief_doc_ids:
                        dmeta = doc_meta_map.get(did)
                        if dmeta and dmeta.get("storage_path"):
                            try:
                                file_bytes = self.supabase.storage.from_("assignments").download(dmeta["storage_path"])
                                zip_file.writestr(f"{folder_name}/Requirements_Attachments/{dmeta['filename']}", file_bytes)
                            except Exception as e:
                                logger.warning(f"Failed to fetch document {did}: {e}")
                                
                    # 2. Solution Text
                    assignment_text = report.get("assignment_text", "")
                    if assignment_text:
                        zip_file.writestr(f"{folder_name}/Solution.txt", assignment_text.encode('utf-8'))
                        
                    # 2b. Solution Document Attachments
                    assignment_doc_ids = report.get("assignment_document_ids") or []
                    for did in assignment_doc_ids:
                        dmeta = doc_meta_map.get(did)
                        if dmeta and dmeta.get("storage_path"):
                            try:
                                file_bytes = self.supabase.storage.from_("assignments").download(dmeta["storage_path"])
                                zip_file.writestr(f"{folder_name}/Solution_Attachments/{dmeta['filename']}", file_bytes)
                            except Exception as e:
                                logger.warning(f"Failed to fetch document {did}: {e}")
                                
                    # 3. Grade Report Details
                    grade_details = {
                        "Title": report.get("title"),
                        "Overall Score": report.get("overall_score"),
                        "Grade Classification": report.get("grade_classification"),
                        "Word Count": report.get("word_count"),
                        "Citations": report.get("citation_count"),
                        "Referencing Style": report.get("referencing_style_detected"),
                        "Examiner Comments": report.get("examiner_comments"),
                        "Improvement Suggestions": report.get("improvement_suggestions"),
                        "Rubric Results": report.get("criterion_results", [])
                    }
                    zip_file.writestr(f"{folder_name}/Grade_Report.json", json.dumps(grade_details, indent=2).encode('utf-8'))
            
            return zip_buffer.getvalue()
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to generate grading zip: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to generate ZIP archive")
    
    # ============ SYSTEM MONITORING ============
    
    async def get_system_health(self) -> Dict:
        """Get system health metrics"""
        try:
            # Test database connection
            self.supabase.table("user_profiles").select("id").limit(1).execute()
            
            return {
                "status": "healthy",
                "database": "connected",
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"System health check failed: {str(e)}")
            return {
                "status": "degraded",
                "database": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def get_logs(self, level: str = "ERROR", limit: int = 100) -> List[Dict]:
        """Get application logs (from admin_logs table)"""
        try:
            result = self.supabase.table("admin_logs")\
                .select("*")\
                .order("created_at", desc=True)\
                .limit(limit)\
                .execute()
            
            return result.data
        except Exception as e:
            logger.error(f"Failed to get logs: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch logs")
    
    # ============ SETTINGS ============
    
    async def get_setting(self, key: str) -> Dict:
        """Get system setting"""
        try:
            result = self.supabase.table("system_settings")\
                .select("*")\
                .eq("key", key)\
                .single()\
                .execute()
            
            if not result.data:
                raise HTTPException(status_code=404, detail="Setting not found")
            
            return result.data
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get setting: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch setting")
    
    async def update_setting(
        self,
        key: str,
        value: dict,
        admin_id: str
    ) -> Dict:
        """Update system setting"""
        try:
            result = self.supabase.table("system_settings")\
                .update({
                    "value": value,
                    "updated_by": admin_id,
                    "updated_at": datetime.utcnow().isoformat()
                })\
                .eq("key", key)\
                .execute()
            
            # Log action
            self.supabase.rpc('log_admin_action', {
                'admin_uuid': admin_id,
                'action_name': 'update_setting',
                'target_type_val': 'setting',
                'target_id_val': key,
                'details_val': {'new_value': value}
            }).execute()
            
            logger.info(f"Admin {admin_id} updated setting {key}")
            
            return result.data[0] if result.data else {}
        except Exception as e:
            logger.error(f"Failed to update setting: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to update setting")
