import asyncio
import os
from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from mcp import StdioServerParameters
from dotenv import load_dotenv
from google.adk.models.lite_llm import LiteLlm
load_dotenv(override=True)

RAPID_API_KEY = os.getenv("RAPIDAPI_KEY")
print("Google API Key configured:", os.getenv("GOOGLE_API_KEY") is not None)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if GROQ_API_KEY:
    os.environ["GROQ_API_KEY"] = GROQ_API_KEY   

print("GROQ API Key configured:", os.getenv("GROQ_API_KEY") is not None)

AGENT_MODEL = LiteLlm(model="groq/llama-3.3-70b-versatile")

job_search_agent = Agent(
    model=AGENT_MODEL, 
    name="job_search_agent",
    instruction=(
        "You are an expert technical recruiting agent specializing in the JSearch platform.\n\n"
        
        "CRITICAL TOOL PARAMETER RULES:\n"
        "When calling the job discovery or search tools, you must respect the following parameter schemas:\n"
        "1. 'query' (string): Must contain the role and location keywords (e.g., 'Python Developer in London').\n"
        "2. 'num_pages' (integer): This represents the page depth. You MUST provide this parameter strictly as an INTEGER (e.g., 1, 2) and NEVER as a string (do NOT use '1').\n"
        "3. 'page' (integer): Always pass as an integer type.\n"
        "4. 'date_posted' (string): Filter values can only be 'all', 'today', '3days', 'week', or 'month'.\n\n"
        
        "Extract clean keywords based on the user's instructions and call the search tool matching these exact validation rules."
    ),

    tools=[
        McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command="npx",
                    args=[
                        "mcp-remote",
                        "https://mcp.rapidapi.com",
                        "--header",
                        "x-api-host: jsearch.p.rapidapi.com",
                        "--header",
                        f"x-api-key: {RAPID_API_KEY}"
                    ]
                )
            )
        )
    ],
)

if __name__ == "__main__":
    print("Booting Job Search Agent via RapidAPI JSearch Server...")

    async def main():
        runner = InMemoryRunner(agent=job_search_agent)
        
        print("\n--- Starting Debug Session ---")
        async for event in await runner.run_debug(
            "Find 3 active engineering jobs at Spotify in London using your tools.",
            verbose=True,
        ):
            print(event)
            
        print("\n--- Debug Session Ended ---")

    asyncio.run(main())