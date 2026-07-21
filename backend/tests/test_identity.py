import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import (
    IdentityInquiry,
    IdentityMatchCandidate,
    IdentitySignal,
    InquiryState,
    LinkStatus,
    Person,
    PersonStatus,
    UserAccount,
)
from app.schemas import ManualIdentityEvidence
from app.security import Principal
from app.services import merge_people, reconcile_manual_identity

HASH_KEY = "identity-test-hmac-key-at-least-32-bytes"


def evidence(**changes: object) -> ManualIdentityEvidence:
    values: dict[str, object] = {
        "verification_code": "owner-verification-code-12345",
        "full_name": "Maya Carter",
        "date_of_birth": date(1980, 1, 1),
        "address_line1": "100 Harbor Road",
        "city": "Baltimore",
        "region": "MD",
        "postal_code": "21201",
        "country": "US",
        "phone": "+1 410 555 0100",
        "government_id_last4": "6789",
        "document_type": "driving_license",
        "document_number": "MD-D12345",
        "issuing_jurisdiction": "MD",
        "document_expiration": date.today() + timedelta(days=365),
        "physical_document_examined": True,
        "likeness_matches": True,
        "owner_consented": True,
    }
    values.update(changes)
    return ManualIdentityEvidence.model_validate(values)


async def pending(session, clerk_id: str) -> tuple[UserAccount, IdentityInquiry]:  # type: ignore[no-untyped-def]
    account = UserAccount(clerk_user_id=clerk_id)
    session.add(account)
    await session.flush()
    inquiry = IdentityInquiry(
        user_account_id=account.id,
        provider_session_id=f"code-{uuid.uuid4()}",
        provider="shelter_manual",
    )
    session.add(inquiry)
    await session.flush()
    return account, inquiry


@pytest.mark.asyncio
async def test_owner_request_only_creates_pending_code(client, auth) -> None:  # type: ignore[no-untyped-def]
    response = await client.post("/api/v1/identity/inquiries", headers=auth())
    assert response.status_code == 201
    assert len(response.json()["verification_code"]) >= 32
    status_response = await client.get("/api/v1/identity/status", headers=auth())
    assert status_response.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_new_identity_is_approved_with_only_hashed_reconciliation_signals() -> None:
    async with SessionLocal() as session:
        account, inquiry = await pending(session, "new-owner")
        classification = await reconcile_manual_identity(session, inquiry, evidence(), HASH_KEY)
        await session.commit()
        assert classification == "new_identity"
        assert account.status == LinkStatus.active and account.person_id
        stored_signals = (
            await session.scalars(
                select(IdentitySignal).where(IdentitySignal.identity_inquiry_id == inquiry.id)
            )
        ).all()
        serialized = " ".join(str(row.__dict__) for row in stored_signals)
        assert "MD-D12345" not in serialized
        assert "100 Harbor Road" not in serialized
        assert "1980-01-01" not in serialized


@pytest.mark.asyncio
async def test_good_exact_match_links_existing_person() -> None:
    async with SessionLocal() as session:
        first, first_inquiry = await pending(session, "first")
        await reconcile_manual_identity(session, first_inquiry, evidence(), HASH_KEY)
        await session.commit()
        original_person = first.person_id
        second, second_inquiry = await pending(session, "second")
        classification = await reconcile_manual_identity(
            session,
            second_inquiry,
            evidence(verification_code="another-owner-code-123456"),
            HASH_KEY,
        )
        await session.commit()
        assert classification == "exact_existing"
        assert second.person_id == original_person
        assert second_inquiry.state == InquiryState.approved


@pytest.mark.asyncio
async def test_fuzzy_name_with_same_dob_is_flagged_for_second_review() -> None:
    async with SessionLocal() as session:
        first, first_inquiry = await pending(session, "first-fuzzy")
        await reconcile_manual_identity(session, first_inquiry, evidence(), HASH_KEY)
        await session.commit()
        second, second_inquiry = await pending(session, "second-fuzzy")
        classification = await reconcile_manual_identity(
            session,
            second_inquiry,
            evidence(
                full_name="Mya Carter", document_number="PA-P99881", issuing_jurisdiction="PA"
            ),
            HASH_KEY,
        )
        await session.commit()
        assert classification == "fuzzy"
        assert second.status == LinkStatus.recovery
        assert second_inquiry.state == InquiryState.needs_review
        assert await session.scalar(
            select(IdentityMatchCandidate).where(
                IdentityMatchCandidate.identity_inquiry_id == second_inquiry.id
            )
        )


@pytest.mark.asyncio
async def test_shared_phone_and_address_without_dob_does_not_merge_people() -> None:
    async with SessionLocal() as session:
        first, first_inquiry = await pending(session, "shared-house-first")
        await reconcile_manual_identity(session, first_inquiry, evidence(), HASH_KEY)
        await session.commit()
        second, second_inquiry = await pending(session, "shared-house-second")
        classification = await reconcile_manual_identity(
            session,
            second_inquiry,
            evidence(
                full_name="Jordan Carter",
                date_of_birth=date(1984, 7, 2),
                document_number="MD-Z99881",
                government_id_last4="1122",
            ),
            HASH_KEY,
        )
        await session.commit()
        assert classification == "new_identity"
        assert second.person_id != first.person_id


@pytest.mark.asyncio
async def test_conflicting_document_and_demographic_candidates_are_never_auto_linked() -> None:
    async with SessionLocal() as session:
        first, first_inquiry = await pending(session, "conflict-a")
        await reconcile_manual_identity(session, first_inquiry, evidence(), HASH_KEY)
        second, second_inquiry = await pending(session, "conflict-b")
        other = evidence(
            full_name="Jordan Lee",
            date_of_birth=date(1975, 5, 4),
            document_number="VA-X9001",
            issuing_jurisdiction="VA",
            address_line1="9 Valley Lane",
            region="VA",
            postal_code="23219",
            government_id_last4="4455",
        )
        await reconcile_manual_identity(session, second_inquiry, other, HASH_KEY)
        await session.commit()
        attacker, attacker_inquiry = await pending(session, "conflict-attempt")
        classification = await reconcile_manual_identity(
            session,
            attacker_inquiry,
            evidence(
                full_name="Jordan Lee",
                date_of_birth=date(1975, 5, 4),
                government_id_last4="4455",
            ),
            HASH_KEY,
        )
        await session.commit()
        assert classification == "conflict"
        assert attacker.person_id is None
        assert attacker_inquiry.state == InquiryState.needs_review


@pytest.mark.asyncio
async def test_unicode_and_punctuation_normalization_cannot_bypass_exact_match() -> None:
    async with SessionLocal() as session:
        first, first_inquiry = await pending(session, "normal-first")
        await reconcile_manual_identity(session, first_inquiry, evidence(), HASH_KEY)
        await session.commit()
        second, second_inquiry = await pending(session, "normal-second")
        classification = await reconcile_manual_identity(
            session,
            second_inquiry,
            evidence(full_name="ＭＡＹＡ—ＣＡＲＴＥＲ", document_number="ｍｄ－ｄ１２３４５"),
            HASH_KEY,
        )
        assert classification == "exact_existing"


@pytest.mark.asyncio
async def test_merge_redirects_accounts_without_rewriting_history() -> None:
    async with SessionLocal() as session:
        source, target = Person(status=PersonStatus.active), Person(status=PersonStatus.active)
        session.add_all([source, target])
        await session.flush()
        account = UserAccount(clerk_user_id="u", person_id=source.id, status=LinkStatus.active)
        session.add(account)
        await merge_people(
            session,
            source.id,
            target.id,
            Principal("admin", "platform_admin"),
            "confirmed consolidation",
        )
        await session.commit()
        assert source.status == PersonStatus.merged and source.merged_into_person_id == target.id
        assert account.person_id == target.id
