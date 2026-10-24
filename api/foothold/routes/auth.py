"""Auth endpoints (CONTRACTS section 13). Every account is a FICTIONAL demo account.

POST /api/auth/login   {email, password} -> {token, token_type, account, expires_at}
GET  /api/auth/me      Bearer token -> {account, expires_at, candidate_id}
POST /api/auth/logout  Bearer token (optional) -> {ok: true}; revokes that one token only,
                       so other tabs signed into the same account stay signed in.
POST /api/auth/register {display_name, email, password, kind, org_name?, place_id?}
                       -> {token, token_type, account, expires_at, profile}  (409 duplicate email, 422 invalid)
GET  /api/auth/me/profile   Bearer -> profile
PATCH /api/auth/me/profile  Bearer {place_id?, lat?, lon?, hours_per_week?, budget_usd?, commute_minutes?,
                       current_credits?, dependents?, interests?, talent_opt_in?, org_name?} -> profile

Errors: 400 empty fields, 401 wrong credentials / missing / invalid / expired session.
Failed sign-ins pause briefly (growing per email and client). Nothing here logs
emails, passwords or tokens.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel

from foothold import auth, profiles
from foothold.auth import Account

log = logging.getLogger("foothold.auth")

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    # Defaults instead of required fields: a missing field gets a friendly 400, and the
    # 422 handler never echoes the submitted body back.
    email: str = ""
    password: str = ""


class LoginOut(BaseModel):
    token: str
    token_type: Literal["bearer"] = "bearer"
    account: Account
    expires_at: str


class MeOut(BaseModel):
    account: Account
    expires_at: str
    # learner's own talent-pool card id (None for employers or before talent_pool.json exists)
    candidate_id: str | None


class LogoutOut(BaseModel):
    ok: bool


class RegisterIn(BaseModel):
    display_name: str = ""
    email: str = ""
    password: str = ""
    kind: str = "learner"
    org_name: str | None = None
    place_id: str | None = None


class RegisterOut(LoginOut):
    profile: dict[str, Any]


class ProfilePatch(BaseModel):
    place_id: str | None = None
    lat: float | None = None
    lon: float | None = None
    hours_per_week: float | None = None
    budget_usd: float | None = None
    commute_minutes: float | None = None
    current_credits: float | None = None
    dependents: int | None = None
    interests: list[str] | None = None
    talent_opt_in: bool | None = None
    org_name: str | None = None


def _client_key(request: Request) -> str:
    host = request.client.host if request.client else ""
    return f"client:{host}" if host else ""


@router.post("/login", response_model=LoginOut)
async def login(body: LoginIn, request: Request) -> LoginOut:
    email = auth.normalize_email(body.email)
    password = body.password
    if not email or not password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Enter your email and password.")

    account = await asyncio.to_thread(auth.authenticate, email, password)
    keys = (f"email:{email}", _client_key(request))
    if account is None:
        pause = auth.register_failed_login(*keys)
        log.info("sign-in failed")
        await asyncio.sleep(pause)
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    auth.clear_failed_logins(*keys)
    token, claims = auth.issue_token(account)
    log.info("signed in: %s", account.id)
    return LoginOut(token=token, account=account, expires_at=claims.expires_at)


@router.post("/register", response_model=RegisterOut, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterIn, request: Request) -> RegisterOut:
    try:
        account = await asyncio.to_thread(
            profiles.register, display_name=body.display_name, email=body.email, password=body.password,
            kind=body.kind, org_name=body.org_name, place_id=body.place_id,
        )
    except profiles.ProfileError as exc:
        pause = auth.register_failed_login(_client_key(request) and f"register:{_client_key(request)}")
        await asyncio.sleep(min(pause, 1.0))
        raise HTTPException(exc.status, detail=exc.detail) from None
    token, claims = auth.issue_token(account)
    prof = await asyncio.to_thread(profiles.get_profile, account)
    return RegisterOut(token=token, account=account, expires_at=claims.expires_at, profile=prof)


@router.get("/me/profile")
def get_my_profile(account: auth.CurrentAccount) -> dict[str, Any]:
    return profiles.get_profile(account)


@router.patch("/me/profile")
def patch_my_profile(body: ProfilePatch, account: auth.CurrentAccount) -> dict[str, Any]:
    try:
        return profiles.update_profile(account, body.model_dump(exclude_unset=True))
    except profiles.ProfileError as exc:
        raise HTTPException(exc.status, detail=exc.detail) from None


@router.get("/me", response_model=MeOut)
def me(session: auth.Session = Depends(auth.current_session)) -> MeOut:
    return MeOut(
        account=session.account,
        expires_at=session.claims.expires_at,
        candidate_id=auth.candidate_id_for(session.account),
    )


@router.post("/logout", response_model=LogoutOut)
def logout(credentials: HTTPAuthorizationCredentials | None = Depends(auth.bearer_scheme)) -> LogoutOut:
    if credentials is not None and credentials.credentials:
        try:
            claims = auth.decode_token(credentials.credentials)
        except auth.TokenError:
            claims = None  # already invalid: nothing to revoke
        if claims is not None:
            auth.revoke(claims)
            log.info("signed out: %s", claims.sub)
    return LogoutOut(ok=True)


# Seed at startup (main.py imports this module when it builds the app). Failures are not
# fatal: auth.ensure_ready() runs again on the first auth request.
try:
    auth.ensure_ready()
except Exception as exc:  # noqa: BLE001
    log.warning("demo accounts not seeded yet: %s", type(exc).__name__)
