from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from clintrace_agent.runtime import run_triage
    _TRIAGE_AVAILABLE = True
except ImportError as e:
    _TRIAGE_AVAILABLE = False
    _IMPORT_ERROR = str(e)

router = APIRouter()


class TriageRequest(BaseModel):
    patient_input: str


@router.post("/triage")
async def run_intake_triage(request: TriageRequest):
    if not _TRIAGE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Triage service unavailable. The ClinTrace agent could not be loaded: {_IMPORT_ERROR}. "
                "Ensure all dependencies are installed and environment variables (GOOGLE_API_KEY or "
                "GEMINI_API_KEY) are configured."
            ),
        )

    if not request.patient_input.strip():
        raise HTTPException(status_code=422, detail="patient_input must not be empty.")

    try:
        result = await run_triage(request.patient_input.strip())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Triage pipeline error: {str(e)}")

    return {
        "audit_report": result.audit_report,
        "trace_id": result.trace_id,
        "actions": result.actions,
        "session_id": result.session_id,
    }
