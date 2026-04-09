import io
from fastapi import UploadFile, HTTPException
import logging

logger = logging.getLogger("text_parser")

# Minimal imports to avoid heavy deps if not present
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    from docx import Document
except ImportError:
    Document = None

try:
    from pptx import Presentation
except ImportError:
    Presentation = None

try:
    import openpyxl
except ImportError:
    openpyxl = None

async def extract_text_from_file(file: UploadFile) -> str:
    filename = file.filename.lower()
    content = await file.read()
    file_stream = io.BytesIO(content)
    
    text = ""
    
    try:
        if filename.endswith(".pdf"):
            if not PdfReader:
                 raise HTTPException(status_code=500, detail="PDF support not installed")
            reader = PdfReader(file_stream)
            for page in reader.pages:
                text += (page.extract_text() or "") + "\n"
                
        elif filename.endswith(".docx"):
            if not Document:
                 raise HTTPException(status_code=500, detail="DOCX support not installed")
            doc = Document(file_stream)
            for para in doc.paragraphs:
                text += para.text + "\n"

        elif filename.endswith(".pptx"):
            if not Presentation:
                raise HTTPException(status_code=500, detail="PPTX support not installed")
            prs = Presentation(file_stream)
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        text += shape.text + "\n"

        elif filename.endswith(".xlsx") or filename.endswith(".xls") or filename.endswith(".xlsm"):
            if not openpyxl:
                raise HTTPException(status_code=500, detail="Excel support not installed")
            try:
                wb = openpyxl.load_workbook(file_stream, data_only=True)
                texts = []
                for sheet in wb.worksheets:
                    for row in sheet.iter_rows(values_only=True):
                        texts.append(" ".join([str(cell) for cell in row if cell is not None]))
                return "\n".join(texts)
            except Exception as e:
                # openpyxl doesn't support old .xls format
                if filename.endswith(".xls"):
                    raise HTTPException(status_code=400, detail="Standard .xls files are old. Please convert to .xlsx or upload as PDF.")
                raise e
            
        elif filename.endswith(".txt"):
            return content.decode("utf-8", errors="ignore")
            
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format. Please use PDF, DOCX, PPTX, XLSX, or plain TXT.")
            
    except Exception as e:
        logger.error(f"Error parsing file {filename}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to parse document: {str(e)}")
        
    # Reset cursor for other uses if needed (like upload to storage)
    await file.seek(0)
    
    return text.strip()
