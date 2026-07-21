import base64
import hashlib
import hmac
import time
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

from app.config import Settings
from app.security import (
    ClerkVerifier,
    principal_from_claims,
    redact,
    verify_clerk_webhook,
    verify_signed_payload,
)


def test_production_rejects_fake_provider() -> None:
    with pytest.raises(ValueError, match="forbidden"):
        Settings(
            environment="production", provider_mode="test", clerk_authorized_parties=["https://x"]
        )


def test_clerk_v2_claims_and_pending_session() -> None:
    principal = principal_from_claims(
        {"sub": "u1", "o": {"id": "org1", "rol": "org:shelter_staff", "per": "x"}}
    )
    assert (principal.organization_id, principal.role) == ("org1", "shelter_staff")
    with pytest.raises(HTTPException) as error:
        principal_from_claims({"sub": "u1", "sts": "pending"})
    assert error.value.status_code == 401


@pytest.mark.asyncio
async def test_clerk_default_session_token_does_not_require_custom_audience(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        environment="development",
        provider_mode="live",
        clerk_issuer="https://fido.clerk.accounts.dev",
        clerk_jwks_url="https://fido.clerk.accounts.dev/.well-known/jwks.json",
        clerk_authorized_parties=["http://127.0.0.1:5173"],
    )
    verifier = ClerkVerifier(settings)
    verifier._jwks = {"keys": [{"kid": "key_1"}]}
    captured: dict[str, Any] = {}

    monkeypatch.setattr("app.security.jwt.get_unverified_header", lambda _token: {"kid": "key_1"})
    monkeypatch.setattr(
        "app.security.jwt.PyJWK.from_dict", lambda _key: SimpleNamespace(key="public-key")
    )

    def decode(_token: str, _key: str, **kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {
            "sub": "owner_1",
            "iss": settings.clerk_issuer,
            "exp": int(time.time()) + 60,
            "iat": int(time.time()),
            "azp": "http://127.0.0.1:5173",
        }

    monkeypatch.setattr("app.security.jwt.decode", decode)

    principal = await verifier.verify("signed-token")

    assert principal.user_id == "owner_1"
    assert captured["audience"] is None
    assert captured["options"]["verify_aud"] is False
    assert "aud" not in captured["options"]["require"]


def test_persona_rotated_signature_and_staleness() -> None:
    raw, secret, timestamp = b'{"safe":true}', "secret", str(int(time.time()))
    signature = hmac.new(
        secret.encode(), timestamp.encode() + b"." + raw, hashlib.sha256
    ).hexdigest()
    verify_signed_payload(raw, f"v1=bad,v1={signature}", secret, timestamp=timestamp)
    with pytest.raises(HTTPException, match="Stale"):
        verify_signed_payload(raw, signature, secret, timestamp="1")


def test_clerk_svix_signature_contract() -> None:
    raw, event_id, timestamp = b"{}", "evt_1", str(int(time.time()))
    key = b"secret-key-material"
    secret = "whsec_" + base64.b64encode(key).decode()
    digest = hmac.new(key, f"{event_id}.{timestamp}.".encode() + raw, hashlib.sha256).digest()
    verify_clerk_webhook(
        raw, event_id, timestamp, "v1," + "v1=" + base64.b64encode(digest).decode(), secret, 300
    )


def test_redaction_is_recursive() -> None:
    assert redact({"authorization": "bearer x", "nested": [{"token": "qr", "ok": 1}]}) == {
        "authorization": "[REDACTED]",
        "nested": [{"token": "[REDACTED]", "ok": 1}],
    }


@pytest.mark.asyncio
async def test_auth_rejects_expired_and_platform_boundary(client, auth) -> None:  # type: ignore[no-untyped-def]
    assert (await client.get("/api/v1/me", headers=auth(expired=True))).status_code == 401
    assert (
        await client.get(
            "/api/v1/admin/identity-reviews", headers=auth(role="shelter_admin", org_id="org1")
        )
    ).status_code == 403
