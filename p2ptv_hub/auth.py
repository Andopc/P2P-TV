"""FastAPI dependency that enforces Bearer-token authentication."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import HubSettings, get_settings

_bearer_scheme = HTTPBearer(auto_error=True)


def verify_token(
    credentials: HTTPAuthorizationCredentials = Security(_bearer_scheme),
    settings: HubSettings = Depends(get_settings),
) -> str:
    """Validate the Bearer token against ``P2PTV_API_KEY``.

    Raises HTTP 401 when the token is absent or incorrect.
    Returns the validated token string on success.
    """
    if credentials.credentials != settings.p2ptv_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials
