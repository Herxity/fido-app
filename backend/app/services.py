import hashlib
import hmac
import uuid
from datetime import timedelta
from typing import Any, cast

from cryptography.fernet import Fernet
from fastapi import HTTPException, status
from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .fraud import derive_identity_signals
from .models import (
    AuditLog,
    CustodyEvent,
    IdentityInquiry,
    IdentityMatchCandidate,
    IdentitySignal,
    InquiryState,
    LinkStatus,
    LookupToken,
    Person,
    PersonStatus,
    Shelter,
    UserAccount,
    now,
)
from .schemas import ManualIdentityEvidence
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


async def reconcile_manual_identity(
    session: AsyncSession,
    inquiry: IdentityInquiry,
    evidence: ManualIdentityEvidence,
    identity_hash_key: str,
) -> str:
    account = await session.get(UserAccount, inquiry.user_account_id, with_for_update=True)
    if account is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Account linkage is unavailable")
    inquiry.received_at = now()
    signals = derive_identity_signals(evidence, identity_hash_key)
    conditions = [
        (IdentitySignal.signal_type == signal.signal_type)
        & (IdentitySignal.value_hash == signal.value_hash)
        for signal in signals
    ]
    matches = (await session.scalars(select(IdentitySignal).where(or_(*conditions)))).all()
    current_by_hash = {(signal.signal_type, signal.value_hash) for signal in signals}
    name_ngrams = {digest for kind, digest in current_by_hash if kind == "name_ngram"}
    address_ngrams = {digest for kind, digest in current_by_hash if kind == "address_ngram"}
    by_person: dict[uuid.UUID, set[tuple[str, str]]] = {}
    for match in matches:
        if match.person_id is not None:
            by_person.setdefault(match.person_id, set()).add((match.signal_type, match.value_hash))

    candidates: list[tuple[uuid.UUID, str, int, list[str]]] = []
    for person_id, person_matches in by_person.items():
        types = {kind for kind, _digest in person_matches}
        matched_name = len(
            {digest for kind, digest in person_matches if kind == "name_ngram"} & name_ngrams
        )
        matched_address = len(
            {digest for kind, digest in person_matches if kind == "address_ngram"} & address_ngrams
        )
        name_ratio = matched_name / max(len(name_ngrams), 1)
        address_ratio = matched_address / max(len(address_ngrams), 1)
        exact_document = "document_semantic" in types
        exact_name_dob = "name_dob" in types
        dob_match = "dob" in types
        evidence_types: list[str] = []
        if exact_document:
            evidence_types.append("same_document")
        if exact_name_dob:
            evidence_types.append("same_name_and_dob")
        if "address_dob" in types:
            evidence_types.append("same_address_and_dob")
        if "id_last4_name_dob" in types:
            evidence_types.append("same_last4_name_and_dob")
        if name_ratio >= 0.65:
            evidence_types.append("similar_name")
        if address_ratio >= 0.60:
            evidence_types.append("similar_address")
        if exact_document and (exact_name_dob or (dob_match and name_ratio >= 0.70)):
            candidates.append((person_id, "exact", 100, evidence_types))
        elif exact_document:
            candidates.append((person_id, "fuzzy", 85, evidence_types))
        elif exact_name_dob:
            candidates.append((person_id, "fuzzy", 80, evidence_types))
        elif dob_match and name_ratio >= 0.65:
            candidates.append(
                (person_id, "fuzzy", min(79, round(55 + name_ratio * 25)), evidence_types)
            )
        elif "address_dob" in types and name_ratio >= 0.40:
            candidates.append((person_id, "fuzzy", 65, evidence_types))

    exact = [candidate for candidate in candidates if candidate[1] == "exact"]
    candidate_people = {candidate[0] for candidate in candidates}
    if len(exact) == 1 and candidate_people == {exact[0][0]}:
        person = await canonical_person(session, exact[0][0])
        classification = "exact_existing"
    elif candidates:
        classification = "conflict" if len(candidate_people) > 1 or len(exact) > 1 else "fuzzy"
        inquiry.state = InquiryState.needs_review
        inquiry.match_classification = classification
        inquiry.repeat_outcome = "possible_existing_identity"
        inquiry.reason_category = f"{classification}_identity_match"
        account.status = LinkStatus.recovery
        for person_id, candidate_class, confidence, evidence_types in candidates:
            session.add(
                IdentityMatchCandidate(
                    identity_inquiry_id=inquiry.id,
                    person_id=person_id,
                    classification=candidate_class,
                    confidence=confidence,
                    evidence_summary=",".join(sorted(set(evidence_types))),
                )
            )
        for signal in signals:
            session.add(
                IdentitySignal(
                    identity_inquiry_id=inquiry.id,
                    signal_type=signal.signal_type,
                    value_hash=signal.value_hash,
                    assurance=signal.assurance,
                )
            )
        return classification
    else:
        person = Person(status=PersonStatus.active)
        classification = "new_identity"
        session.add(person)
        await session.flush()
    person.status = PersonStatus.active
    person.verified_at = now()
    person.verified_display_name = evidence.full_name
    account.person_id = person.id
    account.status = LinkStatus.active
    account.link_reason = "shelter_identity_verified"
    account.linked_at = now()
    inquiry.person_id = person.id
    inquiry.state = InquiryState.approved
    inquiry.match_classification = classification
    inquiry.resolved_at = now()
    for signal in signals:
        session.add(
            IdentitySignal(
                identity_inquiry_id=inquiry.id,
                person_id=person.id,
                signal_type=signal.signal_type,
                value_hash=signal.value_hash,
                assurance=signal.assurance,
            )
        )
    return classification


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
