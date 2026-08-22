from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes_health import router as health_router
from app.api.routes_upload import router as upload_router
from app.api.routes_review import router as review_router
from app.api.routes_analysis import router as analysis_router
from app.api.routes_graph import router as graph_router
from app.api.routes_report import router as report_router
from app.api.routes_config import router as config_router
from app.db.session import engine
from app.db.models import SQLModel
from app.guardrails.privacy_guard import PIIRedactionMiddleware, PIIFilter
import logging

app = FastAPI(
    title="MuleGuard Local",
    description="Fully offline, explainable, formula-driven Mule-Account Detection System",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)


@app.on_event("startup")
async def on_startup():
    SQLModel.metadata.create_all(engine)
    logging.getLogger().addFilter(PIIFilter())

app.add_middleware(PIIRedactionMiddleware)


app.include_router(health_router, prefix="/api", tags=["health"])
app.include_router(upload_router, prefix="/api/statements", tags=["upload"])
app.include_router(review_router, prefix="/api/statements", tags=["review"])
app.include_router(analysis_router, prefix="/api/statements", tags=["analysis"])
app.include_router(graph_router, prefix="/api/statements", tags=["graph"])
app.include_router(report_router, prefix="/api/statements", tags=["report"])
app.include_router(config_router, prefix="/api/config", tags=["config"])


static_dir = Path(__file__).parents[2] / "frontend" / "dist"
if static_dir.is_dir():
    # Mount static assets (JS, CSS, images) under /assets
    app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

    # Catch-all: serve index.html for all non-API routes so React Router works on refresh
    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str, request: Request):
        index = static_dir / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return {"detail": "Frontend not built"}
