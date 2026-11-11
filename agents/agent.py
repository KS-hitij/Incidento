import os
from langgraph.graph import StateGraph, START, END
from langchain.chat_models import init_chat_model
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from pydantic import BaseModel
from utils.classes import InvestigationResult, ProposedResult, ErrorReport
from prompts.orchestrator import system_prompt
from .investigator import investigator_agent
from .proposer import proposer_agent
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")

model = init_chat_model("google_genai:gemini-3.5-flash-lite")

serde = JsonPlusSerializer(
    allowed_msgpack_modules=[
        ("utils.classes", "ErrorReport"),
        ("utils.classes", "InvestigationResult"),
        ("utils.classes", "ProposedResult"),
        ("utils.classes", "CandidateFiles"),
        ("utils.classes", "Keywords"),
        ("utils.classes", "InvestigatedCode"),
    ]
)

class InputValidation(BaseModel):
    is_production_error: bool
    reason: str | None = None


class AgentState(BaseModel):
    messages: list[dict] = []
    investigation_results: InvestigationResult | None = None
    proposed_results: ProposedResult | None = None
    error_report: ErrorReport | None = None
    investigation_retry_count: int = 2
    analysis_retry_count: int = 2
    repo_name: str | None = None
    candidate_files: list[str] | None = None
    approved: bool | None = None
    status: str | None = None
    rejected_reason: str | None = None

def intake_and_validate(state: AgentState):
    """Intake and validate the input messages and produce a structured
    report of the error details provided by human"""
    # if state.repo_name is None:
    #     raise ValueError("Repository name is missing.")

    validation = model.with_structured_output(InputValidation).invoke([
        {"role": "system", "content":
            "Classify whether the user input is a software error report. "
            "Return is_production_error=true if it contains any of: an error code, "
            "exception, stack trace, HTTP failure, compile/type error, lint error, "
            "build failure, or concrete runtime failure. "
            "The input may be a raw JSON diagnostic from an IDE or CI tool. "
            "Return false only for greetings, questions, or unrelated text."},
        {"role": "user", "content": state.messages[-1]["content"]},
    ])


    if not validation.is_production_error:
        return {
            "error_report": None,
            "status": "rejected",
            "rejection_reason": validation.reason or "Input is not a production error report.",
        }
    
    messages = [
        {"role": "system", "content": system_prompt},
        *state.messages,
    ]
    error_report = model.with_structured_output(ErrorReport).invoke(messages)
    return {"error_report": error_report}


def route_after_intake(state: AgentState):
    return END if state.status == "rejected" else "investigate_error_files"


def investigate_error_files(state:AgentState):
    """Investigate the error files based on the structured error report."""
    investigation_results = investigator_agent.invoke({
        "messages":[{"role":"user","content":state.error_report.model_dump_json()}]
    })
    return {"investigation_results": investigation_results.get("structured_response")}

def propose_fix(state:AgentState):
    """Propose a fix based on the investigation results."""
    proposed_results = proposer_agent.invoke({
        "messages":[{"role":"user","content":state.investigation_results.model_dump_json()}]
    })
    return {"proposed_results": proposed_results.get("structured_response")}

def ask_for_approval(state:AgentState):
    """Ask for human approval of the proposed fix."""
    decision = interrupt({
        "type": "approval_request",
        "message": "Do you approve the proposed fix?",
        "problem_details": state.error_report.model_dump_json(),
        "root_cause": state.investigation_results.root_cause,
        "code": state.investigation_results.code,
        "confidence": state.investigation_results.confidence,
        "proposed_fix": state.proposed_results.proposed_fix,
        "proposed_fix_code": state.proposed_results.proposed_fix_code,
        "explanation": state.proposed_results.explanation,
        "patch": state.proposed_results.patch
    })
    approved = str(decision).strip().lower() in ("y", "yes", "approve", "approved")
    return {"approved": approved}


def implementer(state:AgentState):
    """Implement the proposed fix in the github repo."""
    pass


graph = StateGraph(AgentState)
graph.add_node("intake_and_validate", intake_and_validate)
graph.add_node("investigate_error_files", investigate_error_files)
graph.add_node("propose_fix", propose_fix)
graph.add_node("ask_for_approval", ask_for_approval)
graph.add_edge(START, "intake_and_validate")
graph.add_conditional_edges(
    "intake_and_validate",
    route_after_intake,
    {"investigate_error_files": "investigate_error_files", END: END},
)
graph.add_edge("investigate_error_files", "propose_fix")
graph.add_edge("propose_fix", "ask_for_approval")
graph.add_edge("ask_for_approval", END)

checkpointer = InMemorySaver(serde=serde)
graph = graph.compile(checkpointer=checkpointer)


config = {"configurable": {"thread_id": "test_thread"}}
result = graph.invoke(
    {
        "messages": [
            {
                "role": "user",
                "content": r"""I am getting this error:
                    [{
                "resource": "orderflow-api/src/modules/auth/auth.service.ts",
                "owner": "typescript",
                "code": "2345",
                "severity": 8,
                "message": "Argument of type 'User | undefined' is not assignable to parameter of type 'User'.\n  Type 'undefined' is not assignable to type 'User'.",
                "source": "ts",
                "startLineNumber": 45,
                "startColumn": 33,
                "endLineNumber": 45,
                "endColumn": 37,
                "origin": "extHost1"
        }]
                """,
            }
        ]
    },
    config=config,
)

if "__interrupt__" in result:
    print("The process was interrupted. Please check the interrupt details.")
    payload = result["__interrupt__"][0].value
    print("\nRoot Cause:",payload["root_cause"],"\n")
    print("\nCode:",payload["code"],"\n")
    print("\nConfidence:",payload["confidence"],"\n")
    print("\nProposed_fix:\n",payload["proposed_fix"])
    print("\nExplanation:",payload["explanation"],"\n")
    print("\nPatch: ",payload["patch"],"\n")

    decision = input("Approve? (y/n): ").strip()
    result = graph.invoke(Command(resume=decision),config=config)


