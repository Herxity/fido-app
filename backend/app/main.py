import json
import logging
import time
import uuid
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pythonjsonlogger.json import JsonFormatter
from sqlalchemy import and_, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .config import Settings, get_settings
from .db import get_session
from .fraud import verification_code_hash
from .models import (
    CustodyEvent,
    CustodyEventType,
    Dispute,
    DisputeStatus,
    IdentityInquiry,
    IdentityMatchCandidate,
    IdentitySignal,
    InquiryState,
    LinkStatus,
    LookupToken,
    Person,
    PersonStatus,
    Pet,
    Shelter,
    UserAccount,
    WebhookEvent,
    WebhookState,
    now,
)
from .schemas import (
    CorrectionCreate,
    CustodyCreate,
    DisputeCreate,
    DisputePatch,
    LookupRedeem,
    ManualIdentityEvidence,
    PetCreate,
    PetPatch,
    ReviewResolve,
    decode_cursor,
    encode_cursor,
)
from .security import Principal, opaque_token, require_roles, verify_clerk_webhook
from .services import (
    audit,
    canonical_person,
    create_lookup_token,
    encrypt_microchip,
    get_account,
    insert_custody_idempotently,
    merge_people,
    reconcile_manual_identity,
    redeem_lookup_token,
    shelter_for_principal,
    valid_lookup_session,
)

handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s"))
logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
logger = logging.getLogger("fido")
settings = get_settings()
app = FastAPI(
    title="Fido API",
    version="1.0.0",
    docs_url=None if settings.environment == "production" else "/docs",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
)


class RateLimiter:
    def __init__(self) -> None:
        self.events: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, limit: int, window: int = 60) -> None:
        timestamp = time.monotonic()
        bucket = self.events[key]
        while bucket and bucket[0] < timestamp - window:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests")
        bucket.append(timestamp)


rate_limiter = RateLimiter()


@app.middleware("http")
async def request_controls(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))[:100]
    request.state.request_id = request_id
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > settings.request_body_limit:
        return problem(
            413, "Request Too Large", "Request body exceeds the configured limit", request_id
        )
    started = time.monotonic()
    try:
        response = await call_next(request)
    except json.JSONDecodeError:
        response = problem(400, "Bad Request", "Malformed JSON", request_id)
    response.headers.update(
        {
            "X-Request-ID": request_id,
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
            "Cache-Control": "no-store",
        }
    )
    if settings.environment == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    logger.info(
        "request.complete",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": int((time.monotonic() - started) * 1000),
        },
    )
    return response


def problem(code: int, title: str, detail: str, request_id: str | None = None) -> Response:
    payload = {"type": "about:blank", "title": title, "status": code, "detail": detail}
    if request_id:
        payload["request_id"] = request_id
    return Response(json.dumps(payload), code, media_type="application/problem+json")


@app.exception_handler(HTTPException)
async def http_problem(request: Request, exc: HTTPException) -> Response:
    titles = {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        409: "Conflict",
        422: "Unprocessable Entity",
        429: "Too Many Requests",
        503: "Service Unavailable",
    }
    return problem(
        exc.status_code,
        titles.get(exc.status_code, "Request Failed"),
        str(exc.detail),
        getattr(request.state, "request_id", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_problem(request: Request, exc: RequestValidationError) -> Response:
    errors = [
        {"location": ".".join(map(str, item["loc"])), "code": item["type"], "message": item["msg"]}
        for item in exc.errors()
    ]
    payload = {
        "type": "https://fido.invalid/problems/validation",
        "title": "Validation Failed",
        "status": 422,
        "detail": "Request validation failed",
        "errors": errors,
        "request_id": request.state.request_id,
    }
    return Response(json.dumps(payload), 422, media_type="application/problem+json")


def pet_json(pet: Pet) -> dict[str, Any]:
    return {
        "id": pet.id,
        "shelter_id": pet.shelter_id,
        "record_number": pet.record_number,
        "name": pet.name,
        "species": pet.species,
        "breed_description": pet.breed_description,
        "sex": pet.sex,
        "approximate_birth_date": pet.approximate_birth_date,
        "color": pet.color,
        "altered": pet.altered,
        "lifecycle_state": pet.lifecycle_state,
        "created_at": pet.created_at,
        "updated_at": pet.updated_at,
    }


def event_json(event: CustodyEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "pet": {
            "id": event.pet.id,
            "name": event.pet.name,
            "species": event.pet.species,
            "record_number": event.pet.record_number,
        },
        "event_type": event.event_type,
        "effective_at": event.effective_at,
        "entered_local_date": event.entered_local_date,
        "source_shelter": {"id": event.shelter.id, "name": event.shelter.name},
        "source_reference": event.source_reference,
        "reason_category": event.reason_category,
        "factual_note": event.factual_note,
        "corrects_event_id": event.corrects_event_id,
        "created_at": event.created_at,
    }


async def owner_account(
    session: AsyncSession, principal: Principal
) -> tuple[UserAccount, Person | None]:
    account = await get_account(session, principal.user_id, create=True)
    assert account is not None
    person = await canonical_person(session, account.person_id) if account.person_id else None
    return account, person


@app.get("/api/v1/me")
async def me(
    principal: Principal = Depends(
        require_roles(
            "owner",
            "shelter_admin",
            "shelter_staff",
            "shelter_read_only",
            "platform_admin",
        )
    ),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    viewer: dict[str, Any] = {
        "user_id": principal.user_id,
        "mode": "owner",
        "role": principal.role,
        "identity_status": "unverified",
        "display_name": None,
    }
    if principal.role == "owner":
        account, person = await owner_account(session, principal)
        viewer.update(
            {
                "person_id": person.id if person else None,
                "display_name": person.verified_display_name if person else None,
                "identity_status": (
                    "approved" if account.status == LinkStatus.active else account.status.value
                ),
            }
        )
        await session.commit()
        return viewer
    if principal.role.startswith("shelter_"):
        shelter = await shelter_for_principal(session, principal)
        viewer.update(
            {
                "mode": "shelter",
                "identity_status": "not_applicable",
                "shelter": {"id": shelter.id, "name": shelter.name},
            }
        )
        return viewer
    viewer.update({"mode": "platform_admin", "identity_status": "not_applicable"})
    return viewer


@app.post("/api/v1/identity/inquiries", status_code=201)
async def create_inquiry(
    request: Request,
    principal: Principal = Depends(require_roles("owner")),
    session: AsyncSession = Depends(get_session),
    config: Settings = Depends(get_settings),
) -> dict[str, Any]:
    rate_limiter.check(f"identity:{principal.user_id}", 5, 3600)
    account, _ = await owner_account(session, principal)
    if account.status == LinkStatus.active:
        raise HTTPException(409, "Identity is already verified")
    pending_rows = (
        await session.scalars(
            select(IdentityInquiry).where(
                IdentityInquiry.user_account_id == account.id,
                IdentityInquiry.state == InquiryState.pending,
            )
        )
    ).all()
    for pending in pending_rows:
        pending.state = InquiryState.superseded
        pending.resolved_at = now()
    reference = uuid.uuid4()
    verification_code = opaque_token()
    inquiry = IdentityInquiry(
        user_account_id=account.id,
        person_id=account.person_id,
        reference_id=reference,
        provider="shelter_manual",
        provider_session_id=verification_code_hash(verification_code, config.identity_hash_key),
    )
    session.add(inquiry)
    await session.flush()
    await audit(
        session,
        principal,
        "identity_inquiry.create",
        "identity_inquiry",
        str(inquiry.id),
        request_id=request.state.request_id,
    )
    await session.commit()
    return {
        "id": inquiry.id,
        "verification_code": verification_code,
        "expires_at": inquiry.created_at + timedelta(hours=24),
        "status": inquiry.state,
    }


@app.post("/api/v1/identity/manual-verifications", status_code=201)
async def submit_manual_verification(
    payload: ManualIdentityEvidence,
    request: Request,
    principal: Principal = Depends(require_roles("shelter_admin", "shelter_staff")),
    session: AsyncSession = Depends(get_session),
    config: Settings = Depends(get_settings),
) -> dict[str, Any]:
    shelter = await shelter_for_principal(session, principal)
    rate_limiter.check(f"manual-identity:{principal.user_id}", 30, 3600)
    if not all(
        (payload.physical_document_examined, payload.likeness_matches, payload.owner_consented)
    ):
        raise HTTPException(422, "All physical verification attestations are required")
    today = datetime.now(UTC).date()
    if payload.document_expiration < today:
        raise HTTPException(422, "Expired identity document")
    try:
        adult_cutoff = today.replace(year=today.year - 18)
    except ValueError:
        adult_cutoff = today.replace(year=today.year - 18, day=28)
    if payload.date_of_birth > adult_cutoff:
        raise HTTPException(422, "Owner must be at least 18 years old")
    try:
        oldest_plausible = today.replace(year=today.year - 120)
    except ValueError:
        oldest_plausible = today.replace(year=today.year - 120, day=28)
    if payload.date_of_birth < oldest_plausible:
        raise HTTPException(422, "Date of birth is outside the supported range")
    code_hash = verification_code_hash(payload.verification_code, config.identity_hash_key)
    inquiry = await session.scalar(
        select(IdentityInquiry)
        .where(
            IdentityInquiry.provider == "shelter_manual",
            IdentityInquiry.provider_session_id == code_hash,
        )
        .with_for_update()
    )
    if inquiry is None:
        raise HTTPException(404, "Verification request is invalid or expired")
    created_at = inquiry.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    if inquiry.state != InquiryState.pending or created_at < now() - timedelta(hours=24):
        raise HTTPException(404, "Verification request is invalid or expired")
    inquiry.reviewing_shelter_id = shelter.id
    inquiry.submitted_by_user_id = principal.user_id
    inquiry.submitted_display_name = payload.full_name
    classification = await reconcile_manual_identity(
        session, inquiry, payload, config.identity_hash_key
    )
    candidate_count = await session.scalar(
        select(func.count())
        .select_from(IdentityMatchCandidate)
        .where(IdentityMatchCandidate.identity_inquiry_id == inquiry.id)
    )
    await audit(
        session,
        principal,
        "identity.manual_verify",
        "identity_inquiry",
        str(inquiry.id),
        request_id=request.state.request_id,
        metadata={"classification": classification, "candidate_count": candidate_count or 0},
    )
    await session.commit()
    return {
        "id": inquiry.id,
        "state": inquiry.state,
        "classification": classification,
        "candidate_count": candidate_count or 0,
    }


@app.get("/api/v1/identity/status")
async def identity_status(
    principal: Principal = Depends(require_roles("owner")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    account = await get_account(session, principal.user_id)
    if account is None:
        return {"status": "unverified", "inquiry_id": None}
    inquiry = await session.scalar(
        select(IdentityInquiry)
        .where(IdentityInquiry.user_account_id == account.id)
        .order_by(IdentityInquiry.created_at.desc())
    )
    return {
        "status": inquiry.state.value if inquiry else "unverified",
        "inquiry_id": inquiry.id if inquiry else None,
    }


async def history_for_person(
    session: AsyncSession, person: Person, limit: int, cursor: str | None
) -> tuple[list[CustodyEvent], str | None]:
    person_ids = [person.id]
    merged_sources = (
        await session.scalars(select(Person.id).where(Person.merged_into_person_id == person.id))
    ).all()
    person_ids.extend(merged_sources)
    query = (
        select(CustodyEvent)
        .options(selectinload(CustodyEvent.pet), selectinload(CustodyEvent.shelter))
        .where(CustodyEvent.person_id.in_(person_ids))
    )
    if cursor:
        try:
            created, row_id = decode_cursor(cursor)
        except ValueError as exc:
            raise HTTPException(400, "Invalid cursor") from exc
        query = query.where(
            or_(
                CustodyEvent.created_at < created,
                and_(CustodyEvent.created_at == created, CustodyEvent.id < row_id),
            )
        )
    rows = (
        await session.scalars(
            query.order_by(CustodyEvent.created_at.desc(), CustodyEvent.id.desc()).limit(limit + 1)
        )
    ).all()
    next_cursor = (
        encode_cursor(rows[limit - 1].created_at, rows[limit - 1].id) if len(rows) > limit else None
    )
    return list(rows[:limit]), next_cursor


@app.get("/api/v1/me/history")
async def owner_history(
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = None,
    principal: Principal = Depends(require_roles("owner")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    account, person = await owner_account(session, principal)
    if account.status != LinkStatus.active or person is None:
        raise HTTPException(403, "Approved identity required")
    rows, next_cursor = await history_for_person(session, person, limit, cursor)
    return {"items": [event_json(row) for row in rows], "next_cursor": next_cursor}


@app.post("/api/v1/me/lookup-tokens", status_code=201)
async def lookup_token(
    request: Request,
    principal: Principal = Depends(require_roles("owner")),
    session: AsyncSession = Depends(get_session),
    config: Settings = Depends(get_settings),
) -> dict[str, Any]:
    rate_limiter.check(f"qr:{principal.user_id}", 10, 3600)
    row, raw = await create_lookup_token(session, principal, config.lookup_hash_key)
    await session.commit()
    return {"token": raw, "qr_payload": f"fido:lookup:{raw}", "expires_at": row.expires_at}


@app.get("/api/v1/me/access-log")
async def access_log(
    limit: int = Query(50, ge=1, le=100),
    principal: Principal = Depends(require_roles("owner")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    account, person = await owner_account(session, principal)
    if person is None:
        return {"items": [], "next_cursor": None}
    rows = (
        await session.scalars(
            select(LookupToken)
            .where(LookupToken.person_id == person.id, LookupToken.consumed_at.is_not(None))
            .order_by(LookupToken.consumed_at.desc())
            .limit(limit)
        )
    ).all()
    items = []
    for row in rows:
        shelter = await session.get(Shelter, row.redeeming_shelter_id)
        items.append(
            {
                "shelter": {"id": shelter.id, "name": shelter.name} if shelter else None,
                "accessed_at": row.consumed_at,
                "session_expires_at": row.session_expires_at,
            }
        )
    return {"items": items, "next_cursor": None}


@app.post("/api/v1/me/disputes", status_code=201)
async def create_dispute(
    payload: DisputeCreate,
    request: Request,
    principal: Principal = Depends(require_roles("owner")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    account, person = await owner_account(session, principal)
    if account.status != LinkStatus.active or person is None:
        raise HTTPException(403, "Approved identity required")
    event = await session.get(CustodyEvent, payload.event_id)
    if event is None or (await canonical_person(session, event.person_id)).id != person.id:
        raise HTTPException(404, "Event not found")
    row = Dispute(
        person_id=person.id,
        event_id=event.id,
        responsible_shelter_id=event.shelter_id,
        owner_reason=payload.reason,
    )
    session.add(row)
    await session.flush()
    await audit(
        session,
        principal,
        "dispute.create",
        "dispute",
        str(row.id),
        request_id=request.state.request_id,
    )
    await session.commit()
    return {"id": row.id, "status": row.status, "created_at": row.created_at}


@app.post("/api/v1/lookups/redeem")
async def redeem(
    payload: LookupRedeem,
    request: Request,
    principal: Principal = Depends(require_roles("shelter_admin", "shelter_staff")),
    session: AsyncSession = Depends(get_session),
    config: Settings = Depends(get_settings),
) -> dict[str, Any]:
    rate_limiter.check(f"redeem:{principal.organization_id}:{principal.user_id}", 30)
    raw = payload.token.removeprefix("fido:lookup:")
    row = await redeem_lookup_token(session, principal, raw, config.lookup_hash_key)
    await session.commit()
    return {"session_id": row.session_id, "expires_at": row.session_expires_at}


@app.get("/api/v1/lookups/{session_id}/history")
async def lookup_history(
    session_id: uuid.UUID,
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = None,
    principal: Principal = Depends(
        require_roles("shelter_admin", "shelter_staff", "shelter_read_only")
    ),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    lookup = await valid_lookup_session(session, principal, session_id)
    person = await canonical_person(session, lookup.person_id)
    rows, next_cursor = await history_for_person(session, person, limit, cursor)
    await audit(
        session,
        principal,
        "lookup_session.history_access",
        "lookup_session",
        str(session_id),
        request_id=request.state.request_id,
    )
    await session.commit()
    return {
        "person": {"display_name": person.verified_display_name, "verification": "approved"},
        "items": [event_json(row) for row in rows],
        "next_cursor": next_cursor,
    }


async def authorize_shelter_path(
    session: AsyncSession, principal: Principal, shelter_id: uuid.UUID
) -> Shelter:
    shelter = await shelter_for_principal(session, principal)
    if shelter.id != shelter_id:
        raise HTTPException(404, "Resource not found")
    return shelter


@app.get("/api/v1/shelters/{shelter_id}/pets")
async def list_pets(
    shelter_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = None,
    principal: Principal = Depends(
        require_roles("shelter_admin", "shelter_staff", "shelter_read_only")
    ),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    await authorize_shelter_path(session, principal, shelter_id)
    query = select(Pet).where(Pet.shelter_id == shelter_id)
    if cursor:
        try:
            created, row_id = decode_cursor(cursor)
        except ValueError as exc:
            raise HTTPException(400, "Invalid cursor") from exc
        query = query.where(
            or_(Pet.created_at < created, and_(Pet.created_at == created, Pet.id < row_id))
        )
    rows = (
        await session.scalars(query.order_by(Pet.created_at.desc(), Pet.id.desc()).limit(limit + 1))
    ).all()
    next_cursor = (
        encode_cursor(rows[limit - 1].created_at, rows[limit - 1].id) if len(rows) > limit else None
    )
    return {"items": [pet_json(row) for row in rows[:limit]], "next_cursor": next_cursor}


@app.post("/api/v1/shelters/{shelter_id}/pets", status_code=201)
async def create_pet(
    shelter_id: uuid.UUID,
    payload: PetCreate,
    request: Request,
    principal: Principal = Depends(require_roles("shelter_admin", "shelter_staff")),
    session: AsyncSession = Depends(get_session),
    config: Settings = Depends(get_settings),
) -> dict[str, Any]:
    await authorize_shelter_path(session, principal, shelter_id)
    ciphertext, lookup_hash = encrypt_microchip(
        payload.microchip_identifier, config.field_encryption_key, config.lookup_hash_key
    )
    row = Pet(
        shelter_id=shelter_id,
        microchip_ciphertext=ciphertext,
        microchip_lookup_hash=lookup_hash,
        **payload.model_dump(exclude={"microchip_identifier"}),
    )
    session.add(row)
    await session.flush()
    await audit(
        session, principal, "pet.create", "pet", str(row.id), request_id=request.state.request_id
    )
    await session.commit()
    return pet_json(row)


@app.get("/api/v1/shelters/{shelter_id}/pets/{pet_id}")
async def get_pet(
    shelter_id: uuid.UUID,
    pet_id: uuid.UUID,
    principal: Principal = Depends(
        require_roles("shelter_admin", "shelter_staff", "shelter_read_only")
    ),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    await authorize_shelter_path(session, principal, shelter_id)
    row = await session.scalar(select(Pet).where(Pet.id == pet_id, Pet.shelter_id == shelter_id))
    if row is None:
        raise HTTPException(404, "Resource not found")
    return pet_json(row)


@app.patch("/api/v1/shelters/{shelter_id}/pets/{pet_id}")
async def patch_pet(
    shelter_id: uuid.UUID,
    pet_id: uuid.UUID,
    payload: PetPatch,
    request: Request,
    principal: Principal = Depends(require_roles("shelter_admin", "shelter_staff")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    await authorize_shelter_path(session, principal, shelter_id)
    row = await session.scalar(
        select(Pet).where(Pet.id == pet_id, Pet.shelter_id == shelter_id).with_for_update()
    )
    if row is None:
        raise HTTPException(404, "Resource not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    await audit(
        session, principal, "pet.update", "pet", str(row.id), request_id=request.state.request_id
    )
    await session.commit()
    return pet_json(row)


@app.post("/api/v1/custody-events", status_code=201)
async def create_custody(
    payload: CustodyCreate,
    request: Request,
    idempotency_key: str = Header(min_length=8, max_length=200),
    principal: Principal = Depends(require_roles("shelter_admin", "shelter_staff")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    shelter = await shelter_for_principal(session, principal)
    lookup = await valid_lookup_session(session, principal, payload.lookup_session_id)
    pet = await session.scalar(
        select(Pet).where(Pet.id == payload.pet_id, Pet.shelter_id == shelter.id)
    )
    if pet is None:
        raise HTTPException(404, "Resource not found")
    person = await canonical_person(session, lookup.person_id)
    row = CustodyEvent(
        **payload.model_dump(exclude={"lookup_session_id"}),
        shelter_id=shelter.id,
        person_id=person.id,
        actor_clerk_user_id=principal.user_id,
        idempotency_key=idempotency_key,
    )
    row = await insert_custody_idempotently(session, row)
    await audit(
        session,
        principal,
        "custody_event.create",
        "custody_event",
        str(row.id),
        request_id=request.state.request_id,
    )
    await session.commit()
    loaded = await session.scalar(
        select(CustodyEvent)
        .options(selectinload(CustodyEvent.pet), selectinload(CustodyEvent.shelter))
        .where(CustodyEvent.id == row.id)
    )
    assert loaded
    return event_json(loaded)


@app.post("/api/v1/custody-events/{event_id}/corrections", status_code=201)
async def correct_custody(
    event_id: uuid.UUID,
    payload: CorrectionCreate,
    request: Request,
    idempotency_key: str = Header(min_length=8, max_length=200),
    principal: Principal = Depends(require_roles("shelter_admin", "shelter_staff")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    shelter = await shelter_for_principal(session, principal)
    original = await session.scalar(
        select(CustodyEvent).where(
            CustodyEvent.id == event_id, CustodyEvent.shelter_id == shelter.id
        )
    )
    if original is None:
        raise HTTPException(404, "Resource not found")
    row = CustodyEvent(
        pet_id=original.pet_id,
        person_id=original.person_id,
        shelter_id=shelter.id,
        event_type=CustodyEventType.correction,
        effective_at=payload.effective_at,
        factual_note=payload.factual_note,
        reason_category=payload.reason_category,
        actor_clerk_user_id=principal.user_id,
        corrects_event_id=original.id,
        idempotency_key=idempotency_key,
    )
    row = await insert_custody_idempotently(session, row)
    await audit(
        session,
        principal,
        "custody_event.correct",
        "custody_event",
        str(row.id),
        request_id=request.state.request_id,
    )
    await session.commit()
    loaded = await session.scalar(
        select(CustodyEvent)
        .options(selectinload(CustodyEvent.pet), selectinload(CustodyEvent.shelter))
        .where(CustodyEvent.id == row.id)
    )
    assert loaded
    return event_json(loaded)


@app.get("/api/v1/disputes")
async def list_disputes(
    limit: int = Query(50, ge=1, le=100),
    principal: Principal = Depends(
        require_roles("shelter_admin", "shelter_staff", "shelter_read_only", "platform_admin")
    ),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    query = select(Dispute)
    if principal.role != "platform_admin":
        shelter = await shelter_for_principal(session, principal)
        query = query.where(Dispute.responsible_shelter_id == shelter.id)
    rows = (await session.scalars(query.order_by(Dispute.created_at.desc()).limit(limit))).all()
    return {
        "items": [
            {
                "id": row.id,
                "event_id": row.event_id,
                "owner_reason": row.owner_reason,
                "status": row.status,
                "resolution_summary": row.resolution_summary,
                "created_at": row.created_at,
            }
            for row in rows
        ],
        "next_cursor": None,
    }


@app.patch("/api/v1/disputes/{dispute_id}")
async def patch_dispute(
    dispute_id: uuid.UUID,
    payload: DisputePatch,
    request: Request,
    principal: Principal = Depends(
        require_roles("shelter_admin", "shelter_staff", "platform_admin")
    ),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    row = await session.get(Dispute, dispute_id, with_for_update=True)
    if row is None:
        raise HTTPException(404, "Resource not found")
    if principal.role != "platform_admin":
        shelter = await shelter_for_principal(session, principal)
        if row.responsible_shelter_id != shelter.id or payload.status == DisputeStatus.resolved:
            raise HTTPException(404, "Resource not found")
    if payload.correction_event_id:
        correction = await session.get(CustodyEvent, payload.correction_event_id)
        if (
            correction is None
            or correction.event_type != CustodyEventType.correction
            or correction.corrects_event_id != row.event_id
        ):
            raise HTTPException(422, "Correction does not resolve this dispute")
    row.status = payload.status
    row.resolution_summary = payload.resolution_summary
    row.correction_event_id = payload.correction_event_id
    row.assigned_reviewer_id = principal.user_id
    await audit(
        session,
        principal,
        "dispute.update",
        "dispute",
        str(row.id),
        request_id=request.state.request_id,
    )
    await session.commit()
    return {
        "id": row.id,
        "status": row.status,
        "resolution_summary": row.resolution_summary,
        "correction_event_id": row.correction_event_id,
    }


@app.get("/api/v1/identity/manual-reviews")
async def identity_reviews(
    limit: int = Query(50, ge=1, le=100),
    principal: Principal = Depends(
        require_roles("shelter_admin", "shelter_staff", "platform_admin")
    ),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    shelter = None
    if principal.role != "platform_admin":
        shelter = await shelter_for_principal(session, principal)
    criteria = [IdentityInquiry.state == InquiryState.needs_review]
    if shelter is not None:
        criteria.append(IdentityInquiry.reviewing_shelter_id == shelter.id)
    rows = (
        await session.scalars(
            select(IdentityInquiry)
            .where(*criteria)
            .order_by(IdentityInquiry.created_at)
            .limit(limit)
        )
    ).all()
    items: list[dict[str, Any]] = []
    for row in rows:
        candidates = (
            await session.execute(
                select(IdentityMatchCandidate, Person)
                .join(Person, Person.id == IdentityMatchCandidate.person_id)
                .where(IdentityMatchCandidate.identity_inquiry_id == row.id)
                .order_by(IdentityMatchCandidate.confidence.desc())
            )
        ).all()
        items.append(
            {
                "id": row.id,
                "state": row.state,
                "submitted_name": row.submitted_display_name,
                "classification": row.match_classification,
                "reason_category": row.reason_category,
                "created_at": row.created_at,
                "requires_second_reviewer": row.submitted_by_user_id == principal.user_id,
                "candidates": [
                    {
                        "person_id": candidate.person_id,
                        "display_name": person.verified_display_name,
                        "classification": candidate.classification,
                        "confidence": candidate.confidence,
                        "evidence": candidate.evidence_summary.split(","),
                    }
                    for candidate, person in candidates
                ],
            }
        )
    return {
        "items": items,
        "next_cursor": None,
    }


@app.post("/api/v1/identity/manual-reviews/{review_id}/resolve")
async def resolve_review(
    review_id: uuid.UUID,
    payload: ReviewResolve,
    request: Request,
    principal: Principal = Depends(
        require_roles("shelter_admin", "shelter_staff", "platform_admin")
    ),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    inquiry = await session.get(IdentityInquiry, review_id, with_for_update=True)
    if inquiry is None or inquiry.state != InquiryState.needs_review:
        raise HTTPException(404, "Review not found")
    if principal.role != "platform_admin":
        shelter = await shelter_for_principal(session, principal)
        if inquiry.reviewing_shelter_id != shelter.id:
            raise HTTPException(404, "Review not found")
        if inquiry.submitted_by_user_id == principal.user_id:
            raise HTTPException(409, "A second employee must resolve an ambiguous match")
    account = await session.get(UserAccount, inquiry.user_account_id, with_for_update=True)
    assert account
    if payload.decision == "link_existing":
        if payload.target_person_id is None:
            raise HTTPException(422, "target_person_id is required")
        candidate = await session.scalar(
            select(IdentityMatchCandidate).where(
                IdentityMatchCandidate.identity_inquiry_id == inquiry.id,
                IdentityMatchCandidate.person_id == payload.target_person_id,
            )
        )
        if candidate is None:
            raise HTTPException(422, "target_person_id must be a reconciliation candidate")
        person = await canonical_person(session, payload.target_person_id)
        account.person_id, account.status, account.link_reason, account.linked_at = (
            person.id,
            LinkStatus.active,
            "manual_review_link",
            now(),
        )
        inquiry.person_id, inquiry.state, inquiry.resolved_at = (
            person.id,
            InquiryState.approved,
            now(),
        )
    elif payload.decision == "approve_new":
        person = Person(
            status=PersonStatus.active,
            verified_display_name=inquiry.submitted_display_name,
            verified_at=now(),
        )
        session.add(person)
        await session.flush()
        account.person_id, account.status, account.link_reason, account.linked_at = (
            person.id,
            LinkStatus.active,
            "manual_review_new",
            now(),
        )
        inquiry.person_id, inquiry.state, inquiry.resolved_at = (
            person.id,
            InquiryState.approved,
            now(),
        )
    elif payload.decision == "decline":
        inquiry.state, inquiry.resolved_at = InquiryState.declined, now()
        account.status = LinkStatus.pending
    else:
        inquiry.reason_category = "more_information_requested"
    if inquiry.person_id is not None:
        await session.execute(
            update(IdentitySignal)
            .where(IdentitySignal.identity_inquiry_id == inquiry.id)
            .values(person_id=inquiry.person_id)
        )
    await audit(
        session,
        principal,
        "identity_review.resolve",
        "identity_inquiry",
        str(inquiry.id),
        request_id=request.state.request_id,
        metadata={"decision": payload.decision, "explanation": payload.explanation[:300]},
    )
    await session.commit()
    return {"id": inquiry.id, "state": inquiry.state}


@app.post("/api/v1/admin/people/{source_person_id}/merge")
async def merge(
    source_person_id: uuid.UUID,
    payload: ReviewResolve,
    request: Request,
    principal: Principal = Depends(require_roles("platform_admin")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if payload.target_person_id is None:
        raise HTTPException(422, "target_person_id is required")
    target = await merge_people(
        session, source_person_id, payload.target_person_id, principal, payload.explanation
    )
    await session.commit()
    return {"canonical_person_id": target.id}


async def persist_webhook(
    session: AsyncSession, provider: str, event_id: str, event_type: str
) -> tuple[WebhookEvent, bool]:
    existing = await session.scalar(
        select(WebhookEvent).where(
            WebhookEvent.provider == provider, WebhookEvent.provider_event_id == event_id
        )
    )
    if existing:
        return existing, True
    row = WebhookEvent(provider=provider, provider_event_id=event_id, event_type=event_type)
    session.add(row)
    await session.flush()
    return row, False


@app.post("/api/v1/webhooks/clerk", status_code=202)
async def clerk_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
    config: Settings = Depends(get_settings),
) -> dict[str, Any]:
    raw = await request.body()
    event_id = request.headers.get("svix-id", "")
    timestamp = request.headers.get("svix-timestamp")
    signature = request.headers.get("svix-signature", "")
    if timestamp is None:
        raise HTTPException(400, "Missing webhook timestamp")
    verify_clerk_webhook(
        raw,
        event_id,
        timestamp,
        signature,
        config.clerk_webhook_secret,
        config.webhook_tolerance_seconds,
    )
    payload = json.loads(raw)
    event_type = str(payload.get("type", ""))
    if not event_id or not event_type:
        raise HTTPException(422, "Invalid webhook envelope")
    event, duplicate = await persist_webhook(session, "clerk", event_id, event_type)
    if duplicate:
        return {"accepted": True, "duplicate": True}
    data = payload.get("data", {})
    if event_type == "user.deleted":
        account = await session.scalar(
            select(UserAccount).where(UserAccount.clerk_user_id == str(data.get("id")))
        )
        if account:
            account.status = LinkStatus.disabled
    elif event_type in {"organization.created", "organization.updated"}:
        org_id = str(data.get("id", ""))
        shelter = await session.scalar(
            select(Shelter).where(Shelter.clerk_organization_id == org_id)
        )
        if shelter is None:
            shelter = Shelter(clerk_organization_id=org_id, name=str(data.get("name", "Shelter")))
            session.add(shelter)
        else:
            shelter.name = str(data.get("name", shelter.name))
    elif event_type == "organization.deleted":
        shelter = await session.scalar(
            select(Shelter).where(Shelter.clerk_organization_id == str(data.get("id")))
        )
        if shelter:
            shelter.status = "disabled"
    event.state, event.processed_at = WebhookState.processed, now()
    await audit(
        session,
        None,
        "webhook.clerk.process",
        "webhook_event",
        str(event.id),
        request_id=request.state.request_id,
    )
    await session.commit()
    return {"accepted": True, "duplicate": False}


@app.get("/api/v1/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/health/ready")
async def ready(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(503, "Database unavailable") from exc
    return {"status": "ready"}
