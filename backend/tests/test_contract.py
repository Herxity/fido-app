import pytest

from app.db import SessionLocal
from app.main import app
from app.models import Shelter


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
