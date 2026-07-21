import pytest

from app.db import SessionLocal
from app.models import IdentityInquiry, InquiryState, LinkStatus, Person, PersonStatus, UserAccount
from app.schemas import StripeVerificationResult
from app.security import Principal
from app.services import merge_people, process_stripe_result

HASH_KEY = "identity-test-hmac-key-at-least-32-bytes"


@pytest.mark.asyncio
async def test_browser_completion_cannot_approve(client, auth) -> None:  # type: ignore[no-untyped-def]
    response = await client.post("/api/v1/identity/inquiries", headers=auth())
    assert response.status_code == 201
    assert response.json()["client_secret"].startswith("vs_test_")
    status = await client.get("/api/v1/identity/status", headers=auth())
    assert status.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_verified_stripe_result_creates_canonical_person_and_hashed_signals() -> None:
    async with SessionLocal() as session:
        account = UserAccount(clerk_user_id="owner")
        session.add(account)
        await session.flush()
        inquiry = IdentityInquiry(user_account_id=account.id, provider_session_id="vs_1")
        session.add(inquiry)
        await session.flush()
        await process_stripe_result(
            session,
            StripeVerificationResult(
                session_id="vs_1",
                state=InquiryState.approved,
                display_name="Test Owner",
                document_number="D123",
                document_type="driving_license",
                issuing_country="US",
                dob="1980-01-01",
            ),
            HASH_KEY,
        )
        await session.commit()
        assert account.status == LinkStatus.active and account.person_id
        person = await session.get(Person, account.person_id)
        assert person and person.verified_display_name == "Test Owner"
        assert inquiry.state == InquiryState.approved
        assert "D123" not in str(inquiry.__dict__)


@pytest.mark.asyncio
async def test_alternate_document_with_same_name_and_dob_routes_to_manual_review() -> None:
    async with SessionLocal() as session:
        first = UserAccount(clerk_user_id="owner_first")
        session.add(first)
        await session.flush()
        first_inquiry = IdentityInquiry(user_account_id=first.id, provider_session_id="vs_first")
        session.add(first_inquiry)
        await session.flush()
        await process_stripe_result(
            session,
            StripeVerificationResult(
                session_id="vs_first",
                state=InquiryState.approved,
                display_name="Maya Carter",
                document_number="LICENSE-1",
                document_type="driving_license",
                issuing_country="US",
                dob="1980-01-01",
            ),
            HASH_KEY,
        )
        await session.commit()

        second = UserAccount(clerk_user_id="owner_second")
        session.add(second)
        await session.flush()
        second_inquiry = IdentityInquiry(user_account_id=second.id, provider_session_id="vs_second")
        session.add(second_inquiry)
        await session.flush()
        await process_stripe_result(
            session,
            StripeVerificationResult(
                session_id="vs_second",
                state=InquiryState.approved,
                display_name="Maya Carter",
                document_number="PASSPORT-2",
                document_type="passport",
                issuing_country="US",
                dob="1980-01-01",
            ),
            HASH_KEY,
        )
        await session.commit()

        assert second.person_id is None
        assert second.status == LinkStatus.recovery
        assert second_inquiry.state == InquiryState.needs_review
        assert second_inquiry.reason_category == "duplicate_identity_signal"


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
