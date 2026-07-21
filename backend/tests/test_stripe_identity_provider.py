import uuid
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.models import InquiryState
from app.providers import LiveStripeIdentityClient, stripe_result


@pytest.mark.asyncio
async def test_live_stripe_identity_request_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[object, object]] = []

    class Sessions:
        async def create_async(self, params, options):  # type: ignore[no-untyped-def]
            calls.append((params, options))
            return SimpleNamespace(
                id="vs_1",
                client_secret="vs_1_secret_test",  # noqa: S106
                status="requires_input",
            )

    class Client:
        def __init__(self, _key: str, **_kwargs: object) -> None:
            self.v1 = SimpleNamespace(identity=SimpleNamespace(verification_sessions=Sessions()))

    monkeypatch.setattr("app.providers.stripe.StripeClient", Client)
    settings = Settings(
        environment="development",
        provider_mode="live",
        stripe_secret_key="sk_test_safe",  # noqa: S106
        stripe_require_id_number=True,
    )
    provider = LiveStripeIdentityClient(settings)
    reference_id = uuid.uuid4()

    created = await provider.create_session(reference_id)

    assert created == {
        "id": "vs_1",
        "client_secret": "vs_1_secret_test",
        "status": "requires_input",
    }
    params, options = calls[0]
    assert params == {
        "client_reference_id": str(reference_id),
        "metadata": {"fido_reference_id": str(reference_id)},
        "type": "document",
        "options": {
            "document": {
                "allowed_types": ["driving_license", "id_card", "passport"],
                "require_live_capture": True,
                "require_matching_selfie": True,
                "require_id_number": True,
            }
        },
    }
    assert options == {"idempotency_key": f"fido-identity-{reference_id}"}


def test_stripe_result_extracts_sensitive_values_without_retaining_images() -> None:
    result = stripe_result(
        {
            "id": "vs_1",
            "status": "verified",
            "client_reference_id": "reference_1",
            "verified_outputs": {
                "first_name": "Maya",
                "last_name": "Carter",
                "dob": {"year": 1980, "month": 1, "day": 2},
                "id_number": "123456789",
                "address": {"line1": "1 Main", "country": "US"},
            },
            "last_verification_report": {
                "id": "vr_1",
                "document": {
                    "number": "D123",
                    "type": "driving_license",
                    "issuing_country": "US",
                    "files": ["file_sensitive"],
                },
            },
        }
    )

    assert result.state == InquiryState.approved
    assert result.display_name == "Maya Carter"
    assert result.dob == "1980-01-02"
    assert result.id_number_last4 == "6789"
    assert "file_sensitive" not in result.model_dump_json()


def test_requires_input_remains_retryable() -> None:
    result = stripe_result(
        {
            "id": "vs_retry",
            "status": "requires_input",
            "last_error": {"code": "document_unverified_other"},
        }
    )

    assert result.state == InquiryState.pending
    assert result.reason_category == "document_unverified_other"
