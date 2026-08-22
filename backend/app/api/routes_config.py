import yaml
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session
from datetime import datetime

from app.config_loader import load_config, reload_config
from app.db.session import get_session
from app.db.models import ConfigAuditLog
from pathlib import Path

router = APIRouter()


@router.get("/thresholds")
async def get_thresholds():
    return load_config("thresholds")


class ConfigUpdate(BaseModel):
    key: str
    value: object


@router.put("/thresholds")
async def update_thresholds(update: ConfigUpdate, db: Session = Depends(get_session)):
    cfg = load_config("thresholds")
    keys = update.key.split(".")
    target = cfg
    for k in keys[:-1]:
        if k not in target:
            target[k] = {}
        target = target[k]
    old_value = target.get(keys[-1])
    target[keys[-1]] = update.value
    
    path = Path(__file__).parents[3] / "config" / "thresholds.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False, default_flow_style=False)
        
    reload_config("thresholds")
    
    audit_log = ConfigAuditLog(
        changed_by="user",
        change_ts=datetime.utcnow(),
        config_key=update.key,
        old_value=str(old_value) if old_value is not None else None,
        new_value=str(update.value)
    )
    db.add(audit_log)
    db.commit()
    
    return {"status": "updated", "key": update.key, "value": update.value}
