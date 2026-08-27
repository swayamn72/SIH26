"""Case finding SAR/STR investigator draft API and exports."""
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, JSONResponse
from sqlmodel import Session

from app.db.session import get_session
from app.sar.draft import build_sar_draft, draft_html

router = APIRouter()


def _filename(case_id: int, finding_id: str, extension: str) -> str:
    return f"case_{case_id}_finding_{finding_id}_sar_str_draft.{extension}"


@router.get("/{case_id}/findings/{finding_id}/sar-draft")
def get_sar_draft(case_id: int, finding_id: str, db: Session = Depends(get_session)):
    return build_sar_draft(db, case_id, finding_id)


@router.get("/{case_id}/findings/{finding_id}/sar-draft/export")
def export_sar_draft(
    case_id: int,
    finding_id: str,
    format: Literal["json", "html"] = Query("json"),
    db: Session = Depends(get_session),
):
    draft = build_sar_draft(db, case_id, finding_id)
    if format == "html":
        return HTMLResponse(
            draft_html(draft),
            headers={"Content-Disposition": f'attachment; filename="{_filename(case_id, finding_id, "html")}"'},
        )
    return JSONResponse(
        draft,
        headers={"Content-Disposition": f'attachment; filename="{_filename(case_id, finding_id, "json")}"'},
    )
