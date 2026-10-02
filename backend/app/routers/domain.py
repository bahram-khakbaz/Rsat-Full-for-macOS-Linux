from fastapi import APIRouter, Depends
from ..auth import Principal, require
from ..worker_client import worker

router = APIRouter(prefix="/api/domain", tags=["domain-health"])

@router.get("/summary")
async def summary(_: Principal = Depends(require("domain.read"))):
    return await worker.request("GET", "/domain/summary")

@router.get("/controllers")
async def controllers(_: Principal = Depends(require("domain.read"))):
    return await worker.request("GET", "/domain/controllers")

@router.get("/replication")
async def replication(_: Principal = Depends(require("domain.read"))):
    return await worker.request("GET", "/domain/replication")

@router.get("/trusts")
async def trusts(_: Principal = Depends(require("domain.read"))):
    return await worker.request("GET", "/domain/trusts")

@router.get("/sites")
async def sites(_: Principal = Depends(require("domain.read"))):
    return await worker.request("GET", "/domain/sites")
