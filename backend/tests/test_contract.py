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


@pytest.mark.asyncio
async def test_persona_endpoint_accepts_matching_second_rotated_signature(client) -> None:  # type: ignore[no-untyped-def]
    body = json.dumps(
        {
            "data": {
                "id": "evt_rotated_signature",
                "type": "event",
                "attributes": {"name": "inquiry.created", "payload": {"data": {}}},
            }
        },
        separators=(",", ":"),
    ).encode()
    timestamp = str(int(time.time()))
    digest = hmac.new(
        b"persona-test-secret-at-least-32-bytes",
        timestamp.encode() + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    response = await client.post(
        "/api/v1/webhooks/persona",
        content=body,
        headers={"Persona-Signature": f"t={timestamp}, v1=obsolete v1={digest}"},
    )

    assert response.status_code == 202
    assert response.json() == {"accepted": True, "duplicate": False}


@pytest.mark.asyncio
async def test_persona_official_envelope_approves_without_sensitive_fields(client) -> None:  # type: ignore[no-untyped-def]
    async with SessionLocal() as session:
        account = UserAccount(clerk_user_id="persona_contract")
        session.add(account)
        await session.flush()
        session.add(IdentityInquiry(user_account_id=account.id, persona_inquiry_id="inq_official"))
        await session.commit()

    body = json.dumps(
        {
            "data": {
                "id": "evt_official_approved",
                "type": "event",
                "attributes": {
                    "name": "inquiry.approved",
                    "payload": {
                        "data": {
                            "id": "inq_official",
                            "type": "inquiry",
                            "attributes": {
                                "reference-id": "reference-safe",
                                "fields": {
                                    "name-first": {"value": "Maya"},
                                    "name-last": {"value": "Carter"},
                                    "birthdate": {"value": "1980-01-01"},
                                    "address-street-1": {"value": "Sensitive"},
                                },
                            },
                            "relationships": {"account": {"data": {"id": "act_1"}}},
                        }
                    },
                },
            }
        },
        separators=(",", ":"),
    ).encode()
    timestamp = str(int(time.time()))
    digest = hmac.new(
        b"persona-test-secret-at-least-32-bytes",
        timestamp.encode() + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    response = await client.post(
        "/api/v1/webhooks/persona",
        content=body,
        headers={"Persona-Signature": f"t={timestamp},v1={digest}"},
    )
    assert response.status_code == 202

    async with SessionLocal() as session:
        account = await session.scalar(
            __import__("sqlalchemy")
            .select(UserAccount)
            .where(UserAccount.clerk_user_id == "persona_contract")
        )
        assert account and account.status == LinkStatus.active
        inquiry = await session.scalar(
            __import__("sqlalchemy")
            .select(IdentityInquiry)
            .where(IdentityInquiry.persona_inquiry_id == "inq_official")
        )
        assert inquiry and inquiry.state == InquiryState.approved
        person = await session.get(
            __import__("app.models", fromlist=["Person"]).Person, account.person_id
        )
        assert person and person.verified_display_name == "Maya Carter"
