"""Explicit, local-only loader for checked-in synthetic demonstration data."""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.db.session import get_session
from app.demo.project_trident import load_project_trident, reset_project_trident

router = APIRouter()


@router.post("/project-trident/load")
async def load_project_trident_demo(db: Session = Depends(get_session)):
    """Replace only prior Project Trident records, then verify its ring finding."""
    return await load_project_trident(db)


@router.post("/project-trident/reset")
def reset_project_trident_demo(db: Session = Depends(get_session)):
    """Remove only records registered to the Project Trident demo tag."""
    return {"tag": "project-trident", "deleted": reset_project_trident(db)}
