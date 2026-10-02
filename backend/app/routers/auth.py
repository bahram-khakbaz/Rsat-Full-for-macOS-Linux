from fastapi import APIRouter, Depends, HTTPException
from ..auth import LoginRequest, authenticate_local, current_principal, issue_token, Principal

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/login")
def login(body: LoginRequest):
    principal = authenticate_local(body.username, body.password)
    if not principal:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"access_token": issue_token(principal.username, principal.role), "token_type": "bearer", "user": principal.model_dump()}

@router.get("/me")
def me(principal: Principal = Depends(current_principal)):
    return principal
