import json
from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session
from ..auth import Principal, require
from ..db import AuditLog, get_db
from ..config import settings
from .. import demo

router = APIRouter(prefix="/api/audit", tags=["audit"])

@router.get("")
def audit(limit: int = Query(default=100, ge=1, le=500), _: Principal = Depends(require("audit.read")), db: Session = Depends(get_db)):
    rows = db.query(AuditLog).order_by(desc(AuditLog.at)).limit(limit).all()
    if settings.demo_mode and not rows:
        return demo.AUDIT[:limit]
    return [{"id":r.id,"at":r.at,"actor":r.actor,"role":r.role,"action":r.action,"target":r.target,"status":r.status,"details":json.loads(r.details or "{}")} for r in rows]
