import pytest

from app.db import SessionLocal
from app.models import IdentityInquiry, InquiryState, LinkStatus, Person, PersonStatus, UserAccount
from app.schemas import PersonaInquiryResult
from app.security import Principal
from app.services import merge_people, process_persona_result


@pytest.mark.asyncio
async def test_browser_completion_cannot_approve(client, auth) -> None:  # type: ignore[no-untyped-def]
    response = await client.post("/api/v1/identity/inquiries", headers=auth())
    assert response.status_code == 201
    status = await client.get("/api/v1/identity/status", headers=auth())
    assert status.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_approved_webhook_creates_canonical_person() -> None:
    async with SessionLocal() as session:
        account = UserAccount(clerk_user_id="owner")
        session.add(account)
        await session.flush()
        inquiry = IdentityInquiry(user_account_id=account.id, persona_inquiry_id="inq_1")
        session.add(inquiry)
        await session.flush()
        await process_persona_result(
            session,
            PersonaInquiryResult(
                inquiry_id="inq_1",
                state=InquiryState.approved,
                account_id="acct_1",
                display_name="Test Owner",
                repeat_outcome="clear",
            ),
        )
        await session.commit()
        assert account.status == LinkStatus.active and account.person_id
        person = await session.get(Person, account.person_id)
        assert (
            person
            and person.status == PersonStatus.active
            and person.verified_display_name == "Test Owner"
        )


@pytest.mark.asyncio
async def test_ambiguous_and_portrait_conflict_never_auto_merge() -> None:
    for outcome in ("ambiguous", "portrait_conflict", "details_conflict"):
        async with SessionLocal() as session:
            account = UserAccount(clerk_user_id=f"owner_{outcome}")
            session.add(account)
            await session.flush()
            inquiry = IdentityInquiry(
                user_account_id=account.id, persona_inquiry_id=f"inq_{outcome}"
            )
            session.add(inquiry)
            await session.flush()
            await process_persona_result(
                session,
                PersonaInquiryResult(
                    inquiry_id=inquiry.persona_inquiry_id,
                    state=InquiryState.approved,
                    repeat_outcome=outcome,
                ),
            )
            assert inquiry.state == InquiryState.needs_review
            assert account.person_id is None
            await session.commit()


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
