from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.analyze import router as analyze_router

app = FastAPI(
    title="Scam Analyzer API",
    description="Multi-stage scam and phishing analysis API",
    version="0.1.0",
)

# CORS configuration to allow local frontend development servers
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(analyze_router, prefix="/api")


@app.get("/health")
async def health_check():
    return {"status": "ok"}

