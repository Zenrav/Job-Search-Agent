from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks # 1. Added BackgroundTasks
from pydantic import BaseModel
from typing import Any, Dict, Optional, List
import fitz  # PyMuPDF
from uuid import UUID
import psycopg2
from psycopg2.extras import register_uuid, Json
import os
import sys
from dotenv import load_dotenv
import httpx
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# 2. Import your job search agent runner
from agent.job_discovery import run_personalized_discovery

load_dotenv()

register_uuid()

app = FastAPI(
    title="Resume Parser & Storage API",
    description="Multi-step async pipeline optimized for PostgreSQL JSONB architecture.",
    version="2.0.0"
)

AGENT_API_URL = os.getenv("AGENT_API_URL", "http://extractor-agent:8005/extract-agent")

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "job_search_db"),
    "user": os.getenv("DB_USER", "postgres_admin"),
    "password": os.getenv("DB_PASSWORD", "super_secret_password_123"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432")
}

def get_db_connection():
    try:
        return psycopg2.connect(**DB_CONFIG)
    except psycopg2.OperationalError as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

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


@app.post("/resumes/upload")
async def upload_and_extract_resume(
    file: UploadFile = File(...), 
    background_tasks: BackgroundTasks = BackgroundTasks() # 3. Injected background task queue
):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDFs are allowed.")
    
    try:
        # Step 1: Extract raw text from PDF
        pdf_data = await file.read()
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        raw_text = "".join([page.get_text() for page in doc])
        
        # Step 2: Insert initial placeholder into database
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
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
                
                # FIX: Added 'raw_text' to satisfy the NULL constraint in models.py
                cursor.execute(
                    """
                    INSERT INTO resumes (user_id, filename, raw_text)
                    VALUES (%s, %s, %s)
                    RETURNING id, uploaded_at;
                    """,
                    (auto_user_id, file.filename, raw_text)
                )
                db_row = cursor.fetchone()
                new_resume_id = db_row[0]
                uploaded_at = db_row[1]
            conn.commit()

        # Step 3: Call the Extraction Agent API
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

        # Step 4: Map incoming data defensively to verify your JSONB keys align
        preferences_payload = agent_data.get("preferences", {})
        
        # If the extractor used different key names, map them securely here:
        final_preferences = {
            "target_roles": preferences_payload.get("target_roles", preferences_payload.get("job_title", [])),
            "locations": preferences_payload.get("locations", preferences_payload.get("location", [])),
            "salary": preferences_payload.get("salary", "Not Specified"),
            "industries": preferences_payload.get("industries", [])
        }

        # Step 5: Update database with final structured data
        print("UPDATE DB!")   
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
                        Json(final_preferences), # Using the mapped clean dictionary
                        new_resume_id
                    )
                )
            conn.commit()
            print("Updated!")

        # Step 6: Trigger the Job Search Agent in the background!
        # This will run as an isolated task while your API returns a 200 OK response immediately.
        background_tasks.add_task(run_personalized_discovery, str(auto_user_id), str(new_resume_id))
        print(f"Job discovery agent dispatched in background for User ID: {auto_user_id}")

        return {
            "message": "Resume processed and saved successfully! Discovery agent launched.",
            "resume_id": str(new_resume_id),
            "user_id": str(auto_user_id),
            "filename": file.filename,
            "uploaded_at": uploaded_at,
            "extracted_data": agent_data 
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline failure: {str(e)}")

# --- FALLBACK WEBHOOK ---
@app.post("/resumes/agent-callback")
async def agent_callback(payload: AgentCallbackPayload, background_tasks: BackgroundTasks = BackgroundTasks()):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, user_id FROM resumes WHERE id = %s;", (payload.resume_id,))
                row = cursor.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail=f"resume_id '{payload.resume_id}' not found.")
                user_id = row[1]
                
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
        
        # Also trigger discovery here if a fallback webhook execution happens
        background_tasks.add_task(run_personalized_discovery, str(user_id), str(payload.resume_id))
        return {"status": "success", "message": "Updated via callback. Discovery agent launched."}
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Callback failure: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8001, reload=True)