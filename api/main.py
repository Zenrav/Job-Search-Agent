from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional, List
import fitz
from uuid import UUID
import psycopg2
from psycopg2.extras import register_uuid, Json
register_uuid()
from psycopg2.extras import Json
import os

app = FastAPI(
    title="Resume Parser & Storage API",
    description="Multi-step async pipeline optimized for PostgreSQL JSONB architecture.",
    version="2.0.0"
)

# Database Configuration (matches your local environment / Docker bridge)
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "job_search_db"),
    "user": os.getenv("DB_USER", "postgres_admin"),
    "password": os.getenv("DB_PASSWORD", "super_secret_password_123"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432")
}

def get_db_connection():
    """Returns a raw connection object."""
    return psycopg2.connect(**DB_CONFIG)

# --- PYDANTIC SCHEMAS ---
# Enforces exact structure matching your modified 'resumes' table
class AgentCallbackPayload(BaseModel):
    resume_id: UUID
    experience: List[Dict[str, Any]]
    skills: Dict[str, Any]
    education: List[Dict[str, Any]]
    preferences: Optional[Dict[str, Any]] = None # Kept this since it wasn't explicitly removed

@app.get("/")
def read_root():
    return {"message": "Resume Parser Pipeline Running"}

# --- STEP 1: UPLOAD & PDF EXTRACT ---
@app.post("/resumes/upload")
async def upload_and_extract_resume(user_id: UUID, file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDFs are allowed.")
    
    try:
        pdf_data = await file.read()
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        raw_text = "".join([page.get_text() for page in doc])
        
        # FIX: Open connection and cursor cleanly using 'with'
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Verify user exists
                cursor.execute("SELECT id FROM users WHERE id = %s;", (user_id,))
                if not cursor.fetchone():
                    raise HTTPException(status_code=400, detail=f"User ID '{user_id}' does not exist.")
                
                # Insert tracking placeholder
                cursor.execute(
                    """
                    INSERT INTO resumes (user_id, filename)
                    VALUES (%s, %s)
                    RETURNING id, uploaded_at;
                    """,
                    (user_id, file.filename)
                )
                db_row = cursor.fetchone()
                new_resume_id = db_row[0]
                uploaded_at = db_row[1]
        
        return {
            "resume_id": str(new_resume_id),
            "filename": file.filename,
            "uploaded_at": uploaded_at,
            "extracted_text": raw_text
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database execution failure: {str(e)}")

# --- STEP 2: AGENT CALLBACK WEBHOOK ---
@app.post("/resumes/agent-callback")
async def agent_callback(payload: AgentCallbackPayload):
    try:
        # Open connection and cursor safely using context managers
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                
                # Check if record exists
                cursor.execute("SELECT id FROM resumes WHERE id = %s;", (payload.resume_id,))
                if not cursor.fetchone():
                    raise HTTPException(status_code=404, detail=f"resume_id '{payload.resume_id}' not found.")
                
                # Update table payload
                cursor.execute(
                    """
                    UPDATE resumes 
                    SET 
                        experience = %s,
                        skills = %s,
                        education = %s,
                        preferences = %s
                    WHERE id = %s;
                    """,
                    (
                        Json(payload.experience),
                        Json(payload.skills),
                        Json(payload.education),
                        Json(payload.preferences) if payload.preferences else None,
                        payload.resume_id
                    )
                )
        
        return {
            "status": "success",
            "message": f"Successfully updated JSONB relational fields for ID: {payload.resume_id}"
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database update failure: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)