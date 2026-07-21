import hashlib
import hmac
import json
import time

import pytest

from app.db import SessionLocal
from app.main import app
from app.models import IdentityInquiry, InquiryState, LinkStatus, Shelter, UserAccount


@pytest.mark.asyncio
async def test_owner_me_contract(client, auth) -> None:  # type: ignore[no-untyped-def]
    response = await client.get("/api/v1/me", headers=auth("owner_contract"))

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "owner_contract",
        "mode": "owner",
        "role": "owner",
        "identity_status": "pending",
        "display_name": None,
        "person_id": None,
    }


@pytest.mark.asyncio
async def test_shelter_me_contract_resolves_clerk_organization(client, auth) -> None:  # type: ignore[no-untyped-def]
    async with SessionLocal() as session:
        shelter = Shelter(clerk_organization_id="org_contract", name="Harbor County Animal Care")
        session.add(shelter)
        await session.commit()
        shelter_id = str(shelter.id)

    response = await client.get(
        "/api/v1/me",
        headers=auth("staff_contract", "shelter_staff", "org_contract"),
    )

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "staff_contract",
        "mode": "shelter",
        "role": "shelter_staff",
        "identity_status": "not_applicable",
        "display_name": None,
        "shelter": {"id": shelter_id, "name": "Harbor County Animal Care"},
    }


def test_openapi_contains_all_public_paths() -> None:
    schema = app.openapi()
    assert len(schema["paths"]) == 22
    assert "/api/v1/me" in schema["paths"]


def stripe_signature(body: bytes) -> str:
    timestamp = str(int(time.time()))
    digest = hmac.new(
        b"whsec_stripe-test-secret-at-least-32-bytes",
        timestamp.encode() + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    return f"t={timestamp},v1={digest}"


@pytest.mark.asyncio
async def test_stripe_webhook_is_verified_and_idempotent(client) -> None:  # type: ignore[no-untyped-def]
    body = json.dumps(
        {
            "id": "evt_created",
            "object": "event",
            "type": "identity.verification_session.created",
            "data": {"object": {"id": "vs_created"}},
        },
        separators=(",", ":"),
    ).encode()
    headers = {"Stripe-Signature": stripe_signature(body)}
    first = await client.post("/api/v1/webhooks/stripe", content=body, headers=headers)
    duplicate = await client.post("/api/v1/webhooks/stripe", content=body, headers=headers)

    assert first.status_code == 202
    assert first.json() == {"accepted": True, "duplicate": False}
    assert duplicate.json() == {"accepted": True, "duplicate": True}


@pytest.mark.asyncio
async def test_stripe_verified_event_approves_without_storing_sensitive_fields(client) -> None:  # type: ignore[no-untyped-def]
    async with SessionLocal() as session:
        account = UserAccount(clerk_user_id="stripe_contract")
        session.add(account)
        await session.flush()
        session.add(IdentityInquiry(user_account_id=account.id, provider_session_id="vs_official"))
        await session.commit()

    body = json.dumps(
        {
            "id": "evt_official_verified",
            "object": "event",
            "type": "identity.verification_session.verified",
            "data": {"object": {"id": "vs_official"}},
        },
        separators=(",", ":"),
    ).encode()
    response = await client.post(
        "/api/v1/webhooks/stripe",
        content=body,
        headers={"Stripe-Signature": stripe_signature(body)},
    )
    assert response.status_code == 202

    async with SessionLocal() as session:
        account = await session.scalar(
            __import__("sqlalchemy")
            .select(UserAccount)
            .where(UserAccount.clerk_user_id == "stripe_contract")
        )
        assert account and account.status == LinkStatus.active
        inquiry = await session.scalar(
            __import__("sqlalchemy")
            .select(IdentityInquiry)
            .where(IdentityInquiry.provider_session_id == "vs_official")
        )
        assert inquiry and inquiry.state == InquiryState.approved
        person = await session.get(
            __import__("app.models", fromlist=["Person"]).Person, account.person_id
        )
        assert person and person.verified_display_name == "Test Owner"
