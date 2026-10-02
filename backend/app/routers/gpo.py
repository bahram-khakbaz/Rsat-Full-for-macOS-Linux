from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..auth import Principal, require
from ..db import get_db
from ..audit import write_audit
from ..worker_client import worker

router = APIRouter(prefix="/api/gpo", tags=["group-policy"])

class GpoCreate(BaseModel):
    name: str
    comment: str = ""

@router.get("")
async def list_gpo(_: Principal = Depends(require("gpo.read"))):
    return await worker.request("GET", "/gpo")

@router.post("")
async def create_gpo(body: GpoCreate, principal: Principal = Depends(require("gpo.write")), db: Session = Depends(get_db)):
    result = await worker.request("POST", "/gpo", payload=body.model_dump())
    write_audit(db, principal, "gpo.create", body.name, details=body.model_dump())
    return result
