from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from utils.classes import ProposedResult
from langchain.agents import create_agent
from tools.git_tools import search_code, read_file,get_repo_metadata,get_snippet,list_directory
from prompts.proposer import proposer_system_prompt
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware

load_dotenv()

model = init_chat_model("google_genai:gemini-3.5-flash-lite")

proposer_agent = create_agent(
    model=model,
    tools=[read_file,get_snippet,search_code,get_repo_metadata,list_directory],
    system_prompt=proposer_system_prompt,
    response_format=ProposedResult,
    middleware=[
        ModelCallLimitMiddleware(run_limit=25,thread_limit=25),
        ToolCallLimitMiddleware(run_limit=20,thread_limit=20)
    ]
)