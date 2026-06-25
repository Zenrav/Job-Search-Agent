from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional, List
import fitz  # PyMuPDF
from uuid import UUID
import psycopg2
from psycopg2.extras import register_uuid, Json
import os
import httpx


# Register UUID adapter for psycopg2
register_uuid()

app = FastAPI(
    title="Resume Parser & Storage API",
    description="Multi-step async pipeline optimized for PostgreSQL JSONB architecture.",
    version="2.0.0"
)

# --- CONFIGURATION ---
# By default, this points to the MOCK endpoint running on your local FastAPI server.
# When your friend is ready, change this to their URL (e.g., "http://their-ip:8001/parse")
AGENT_API_URL = os.getenv("AGENT_API_URL", "http://127.0.0.1:8000/extract-agent")

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "job_search_db"),
    "user": os.getenv("DB_USER", "postgres_admin"),
    "password": os.getenv("DB_PASSWORD", "super_secret_password_123"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432")
}

def get_db_connection():
    """Returns a raw database connection object."""
    try:
        return psycopg2.connect(**DB_CONFIG)
    except psycopg2.OperationalError as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

# --- PYDANTIC SCHEMAS ---
class AgentCallbackPayload(BaseModel):
    resume_id: UUID
    experience: List[Dict[str, Any]]
    skills: Dict[str, Any]
    education: List[Dict[str, Any]]
    preferences: Optional[Dict[str, Any]] = None

class AgentRequestPayload(BaseModel):
    text: str

@app.get("/")
def read_root():
    return {"message": "Resume Parser Pipeline Running"}






# --- MAIN PIPELINE: UPLOAD, EXTRACT, CALL AGENT, & SAVE ---
@app.post("/resumes/upload")
async def upload_and_extract_resume(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDFs are allowed.")
    
    try:
        # 1. Extract raw text from PDF
        pdf_data = await file.read()
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        raw_text = "".join([page.get_text() for page in doc])
        
        # 2. Insert initial placeholder into database
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Automatically generate a dummy user row first
                import random
                random_suffix = random.randint(1000, 9999)
                cursor.execute(
                    """
                    INSERT INTO users (email) 
                    VALUES (%s) 
                    RETURNING id;
                    """,
                    (f"auto_user_{random_suffix}@example.com",)
                )
                auto_user_id = cursor.fetchone()[0]
                
                # Insert Resume tracking row linked to our new auto-generated user
                cursor.execute(
                    """
                    INSERT INTO resumes (user_id, filename)
                    VALUES (%s, %s)
                    RETURNING id, uploaded_at;
                    """,
                    (auto_user_id, file.filename)
                )
                db_row = cursor.fetchone()
                new_resume_id = db_row[0]
                uploaded_at = db_row[1]
            conn.commit()

        # 3. Call the Agent API (Currently hits the /mock-agent endpoint)
        async with httpx.AsyncClient() as client:
            try:
                agent_response = await client.post(
                    AGENT_API_URL,
                    json={"text": raw_text},
                    timeout=30.0
                )
                agent_response.raise_for_status()
                agent_data = agent_response.json()
            except httpx.HTTPStatusError as e:
                raise HTTPException(status_code=502, detail=f"Agent API error: {e.response.text}")
            except httpx.RequestError as e:
                raise HTTPException(status_code=503, detail=f"Agent API unreachable: {str(e)}")

        # 4. Unpack the JSON and update database
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
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
                        Json(agent_data.get("work_history", [])),
                        Json(agent_data.get("skills", {})),
                        Json(agent_data.get("education_history", [])),
                        Json(agent_data.get("preferences", {})),
                        new_resume_id
                    )
                )
            conn.commit() # Commit the update

        return {
            "message": "Resume processed and saved successfully!",
            "resume_id": str(new_resume_id),
            "filename": file.filename,
            "uploaded_at": uploaded_at,
            "extracted_data": agent_data # Returning to you so you can verify it worked
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline failure: {str(e)}")

# --- FALLBACK WEBHOOK ---
@app.post("/resumes/agent-callback")
async def agent_callback(payload: AgentCallbackPayload):
    # This remains in case your friend wants to POST directly back to your DB asynchronously later.
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM resumes WHERE id = %s;", (payload.resume_id,))
                if not cursor.fetchone():
                    raise HTTPException(status_code=404, detail=f"resume_id '{payload.resume_id}' not found.")
                
                cursor.execute(
                    """
                    UPDATE resumes 
                    SET experience = %s, skills = %s, education = %s, preferences = %s
                    WHERE id = %s;
                    """,
                    (
                        Json(payload.experience), Json(payload.skills),
                        Json(payload.education), Json(payload.preferences) if payload.preferences else None,
                        payload.resume_id
                    )
                )
            conn.commit()
        
        return {"status": "success", "message": "Updated via callback"}
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Callback failure: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8001, reload=True)