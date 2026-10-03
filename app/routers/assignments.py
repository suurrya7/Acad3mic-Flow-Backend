from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from fastapi.responses import Response, StreamingResponse
import logging
import asyncio
import json
from app.dependencies import get_current_user
from app.services.ai_service import get_ai_service
from app.services.user_service import user_service
from app.db.supabase import get_supabase_admin
from app.models.assignment import AssignmentRequest, AssignmentResponse, AssignmentChunkResponse
from app.models.grading import GradingRequest, GradingResponse
from app.services.grading_service import get_grading_service
from app.services.citation_validator import get_citation_validator
from app.services.document_export import get_docx_exporter
from app.limiter import limiter
from uuid import UUID

logger = logging.getLogger("assignments")

router = APIRouter(
    prefix="/assignments",
    tags=["Assignments"]
)

async def process_assignment_task(assignment_id: str, user_id: str, topic: str, instructions: str, combined_docs_text: str, file_uris: list = None):
    """
    Background task to process the academic assignment pipeline.
    Includes Intelligent Requirement Check, Interactive Pause (awaiting_info), 
    Live Web Research, Bounded Parallel Chunk Generation, DOI Validation, and Checkpoint-based resumption.
    """
    ai_service = get_ai_service()
    supabase = get_supabase_admin()

    def _set_stage(stage: str):
        """Helper: update progress_stage in DB silently."""
        try:
            supabase.table("assignments").update({"progress_stage": stage}).eq("id", assignment_id).execute()
        except Exception as ex:
            logger.warning(f"[{assignment_id}] Could not set progress_stage={stage}: {ex}")
    
    try:
        # ── Stage 1: Validating requirements ──────────────────────────────────
        _set_stage("validating")
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
                logger.warning(f"[{assignment_id}] Pausing — awaiting user info: {missing}")
                supabase.table("assignments").update({
                    "status": "awaiting_info",
                    "progress_stage": "awaiting_info",
                    "missing_info_details": missing,
                    "error_message": f"The AI needs more information: {reason}"
                }).eq("id", assignment_id).execute()
                return
            
            elif action == "search_web":
                # ── Stage 2a: Researching missing items ───────────────────────
                _set_stage("researching")
                logger.info(f"[{assignment_id}] Researching {len(missing)} missing items online...")
                for item in missing:
                    research_res = await ai_service.perform_web_research(item, context=instructions)
                    researched_data += f"\n--- Online Research: {item} ---\n{research_res}\n"

        # ── Stage 2b: Fetching verified academic citations ─────────────────────
        _set_stage("researching")
        logger.info(f"[{assignment_id}] Fetching verified academic citations...")
        verified_sources = await ai_service.fetch_real_academic_sources(topic)
        if verified_sources:
            researched_data += f"\n\n--- VERIFIED ACADEMIC SOURCES ---\n{verified_sources}\n"

        # ── Fetch User Writing Profile ─────────────────────────────────────────
        profile_res = supabase.table("user_profiles").select("writing_profile").eq("id", user_id).single().execute()
        writing_profile = profile_res.data.get("writing_profile", {}) if profile_res.data else {}

        # ── Stage 3: Generating content with Parallel Bounded Chunks ──────────
        _set_stage("generating")
        logger.info(f"[{assignment_id}] Starting assignment generation (Profile: {writing_profile})...")
        
        async def on_chunk_complete(chunk_idx: int, total_chunks: int, heading: str):
            stage_str = f"writing_section_{chunk_idx + 1}_of_{total_chunks}"
            _set_stage(stage_str)
            logger.info(f"[{assignment_id}] Completed section {chunk_idx + 1}/{total_chunks}: '{heading}'")

        final_text = await ai_service.generate_assignment(
            topic=topic,
            instructions=instructions,
            files_content=combined_docs_text,
            researched_data=researched_data,
            assignment_id=assignment_id,
            file_uris=file_uris,
            writing_profile=writing_profile,
            on_chunk_complete=on_chunk_complete
        )
        
        logger.info(f"[{assignment_id}] Generation complete. Words: {len(final_text.split())}")

        # ── Stage 3b: DOI / CrossRef Citation Validation ──────────────────────
        _set_stage("verifying_citations")
        try:
            validator = get_citation_validator()
            final_text, cit_stats = await validator.validate_document_citations(final_text)
            logger.info(f"[{assignment_id}] Citation validation complete: {cit_stats}")
        except Exception as cit_err:
            logger.warning(f"[{assignment_id}] Citation validation skipped: {cit_err}")
        
        # ── Stage 3c: Self-Similarity Check ───────────────────────────────────
        _set_stage("checking_similarity")
        try:
            # Fetch last 5 assignments from the user
            past_res = supabase.table("assignments").select("output_text").eq("user_id", user_id).neq("id", assignment_id).neq("status", "failed").order("created_at", desc=True).limit(5).execute()
            if past_res.data:
                past_texts = [row["output_text"] for row in past_res.data if row.get("output_text")]
                if past_texts:
                    from app.utils.similarity import get_max_similarity
                    sim_score = get_max_similarity(final_text, past_texts)
                    logger.info(f"[{assignment_id}] Self-similarity score: {sim_score:.2f}")
                else:
                    sim_score = 0.0
            else:
                sim_score = 0.0
        except Exception as sim_err:
            logger.warning(f"[{assignment_id}] Similarity check failed: {sim_err}")
            sim_score = None

        # 5. Deduct words (non-fatal)
        try:
            word_count = len(final_text.split())
            user_service.deduct_words(user_id, word_count)
        except Exception as deduct_err:
            logger.warning(f"[{assignment_id}] Word deduction failed: {str(deduct_err)}")
            word_count = 0

        # ── Stage 4: Saving – stream-refine is triggered by client next ────────
        _set_stage("ready_to_refine")
        update_payload = {
            "status": "completed",
            "progress_stage": "ready_to_refine",
            "output_text": final_text,
            "error_message": None,
            "missing_info_details": None,
            "words_used": word_count
        }
        if sim_score is not None:
            update_payload["self_similarity_score"] = float(sim_score)
            
        supabase.table("assignments").update(update_payload).eq("id", assignment_id).execute()
        
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
    file_uris = []
    if request_data.document_ids:
        doc_ids_str = [str(did) for did in request_data.document_ids]
        docs_res = supabase.table("documents").select("content_extracted, gemini_file_uri").in_("id", doc_ids_str).eq("user_id", user_id).execute()
        
        for doc in docs_res.data:
            if doc.get("content_extracted"):
                combined_docs_text += doc["content_extracted"] + "\n\n"
            if doc.get("gemini_file_uri"):
                file_uris.append(doc["gemini_file_uri"])
                
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
        combined_docs_text,
        file_uris
    )
    
    return assignment


@router.get("/{assignment_id}/stream-refine")
async def stream_refined_content(
    assignment_id: UUID,
    token: str = None,
    current_user: dict = Depends(get_current_user)
):
    """
    SSE endpoint that streams refined content for a completed assignment.
    Supports 'token' as a query param because EventSource cannot send headers.
    """
    from fastapi.responses import StreamingResponse
    from app.services.ai_service import get_ai_service

    supabase = get_supabase_admin()
    user_id = current_user["id"]

    # Fetch the completed assignment output
    res = supabase.table("assignments").select("output_text, status").eq("id", str(assignment_id)).eq("user_id", user_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Assignment not found")

    data = res.data
    if data.get("status") != "completed" or not data.get("output_text"):
        raise HTTPException(status_code=400, detail="Assignment is not completed yet or has no output.")

    raw_text = data["output_text"]
    ai_service = get_ai_service()

    async def event_generator():
        try:
            supabase.table("assignments").update({"progress_stage": "refining"}).eq("id", str(assignment_id)).execute()

            async for tok in ai_service.refine_content_stream(raw_text):
                safe = tok.replace("\n", "\\n")
                yield f"data: {safe}\n\n"

            supabase.table("assignments").update({"progress_stage": "done"}).eq("id", str(assignment_id)).execute()
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"SSE stream error for {assignment_id}: {str(e)}")
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )

@router.get("/{assignment_id}", response_model=AssignmentResponse)
async def get_assignment(assignment_id: UUID, current_user: dict = Depends(get_current_user)):
    supabase = get_supabase_admin()
    user_id = current_user["id"]
    
    res = supabase.table("assignments").select("*").eq("id", str(assignment_id)).eq("user_id", user_id).single().execute()
    
    if not res.data:
        raise HTTPException(status_code=404, detail="Assignment not found")
        
    data = res.data
    # Compute completed chunks count for client polling / reconnection
    try:
        chunks_res = supabase.table("assignment_chunks").select("chunk_index", count="exact").eq("assignment_id", str(assignment_id)).execute()
        data["completed_chunks"] = chunks_res.count if chunks_res.count is not None else len(chunks_res.data or [])
    except Exception:
        data["completed_chunks"] = 0

    return data

@router.get("/{assignment_id}/chunks", response_model=list[AssignmentChunkResponse])
async def get_assignment_chunks(assignment_id: UUID, current_user: dict = Depends(get_current_user)):
    """
    Returns all saved assignment chunks for live preview or resumption.
    """
    supabase = get_supabase_admin()
    user_id = current_user["id"]

    # Verify ownership
    res = supabase.table("assignments").select("id").eq("id", str(assignment_id)).eq("user_id", user_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Assignment not found")

    chunks_res = supabase.table("assignment_chunks")\
        .select("*")\
        .eq("assignment_id", str(assignment_id))\
        .order("chunk_index", desc=False)\
        .execute()

    return chunks_res.data or []

@router.get("/{assignment_id}/progress-stream")
async def stream_assignment_progress(
    assignment_id: UUID,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    SSE endpoint that streams real-time assignment progress and chunk events.
    Supports ?token=... query param for EventSource connections.
    """
    supabase = get_supabase_admin()
    user_id = current_user["id"]

    # Verify ownership
    res = supabase.table("assignments").select("id, status, progress_stage").eq("id", str(assignment_id)).eq("user_id", user_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Assignment not found")

    async def event_generator():
        last_stage = None
        last_chunks_count = -1
        poll_count = 0
        max_polls = 600  # 10 minutes max duration

        try:
            while poll_count < max_polls:
                poll_count += 1
                curr_res = supabase.table("assignments")\
                    .select("status, progress_stage, error_message, missing_info_details")\
                    .eq("id", str(assignment_id))\
                    .single()\
                    .execute()

                if not curr_res.data:
                    yield f"data: {json.dumps({'error': 'Assignment not found'})}\n\n"
                    break

                curr = curr_res.data
                status = curr.get("status")
                stage = curr.get("progress_stage") or "queued"

                chunks_count = 0
                try:
                    c_res = supabase.table("assignment_chunks").select("chunk_index", count="exact").eq("assignment_id", str(assignment_id)).execute()
                    chunks_count = c_res.count if c_res.count is not None else len(c_res.data or [])
                except Exception:
                    pass

                if stage != last_stage or chunks_count != last_chunks_count or (poll_count % 5 == 0):
                    last_stage = stage
                    last_chunks_count = chunks_count
                    payload = {
                        "assignment_id": str(assignment_id),
                        "status": status,
                        "progress_stage": stage,
                        "completed_chunks": chunks_count,
                        "error_message": curr.get("error_message"),
                        "missing_info_details": curr.get("missing_info_details")
                    }
                    yield f"data: {json.dumps(payload)}\n\n"

                if status in ["completed", "failed", "awaiting_info"]:
                    yield "data: [DONE]\n\n"
                    break

                await asyncio.sleep(1.0)
        except Exception as e:
            logger.error(f"Progress SSE error for {assignment_id}: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )

@router.get("/{assignment_id}/export-docx")
async def export_assignment_docx(
    assignment_id: UUID,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Generates and downloads a university-grade formatted Word (.docx) document
    complete with Cover Page, Times New Roman 12pt, 1.5 spacing, 1-inch margins,
    and hanging indent references. Supports ?token=... for window.open downloads.
    """
    supabase = get_supabase_admin()
    user_id = current_user["id"]

    res = supabase.table("assignments").select("title, output_text, status, created_at").eq("id", str(assignment_id)).eq("user_id", user_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Assignment not found")

    data = res.data
    if data.get("status") != "completed" or not data.get("output_text"):
        raise HTTPException(status_code=400, detail="Assignment is not yet completed or has no content to export.")

    title = data.get("title") or "Academic Assignment"
    content = data.get("output_text")

    user_email = current_user.get("email", "Student Submission")
    exporter = get_docx_exporter()
    docx_stream = exporter.generate_docx(
        title=title,
        content_markdown=content,
        student_name=user_email,
        course_name="Coursework Submission"
    )

    clean_filename = "".join(c for c in title if c.isalnum() or c in (' ', '_', '-')).rstrip()[:50]
    filename = f"{clean_filename or 'Assignment'}.docx"

    return Response(
        content=docx_stream.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache"
        }
    )

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
