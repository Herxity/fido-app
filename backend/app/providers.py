import uuid
from typing import Any, Protocol, cast

import stripe
from stripe.params.identity import VerificationSessionCreateParams

from .config import Settings
from .models import InquiryState
from .schemas import StripeVerificationResult


class IdentityProvider(Protocol):
    async def create_session(self, reference_id: uuid.UUID) -> dict[str, Any]: ...

    async def resume_session(self, session_id: str) -> dict[str, Any]: ...

    async def retrieve_result(self, session_id: str) -> StripeVerificationResult: ...

    async def redact_session(self, session_id: str) -> None: ...


def _nested(value: Any, *keys: str) -> Any:
    for key in keys:
        if value is None:
            return None
        value = value.get(key) if isinstance(value, dict) else getattr(value, key, None)
    return value


def _date_string(value: Any) -> str | None:
    if not value:
        return None
    year, month, day = (_nested(value, part) for part in ("year", "month", "day"))
    if not all(isinstance(part, int) for part in (year, month, day)):
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def stripe_result(session: Any) -> StripeVerificationResult:
    status_map = {
        "verified": InquiryState.approved,
        "requires_input": InquiryState.pending,
        "canceled": InquiryState.declined,
        "processing": InquiryState.pending,
    }
    outputs = _nested(session, "verified_outputs") or {}
    report = _nested(session, "last_verification_report") or {}
    first_name = _nested(outputs, "first_name")
    last_name = _nested(outputs, "last_name")
    display_name = " ".join(str(part).strip() for part in (first_name, last_name) if part) or None
    document = _nested(report, "document") or {}
    id_number = _nested(outputs, "id_number")
    id_last4 = str(id_number)[-4:] if id_number and str(id_number) != "[redacted]" else None
    error_code = _nested(session, "last_error", "code") or _nested(document, "error", "code")
    return StripeVerificationResult(
        session_id=str(_nested(session, "id") or ""),
        state=status_map.get(str(_nested(session, "status")), InquiryState.needs_review),
        reference_id=str(_nested(session, "client_reference_id") or "") or None,
        display_name=display_name,
        report_id=str(_nested(report, "id") or "") or None,
        document_number=str(_nested(document, "number") or "") or None,
        document_type=str(_nested(document, "type") or "") or None,
        issuing_country=str(_nested(document, "issuing_country") or "") or None,
        dob=_date_string(_nested(outputs, "dob")),
        address=dict(_nested(outputs, "address") or {}) or None,
        phone=str(_nested(outputs, "phone") or "") or None,
        id_number_last4=id_last4,
        reason_category=str(error_code) if error_code else None,
    )


class LiveStripeIdentityClient:
    def __init__(self, settings: Settings) -> None:
        if not settings.stripe_secret_key:
            raise RuntimeError("Stripe Identity secret key is not configured")
        self.settings = settings
        self.client = stripe.StripeClient(settings.stripe_secret_key, max_network_retries=2)
        result_key = settings.stripe_identity_restricted_key or settings.stripe_secret_key
        self.results_client = stripe.StripeClient(result_key, max_network_retries=2)

    async def create_session(self, reference_id: uuid.UUID) -> dict[str, Any]:
        params: dict[str, Any] = {
            "client_reference_id": str(reference_id),
            "metadata": {"fido_reference_id": str(reference_id)},
        }
        if self.settings.stripe_verification_flow_id:
            params["verification_flow"] = self.settings.stripe_verification_flow_id
        else:
            params.update(
                {
                    "type": "document",
                    "options": {
                        "document": {
                            "allowed_types": ["driving_license", "id_card", "passport"],
                            "require_live_capture": True,
                            "require_matching_selfie": True,
                            "require_id_number": self.settings.stripe_require_id_number,
                        }
                    },
                }
            )
        created = await self.client.v1.identity.verification_sessions.create_async(
            cast(VerificationSessionCreateParams, params),
            {"idempotency_key": f"fido-identity-{reference_id}"},
        )
        return {
            "id": created.id,
            "client_secret": created.client_secret,
            "status": created.status,
        }

    async def resume_session(self, session_id: str) -> dict[str, Any]:
        current = await self.client.v1.identity.verification_sessions.retrieve_async(session_id)
        return {
            "id": current.id,
            "client_secret": current.client_secret,
            "status": current.status,
        }

    async def retrieve_result(self, session_id: str) -> StripeVerificationResult:
        current = await self.results_client.v1.identity.verification_sessions.retrieve_async(
            session_id,
            {
                "expand": [
                    "verified_outputs",
                    "verified_outputs.dob",
                    "verified_outputs.id_number",
                    "last_verification_report",
                    "last_verification_report.document.number",
                    "last_verification_report.document.expiration_date",
                ]
            },
        )
        return stripe_result(current)

    async def redact_session(self, session_id: str) -> None:
        await self.client.v1.identity.verification_sessions.redact_async(session_id)


class FakeStripeIdentityClient:
    async def create_session(self, reference_id: uuid.UUID) -> dict[str, Any]:
        return {
            "id": f"vs_test_{reference_id.hex}",
            "client_secret": f"vs_test_{reference_id.hex}_secret_test",
            "status": "requires_input",
        }

    async def resume_session(self, session_id: str) -> dict[str, Any]:
        return {
            "id": session_id,
            "client_secret": f"{session_id}_secret_test",
            "status": "requires_input",
        }

    async def retrieve_result(self, session_id: str) -> StripeVerificationResult:
        return StripeVerificationResult(
            session_id=session_id,
            state=InquiryState.approved,
            display_name="Test Owner",
            document_number=session_id,
            document_type="driving_license",
            issuing_country="US",
            dob="1980-01-01",
        )

    async def redact_session(self, session_id: str) -> None:
        return None


def identity_provider(settings: Settings) -> IdentityProvider:
    if settings.provider_mode in {"development", "test"}:
        return FakeStripeIdentityClient()
    return LiveStripeIdentityClient(settings)
