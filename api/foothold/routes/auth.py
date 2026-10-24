"""Auth endpoints (CONTRACTS section 13). Every account is a FICTIONAL demo account.

POST /api/auth/login   {email, password} -> {token, token_type, account, expires_at}
GET  /api/auth/me      Bearer token -> {account, expires_at, candidate_id}
POST /api/auth/logout  Bearer token (optional) -> {ok: true}; revokes that one token only,
                       so other tabs signed into the same account stay signed in.

Errors: 400 empty fields, 401 wrong credentials / missing / invalid / expired session.
Failed sign-ins pause briefly (growing per email and client). Nothing here logs
emails, passwords or tokens.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel

from foothold import auth
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
