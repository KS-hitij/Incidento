# Incidento

Incidento is a multi-agent system for investigating production errors.
Given an error report, it inspects a GitHub repository, identifies the
code that likely caused the problem, and proposes a fix. The intended
end state is to apply approved fixes back to the repository. That part
is still in progress.

## Status

Work in progress. The investigation and fix-proposal flow runs end to
end. Human approval is handled through a LangGraph interrupt. Applying
changes to the target repository is not implemented yet.

## Requirements

- Python 3.11
- A GitHub personal access token with repository access
- A Google API key for Gemini

## Setup

1. Clone the repository and create a virtual environment:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Create a `.env` file in the project root:

   ```bash
   export GOOGLE_API_KEY="your-google-api-key"
   GITHUB_TOKEN="your-github-token"
   TARGET_REPO="owner/repo-name"
   ```

   `TARGET_REPO` must be in `owner/repo` form, for example
   `KS-hitij/orderflow-api`.

3. Edit the error input in `agents/agent.py`. The error is currently
   hardcoded in the `graph.invoke(...)` call near the bottom of the file.

4. Run the agent:

   ```bash
   python -m agents.agent
   ```

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_API_KEY` | Yes | Google Gemini API key |
| `GITHUB_TOKEN` | Yes | GitHub personal access token |
| `TARGET_REPO` | Yes | Target repository in `owner/repo` form |

## Project layout

```text
agents/
  agent.py          Manager graph: intake, investigation, proposal, approval
  investigator.py   Agent that inspects the repository
  proposer.py       Agent that proposes a fix
prompts/
  orchestrator.py   Prompt for converting raw input into ErrorReport
  investigator.py   Investigator system prompt
  proposer.py       Proposer system prompt
tools/
  investigator.py   Investigator tools
  git_tools.py      Repository tools used by the proposer
utils/
  classes.py        Pydantic models
  github.py         GitHub client and repository handle
  investigator.py   README section helpers
```

## How it works

1. `intake_and_validate` converts the user's error message into an
   `ErrorReport`.
2. `investigate_error_files` runs the investigator agent. It searches
   the repository, reads files, and returns an `InvestigationResult`.
3. `propose_fix` runs the proposer agent. It reads the relevant code
   and returns a `ProposedResult` with a suggested fix and code.
4. `ask_for_approval` pauses the graph with a LangGraph interrupt.
   The script prints the proposal and waits for `y` or `n`.
5. If approved, the flow continues to `implementer`. That node is
   a placeholder and does not modify the repository yet.

## Available tools

The agents use read-only repository tools:

- `search_code` - search the repository using GitHub code search
- `read_file` - read a file with line numbers
- `get_snippet` - read a numbered window of lines around a range
- `list_directory` - list files and folders in a directory
- `find_files_by_name` - find files by filename keywords
- `find_files_by_content` - find files by content keywords
- `get_repo_metadata` - repository name, language, branch, URL
- `recent_changes_made_in_code` - recently changed files
- `get_file_changes` - details of a specific commit

## Limitations

- Applying changes to the target repository is not implemented yet.
- GitHub code search is limited to 30 requests per minute.
- Gemini free-tier token limits apply.
- `find_files_by_name` and `find_files_by_content` only search the
  top level of the given directory.
- `TARGET_REPO` must be set and in `owner/repo` form.
- There is no sandboxed execution of proposed fixes.
- There are no automated tests for this project yet.

## Development

Run the project:

```bash
python -m agents.agent
```

The input error is hardcoded in `agents/agent.py`. Change it there to
test different cases.

Dependencies are listed in `requirements.txt`.
