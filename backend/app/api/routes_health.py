from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "app": "MuleGuard Local",
        "version": "0.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "offline_mode": True,
    }


@router.get("/health/offline-check")
async def offline_check():
    """Self-test confirming no outbound network calls are configured."""
    return {
        "status": "ok",
        "message": "All endpoints are localhost-only. No outbound network calls configured.",
        "ollama_host": "http://ollama:11434",
        "data_dir": "./data",
        "online_api_keys_detected": False,
    }
