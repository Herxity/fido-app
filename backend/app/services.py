import hashlib
import hmac
import uuid
from datetime import timedelta
from typing import Any, cast

from cryptography.fernet import Fernet
from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    AuditLog,
    CustodyEvent,
    IdentityInquiry,
    InquiryState,
    LinkStatus,
    LookupToken,
    Person,
    PersonStatus,
    Shelter,
    UserAccount,
    now,
)
from .schemas import PersonaInquiryResult
from .security import Principal, keyed_hash, opaque_token


async def audit(
    session: AsyncSession,
    principal: Principal | None,
    action: str,
    resource_type: str | None,
    resource_id: str | None,
    outcome: str = "success",
    request_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    session.add(
        AuditLog(
            actor_user_id=principal.user_id if principal else None,
            organization_id=principal.organization_id if principal else None,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome=outcome,
            request_id=request_id,
            security_metadata=metadata or {},
        )
    )


async def get_account(
    session: AsyncSession, user_id: str, *, create: bool = False
) -> UserAccount | None:
    account = await session.scalar(select(UserAccount).where(UserAccount.clerk_user_id == user_id))
    if account is None and create:
        account = UserAccount(clerk_user_id=user_id)
        session.add(account)
        await session.flush()
    return account


async def canonical_person(session: AsyncSession, person_id: uuid.UUID) -> Person:
    seen: set[uuid.UUID] = set()
    person = await session.get(Person, person_id)
    while person is not None and person.status == PersonStatus.merged:
        if person.id in seen or person.merged_into_person_id is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Identity linkage is inconsistent")
        seen.add(person.id)
        person = await session.get(Person, person.merged_into_person_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resource not found")
    return person


async def process_persona_result(session: AsyncSession, result: PersonaInquiryResult) -> None:
    inquiry = await session.scalar(
        select(IdentityInquiry)
        .where(IdentityInquiry.persona_inquiry_id == result.inquiry_id)
        .with_for_update()
    )
    if inquiry is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown inquiry reference")
    if inquiry.state in {InquiryState.approved, InquiryState.declined, InquiryState.superseded}:
        return
    account = await session.get(UserAccount, inquiry.user_account_id, with_for_update=True)
    if account is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Account linkage is unavailable")
    inquiry.received_at = now()
    inquiry.persona_account_id = result.account_id
    inquiry.repeat_outcome = result.repeat_outcome
    inquiry.workflow_reference = result.workflow_reference
    inquiry.case_reference = result.case_reference
    inquiry.reason_category = result.reason_category
    account.persona_account_id = result.account_id
    # Strong provider evidence may recover the already-known canonical identity.
    if result.state == InquiryState.approved and result.repeat_outcome in {None, "clear"}:
        if account.person_id is None:
            person = Person(
                status=PersonStatus.active,
                verified_display_name=result.display_name,
                verified_at=now(),
            )
            session.add(person)
            await session.flush()
            account.person_id = person.id
        else:
            person = await canonical_person(session, account.person_id)
            person.status = PersonStatus.active
            person.verified_at = now()
            if result.display_name:
                person.verified_display_name = result.display_name
        account.status = LinkStatus.active
        account.link_reason = "persona_workflow_approved"
        account.linked_at = now()
        inquiry.person_id = person.id
        inquiry.state = InquiryState.approved
        inquiry.resolved_at = now()
    elif (
        result.state == InquiryState.approved
        and result.repeat_outcome == "strong_match"
        and result.matched_person_id is not None
    ):
        target = await canonical_person(session, result.matched_person_id)
        account.person_id = target.id
        account.status = LinkStatus.recovery
        account.link_reason = "persona_strong_repeat_match"
        account.linked_at = now()
        inquiry.person_id = target.id
        inquiry.state = InquiryState.needs_review
    elif result.state == InquiryState.declined:
        inquiry.state = InquiryState.declined
        inquiry.resolved_at = now()
        account.status = LinkStatus.pending
    else:
        inquiry.state = InquiryState.needs_review
        if account.person_id:
            person = await canonical_person(session, account.person_id)
            person.status = PersonStatus.review
        account.status = LinkStatus.recovery


async def merge_people(
    session: AsyncSession,
    source_id: uuid.UUID,
    target_id: uuid.UUID,
    principal: Principal,
    explanation: str,
) -> Person:
    if source_id == target_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Source and target must differ")
    source = await canonical_person(session, source_id)
    target = await canonical_person(session, target_id)
    if source.id == target.id:
        return target
    if target.status in {PersonStatus.restricted, PersonStatus.deleted}:
        raise HTTPException(status.HTTP_409_CONFLICT, "Target identity cannot receive a merge")
    source.status = PersonStatus.merged
    source.merged_into_person_id = target.id
    source.reviewed_at = now()
    await session.execute(
        update(UserAccount).where(UserAccount.person_id == source.id).values(person_id=target.id)
    )
    await audit(
        session,
        principal,
        "person.merge",
        "person",
        str(source.id),
        metadata={"target_person_id": str(target.id), "explanation": explanation[:300]},
    )
    return target


def encrypt_microchip(
    value: str | None, encryption_key: str, lookup_key: str
) -> tuple[bytes | None, str | None]:
    if not value:
        return None, None
    normalized = "".join(value.upper().split())
    if not encryption_key:
        raise RuntimeError("field encryption key is required")
    ciphertext = Fernet(encryption_key.encode()).encrypt(normalized.encode())
    digest = hmac.new(lookup_key.encode(), normalized.encode(), hashlib.sha256).hexdigest()
    return ciphertext, digest


async def shelter_for_principal(session: AsyncSession, principal: Principal) -> Shelter:
    if not principal.organization_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Organization context required")
    shelter = await session.scalar(
        select(Shelter).where(
            Shelter.clerk_organization_id == principal.organization_id,
            Shelter.status == "active",
        )
    )
    if shelter is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Organization is not active")
    return shelter


async def create_lookup_token(
    session: AsyncSession, principal: Principal, lookup_key: str
) -> tuple[LookupToken, str]:
    account = await get_account(session, principal.user_id)
    if account is None or account.status != LinkStatus.active or account.person_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Approved identity required")
    person = await canonical_person(session, account.person_id)
    if person.status != PersonStatus.active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Approved identity required")
    raw = opaque_token()
    row = LookupToken(
        token_hash=keyed_hash(raw, lookup_key),
        person_id=person.id,
        created_by_user_id=principal.user_id,
        expires_at=now() + timedelta(minutes=5),
    )
    session.add(row)
    await session.flush()
    await audit(session, principal, "lookup_token.create", "lookup_token", str(row.id))
    return row, raw


async def redeem_lookup_token(
    session: AsyncSession, principal: Principal, raw: str, lookup_key: str
) -> LookupToken:
    shelter = await shelter_for_principal(session, principal)
    token_hash = keyed_hash(raw, lookup_key)
    result = await session.execute(
        update(LookupToken)
        .where(
            LookupToken.token_hash == token_hash,
            LookupToken.consumed_at.is_(None),
            LookupToken.revoked_at.is_(None),
            LookupToken.expires_at > now(),
        )
        .values(
            consumed_at=now(),
            redeeming_shelter_id=shelter.id,
            redeeming_user_id=principal.user_id,
            session_id=uuid.uuid4(),
            session_expires_at=now() + timedelta(minutes=30),
        )
        .returning(LookupToken)
    )
    row: LookupToken | None = result.scalar_one_or_none()
    if row is None:
        await audit(session, principal, "lookup_token.redeem", None, None, "denied")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Lookup code is invalid or unavailable")
    await audit(session, principal, "lookup_token.redeem", "lookup_session", str(row.session_id))
    return row


async def valid_lookup_session(
    session: AsyncSession, principal: Principal, session_id: uuid.UUID
) -> LookupToken:
    shelter = await shelter_for_principal(session, principal)
    row = await session.scalar(
        select(LookupToken).where(
            LookupToken.session_id == session_id,
            LookupToken.redeeming_shelter_id == shelter.id,
            LookupToken.redeeming_user_id == principal.user_id,
            LookupToken.revoked_at.is_(None),
            LookupToken.session_expires_at > now(),
        )
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lookup session not found")
    return row


async def insert_custody_idempotently(session: AsyncSession, event: CustodyEvent) -> CustodyEvent:
    existing = await session.scalar(
        select(CustodyEvent).where(
            CustodyEvent.shelter_id == event.shelter_id,
            CustodyEvent.idempotency_key == event.idempotency_key,
        )
    )
    if existing:
        return existing
    session.add(event)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        existing = await session.scalar(
            select(CustodyEvent).where(
                CustodyEvent.shelter_id == event.shelter_id,
                CustodyEvent.idempotency_key == event.idempotency_key,
            )
        )
        if existing:
            return cast(CustodyEvent, existing)
        raise
    return event


async def purge_expired_metadata(session: AsyncSession) -> dict[str, int]:
    # Custody and dispute records are intentionally excluded from automated deletion.
    unused_before = now() - timedelta(hours=24)
    session_cutoff = now() - timedelta(days=30)
    result = await session.execute(
        update(LookupToken)
        .where(LookupToken.consumed_at.is_(None), LookupToken.expires_at < unused_before)
        .values(revoked_at=now())
    )
    sessions = await session.execute(
        update(LookupToken)
        .where(LookupToken.session_expires_at < session_cutoff)
        .values(session_id=None, session_expires_at=None)
    )
    return {"unused_tokens_revoked": result.rowcount, "expired_sessions_removed": sessions.rowcount}
