from google.adk.agents import Agent
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams, StdioConnectionParams
from mcp import StdioServerParameters
import os
import asyncio
from google.adk.runners import InMemoryRunner
from dotenv import load_dotenv


load_dotenv(override=True)

APIFY_TOKEN = os.getenv("APIFY_API_TOKEN")
print(os.getenv("GOOGLE_API_KEY"))
#JOB_SEARCH_LLM = "groq/llama-3.3-70b-versatile"
#llm = LiteLlm(model=JOB_SEARCH_LLM)

job_search_agent = Agent(
    model = "gemini-2.5-flash",
    name = "job_search_agent",
    instruction = (
        "You are an expert technical recruiting agent and data writer. Your workflow is:\n"
        "1. Fetch data: Use 'fetch_cat--lever-jobs-scraper' to find job postings, then immediately "
        "invoke 'get-dataset-items' with the datasetId to pull the raw details.\n"
        "2. Score: Compare the job descriptions against these user skills: [Python, React, SQL, Graph Neural Networks]. "
        "Calculate an estimated match percentage score (0-100%) for each job.\n"
        "3. Export: Use your Excel tools to create a workbook named 'Job_Match_Report.xlsx'. "
        "Write rows containing the Company Name, Job Posting URL, and Skill Match Score."
    ),

    tools = [
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url="https://mcp.apify.com?tools=fetch_cat/lever-jobs-scraper",
                headers={
                    "Authorization": f"Bearer {APIFY_TOKEN}",
                },
            ),
            tool_filter=["fetch_cat--lever-jobs-scraper", "get-dataset-items"]
        ),

        McpToolset(
            connection_params=StdioConnectionParams(
                timeout=50,
                server_params = StdioServerParameters(
                    command="python",
                    args=["-m", "excel_mcp", "stdio"],
                    # We point the tool's execution directory to /app so files save directly to your workspace folder
                    env={"EXCEL_FILES_PATH": "/app"}
                )
            )
        )
    ],
)


if __name__ == "__main__":
    print("Booting Job Search Agent")


    async def main():
        runner = InMemoryRunner(agent=job_search_agent)
        events = await runner.run_debug(
            "Find 3 active engineering jobs at Spotify in London, calculate their match scores, and export them to an Excel file.",
            verbose=True,
        )

    asyncio.run(main())
