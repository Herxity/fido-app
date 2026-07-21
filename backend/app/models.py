import enum
import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class PersonStatus(str, enum.Enum):
    active = "active"
    review = "review"
    merged = "merged"
    restricted = "restricted"
    deleted = "deleted"


class LinkStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    recovery = "recovery"
    disabled = "disabled"


class InquiryState(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    declined = "declined"
    needs_review = "needs_review"
    superseded = "superseded"


class CustodyEventType(str, enum.Enum):
    adoption = "adoption"
    return_from_adoption = "return_from_adoption"
    owner_surrender = "owner_surrender"
    reclaim_by_owner = "reclaim_by_owner"
    transfer_in = "transfer_in"
    transfer_out = "transfer_out"
    foster_start = "foster_start"
    foster_end = "foster_end"
    correction = "correction"


class DisputeStatus(str, enum.Enum):
    open = "open"
    shelter_review = "shelter_review"
    platform_review = "platform_review"
    resolved = "resolved"
    rejected = "rejected"


class WebhookState(str, enum.Enum):
    received = "received"
    processed = "processed"
    retry = "retry"
    failed = "failed"


class Person(Base):
    __tablename__ = "people"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    status: Mapped[PersonStatus] = mapped_column(Enum(PersonStatus), default=PersonStatus.review)
    verified_display_name: Mapped[str | None] = mapped_column(String(200))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    merged_into_person_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("people.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    merged_into: Mapped["Person | None"] = relationship(remote_side="Person.id")

    __table_args__ = (
        CheckConstraint(
            "(status = 'merged' AND merged_into_person_id IS NOT NULL) OR "
            "(status <> 'merged' AND merged_into_person_id IS NULL)",
            name="ck_people_merge_target",
        ),
        CheckConstraint(
            "merged_into_person_id IS NULL OR merged_into_person_id <> id", name="ck_no_self_merge"
        ),
    )


class UserAccount(Base):
    __tablename__ = "user_accounts"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    clerk_user_id: Mapped[str] = mapped_column(String(200), unique=True)
    person_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("people.id", ondelete="RESTRICT")
    )
    status: Mapped[LinkStatus] = mapped_column(Enum(LinkStatus), default=LinkStatus.pending)
    link_reason: Mapped[str | None] = mapped_column(String(100))
    linked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Shelter(Base):
    __tablename__ = "shelters"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    clerk_organization_id: Mapped[str] = mapped_column(String(200), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30), default="active")
    contact: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Pet(Base):
    __tablename__ = "pets"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    shelter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shelters.id", ondelete="RESTRICT"))
    record_number: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(150))
    species: Mapped[str] = mapped_column(String(80))
    breed_description: Mapped[str | None] = mapped_column(String(250))
    sex: Mapped[str | None] = mapped_column(String(30))
    approximate_birth_date: Mapped[date | None] = mapped_column(Date)
    color: Mapped[str | None] = mapped_column(String(100))
    altered: Mapped[bool | None] = mapped_column(Boolean)
    microchip_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary)
    microchip_lookup_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    lifecycle_state: Mapped[str] = mapped_column(String(50), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    shelter: Mapped[Shelter] = relationship()
    __table_args__ = (
        UniqueConstraint("shelter_id", "record_number", name="uq_pet_shelter_record"),
    )


class CustodyEvent(Base):
    __tablename__ = "custody_events"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    pet_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pets.id", ondelete="RESTRICT"))
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("people.id", ondelete="RESTRICT"), index=True
    )
    shelter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shelters.id", ondelete="RESTRICT"))
    event_type: Mapped[CustodyEventType] = mapped_column(Enum(CustodyEventType))
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    entered_local_date: Mapped[date | None] = mapped_column(Date)
    source_reference: Mapped[str | None] = mapped_column(String(200))
    reason_category: Mapped[str | None] = mapped_column(String(100))
    factual_note: Mapped[str | None] = mapped_column(Text)
    actor_clerk_user_id: Mapped[str] = mapped_column(String(200))
    corrects_event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("custody_events.id", ondelete="RESTRICT")
    )
    idempotency_key: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    pet: Mapped[Pet] = relationship()
    shelter: Mapped[Shelter] = relationship()
    __table_args__ = (
        UniqueConstraint("shelter_id", "idempotency_key", name="uq_custody_idempotency"),
        CheckConstraint(
            "(event_type = 'correction' AND corrects_event_id IS NOT NULL) OR "
            "(event_type <> 'correction' AND corrects_event_id IS NULL)",
            name="ck_correction_reference",
        ),
    )


class IdentityInquiry(Base):
    __tablename__ = "identity_inquiries"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="RESTRICT")
    )
    person_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("people.id", ondelete="RESTRICT")
    )
    reference_id: Mapped[uuid.UUID] = mapped_column(Uuid, unique=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(30), default="stripe")
    provider_session_id: Mapped[str] = mapped_column(String(200), unique=True)
    provider_report_id: Mapped[str | None] = mapped_column(String(200))
    state: Mapped[InquiryState] = mapped_column(Enum(InquiryState), default=InquiryState.pending)
    repeat_outcome: Mapped[str | None] = mapped_column(String(80))
    reason_category: Mapped[str | None] = mapped_column(String(100))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class IdentitySignal(Base):
    __tablename__ = "identity_signals"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    identity_inquiry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("identity_inquiries.id", ondelete="RESTRICT"), index=True
    )
    person_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("people.id", ondelete="RESTRICT"), index=True
    )
    signal_type: Mapped[str] = mapped_column(String(50))
    value_hash: Mapped[str] = mapped_column(String(64))
    assurance: Mapped[str] = mapped_column(String(20))
    key_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    __table_args__ = (
        Index("ix_identity_signal_match", "signal_type", "value_hash"),
        UniqueConstraint(
            "identity_inquiry_id", "signal_type", name="uq_identity_signal_inquiry_type"
        ),
    )


class LookupToken(Base):
    __tablename__ = "lookup_tokens"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.id", ondelete="RESTRICT"))
    created_by_user_id: Mapped[str] = mapped_column(String(200))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    redeeming_shelter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("shelters.id"))
    redeeming_user_id: Mapped[str | None] = mapped_column(String(200))
    session_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, unique=True)
    session_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Dispute(Base):
    __tablename__ = "disputes"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.id", ondelete="RESTRICT"))
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("custody_events.id", ondelete="RESTRICT")
    )
    responsible_shelter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shelters.id", ondelete="RESTRICT")
    )
    owner_reason: Mapped[str] = mapped_column(Text)
    status: Mapped[DisputeStatus] = mapped_column(Enum(DisputeStatus), default=DisputeStatus.open)
    assigned_reviewer_id: Mapped[str | None] = mapped_column(String(200))
    resolution_summary: Mapped[str | None] = mapped_column(Text)
    correction_event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("custody_events.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    __table_args__ = (UniqueConstraint("person_id", "event_id", name="uq_dispute_person_event"),)


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(30))
    provider_event_id: Mapped[str] = mapped_column(String(200))
    event_type: Mapped[str] = mapped_column(String(150))
    state: Mapped[WebhookState] = mapped_column(Enum(WebhookState), default=WebhookState.received)
    attempt_count: Mapped[int] = mapped_column(Integer, default=1)
    sanitized_failure: Mapped[str | None] = mapped_column(String(300))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("provider", "provider_event_id", name="uq_webhook_provider_event"),
    )


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    actor_user_id: Mapped[str | None] = mapped_column(String(200))
    organization_id: Mapped[str | None] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(100), index=True)
    resource_type: Mapped[str | None] = mapped_column(String(80))
    resource_id: Mapped[str | None] = mapped_column(String(200))
    outcome: Mapped[str] = mapped_column(String(30))
    request_id: Mapped[str | None] = mapped_column(String(100))
    security_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


Index("ix_lookup_session_binding", LookupToken.session_id, LookupToken.redeeming_shelter_id)
