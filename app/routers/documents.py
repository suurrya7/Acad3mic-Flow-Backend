from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import RedirectResponse

from app.dependencies import get_current_user
from app.db.supabase import get_supabase_admin
from app.utils.text_parser import extract_text_from_file
from app.models.assignment import DocumentResponse
from app.services.ai_service import AIService, get_ai_service
from uuid import uuid4
import logging
import json

logger = logging.getLogger("documents")

async def summarize_document_task(document_id: str, document_text: str):
    """Background task to generate AI summary and tags for a newly uploaded document."""
    try:
        supabase = get_supabase_admin()
        ai_service = get_ai_service()
        
        prompt = f"""
        You are an intelligent document analyzer. Read the following document text and provide:
        1. "summary": A concise 2-sentence summary of the document's main idea.
        2. "tag": A single, highly descriptive 1-3 word tag/category (e.g., "Biology Notes", "Project Proposal").

        Output EXACTLY a valid JSON object with the keys "summary" and "tag". Do not output markdown code blocks.

        Document Text:
        {document_text[:10000]}
        """
        
        result_text = await ai_service.generate_content(prompt, system_instruction="Output valid JSON only.", timeout=30)
        
        # Clean up JSON if needed
        clean_json = result_text.strip()
        if clean_json.startswith("```json"):
            clean_json = clean_json.split("```json")[1].split("```")[0].strip()
        elif clean_json.startswith("```"):
            clean_json = clean_json.split("```")[1].split("```")[0].strip()
            
        data = json.loads(clean_json)
        ai_summary = data.get("summary", "Document summarized.")
        ai_tag = data.get("tag", "Document")
        
        supabase.table("documents").update({
            "ai_summary": ai_summary,
            "ai_tag": ai_tag
        }).eq("id", document_id).execute()
        
        logger.info(f"Summarized document {document_id}: {ai_tag}")
        
    except Exception as e:
        logger.error(f"Summarization failed for document {document_id}: {str(e)}")

# Allowed file types for upload
ALLOWED_EXTENSIONS = {"pdf", "docx", "txt", "doc", "pptx", "xlsx", "xls"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
}
MAX_DOCUMENTS_PER_USER = 50

router = APIRouter(
    prefix="/documents",
    tags=["Documents"]
)

@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...), 
    current_user: dict = Depends(get_current_user)
):
    supabase = get_supabase_admin()
    user_id = current_user["id"]

    # 0. Validate file type (extension + MIME)
    file_ext = (file.filename or "").split(".")[-1].lower()
    if file_ext not in ALLOWED_EXTENSIONS or file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # 0b. Enforce document count limit per user
    count_res = supabase.table("documents").select("id", count="exact").eq("user_id", user_id).execute()
    if count_res.count is not None and count_res.count >= MAX_DOCUMENTS_PER_USER:
        raise HTTPException(
            status_code=400,
            detail=f"Document limit reached ({MAX_DOCUMENTS_PER_USER} max). Please delete some documents first."
        )

    # 1. Validate file size (10 MB limit)
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
    content = await file.read()
    
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)} MB"
        )
    
    # Reset file pointer for text extraction
    await file.seek(0)
    
    # 2. Extract Text for AI Context
    extracted_text = await extract_text_from_file(file)
    
    if not extracted_text:
         raise HTTPException(status_code=400, detail="Could not extract text from file")
         
    # 3. Upload to Supabase Storage
    try:
        storage_path = f"{user_id}/{uuid4()}.{file_ext}"
        
        # We use the raw bytes 'content' read earlier
        res = supabase.storage.from_("assignments").upload(
            path=storage_path,
            file=content,
            file_options={"content-type": file.content_type}
        )
    except Exception as e:
        # Log the specific error for debugging
        logger.error(f"Storage upload failed for {file.filename}: {str(e)}")
        # If it's a bucket missing error, we suggest the fix
        if "bucket" in str(e).lower() or "not found" in str(e).lower():
            raise HTTPException(status_code=500, detail="Storage bucket 'assignments' not found. Please create it or run scripts.setup_storage.")
        
        raise HTTPException(status_code=500, detail=f"Storage upload failed: {str(e)}")

    # 4. Upload to Gemini Files API
    gemini_file_uri = None
    try:
        ai_service = AIService()
        gemini_file_uri = await ai_service.upload_to_gemini_files(
            file_bytes=content,
            mime_type=file.content_type,
            filename=file.filename
        )
    except Exception as e:
        logger.error(f"Failed to upload {file.filename} to Gemini Files API: {str(e)}")
        # We don't fail the whole request here, the DB structure allows NULL
        pass

    # 5. Save Metadata & Extracted Text to DB
    doc_data = {
        "user_id": user_id,
        "filename": file.filename,
        "storage_path": storage_path,
        "content_extracted": extracted_text,
        "gemini_file_uri": gemini_file_uri
    }
    
    db_res = supabase.table("documents").insert(doc_data).execute()
    
    if not db_res.data:
         raise HTTPException(status_code=500, detail="Failed to save document metadata")
         
    new_doc_id = db_res.data[0]["id"]
    
    # 6. Background Task for AI Summary & Tags
    background_tasks.add_task(summarize_document_task, new_doc_id, extracted_text)
         
    return db_res.data[0]
    
@router.get("", response_model=list[DocumentResponse])
async def list_documents(current_user: dict = Depends(get_current_user)):
    supabase = get_supabase_admin()
    user_id = current_user["id"]
    
    response = supabase.table("documents").select("id, filename, ai_summary, ai_tag, created_at").eq("user_id", user_id).execute()
    return response.data

@router.get("/{document_id}/download")
async def download_document(document_id: str, current_user: dict = Depends(get_current_user)):
    supabase = get_supabase_admin()
    user_id = current_user["id"]
    
    logger.info(f"Download request: doc_id={document_id}, user_id={user_id}")
    
    # 1. Verify ownership and get storage path
    try:
        res = supabase.table("documents").select("storage_path").eq("id", document_id).eq("user_id", user_id).execute()
        
        if not res.data:
            logger.warning(f"Download failed: doc_id={document_id} not found for user {user_id}")
            raise HTTPException(status_code=404, detail="Document not found")
            
        storage_path = res.data[0]["storage_path"]
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        logger.error(f"Download DB Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error fetching document info")
    
    # 2. Generate Signed URL (expires in 60 seconds)
    try:
        # Use create_signed_url to get a temporary public link
        signed_url_res = supabase.storage.from_("assignments").create_signed_url(storage_path, 60)
        return RedirectResponse(url=signed_url_res['signedURL'])
    except Exception as e:
        logger.error(f"Failed to generate download URL: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate download link")

@router.delete("/{document_id}")
async def delete_document(document_id: str, current_user: dict = Depends(get_current_user)):
    supabase = get_supabase_admin()
    user_id = current_user["id"]
    
    logger.info(f"Delete request: doc_id={document_id}, user_id={user_id}")
    
    # 1. Verify ownership and get storage path
    try:
        res = supabase.table("documents").select("storage_path").eq("id", document_id).eq("user_id", user_id).execute()
        
        if not res.data:
            logger.warning(f"Delete failed: doc_id={document_id} not found for user {user_id}")
            raise HTTPException(status_code=404, detail="Document not found")
            
        storage_path = res.data[0]["storage_path"]
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        logger.error(f"Delete DB Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error fetching document info for deletion")
        
    # 2. Delete from Storage
    try:
        supabase.storage.from_("assignments").remove([storage_path])
    except Exception as e:
        logger.warning(f"Failed to remove file from storage (might already be gone): {str(e)}")
    
    # 3. Delete from DB
    supabase.table("documents").delete().eq("id", document_id).eq("user_id", user_id).execute()
    
    return {"message": "Document deleted successfully"}
