"""Seed the minimum synthetic tenant required for local shelter workflows."""

import asyncio
from datetime import date, timedelta

from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.fraud import verification_code_hash
from app.models import IdentityInquiry, LinkStatus, Shelter, UserAccount
from app.schemas import ManualIdentityEvidence
from app.services import reconcile_manual_identity

BASELINE_CODE = "LOCAL-BASELINE-OWNER-IDENTITY-0001"
EXACT_CHANGED_ADDRESS_CODE = "LOCAL-EXACT-CHANGED-ADDRESS-0005"
FUZZY_REVIEW_CODE = "LOCAL-FUZZY-REVIEW-OWNER-0003"
NEW_IDENTITY_CODE = "LOCAL-NEW-IDENTITY-OWNER-0004"


def baseline_evidence(code: str = BASELINE_CODE) -> ManualIdentityEvidence:
    return ManualIdentityEvidence(
        verification_code=code,
        full_name="Maya Carter",
        date_of_birth=date(1980, 1, 1),
        address_line1="100 Harbor Road",
        city="Baltimore",
        region="MD",
        postal_code="21201",
        country="US",
        phone="+14105550100",
        government_id_last4="6789",
        document_type="driving_license",
        document_number="MD-D12345",
        issuing_jurisdiction="MD",
        document_expiration=date.today() + timedelta(days=365),
        physical_document_examined=True,
        likeness_matches=True,
        owner_consented=True,
    )


async def ensure_pending_account(session, clerk_user_id: str, code: str, key: str) -> None:  # type: ignore[no-untyped-def]
    account = await session.scalar(
        select(UserAccount).where(UserAccount.clerk_user_id == clerk_user_id)
    )
    if account is None:
        account = UserAccount(clerk_user_id=clerk_user_id)
        session.add(account)
        await session.flush()
    code_hash = verification_code_hash(code, key)
    inquiry = await session.scalar(
        select(IdentityInquiry).where(IdentityInquiry.provider_session_id == code_hash)
    )
    if inquiry is None:
        session.add(
            IdentityInquiry(
                user_account_id=account.id,
                provider="shelter_manual",
                provider_session_id=code_hash,
            )
        )


async def seed() -> None:
    settings = get_settings()
    if settings.environment != "development":
        raise RuntimeError("Development seed is disabled outside FIDO_ENVIRONMENT=development")
    if not settings.development_clerk_org_id:
        raise RuntimeError("FIDO_DEVELOPMENT_CLERK_ORG_ID is required for the local seed")
    async with SessionLocal() as session:
        shelter = await session.scalar(
            select(Shelter).where(
                Shelter.clerk_organization_id == settings.development_clerk_org_id
            )
        )
        if shelter is None:
            session.add(
                Shelter(
                    clerk_organization_id=settings.development_clerk_org_id,
                    name="Harbor Shelter (Local)",
                    contact={"synthetic": True},
                    configuration={"environment": "development"},
                )
            )
        baseline_account = await session.scalar(
            select(UserAccount).where(UserAccount.clerk_user_id == "local-owner-baseline")
        )
        if baseline_account is None:
            baseline_account = UserAccount(clerk_user_id="local-owner-baseline")
            session.add(baseline_account)
            await session.flush()
        if baseline_account.status != LinkStatus.active:
            inquiry = IdentityInquiry(
                user_account_id=baseline_account.id,
                provider="shelter_manual",
                provider_session_id=verification_code_hash(
                    BASELINE_CODE, settings.identity_hash_key
                ),
            )
            session.add(inquiry)
            await session.flush()
            await reconcile_manual_identity(
                session, inquiry, baseline_evidence(), settings.identity_hash_key
            )
        await ensure_pending_account(
            session,
            "local-owner-exact-address-change-v2",
            EXACT_CHANGED_ADDRESS_CODE,
            settings.identity_hash_key,
        )
        await ensure_pending_account(
            session, "local-owner-fuzzy", FUZZY_REVIEW_CODE, settings.identity_hash_key
        )
        await ensure_pending_account(
            session, "local-owner-new", NEW_IDENTITY_CODE, settings.identity_hash_key
        )
        await session.commit()

    print("Synthetic local verification codes:")
    print(f"  exact match with changed address: {EXACT_CHANGED_ADDRESS_CODE}")
    print(f"  fuzzy review: {FUZZY_REVIEW_CODE}")
    print(f"  new identity: {NEW_IDENTITY_CODE}")


if __name__ == "__main__":
    asyncio.run(seed())
