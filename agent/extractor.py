import asyncio
import json
from fastapi import FastAPI, HTTPException
import os
from typing import List
import litellm
from dotenv import load_dotenv
from google.adk import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import InMemoryRunner
from pydantic import BaseModel, Field
import uvicorn
load_dotenv(override=True)

app = FastAPI()

api_key = os.getenv("GOOGLE_API_KEY")
if api_key:
    os.environ["GEMINI_API_KEY"] = api_key

groq_api_key = os.getenv("GROQ_API_KEY")
if groq_api_key:
    os.environ["GROQ_API_KEY"] = groq_api_key

EXTRACTION_MODEL = "groq/llama-3.3-70b-versatile"
AGENT_MODEL = LiteLlm(model=EXTRACTION_MODEL)


# ==========================================
# SCHEMA STRUCTS
# ==========================================
class ExtractorSkills(BaseModel):
    hard_skills: List[str] = Field(
        description="Teachable, measurable abilities or proficiencies specific to the job."
    )
    tools_and_technologies: List[str] = Field(
        description="Software, hardware, machinery, or physical tools used."
    )
    core_competencies: List[str] = Field(
        description="Interpersonal, behavioral, or organizational strengths."
    )

class WorkExperienceItem(BaseModel):
    company: str = Field(description="Name of the company or organization")
    role: str = Field(description="Job title or position held")
    start_date: str = Field(description="Start date of employment")
    end_date: str = Field(description="End date or 'Present'")
    responsibilities: List[str] = Field(description="Bullet points describing duties and achievements")

class EducationItem(BaseModel):
    institution: str = Field(description="Name of the university, college, or school")
    degree: str = Field(description="Degree earned")
    field_of_study: str = Field(description="Major or specialization")
    graduation_date: str = Field(description="Graduation date or expected graduation")

class FullResumeExtraction(BaseModel):
    skills: ExtractorSkills = Field(description="Categorized inventory of all skills found.")
    work_history: List[WorkExperienceItem] = Field(description="Chronological history of experience.")
    education_history: List[EducationItem] = Field(description="List of academic accomplishments.")

class ResumePayload(BaseModel):
    text: str


# ==========================================
# TOOL FUNCTION
# ==========================================
def extraction(text: str) -> dict:
    """
    Analyzes the entire raw resume text and extracts structural profiles 
    using the assigned LiteLLM back-end model wrapper.
    """
    system_instruction = (
        "You are an expert HR parsing engine. Analyze the provided resume text and "
        "comprehensively extract all professional information into the requested structured JSON format.\n\n"
        "Guidelines:\n"
        "1. Do not skip or truncate any details. Ensure all bullet points under experience are completely preserved.\n"
        "2. Parse dates cleanly into standard readable text.\n"
        "3. Only extract values explicitly supported by the text. Avoid hallucinations."
    )
    
    user_prompt = f"RESUME TEXT: \n{text}"

    response = litellm.completion(
        model=EXTRACTION_MODEL,
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_prompt},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "FullResumeExtraction",
                "schema": FullResumeExtraction.model_json_schema(),
            },
        },
        temperature=0.1,
    )

    return json.loads(response.choices[0].message.content)

# ==========================================
# AGENT DECLARATION
# ==========================================
extract_agent = Agent(
    model=AGENT_MODEL,
    name="extract_agent",
    description="Extracts structured skills, work history, and education profiles from raw text.",
    instruction=(
        "You are a specialized HR Data Extraction Agent. Call your `extraction` tool function "
        "on the input text payload. You must output the final result as a raw JSON string matching "
        "the structure returned by the tool, enclosed in standard markdown backticks."
    ),
    tools=[extraction]
)



@app.post("/extract-agent", response_model=FullResumeExtraction)
async def extract_resume_data(payload: ResumePayload):
    """
    Accepts raw text from parsed document payloads and pipelines it through
    the ADK Agent + Groq Llama-3.3 model engine, returning a clean JSON structure.
    """
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Provided resume text content cannot be blank.")

    async with InMemoryRunner(agent=extract_agent) as runner:
        try:
            events = await runner.run_debug(
                f"Use your extraction tool to pull everything out of this text:\n{payload.text}",
                quiet=True,
            )
            for event in events:
                for fr in event.get_function_responses():
                    if fr.name == "extraction" and fr.response:
                        return FullResumeExtraction.model_validate(fr.response)

            for event in reversed(events):
                if not event.content or not event.content.parts:
                    continue
                for part in event.content.parts:
                    if not part.text:
                        continue
                    text_content = part.text.strip()
                    if "```json" in text_content:
                        text_content = text_content.split("```json")[1].split("```")[0].strip()
                    elif "```" in text_content:
                        text_content = text_content.split("```")[1].split("```")[0].strip()
                    try:
                        return FullResumeExtraction.model_validate_json(text_content)
                    except Exception:
                        continue

            raise HTTPException(
                status_code=502,
                detail="The agent framework failed to produce a cleanly structured JSON response.",
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Internal agent pipeline execution crash: {str(e)}",
            )

if __name__ == "__main__":
    uvicorn.run("extractor:app", host="127.0.0.1", port=8005, reload=True)