from github import Github, Auth
import os
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("GITHUB_TOKEN")
if token:
    auth = Auth.Token(token)
    g = Github(auth=auth)
else:
    g = Github()

try:
    user = g.get_user()
except Exception:
    user = None
# Default repository used by repo-level tools (set TARGET_REPO in .env)
_repo_name = os.getenv("TARGET_REPO")
repo = g.get_repo(f'{_repo_name}') if _repo_name else None