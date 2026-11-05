from pydantic import BaseModel, Field

class ProposedResult(BaseModel):
    """A class representing the result of analysis sub agent having the root cause of
    the issue, evidence, code that might have caused the issue, proposed fix and
    proposed fix code."""

    proposed_fix: str
    proposed_fix_code: str
    explanation: str
    changes: str


class ErrorReport(BaseModel):
    error_code: str | None = Field(
        default=None,
        description="An actual error code explicitly present in the user's input. "
        "Do not use an exception name such as TypeError. Use null if absent.",
    )
    error_type: str | None = Field(
        default=None,
        description="Exception or error type, such as TypeError, if explicitly stated.",
    )
    error_description: str | None = None
    logs: str | None = Field(
        default=None,
        description="Log lines or stack trace explicitly provided by the user. "
        "Do not generate or summarize logs. Use null if absent.",
    )
    source_file: str | None = Field(
        
        default=None,
        description="File path explicitly mentioned in the user's input that contains the error. "
        "Do not infer or guess file paths. Use null if absent.",
    )
    line_number: int | None = Field(
        default=None,
        description="Error Line number explicitly mentioned in the user's input. "
        "Do not infer or guess line numbers. Use null if absent.",
    )


class CandidateFiles(BaseModel):
    """Structured model output containing likely files to inspect."""
    file_names: list[str]

class Keywords(BaseModel):
    """Structured model output containing likely keywords to search for in the code."""
    keywords: list[str]


class InvestigatedCode(BaseModel):
    """Structured model output containing the code that might have caused the issue."""
    file_path: str
    matching_lines: list[str]


class InvestigationResult(BaseModel):
    """Structured model output containing the results of the investigation."""
    root_cause: str
    evidence: str
    code: list[InvestigatedCode]
    confidence: float