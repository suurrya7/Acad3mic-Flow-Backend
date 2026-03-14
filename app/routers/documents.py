from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import RedirectResponse

from app.dependencies import get_current_user
from app.db.supabase import get_supabase_admin
from app.utils.text_parser import extract_text_from_file
from app.models.assignment import DocumentResponse
from uuid import uuid4
import logging

logger = logging.getLogger("documents")

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
    # Generate unique path
    file_ext = file.filename.split('.')[-1]
    storage_path = f"{user_id}/{uuid4()}.{file_ext}"
    
    # Supabase storage upload
    try:
        res = supabase.storage.from_("assignments").upload(
            path=storage_path,
            file=content,
            file_options={"content-type": file.content_type}
        )
    except Exception as e:
        # If bucket missing or other error
        raise HTTPException(status_code=500, detail="Storage upload failed. Ensure 'assignments' bucket exists.")

    # 3. Save Metadata & Extracted Text to DB
    doc_data = {
        "user_id": user_id,
        "filename": file.filename,
        "storage_path": storage_path,
        "content_extracted": extracted_text
    }
    
    db_res = supabase.table("documents").insert(doc_data).execute()
    
    if not db_res.data:
         raise HTTPException(status_code=500, detail="Failed to save document metadata")
         
    return db_res.data[0]
    
@router.get("", response_model=list[DocumentResponse])
async def list_documents(current_user: dict = Depends(get_current_user)):
    supabase = get_supabase_admin()
    user_id = current_user["id"]
    
    response = supabase.table("documents").select("id, filename, created_at").eq("user_id", user_id).execute()
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
