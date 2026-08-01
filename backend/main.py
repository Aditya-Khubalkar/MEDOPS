from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import router as api_router
from realtime.sockets import router as ws_router

app = FastAPI(title="MEDOPS Unified Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")
app.include_router(ws_router, prefix="/ws")

@app.get("/")
async def root():
    return {"message": "MEDOPS Unified API is running"}
