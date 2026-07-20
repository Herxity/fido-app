from datetime import UTC, datetime

import pytest

from app.db import SessionLocal
from app.models import LinkStatus, Person, PersonStatus, Pet, Shelter, UserAccount


async def seed() -> tuple[Shelter, Shelter, Person, Pet]:
    async with SessionLocal() as session:
        one = Shelter(clerk_organization_id="org1", name="One")
        two = Shelter(clerk_organization_id="org2", name="Two")
        person = Person(status=PersonStatus.active, verified_display_name="Owner")
        session.add_all([one, two, person])
        await session.flush()
        account = UserAccount(clerk_user_id="owner", person_id=person.id, status=LinkStatus.active)
        pet = Pet(shelter_id=one.id, record_number="R1", name="Fido", species="dog")
        session.add_all([account, pet])
        await session.commit()
        return one, two, person, pet


@pytest.mark.asyncio
async def test_tenant_idor_and_read_only_write_denied(client, auth) -> None:  # type: ignore[no-untyped-def]
    one, two, _, _ = await seed()
    assert (
        await client.get(
            f"/api/v1/shelters/{two.id}/pets", headers=auth("staff", "shelter_staff", "org1")
        )
    ).status_code == 404
    response = await client.post(
        f"/api/v1/shelters/{one.id}/pets",
        headers=auth("reader", "shelter_read_only", "org1"),
        json={"record_number": "X", "name": "X", "species": "cat"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_custody_idempotency_correction_and_cross_shelter_guard(client, auth) -> None:  # type: ignore[no-untyped-def]
    one, _, person, pet = await seed()
    token = await client.post("/api/v1/me/lookup-tokens", headers=auth("owner"))
    redemption = await client.post(
        "/api/v1/lookups/redeem",
        headers=auth("staff", "shelter_staff", "org1"),
        json={"token": token.json()["token"]},
    )
    payload = {
        "pet_id": str(pet.id),
        "lookup_session_id": redemption.json()["session_id"],
        "event_type": "adoption",
        "effective_at": datetime.now(UTC).isoformat(),
        "factual_note": "Adopted",
    }
    headers = {**auth("staff", "shelter_staff", "org1"), "Idempotency-Key": "unique-key-0001"}
    no_authorization = await client.post(
        "/api/v1/custody-events",
        headers={**headers, "Idempotency-Key": "known-person-no-session"},
        json={
            **payload,
            "lookup_session_id": "00000000-0000-0000-0000-000000000000",
            "person_id": str(person.id),
        },
    )
    assert no_authorization.status_code == 404
    wrong_staff = await client.post(
        "/api/v1/custody-events",
        headers={
            **auth("different_staff", "shelter_staff", "org1"),
            "Idempotency-Key": "wrong-staff-session",
        },
        json=payload,
    )
    assert wrong_staff.status_code == 404
    first = await client.post("/api/v1/custody-events", headers=headers, json=payload)
    second = await client.post("/api/v1/custody-events", headers=headers, json=payload)
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    correction = await client.post(
        f"/api/v1/custody-events/{first.json()['id']}/corrections",
        headers={**headers, "Idempotency-Key": "correction-0001"},
        json={
            "effective_at": datetime.now(UTC).isoformat(),
            "factual_note": "Corrected factual note",
        },
    )
    assert (
        correction.status_code == 201
        and correction.json()["corrects_event_id"] == first.json()["id"]
    )
    denied = await client.post(
        f"/api/v1/custody-events/{first.json()['id']}/corrections",
        headers={**auth("staff2", "shelter_staff", "org2"), "Idempotency-Key": "correction-0002"},
        json={"effective_at": datetime.now(UTC).isoformat(), "factual_note": "No access"},
    )
    assert denied.status_code == 404


@pytest.mark.asyncio
async def test_qr_single_use_binding_expiration_and_access_log(client, auth) -> None:  # type: ignore[no-untyped-def]
    one, _, _, _ = await seed()
    created = await client.post("/api/v1/me/lookup-tokens", headers=auth("owner"))
    assert created.status_code == 201 and "Owner" not in created.json()["qr_payload"]
    raw = created.json()["token"]
    redeem = await client.post(
        "/api/v1/lookups/redeem",
        headers=auth("staff", "shelter_staff", "org1"),
        json={"token": raw},
    )
    assert redeem.status_code == 200
    assert (
        await client.post(
            "/api/v1/lookups/redeem",
            headers=auth("staff", "shelter_staff", "org1"),
            json={"token": raw},
        )
    ).status_code == 400
    session_id = redeem.json()["session_id"]
    assert (
        await client.get(
            f"/api/v1/lookups/{session_id}/history", headers=auth("other", "shelter_staff", "org1")
        )
    ).status_code == 404
    assert (
        await client.get(
            f"/api/v1/lookups/{session_id}/history", headers=auth("staff2", "shelter_staff", "org2")
        )
    ).status_code == 404
    log = await client.get("/api/v1/me/access-log", headers=auth("owner"))
    assert log.status_code == 200 and log.json()["items"][0]["shelter"]["id"] == str(one.id)


def test_postgresql_migration_contains_append_only_trigger() -> None:
    migration = (
        __import__("pathlib").Path(__file__).parents[1] / "alembic/versions/0001_initial.py"
    ).read_text()
    assert "BEFORE UPDATE OR DELETE ON custody_events" in migration
    assert "fido_reject_custody_mutation" in migration
