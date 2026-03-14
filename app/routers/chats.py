from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from app.dependencies import get_current_user
from app.services.ai_service import get_ai_service
from app.services.user_service import user_service
from app.db.supabase import get_supabase_admin
from app.models.chat import ChatCreate, ChatResponse, MessageCreate, MessageResponse, ChatHistoryResponse
from app.limiter import limiter
from typing import List
from uuid import UUID
import logging
import json
import asyncio

logger = logging.getLogger("chats")

async def generate_and_update_title(chat_id: str, user_message: str):
    """Background task to generate chat title"""
    try:
        supabase = get_supabase_admin()
        ai_service = get_ai_service()
        
        # Check if title is default
        chat = supabase.table("chats").select("title").eq("id", chat_id).single().execute()
        
        if chat.data and chat.data["title"] == "New Chat":
            new_title = await ai_service.generate_chat_title(user_message)
            supabase.table("chats").update({"title": new_title}).eq("id", chat_id).execute()
            logger.info(f"Updated chat {chat_id} title to: {new_title}")
            
    except Exception as e:
        logger.error(f"Background title generation failed: {str(e)}")

router = APIRouter(
    prefix="/chats",
    tags=["Chats"]
)

@router.post("", response_model=ChatResponse)
async def create_chat(chat_data: ChatCreate, current_user: dict = Depends(get_current_user)):
    supabase = get_supabase_admin()
    user_id = current_user["id"]
    
    # Insert new chat
    data = {
        "user_id": user_id,
        "title": chat_data.title
    }
    response = supabase.table("chats").insert(data).execute()
    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to create chat")
        
    return response.data[0]

@router.get("", response_model=List[ChatResponse])
async def list_chats(current_user: dict = Depends(get_current_user)):
    supabase = get_supabase_admin()
    user_id = current_user["id"]
    
    response = supabase.table("chats").select("*").eq("user_id", user_id).order("updated_at", desc=True).execute()
    return response.data

@router.get("/{chat_id}", response_model=ChatHistoryResponse)
async def get_chat_details(
    chat_id: UUID, 
    limit: int = 50, 
    offset: int = 0,
    current_user: dict = Depends(get_current_user)
):
    supabase = get_supabase_admin()
    user_id = current_user["id"]
    
    # 1. Verify ownership
    chat_check = supabase.table("chats").select("id").eq("id", str(chat_id)).eq("user_id", user_id).execute()
    if not chat_check.data:
        raise HTTPException(status_code=404, detail="Chat not found")
        
    chat_details = supabase.table("chats").select("*").eq("id", str(chat_id)).single().execute()
    
    # 2. Fetch Paginated Messages (latest first? no, typically chronological for chat UI, so use range/offset)
    # We use range(start, end) where end is inclusive
    messages = supabase.table("messages")\
        .select("*")\
        .eq("chat_id", str(chat_id))\
        .order("created_at")\
        .range(offset, offset + limit - 1)\
        .execute()
    
    result = chat_details.data
    result["messages"] = messages.data
    return result

@router.post("/{chat_id}/messages", response_model=MessageResponse)
async def send_message(
    chat_id: UUID, 
    message: MessageCreate, 
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    supabase = get_supabase_admin()
    user_id = current_user["id"]
    ai_service = get_ai_service()

    # 1. Check Balance (Prevent usage if 0)
    if not user_service.check_balance(user_id, required_words=1):
        raise HTTPException(status_code=402, detail="Insufficient word balance. Please upgrade your plan.")

    # 2. Verify ownership and get history
    chat_check = supabase.table("chats").select("*").eq("id", str(chat_id)).eq("user_id", user_id).execute()
    if not chat_check.data:
        raise HTTPException(status_code=404, detail="Chat not found")
        
    # Get previous messages for context
    history_data = supabase.table("messages").select("role, content").eq("chat_id", str(chat_id)).order("created_at").execute()
    
    # 3. Save User Message
    user_msg_data = {
        "chat_id": str(chat_id),
        "role": "user",
        "content": message.content
    }
    supabase.table("messages").insert(user_msg_data).execute()
    
    # Get current summary
    current_chat = chat_check.data[0]
    current_summary = current_chat.get("summary", "") or ""
    
    # 4. Generate AI Response with Memory
    try:
        # Convert DB history to generic list for service
        context = history_data.data # List of {role, content}
        
        # Call AI with Memory
        ai_result = await ai_service.chat_with_memory(current_summary, context, message.content)
        
        response_text = ai_result["assistant_reply"]
        new_summary = ai_result["updated_summary"]
        
        # 5. Save AI Response
        ai_msg_data = {
            "chat_id": str(chat_id),
            "role": "assistant",
            "content": response_text
        }
        ai_msg_res = supabase.table("messages").insert(ai_msg_data).execute()
        
        # 6. Update Chat Summary
        supabase.table("chats").update({"summary": new_summary}).eq("id", str(chat_id)).execute()
        
        # 7. Deduct Words
        # Simple word count: split by whitespace
        word_count = len(response_text.split())
        user_service.deduct_words(user_id, word_count)
        
        # 8. Generate Title in Background (if needed)
        background_tasks.add_task(generate_and_update_title, str(chat_id), message.content)
        
        return ai_msg_res.data[0]
        
    except Exception as e:
        logger.error(f"Error in send_message: {str(e)}")
        # If AI fails, we already saved user message. 
        raise HTTPException(status_code=500, detail="AI processing failed")


from app.limiter import limiter

@router.post("/{chat_id}/messages/stream")
@limiter.limit("20/minute")
async def send_message_stream(
    chat_id: UUID,
    message: MessageCreate,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    request: Request = None
):
    """
    Streaming version of send_message with SSE.
    Generates the full AI response, saves it to DB first, then streams it to the client.
    This ensures messages are never lost even if the client disconnects mid-stream.
    Rate limit: 20 requests per minute per user.
    """
    async def event_generator():
        try:
            supabase = get_supabase_admin()
            user_id = current_user["id"]
            ai_service = get_ai_service()

            # 1. Check Balance
            if not user_service.check_balance(user_id, required_words=10):
                yield f"data: {json.dumps({'type': 'error', 'content': 'Insufficient word balance'})}\n\n"
                return

            # 2. Verify ownership and get history
            chat_check = supabase.table("chats").select("*").eq("id", str(chat_id)).eq("user_id", user_id).execute()
            if not chat_check.data:
                yield f"data: {json.dumps({'type': 'error', 'content': 'Chat not found'})}\n\n"
                return
            
            history_data = supabase.table("messages").select("role, content").eq("chat_id", str(chat_id)).order("created_at").execute()
            
            # 4. Fetch attached documents if any to build context AND append to message record
            combined_docs_text = ""
            attached_files_meta = []
            if message.document_ids:
                doc_ids_str = [str(did) for did in message.document_ids]
                docs_res = supabase.table("documents").select("id, filename, content_extracted").in_("id", doc_ids_str).eq("user_id", user_id).execute()
                for doc in docs_res.data:
                    attached_files_meta.append(doc["filename"])
                    if doc.get("content_extracted"):
                        combined_docs_text += f"\n\n[Document: {doc['filename']}]\n{doc['content_extracted']}\n\n"
            
            # 3. Save User Message immediately (so it's always persisted)
            # We append the attached files metadata to the content so it renders in the chat history
            final_user_content = message.content
            if attached_files_meta:
                files_str = ", ".join(attached_files_meta)
                final_user_content += f"\n\n📎 **Attached:** {files_str}"
                
            user_msg_data = {
                "chat_id": str(chat_id),
                "role": "user",
                "content": final_user_content
            }
            supabase.table("messages").insert(user_msg_data).execute()
            
            current_chat = chat_check.data[0]
            current_summary = current_chat.get("summary", "") or ""
            
            # 5. Detect Intent
            yield f"data: {json.dumps({'type': 'status', 'content': 'Analyzing request...'})}\n\n"
            try:
                intent = await ai_service.detect_assignment_intent(message.content)
                is_assignment = intent.get("is_assignment", False)
                confidence = intent.get("confidence", 0.0)
            except Exception as intent_err:
                logger.warning(f"Intent detection failed (falling back to standard chat): {str(intent_err)}")
                is_assignment = False
                confidence = 0.0
            
            response_text = ""

            if is_assignment and confidence > 0.7:
                assignment_type = intent.get("assignment_type", "academic")
                yield f"data: {json.dumps({'type': 'status', 'content': f'Analyzing {assignment_type} requirements...'})}\n\n"
                
                # 1. Evaluate Data Sufficiency
                sufficiency = await ai_service.evaluate_data_sufficiency(
                    topic=message.content[:500],
                    instructions=message.content,
                    files_content=combined_docs_text
                )
                
                if not sufficiency.get("is_sufficient", True):
                    action = sufficiency.get("suggested_action", "ask_user")
                    missing = sufficiency.get("missing_items", [])
                    reason = sufficiency.get("reason", "Incomplete data.")
                    
                    if action == "ask_user" and missing:
                        # PAUSE AND ASK: Inform the user and yield as content
                        missing_str = ", ".join(missing)
                        response_text = f"I've analyzed your requirements, but I noticed some critical information is missing: **{missing_str}**. \n\n{reason}\n\n**Can you provide these details or upload the relevant files?** If you don't have them, just let me know and I will try to search for the data online."
                        
                        yield f"data: {json.dumps({'type': 'status', 'content': 'Missing requirements detected.'})}\n\n"
                        for i in range(0, len(response_text), 60):
                            yield f"data: {json.dumps({'type': 'content', 'content': response_text[i:i+60]})}\n\n"
                            await asyncio.sleep(0.01)
                        
                        # Stop here - wait for user response in next message
                    
                    elif action == "search_web" and missing:
                        # FALLBACK TO SEARCH
                        researched_data = ""
                        for item in missing:
                            yield f"data: {json.dumps({'type': 'status', 'content': f'Searching for {item} online...'})}\n\n"
                            research_res = await ai_service.perform_web_research(item, context=message.content)
                            researched_data += f"\n--- Research for {item} ---\n{research_res}\n"
                        
                        yield f"data: {json.dumps({'type': 'status', 'content': 'Research complete. Generating assignment...'})}\n\n"
                        full_text = await ai_service.generate_assignment(
                            topic=message.content[:100],
                            instructions=message.content,
                            files_content=combined_docs_text,
                            researched_data=researched_data
                        )
                        response_text = full_text
                        for i in range(0, len(full_text), 60):
                            yield f"data: {json.dumps({'type': 'content', 'content': full_text[i:i+60]})}\n\n"
                            await asyncio.sleep(0.015)
                    else:
                        # Proceed normally if action is unrecognized but marked insufficient
                        is_assignment = True # Continue to normal logic below
                
                if not response_text: # If we haven't handled it yet (sufficient)
                    yield f"data: {json.dumps({'type': 'status', 'content': f'Generating {assignment_type} assignment...'})}\n\n"
                    full_text = await ai_service.generate_assignment(
                        topic=message.content[:100],
                        instructions=message.content,
                        files_content=combined_docs_text
                    )
                    response_text = full_text
                    for i in range(0, len(full_text), 60):
                        yield f"data: {json.dumps({'type': 'content', 'content': full_text[i:i+60]})}\n\n"
                        await asyncio.sleep(0.015)
                
            else:
                # CHAT PATH: stream chunks live as the AI generates them
                yield f"data: {json.dumps({'type': 'status', 'content': 'Thinking...'})}\n\n"
                
                context = history_data.data
                raw_response_full = ""
                
                async for chunk in ai_service.chat_with_memory_stream(current_summary, context, message.content, combined_docs_text):
                    raw_response_full += chunk
                    yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
                
                response_text = raw_response_full

            # 6. Save raw AI response to DB immediately (persists even if client disconnects)
            ai_msg_data = {
                "chat_id": str(chat_id),
                "role": "assistant",
                "content": response_text
            }
            ai_msg_res = supabase.table("messages").insert(ai_msg_data).execute()
            saved_msg_id = str(ai_msg_res.data[0]["id"])

            # 7. Humanize the raw response, then replace in UI + DB
            if response_text:
                yield f"data: {json.dumps({'type': 'status', 'content': 'Refining response...'})}\n\n"
                try:
                    humanized_text = await ai_service.humanize_text(response_text)
                    if humanized_text and humanized_text != response_text:
                        # Update DB with humanized version
                        supabase.table("messages").update({"content": humanized_text}).eq("id", saved_msg_id).execute()
                        response_text = humanized_text
                        # Tell the frontend to replace the raw streamed text with the polished version
                        yield f"data: {json.dumps({'type': 'replace', 'content': humanized_text})}\n\n"
                except Exception as humanize_err:
                    logger.warning(f"Humanization failed (keeping raw response): {str(humanize_err)}")
                    # No replace event — frontend keeps the raw text already shown

            # 8. Update Chat Summary (non-fatal)
            try:
                new_summary = await ai_service.update_summary(current_summary, message.content, response_text)
            except Exception:
                new_summary = current_summary
            supabase.table("chats").update({"summary": new_summary}).eq("id", str(chat_id)).execute()

            # 9. Send completion event
            word_count = len(response_text.split())
            yield f"data: {json.dumps({'type': 'complete', 'message_id': saved_msg_id, 'final_content': response_text, 'word_count': word_count})}\n\n"
            
            # 10. Deduct Words (non-fatal)
            try:
                user_service.deduct_words(user_id, word_count)
            except Exception as deduct_err:
                logger.warning(f"Word deduction failed in chat (non-fatal): {str(deduct_err)}")
            
        except Exception as e:
            logger.error(f"Streaming error in chats: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
    
    # Trigger background title generation
    background_tasks.add_task(generate_and_update_title, str(chat_id), message.content)
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


