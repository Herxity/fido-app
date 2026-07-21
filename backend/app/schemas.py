import base64
import json
import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from .models import CustodyEventType, DisputeStatus, InquiryState


class Page(BaseModel):
    items: list[dict[str, Any]]
    next_cursor: str | None = None


def encode_cursor(created_at: datetime, row_id: uuid.UUID) -> str:
    raw = json.dumps([created_at.isoformat(), str(row_id)], separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(value: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        timestamp, row_id = json.loads(raw)
        return datetime.fromisoformat(timestamp), uuid.UUID(row_id)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid cursor") from exc


class PetCreate(BaseModel):
    record_number: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=150)
    species: str = Field(min_length=1, max_length=80)
    breed_description: str | None = Field(None, max_length=250)
    sex: str | None = Field(None, max_length=30)
    approximate_birth_date: date | None = None
    color: str | None = Field(None, max_length=100)
    altered: bool | None = None
    microchip_identifier: str | None = Field(None, min_length=6, max_length=40)
    lifecycle_state: str = Field("active", max_length=50)


class PetPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=150)
    breed_description: str | None = Field(None, max_length=250)
    sex: str | None = Field(None, max_length=30)
    approximate_birth_date: date | None = None
    color: str | None = Field(None, max_length=100)
    altered: bool | None = None
    lifecycle_state: str | None = Field(None, max_length=50)


class CustodyCreate(BaseModel):
    pet_id: uuid.UUID
    lookup_session_id: uuid.UUID
    event_type: CustodyEventType
    effective_at: datetime
    entered_local_date: date | None = None
    source_reference: str | None = Field(None, max_length=200)
    reason_category: str | None = Field(None, max_length=100)
    factual_note: str | None = Field(None, max_length=2000)

    @field_validator("event_type")
    @classmethod
    def no_direct_correction(cls, value: CustodyEventType) -> CustodyEventType:
        if value == CustodyEventType.correction:
            raise ValueError("use the correction endpoint")
        return value


class CorrectionCreate(BaseModel):
    effective_at: datetime
    factual_note: str = Field(min_length=1, max_length=2000)
    reason_category: str | None = Field(None, max_length=100)


class LookupRedeem(BaseModel):
    token: str = Field(min_length=32, max_length=200)


class DisputeCreate(BaseModel):
    event_id: uuid.UUID
    reason: str = Field(min_length=10, max_length=3000)


class DisputePatch(BaseModel):
    status: DisputeStatus
    resolution_summary: str | None = Field(None, max_length=3000)
    correction_event_id: uuid.UUID | None = None


class ReviewResolve(BaseModel):
    decision: Literal["link_existing", "approve_new", "decline", "request_more_information"]
    target_person_id: uuid.UUID | None = None
    explanation: str = Field(min_length=3, max_length=1000)


class IdentityStatus(BaseModel):
    status: Literal["unverified", "pending", "approved", "declined", "needs_review"]
    inquiry_id: uuid.UUID | None = None


class WebhookEnvelope(BaseModel):
    id: str
    type: str
    data: dict[str, Any]


class StripeVerificationResult(BaseModel):
    session_id: str
    state: InquiryState
    reference_id: str | None = None
    display_name: str | None = Field(None, max_length=200)
    report_id: str | None = None
    document_number: str | None = None
    document_type: str | None = None
    issuing_country: str | None = None
    dob: str | None = None
    address: dict[str, Any] | None = None
    phone: str | None = None
    id_number_last4: str | None = None
    reason_category: str | None = None
