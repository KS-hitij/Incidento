from datetime import datetime, timedelta
import os
from utils.github import g, user, repo
from langchain.tools import tool

def _normalize_path(p: str) -> str:
    p = p.strip().lstrip("/")
    # strip a leading repo-name segment if present
    repo_name = os.getenv("TARGET_REPO", "").split("/")[-1]
    if repo_name and p.startswith(repo_name + "/"):
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
    if contents is None or contents.type != "dir":
        raise ValueError(f"Path '{path}' is not a valid directory in the repository.")
    
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
    contents = repo.get_contents(directory)

    for content_file in contents:
        if content_file.type == "file":
            if any(keyword.lower() in content_file.name.lower() for keyword in keywords):
                results.append(content_file.path)
    return results


@tool
def get_snippet(file_path:str, start_line:int, end_line:int,context:int=15):
    """Returns a snippet of the specified file in the repository, from start_line to end_line (inclusive).
    Use this tool to get a snippet of a file in the repository, with optional context lines before and after the specified range.
    Arguments:
    file_path: The path to the file in the repository.
    start_line: The starting line number (1-based index).
    end_line: The ending line number (1-based index).
    context: The number of context lines to include before and after the specified range.
    Returns:
    A dictionary containing the file path, line numbers, total lines, and the snippet lines.
    """
    file_path = _normalize_path(file_path)
    raw = repo.get_contents(file_path).decoded_content
    if raw is None:
        raise ValueError(f"Can not read binary/large file: {file_path}")
    content = raw.decode("utf-8")
    lines = content.splitlines()

    if lines is None or len(lines) == 0:
        raise ValueError(f"File is empty or could not be read: {file_path}")
    
    # Adjust for 1-based index
    start_index = max(start_line -  context, 1)
    end_index = min(end_line + context, len(lines))

    if start_index > end_index:
        raise ValueError(f"Invalid line range: start_line ({start_line}) is greater than end_line ({end_line})")
    
    snippet_lines = [{"line_number": i + 1, "content": lines[i]} for i in range(start_index - 1, end_index)]
    
    return{
        "file_path": file_path,
        "start_line": start_line,
        "end_line": end_line,
        "total_lines": len(lines),
        "snippet_lines": snippet_lines
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
