from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.analyze import router as analyze_router
from app.config import settings
from app.security import BodySizeLimitMiddleware, SecurityHeadersMiddleware

# Interactive docs are a map of the API: on locally, off in production (ENABLE_DOCS=false).
docs_enabled = settings.enable_docs

app = FastAPI(
    title="Scam Analyzer API",
    description="Multi-stage scam and phishing analysis API",
    version="0.1.0",
    docs_url="/docs" if docs_enabled else None,
    redoc_url="/redoc" if docs_enabled else None,
    openapi_url="/openapi.json" if docs_enabled else None,
)

# CORS: exact origins only. Local dev servers always; the deployed frontend via CORS_ORIGINS (see config.py).
LOCAL_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]

# Middleware added last runs first. Order (outermost -> innermost): CORS, body-size cap, security headers.
# CORS is outermost so even 413/429 errors carry CORS headers and the browser can show their message.
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(BodySizeLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=LOCAL_ORIGINS + settings.cors_origin_list,
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_credentials=False,  # no cookies or auth: nothing to share cross-origin
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# Register routes
app.include_router(analyze_router, prefix="/api")


@app.get("/health")
async def health_check():
    return {"status": "ok"}
