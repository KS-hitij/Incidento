from datetime import datetime, timedelta
import os
from utils.github import g, user, repo
from langchain.tools import tool

def _normalize_path(p: str) -> str:
    p = (p or "").strip().lstrip("/")
    repo_name = os.getenv("TARGET_REPO", "").split("/")[-1]
    if repo_name:
        if p == repo_name:
            return ""
        if p.startswith(repo_name + "/"):
            p = p[len(repo_name) + 1:]
    return p



@tool
def search_code(query: str, repo_name: str = None):
    """Searches the repository using GitHub code search and returns matching files with line text.
    Arguments:
    query: The search query string.
    repo_name: The "owner/repo" name. Falls back to TARGET_REPO env var.
    Returns:
    A list of dictionaries containing the file path and matching lines.
    """
    results = []
    name = repo_name or os.getenv("TARGET_REPO")
    qualifiers = {}
    if name:
        qualifiers["repo"] = name
    try:
        search_result = g.search_code(query, **qualifiers)
        items = list(search_result)[:20]
    except Exception as e:
        return [{"error": f"search failed: {e}"}]

    for item in items:
        cf = None
        if repo is not None:
            try:
                cf = repo.get_contents(item.path)
            except Exception:
                cf = None
        if cf is None and getattr(item, "repository", None):
            try:
                cf = item.repository.get_contents(item.path)
            except Exception:
                cf = None

        raw = getattr(cf, "decoded_content", None) if cf is not None else None
        lines = raw.decode("utf-8", errors="replace").splitlines() if raw is not None else []

        matches = []
        for ln in (item.line_numbers or []):
            try:
                idx = int(ln) - 1
                if 0 <= idx < len(lines):
                    matches.append({"line": int(ln), "text": lines[idx]})
            except (ValueError, TypeError):
                continue

        results.append({
            "file": item.path,
            "matches": matches,
            "line_numbers": item.line_numbers,
            "url": item.html_url,
        })

    return results


@tool
def read_file(file_path: str):
    """Reads the content of the specified file in the repository and returns it with line numbers.

    Arguments:
    file_path: The path to the file in the repository.
    Returns:
    A dictionary containing the file path, total lines, and a list of {line, text} entries.
    """
    try:
        file_path = _normalize_path(file_path)
        content_file = repo.get_contents(file_path)
    except Exception as e:
        return {"file": file_path, "error": f"could not read file: {e}"}

    raw = content_file.decoded_content
    if raw is None:
        return {"file": file_path, "error": "binary or too-large file"}

    lines = raw.decode("utf-8", errors="replace").splitlines()
    return {
        "file": file_path,
        "total_lines": len(lines),
        "lines": [{"line": i, "text": text} for i, text in enumerate(lines, 1)],
    }

@tool
def get_repo_metadata():
    """Returns basic information about the GitHub repository.
    Use this tool to get the repository name, description, URL, default branch, and primary language.
    Returns:
    A dictionary containing the repository name, description, URL, default branch, and primary language."""
    if not repo:
        return {"error": "TARGET_REPO not set"}
    return {
        "name": repo.name,
        "description": repo.description,
        "url": repo.html_url,
        "default_branch": repo.default_branch,
        "language": repo.language
    }


@tool
def list_directory(path:str):
    """Lists the contents of the specified directory in the repository.
    Use this tool to explore the files and directories in the repository.
    Arguments:
    path: The path to the directory in the repository.
    Returns:
    A list of dictionaries containing the name, path, type (file or directory), and size (if applicable) of each item in the directory.
    """
    path = _normalize_path(path)
    print("Path in list directory: ",path)
    contents = repo.get_contents(path)
    if not isinstance(contents, list):
        return [{"error": f"Path '{path}' is not a directory"}]
    
    results = []
    for content_file in contents:
        file_name = content_file.name
        file_path = content_file.path
        type = "dir" if content_file.type == "dir" else "file"
        file_size = content_file.size if type == "file" else None
        results.append({
            "name": file_name,
            "path": file_path,
            "type": type,
            "size": file_size
        })
    return results


@tool
def find_files_by_content(directory:str,keywords:list):
    """Explores the specified directory in the repository and returns a list of files that have data matching the given keywords from the error report.
    Does not search in subdirectories.
    Use this tool to find files that contain specific keywords in their content.
    Arguments:
    directory: The path to the directory in the repository.
    keywords: A list of keywords to search for in the file contents.
    Returns:
    A list of file paths that match the given keywords.
    """
    results = []
    contents = repo.get_contents(directory)

    if not isinstance(contents,list):
        return [{"error": f"No files present with the given keywords in the repo"}]

    for content_file in contents:
        if content_file.type == "file":
            data = content_file.decoded_content.decode("utf-8")
            if any(keyword.lower() in data.lower() for keyword in keywords):
                results.append(content_file.path)
    return results

@tool
def find_files_by_name(directory:str,keywords:list):
    """Explores the specified directory in the repository and returns a list of files that have names matching the given keywords from the error report.
    Does not search the content of the files, only their names.
    Does not explore subdirectories, only the specified directory.
    Use this tool to find files that contain specific keywords in their names.
    Arguments:
    directory: The path to the directory in the repository.
    keywords: A list of keywords to search for in the file names.
    Returns:
    A list of file paths that match the given keywords.
    """
    results = []
    try:
        contents = repo.get_contents(directory)
        if not isinstance(contents,list):
            return [{"error": f"No files with this name present"}]

        for content_file in contents:
            if content_file.type == "file":
                if any(keyword.lower() in content_file.name.lower() for keyword in keywords):
                    results.append(content_file.path)
        return results
    except Exception:
        return [{"error":f"{Exception}"}]



@tool
def get_snippet(file_path: str, start_line: int, end_line: int, context: int = 5):
    """Returns a numbered window of lines around the requested range.

    Arguments:
    file_path: Path to the file in the repository.
    start_line: Starting line number (1-based, inclusive).
    end_line: Ending line number (1-based, inclusive).
    context: Number of lines to include before and after the range.
    Returns:
    A dictionary with requested bounds, actual snippet bounds, total lines,
    and numbered snippet lines.
    """
    file_path = _normalize_path(file_path)

    if not repo:
        return {"file_path": file_path, "error": "TARGET_REPO not set"}

    try:
        content_file = repo.get_contents(file_path)
    except Exception as e:
        return {"file_path": file_path, "error": f"could not read file: {e}"}

    if isinstance(content_file, list):
        return {"file_path": file_path, "error": "path is a directory, not a file"}

    raw = content_file.decoded_content
    if raw is None:
        return {"file_path": file_path, "error": "binary or too-large file"}

    lines = raw.decode("utf-8", errors="replace").splitlines()
    total = len(lines)

    if total == 0:
        return {"file_path": file_path, "error": "file is empty"}

    if start_line < 1 or end_line < 1 or start_line > end_line:
        return {"file_path": file_path, "error": "invalid line range"}

    if start_line > total or end_line > total:
        return {
            "file_path": file_path,
            "error": f"line range out of bounds (file has {total} lines)",
        }

    snippet_start = max(1, start_line - context)
    snippet_end = min(total, end_line + context)

    snippet_lines = [
        {"line": i, "text": lines[i - 1]}
        for i in range(snippet_start, snippet_end + 1)
    ]

    return {
        "file_path": file_path,
        "requested_start_line": start_line,
        "requested_end_line": end_line,
        "snippet_start_line": snippet_start,
        "snippet_end_line": snippet_end,
        "total_lines": total,
        "snippet_lines": snippet_lines,
    }


@tool
def recent_changes_made_in_code(days:int=7):
    """Returns a list of files with messages of the changes that were made in the last 'days' days in the repository.
    Use this tool to get a list of recently changed files in the repository, along with their commit messages.
    Arguments:
    days: The number of days to look back for recent changes (default is 7).
    Returns:
    A list of dictionaries containing the file path, commit message, and commit date for each recently changed file.
    """
    commits = repo.get_commits(since=datetime.now() - timedelta(days=days))
    results = []
    for commit in commits:
        for file in commit.files:
            results.append({
                "file_path": file.filename,
                "commit_message": commit.commit.message,
                "commit_date": commit.commit.author.date.isoformat(),
                "commit_sha": commit.sha
            })
    return results

@tool
def get_file_changes(sha:str):
    """Returns the changes made in a specific commit identified by its SHA.
    Use this tool to get the details of the changes made in a specific commit in the repository.
    Arguments:
    sha: The SHA of the commit to retrieve changes for.
    Returns:
    A list of dictionaries containing the file path, change type (added, modified, removed), and patch (if applicable) for each changed file in the commit.
    """
    commit = repo.get_commit(sha)
    results = []
    for file in commit.files:
        results.append({
            "file_path": file.filename,
            "change_type": file.status,
            "patch": file.patch if hasattr(file, 'patch') else None,
            "additions": file.additions,
            "deletions": file.deletions,
            "changes": file.changes
        })
    return results
