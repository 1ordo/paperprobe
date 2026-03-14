import hashlib
import hmac
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from app.config import settings

router = APIRouter()
security = HTTPBearer(auto_error=False)

TOKEN_TTL = 7 * 24 * 3600  # 7 days


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    token: str
    email: str


def _make_token(email: str, ts: int) -> str:
    """Create an HMAC-signed token: email:timestamp:signature."""
    payload = f"{email}:{ts}"
    sig = hmac.new(
        settings.auth_secret.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    return f"{payload}:{sig}"


def _verify_token(token: str) -> str | None:
    """Verify token and return email if valid, None otherwise."""
    parts = token.split(":")
    if len(parts) != 3:
        return None
    email, ts_str, sig = parts
    try:
        ts = int(ts_str)
    except ValueError:
        return None
    if time.time() - ts > TOKEN_TTL:
        return None
    expected = hmac.new(
        settings.auth_secret.encode(), f"{email}:{ts}".encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    return email


async def require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    """FastAPI dependency — returns authenticated email or raises 401.
    Accepts token via Authorization header or ?token= query param (for file downloads).
    """
    raw_token = None
    if credentials:
        raw_token = credentials.credentials
    elif "token" in request.query_params:
        raw_token = request.query_params["token"]
    if raw_token is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    email = _verify_token(raw_token)
    if email is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return email


@router.post("/auth/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    if body.email != settings.auth_email or body.password != settings.auth_password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = _make_token(body.email, int(time.time()))
    return LoginResponse(token=token, email=body.email)


@router.get("/auth/me")
async def me(email: str = Depends(require_auth)):
    return {"email": email}
