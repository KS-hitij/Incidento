from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from utils.classes import InvestigationResult
from langchain.agents import create_agent
from tools.git_tools import search_code, read_file,get_file_changes,get_repo_metadata,get_snippet,recent_changes_made_in_code,find_files_by_content,find_files_by_name,list_directory
from prompts.investigator import investigator_system_prompt
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware

# from utils.github import g, user

load_dotenv()

model = init_chat_model("google_genai:gemini-3.5-flash-lite")

investigator_agent = create_agent(
    model=model,
    tools=[search_code, read_file,get_file_changes,get_repo_metadata,get_snippet,recent_changes_made_in_code,find_files_by_content,find_files_by_name,list_directory],
    system_prompt=investigator_system_prompt,
    response_format=InvestigationResult,
    middleware=[
        ModelCallLimitMiddleware(run_limit=20,thread_limit=20),
        ToolCallLimitMiddleware(run_limit=10)
    ]
)

