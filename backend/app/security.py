import base64
import binascii
import hashlib
import hmac
import json
import logging
import re
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import Settings, get_settings

logger = logging.getLogger(__name__)
bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    user_id: str
    role: str
    organization_id: str | None = None


class ClerkVerifier:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._jwks: dict[str, Any] | None = None

    async def verify(self, token: str) -> Principal:
        if self.settings.provider_mode in {"development", "test"}:
            # Explicit fake format: dev.<base64url JSON>. No production fallback exists.
            try:
                prefix, encoded = token.split(".", 1)
                if prefix != "dev":
                    raise ValueError
                claims = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
                if int(claims.get("exp", 0)) <= int(time.time()):
                    raise ValueError
                return principal_from_claims(claims)
            except (ValueError, KeyError, json.JSONDecodeError) as exc:
                raise unauthorized() from exc
        if not self.settings.clerk_jwks_url or not self.settings.clerk_issuer:
            raise RuntimeError("live Clerk configuration is incomplete")
        try:
            header = jwt.get_unverified_header(token)
            if self._jwks is None:
                async with httpx.AsyncClient(timeout=5) as client:
                    response = await client.get(self.settings.clerk_jwks_url)
                    response.raise_for_status()
                    self._jwks = response.json()
            key_data = next(k for k in self._jwks["keys"] if k["kid"] == header["kid"])
            key = jwt.PyJWK.from_dict(key_data).key
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=self.settings.clerk_audience,
                issuer=self.settings.clerk_issuer,
                options={"require": ["exp", "iat", "sub", "iss", "aud"]},
            )
            azp = claims.get("azp")
            if (
                self.settings.clerk_authorized_parties
                and azp not in self.settings.clerk_authorized_parties
            ):
                raise unauthorized()
            if (
                not isinstance(claims.get("o"), dict)
                and self.settings.clerk_allow_legacy_org_claims
            ):
                claims["o"] = {"id": claims.get("org_id"), "rol": claims.get("org_role")}
            return principal_from_claims(claims)
        except (jwt.PyJWTError, StopIteration, KeyError, httpx.HTTPError) as exc:
            self._jwks = None
            raise unauthorized() from exc


def principal_from_claims(claims: dict[str, Any]) -> Principal:
    if claims.get("sts") == "pending":
        raise unauthorized()
    organization = claims.get("o")
    org_id: Any = None
    role_value: Any = claims.get("role") or "owner"
    if isinstance(organization, dict):
        org_id = organization.get("id")
        role_value = organization.get("rol") or role_value
    role = str(role_value).removeprefix("org:")
    allowed = {"owner", "shelter_admin", "shelter_staff", "shelter_read_only", "platform_admin"}
    if role not in allowed:
        raise unauthorized()
    if role.startswith("shelter_") and not org_id:
        raise unauthorized()
    return Principal(str(claims["sub"]), role, str(org_id) if org_id else None)


def unauthorized() -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid authentication credentials")


async def current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    settings: Settings = Depends(get_settings),
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized()
    return await ClerkVerifier(settings).verify(credentials.credentials)


def require_roles(*roles: str):  # type: ignore[no-untyped-def]
    async def dependency(principal: Principal = Depends(current_principal)) -> Principal:
        if principal.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permission")
        return principal

    return dependency


def verify_signed_payload(
    raw: bytes,
    signature: str,
    secret: str,
    *,
    timestamp: str | None = None,
    tolerance_seconds: int = 300,
    encoding: Literal["hex", "base64"] = "hex",
) -> None:
    if not secret:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Webhook is not configured")
    if timestamp is not None:
        try:
            if abs(int(datetime.now(UTC).timestamp()) - int(timestamp)) > tolerance_seconds:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Stale webhook")
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid webhook timestamp") from exc
    message = (timestamp.encode() + b"." + raw) if timestamp else raw
    digest = hmac.new(secret.encode(), message, hashlib.sha256).digest()
    expected = digest.hex() if encoding == "hex" else base64.b64encode(digest).decode()
    candidates = [part.split("=", 1)[-1].strip() for part in signature.split(",")]
    if not any(hmac.compare_digest(expected, item) for item in candidates):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid webhook signature")


def verify_persona_webhook(
    raw: bytes, signature_header: str, secret: str, tolerance_seconds: int
) -> None:
    timestamp_match = re.search(r"(?:^|[,\s])t=([^,\s]+)", signature_header)
    signatures = re.findall(r"(?:^|[,\s])v1=([^,\s]+)", signature_header)
    if timestamp_match is None or not signatures:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid webhook signature")
    verify_signed_payload(
        raw,
        ",".join(f"v1={candidate}" for candidate in signatures),
        secret,
        timestamp=timestamp_match.group(1),
        tolerance_seconds=tolerance_seconds,
    )


def verify_clerk_webhook(
    raw: bytes, event_id: str, timestamp: str, signature: str, secret: str, tolerance_seconds: int
) -> None:
    try:
        if abs(int(datetime.now(UTC).timestamp()) - int(timestamp)) > tolerance_seconds:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Stale webhook")
        encoded_secret = secret.removeprefix("whsec_")
        key = base64.b64decode(encoded_secret, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Webhook is not configured"
        ) from exc
    digest = hmac.new(
        key, event_id.encode() + b"." + timestamp.encode() + b"." + raw, hashlib.sha256
    ).digest()
    expected = base64.b64encode(digest).decode()
    candidates = [part.split("=", 1)[-1].strip() for part in signature.split()]
    if not any(hmac.compare_digest(expected, candidate) for candidate in candidates):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid webhook signature")


def opaque_token() -> str:
    return secrets.token_urlsafe(32)


def keyed_hash(value: str, key: str) -> str:
    if len(key) < 16:
        raise RuntimeError("lookup hash key is not configured securely")
    return hmac.new(key.encode(), value.encode(), hashlib.sha256).hexdigest()


SENSITIVE_KEYS = {"authorization", "token", "lookup_token", "api_key", "secret", "password"}


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: "[REDACTED]" if k.lower() in SENSITIVE_KEYS else redact(v) for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value
