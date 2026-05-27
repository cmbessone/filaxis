from dataclasses import dataclass
from typing import Literal

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from filaxis.config import settings

_bearer = HTTPBearer()


@dataclass
class TokenPayload:
    sub: str  # patient_id or user identifier
    role: Literal["patient", "physician"]


def _decode(token: str) -> TokenPayload:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    sub = payload.get("sub")
    role = payload.get("role", "patient")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing sub claim")
    return TokenPayload(sub=sub, role=role)


def get_current_token(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> TokenPayload:
    return _decode(credentials.credentials)


def require_physician(token: TokenPayload = Depends(get_current_token)) -> TokenPayload:
    if token.role != "physician":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Physician role required")
    return token
