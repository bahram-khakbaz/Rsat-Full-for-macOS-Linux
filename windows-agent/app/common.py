import re
from fastapi import HTTPException

SAFE_ID = re.compile(r"^[A-Za-z0-9_.@\\,=+() -]{1,512}$")

def identity(value: str) -> str:
    if not SAFE_ID.fullmatch(value):
        raise HTTPException(status_code=400, detail="Invalid identity")
    return value

def list_result(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]
