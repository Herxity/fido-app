from datetime import date, timedelta

import pytest

from app.db import SessionLocal
from app.models import Shelter


def payload(code: str, **changes: object) -> dict[str, object]:
    values: dict[str, object] = {
        "verification_code": code,
        "full_name": "Maya Carter",
        "date_of_birth": "1980-01-01",
        "address_line1": "100 Harbor Road",
        "city": "Baltimore",
        "region": "MD",
        "postal_code": "21201",
        "country": "US",
        "phone": "+14105550100",
        "government_id_last4": "6789",
        "document_type": "driving_license",
        "document_number": "MD-D12345",
        "issuing_jurisdiction": "MD",
        "document_expiration": (date.today() + timedelta(days=365)).isoformat(),
        "physical_document_examined": True,
        "likeness_matches": True,
        "owner_consented": True,
    }
    values.update(changes)
    return values


async def create_shelter() -> None:
    async with SessionLocal() as session:
        session.add(Shelter(clerk_organization_id="org_identity", name="Harbor Shelter"))
        await session.commit()


@pytest.mark.asyncio
async def test_manual_verification_requires_shelter_role_valid_code_and_attestations(
    client, auth
) -> None:  # type: ignore[no-untyped-def]
    await create_shelter()
    request = await client.post("/api/v1/identity/inquiries", headers=auth("owner-intake"))
    code = request.json()["verification_code"]
    owner_attempt = await client.post(
        "/api/v1/identity/manual-verifications",
        headers=auth("owner-intake"),
        json=payload(code),
    )
    bad_code = await client.post(
        "/api/v1/identity/manual-verifications",
        headers=auth("staff", "shelter_staff", "org_identity"),
        json=payload("invalid-verification-code-12345"),
    )
    case_changed_code = await client.post(
        "/api/v1/identity/manual-verifications",
        headers=auth("staff", "shelter_staff", "org_identity"),
        json=payload(code.swapcase()),
    )
    missing_attestation = await client.post(
        "/api/v1/identity/manual-verifications",
        headers=auth("staff", "shelter_staff", "org_identity"),
        json=payload(code, likeness_matches=False),
    )
    expired_document = await client.post(
        "/api/v1/identity/manual-verifications",
        headers=auth("staff", "shelter_staff", "org_identity"),
        json=payload(code, document_expiration="2020-01-01"),
    )
    impossible_age = await client.post(
        "/api/v1/identity/manual-verifications",
        headers=auth("staff", "shelter_staff", "org_identity"),
        json=payload(code, date_of_birth="1800-01-01"),
    )

    assert owner_attempt.status_code == 403
    assert bad_code.status_code == 404
    assert case_changed_code.status_code == 404
    assert missing_attestation.status_code == 422
    assert expired_document.status_code == 422
    assert impossible_age.status_code == 422


@pytest.mark.asyncio
async def test_ambiguous_match_requires_a_different_employee(client, auth) -> None:  # type: ignore[no-untyped-def]
    await create_shelter()
    staff_one = auth("staff-one", "shelter_staff", "org_identity")
    staff_two = auth("staff-two", "shelter_staff", "org_identity")

    first_request = await client.post("/api/v1/identity/inquiries", headers=auth("owner-first"))
    first = await client.post(
        "/api/v1/identity/manual-verifications",
        headers=staff_one,
        json=payload(first_request.json()["verification_code"]),
    )
    assert first.json()["classification"] == "new_identity"

    second_request = await client.post("/api/v1/identity/inquiries", headers=auth("owner-second"))
    second = await client.post(
        "/api/v1/identity/manual-verifications",
        headers=staff_one,
        json=payload(
            second_request.json()["verification_code"],
            full_name="Mya Carter",
            document_number="PA-P99881",
            issuing_jurisdiction="PA",
        ),
    )
    assert second.json()["classification"] == "fuzzy"
    review_id = second.json()["id"]
    candidate = (await client.get("/api/v1/identity/manual-reviews", headers=staff_one)).json()[
        "items"
    ][0]["candidates"][0]
    same_employee = await client.post(
        f"/api/v1/identity/manual-reviews/{review_id}/resolve",
        headers=staff_one,
        json={
            "decision": "link_existing",
            "target_person_id": candidate["person_id"],
            "explanation": "Physical card and person were compared again.",
        },
    )
    second_employee = await client.post(
        f"/api/v1/identity/manual-reviews/{review_id}/resolve",
        headers=staff_two,
        json={
            "decision": "link_existing",
            "target_person_id": candidate["person_id"],
            "explanation": "Second employee confirmed the typographical name difference.",
        },
    )
    assert same_employee.status_code == 409
    assert second_employee.status_code == 200


@pytest.mark.asyncio
async def test_same_document_and_demographics_match_when_address_changes(client, auth) -> None:  # type: ignore[no-untyped-def]
    await create_shelter()
    staff = auth("staff", "shelter_staff", "org_identity")

    first_request = await client.post("/api/v1/identity/inquiries", headers=auth("owner-one"))
    first = await client.post(
        "/api/v1/identity/manual-verifications",
        headers=staff,
        json=payload(first_request.json()["verification_code"]),
    )
    assert first.status_code == 201
    assert first.json()["classification"] == "new_identity"

    second_request = await client.post("/api/v1/identity/inquiries", headers=auth("owner-two"))
    second = await client.post(
        "/api/v1/identity/manual-verifications",
        headers=staff,
        json=payload(
            second_request.json()["verification_code"],
            address_line1="800 New Address Avenue",
            city="Annapolis",
            postal_code="21401",
        ),
    )
    assert second.status_code == 201
    assert second.json()["classification"] == "exact_existing"
