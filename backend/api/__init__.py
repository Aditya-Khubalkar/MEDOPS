from fastapi import APIRouter
from .decoder import router as decoder_router
from .triage import router as triage_router

router = APIRouter()

@router.get("/health")
async def health_check():
    return {"status": "healthy"}

router.include_router(decoder_router)
router.include_router(triage_router)
