import asyncio
import os
import sys
import uuid
import json
import httpx
from dotenv import load_dotenv

# Ensure local module path resolution works smoothly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.database import AsyncSessionLocal  
from api.models import Resume, Job         
from sqlalchemy.future import select        

from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner
from google.adk.models.lite_llm import LiteLlm

# Required structured types for Google GenAI compatibility
from google.genai.types import Content, Part

load_dotenv(override=True)
RAPID_API_KEY = os.getenv("RAPIDAPI_KEY")
AGENT_MODEL = LiteLlm(model="groq/llama-3.3-70b-versatile")


async def search_jobs(query: str, num_pages: str = "1", date_posted: str = "all") -> str:
    """
    Search for active job listings using the JSearch API platform.

    Args:
        query: The job roles and location keywords combined (e.g., 'Python Developer in New York').
        num_pages: Number of pages to fetch as a numeric string. Defaults to "1".
        date_posted: Filter by date posted. Values: 'all', 'today', '3days', 'week', 'month'. Defaults to 'all'.
    """
    # Defensive type parsing to handle any alternative string formats seamlessly
    try:
        validated_pages = int(num_pages)
    except (ValueError, TypeError):
        validated_pages = 1

    url = "https://jsearch.p.rapidapi.com/search"
    headers = {
        "x-api-host": "jsearch.p.rapidapi.com",
        "x-api-key": RAPID_API_KEY
    }
    params = {
        "query": query,
        "page": 1,
        "num_pages": validated_pages,
        "date_posted": date_posted
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params, timeout=20.0)
            
            if response.status_code == 200:
                data = response.json()
                results = data.get("data", [])
                
                cleaned_jobs = []
                for job in results[:5]:  # Process top 5 matches
                    cleaned_jobs.append({
                        "title": job.get("job_title"),
                        "company": job.get("employer_name"),
                        "location": f"{job.get('job_city', '')}, {job.get('job_country', '')}".strip(", "),
                        "jd_url": job.get("job_apply_link"),
                        "source": "jsearch"
                    })
                return json.dumps(cleaned_jobs)
            else:
                return f"Error from JSearch API: Status {response.status_code} - {response.text}"
    except Exception as e:
        return f"Failed to fetch jobs due to network exception: {str(e)}"


async def fetch_user_preferences_async(user_id: uuid.UUID) -> dict:
    """Asynchronously queries the resumes table for the target user's JSONB preference block."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Resume).where(Resume.user_id == user_id)
        )
        resume = result.scalar_one_or_none()
        if resume and resume.preferences:
            return resume.preferences
    return {}


def create_personalized_agent(preferences: dict) -> Agent:
    """Maps custom JSONB preference parameters into structured instructions for the native search tool."""
    raw_roles = preferences.get("target_roles", "Software Engineer")
    role = raw_roles[0] if isinstance(raw_roles, list) and raw_roles else raw_roles

    raw_locations = preferences.get("locations", "United States")
    location = raw_locations[0] if isinstance(raw_locations, list) and raw_locations else raw_locations

    instruction_payload = (
        "You are an expert job search agent. Your sole purpose is to find open job positions matching a candidate profile.\n\n"
        "CANDIDATE CRITERIA:\n"
        f"- Target Role: {role}\n"
        f"- Target Location: {location}\n\n"
        "EXECUTION PROTOCOL:\n"
        f"1. You must immediately call the `search_jobs` tool. Use exactly '{role} in {location}' as your search query argument value.\n"
        "2. Rely entirely on the tool's structural definition parameters. Do not attempt to alter or invent parameter wrappers.\n"
        "3. Once you receive data back from the tool execution, convert those results into a raw JSON array of objects.\n"
        "4. Your final message response must exclusively be the JSON array containing these exact keys: 'title', 'company', 'location', 'jd_url', 'source'. "
        "Do not include any markdown fences, conversational introductions, or explanations."
    )

    return Agent(
        model=AGENT_MODEL, 
        name="job_search_agent",
        instruction=instruction_payload,
        tools=[search_jobs],  
    )


async def run_personalized_discovery(user_id_str: str, resume_id_str: str):
    """Executes the core pipeline to retrieve recommendations from the agent and persist results."""
    user_uuid = uuid.UUID(user_id_str)
    resume_uuid = uuid.UUID(resume_id_str)
    
    print(f"\n--- Starting Discovery Job Pipeline for Resume UUID: {resume_uuid} ---")

    # 1. Fetch user preferences from DB
    preferences = await fetch_user_preferences_async(user_uuid)
    
    # 2. Setup agent and underlying runner
    job_search_agent = create_personalized_agent(preferences)
    app_name = job_search_agent.name or "job_search_agent"
    
    runner = InMemoryRunner(agent=job_search_agent, app_name=app_name)
    
    # 3. Pre-register the dynamically generated session ID to avoid SessionNotFoundError
    await runner.session_service.create_session(
        app_name=app_name,
        user_id=user_id_str,
        session_id=resume_id_str
    )
    
    print("Launching JSearch Agent queries...")
    search_prompt = "Execute a job search using your tool based on the candidate's custom role and location rules."
    final_text = ""
    
    # 4. Construct ADK/GenAI payload layout
    user_message = Content(
        role="user",
        parts=[Part.from_text(text=search_prompt)]
    )
    
    # 5. Execute agent query loop asynchronously
    async for event in runner.run_async(
        user_id=user_id_str,
        session_id=resume_id_str,
        new_message=user_message
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = event.content.parts[0].text.strip()
            print("\n--- Raw Agent Response Output Captured ---")

    # 6. Parse structured final output payload and update database
    try:
        if not final_text:
            raise ValueError("Agent failed to return a valid final response block.")

        # Strip standard markdown formatting fences if returned by the LLM
        if final_text.startswith("```"):
            final_text = final_text.split("```")[1].replace("json", "").strip()
            
        found_jobs = json.loads(final_text)
        print(f"Agent successfully extracted {len(found_jobs)} matching job listings!")
        
        async with AsyncSessionLocal() as session:
            for job_data in found_jobs:
                new_job = Job(
                    resume_id=resume_uuid,
                    title=job_data.get("title"),
                    company=job_data.get("company"),
                    location=job_data.get("location"),
                    jd_url=job_data.get("jd_url"),
                    source=job_data.get("source", "jsearch"),
                    match_score=1.0
                )
                session.add(new_job)
            await session.commit()
            
        print("Successfully synchronized agent data to PostgreSQL 'jobs' table!")
        
    except Exception as e:
        print(f"Failed to automatically store jobs to DB: {str(e)}")
        print(f"Raw Agent Text was: {final_text}")


if __name__ == "__main__":
    # Test execution harness
    async def run_local_test_harness():
        print("Initializing database lookup for verification test...")
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Resume).limit(1))
            sample_record = result.scalar_one_or_none()
            
            if sample_record:
                print(f"Found existing record. User ID: {sample_record.user_id} | Resume ID: {sample_record.id}")
                await run_personalized_discovery(str(sample_record.user_id), str(sample_record.id))
            else:
                print("❌ Testing Error: The resumes table is currently empty.")

    asyncio.run(run_local_test_harness())