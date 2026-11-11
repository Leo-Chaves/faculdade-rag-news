import os
import secrets
from typing import Annotated

import httpx
from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer = HTTPBearer(auto_error=False)


def public_config() -> dict[str, str]:
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    key = os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()
    if not url.startswith("https://") or not key.startswith("sb_publishable_"):
        raise HTTPException(503, "Login ainda não configurado no servidor.")
    return {"url": url, "key": key}


def require_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> None:
    if credentials is None:
        raise HTTPException(401, "Entre para continuar.", headers={"WWW-Authenticate": "Bearer"})

    config = public_config()
    try:
        response = httpx.get(
            f"{config['url']}/auth/v1/user",
            headers={"apikey": config["key"], "Authorization": f"Bearer {credentials.credentials}"},
            timeout=8,
        )
    except httpx.RequestError as exc:
        raise HTTPException(503, "Serviço de login indisponível. Tente novamente.") from exc

    if response.status_code in (401, 403):
        raise HTTPException(401, "Sessão expirada. Entre novamente.", headers={"WWW-Authenticate": "Bearer"})
    if response.status_code != 200:
        raise HTTPException(503, "Serviço de login indisponível. Tente novamente.")


def require_admin(x_admin_key: Annotated[str | None, Header()] = None) -> None:
    expected = os.getenv("RAG_ADMIN_KEY", "")
    if not expected or not secrets.compare_digest((x_admin_key or "").encode(), expected.encode()):
        raise HTTPException(403, "Acesso administrativo necessário.")
