from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
import logging
from app.dependencies import get_current_user
from app.services.ai_service import get_ai_service
from app.services.user_service import user_service
from app.db.supabase import get_supabase_admin
from app.models.assignment import AssignmentRequest, AssignmentResponse
from app.models.grading import GradingRequest, GradingResponse
from app.services.grading_service import get_grading_service
from app.limiter import limiter
from uuid import UUID

logger = logging.getLogger("assignments")

router = APIRouter(
    prefix="/assignments",
    tags=["Assignments"]
)

async def process_assignment_task(assignment_id: str, user_id: str, topic: str, instructions: str, combined_docs_text: str):
    """
    Background task to process the academic assignment pipeline.
    Includes Intelligent Requirement Check, Interactive Pause (awaiting_info), 
    Live Web Research, and Checkpoint-based resumption.
    """
    ai_service = get_ai_service()
    supabase = get_supabase_admin()
    
    try:
        # 1. Evaluate Data Sufficiency
        logger.info(f"[{assignment_id}] Checking data sufficiency...")
        sufficiency = await ai_service.evaluate_data_sufficiency(
            topic=topic,
            instructions=instructions,
            files_content=combined_docs_text
        )
        
        researched_data = ""
        if not sufficiency.get("is_sufficient", True):
            action = sufficiency.get("suggested_action", "ask_user")
            missing = sufficiency.get("missing_items", [])
            reason = sufficiency.get("reason", "Incomplete data.")
            
            if action == "ask_user":
                # Mark as AWAITING_INFO (not failed!) — the user can re-submit with more info
                logger.warning(f"[{assignment_id}] Pausing — awaiting user info: {missing}")
                supabase.table("assignments").update({
                    "status": "awaiting_info",
                    "missing_info_details": missing,
                    "error_message": f"The AI needs more information: {reason}"
                }).eq("id", assignment_id).execute()
                return  # Pause cleanly — do not fail
            
            elif action == "search_web":
                # Research each missing item live
                logger.info(f"[{assignment_id}] Researching {len(missing)} missing items online...")
                for item in missing:
                    research_res = await ai_service.perform_web_research(item, context=instructions)
                    researched_data += f"\n--- Online Research: {item} ---\n{research_res}\n"

        # 2. Generate Content (with checkpoint-based resumption)
        logger.info(f"[{assignment_id}] Starting assignment generation...")
        
        final_text = await ai_service.generate_assignment(
            topic=topic,
            instructions=instructions,
            files_content=combined_docs_text,
            researched_data=researched_data,
            assignment_id=assignment_id  # Enables per-section checkpointing
        )
        
        logger.info(f"[{assignment_id}] Generation complete. Words: {len(final_text.split())}")
        
        # 3. Save completed output
        supabase.table("assignments").update({
            "status": "completed",
            "output_text": final_text,
            "error_message": None,
            "missing_info_details": None
        }).eq("id", assignment_id).execute()
        
        # 4. Deduct words (non-fatal if it fails)
        try:
            word_count = len(final_text.split())
            user_service.deduct_words(user_id, word_count)
        except Exception as deduct_err:
            logger.warning(f"[{assignment_id}] Word deduction failed: {str(deduct_err)}")
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"[{assignment_id}] Fatal error:\n{error_details}")
        
        friendly_error = str(e)
        if "404" in friendly_error:
            friendly_error = f"AI Model Configuration Error: {friendly_error}. Check GEMINI_MODEL_NAME environment variable."
        elif "quota" in friendly_error.lower():
            friendly_error = "AI Quota Exceeded. Please try again later."
            
        supabase.table("assignments").update({
            "status": "failed",
            "error_message": friendly_error
        }).eq("id", assignment_id).execute()


@router.post("/submit", response_model=AssignmentResponse, status_code=202)
@limiter.limit("5/minute")
async def submit_assignment(
    request_data: AssignmentRequest, 
    background_tasks: BackgroundTasks,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    supabase = get_supabase_admin()
    user_id = current_user["id"]
    
    # 1. Check Balance
    from app.services.user_service import user_service
    if not user_service.check_balance(user_id, required_words=500):
         raise HTTPException(status_code=402, detail="Insufficient word balance for assignment.")
         
    # 2. Gather Document Content
    combined_docs_text = ""
    if request_data.document_ids:
        doc_ids_str = [str(did) for did in request_data.document_ids]
        docs_res = supabase.table("documents").select("content_extracted").in_("id", doc_ids_str).eq("user_id", user_id).execute()
        
        for doc in docs_res.data:
            if doc.get("content_extracted"):
                combined_docs_text += doc["content_extracted"] + "\n\n"
                
    # 3. Create Assignment Record (Processing)
    assignment_data = {
        "user_id": user_id,
        "title": request_data.topic if len(request_data.topic) < 50 else request_data.topic[:50] + "...",
        "status": "processing",
        "document_ids": [str(d) for d in request_data.document_ids] if request_data.document_ids else []
    }
    
    insert_res = supabase.table("assignments").insert(assignment_data).execute()
    if not insert_res.data:
        raise HTTPException(status_code=500, detail="Failed to initialize assignment")
        
    assignment = insert_res.data[0]
    
    # 4. Trigger Background Processing
    background_tasks.add_task(
        process_assignment_task,
        assignment['id'],
        user_id,
        request_data.topic,
        request_data.instructions,
        combined_docs_text
    )
    
    return assignment

@router.get("/{assignment_id}", response_model=AssignmentResponse)
async def get_assignment(assignment_id: UUID, current_user: dict = Depends(get_current_user)):
    supabase = get_supabase_admin()
    user_id = current_user["id"]
    
    res = supabase.table("assignments").select("*").eq("id", str(assignment_id)).eq("user_id", user_id).single().execute()
    
    if not res.data:
        raise HTTPException(status_code=404, detail="Assignment not found")
        
    return res.data

@router.get("/", response_model=list[AssignmentResponse])
async def list_assignments(current_user: dict = Depends(get_current_user)):
    supabase = get_supabase_admin()
    user_id = current_user["id"]
    
    res = supabase.table("assignments").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
    return res.data

@router.post("/grade", response_model=GradingResponse)
@limiter.limit("5/minute")
async def grade_assignment(
    request_data: GradingRequest,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Evaluates an assignment and generates a professional grading report.
    """
    supabase = get_supabase_admin()
    user_id = current_user["id"]
    grading_service = get_grading_service()
    
    # 1. Check Balance
    if not user_service.check_grading_balance(user_id):
        raise HTTPException(status_code=402, detail="Insufficient grading checks remaining.")
    
    try:
        # 2. Extract Document Content based on categories
        combined_brief_text = request_data.brief_text
        combined_assignment_text = request_data.assignment_text
        
        # Collect all unique IDs to fetch in one go
        all_ids_set = set()
        if request_data.document_ids:
            all_ids_set.update([str(did) for did in request_data.document_ids])
        if request_data.brief_document_ids:
            all_ids_set.update([str(did) for did in request_data.brief_document_ids])
        if request_data.assignment_document_ids:
            all_ids_set.update([str(did) for did in request_data.assignment_document_ids])
            
        if all_ids_set:
            docs_res = supabase.table("documents").select("id, content_extracted").in_("id", list(all_ids_set)).eq("user_id", user_id).execute()
            doc_map = {doc["id"]: doc.get("content_extracted", "") for doc in docs_res.data}
            
            # Append to brief text (legacy document_ids go here to be safe, plus specific brief docs)
            brief_ids = set([str(did) for did in (request_data.document_ids or [])] + [str(did) for did in (request_data.brief_document_ids or [])])
            for did in brief_ids:
                if doc_map.get(did):
                    combined_brief_text += "\n\n[Attached Brief Document]:\n" + doc_map[did]
                    
            # Append to assignment text
            assignment_ids = set([str(did) for did in (request_data.assignment_document_ids or [])])
            for did in assignment_ids:
                if doc_map.get(did):
                    combined_assignment_text += "\n\n[Attached Submission Document]:\n" + doc_map[did]
                    
        # Update request with combined text
        request_data.brief_text = combined_brief_text
        request_data.assignment_text = combined_assignment_text


        # 3. Generate Report (This is a complex AI task, can be long-running)
        # Note: For production, this could be a background task with SSE/Polling
        # For now, we do it in-line (300s timeout in AI service handles the duration)
        report = await grading_service.generate_full_report(request_data)
        
        # 4. Save to Database
        # Using exclude_none=True to avoid sending 'id: null' which violates NOT NULL constraints
        # when the database is expected to generate the UUID.
        from fastapi.encoders import jsonable_encoder
        report_data = jsonable_encoder(report, exclude_none=True)
        report_data["user_id"] = user_id
        
        insert_res = supabase.table("grading_reports").insert(report_data).execute()
        if not insert_res.data:
             logger.error("Failed to save grading report to Supabase")
        
        # 5. Deduct Balance
        user_service.deduct_grading_check(user_id)
        
        return {"report": report, "status": "completed"}
        
    except Exception as e:
        logger.error(f"Grading failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Grading failed: {str(e)}")

@router.get("/grade/history")
async def get_grading_history(request: Request, current_user: dict = Depends(get_current_user)):
    """
    Fetches the user's grading report history.
    """
    supabase = get_supabase_admin()
    user_id = current_user["id"]
    
    res = supabase.table("grading_reports").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
    return res.data

@router.get("/grade/{report_id}")
async def get_grading_report(report_id: UUID, current_user: dict = Depends(get_current_user)):
    supabase = get_supabase_admin()
    user_id = current_user["id"]
    
    res = supabase.table("grading_reports").select("*").eq("id", str(report_id)).eq("user_id", user_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Report not found")
        
    return res.data
