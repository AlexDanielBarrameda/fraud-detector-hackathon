from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.analyze import router as analyze_router
from app.config import settings

app = FastAPI(
    title="Scam Analyzer API",
    description="Multi-stage scam and phishing analysis API",
    version="0.1.0",
)

# CORS: local dev servers always; plus any CORS_ORIGINS and the Vercel URL pattern (see config.py).
LOCAL_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=LOCAL_ORIGINS + settings.cors_origin_list,
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(analyze_router, prefix="/api")


@app.get("/health")
async def health_check():
    return {"status": "ok"}

