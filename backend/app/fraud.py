import hashlib
import hmac
import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from .schemas import StripeVerificationResult


@dataclass(frozen=True)
class DerivedSignal:
    signal_type: str
    value_hash: str
    assurance: str


def _text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold().strip()
    return re.sub(r"\s+", " ", normalized)


def _phone(value: str) -> str:
    return "+" + re.sub(r"\D", "", value)


def _address(value: dict[str, Any]) -> str:
    keys = ("line1", "line2", "city", "state", "postal_code", "country")
    return "|".join(_text(str(value.get(key, ""))) for key in keys)


def identity_fingerprint(signal_type: str, parts: list[str], key: str) -> str:
    if len(key) < 32:
        raise RuntimeError("identity hash key must be at least 32 characters")
    canonical = "\0".join(["fido.identity.v1", signal_type, *(_text(part) for part in parts)])
    return hmac.new(key.encode(), canonical.encode(), hashlib.sha256).hexdigest()


def derive_identity_signals(result: StripeVerificationResult, key: str) -> list[DerivedSignal]:
    raw: list[tuple[str, list[str], str]] = []
    if result.document_number and result.document_type and result.issuing_country:
        raw.append(
            (
                "document_semantic",
                [result.issuing_country, result.document_type, result.document_number],
                "strong",
            )
        )
    if result.display_name and result.dob:
        raw.append(("name_dob", [result.display_name, result.dob], "corroborating"))
    if result.address and result.dob:
        raw.append(("address_dob", [_address(result.address), result.dob], "corroborating"))
    if result.phone:
        raw.append(("phone", [_phone(result.phone)], "weak"))
    if result.id_number_last4 and result.display_name and result.dob:
        raw.append(
            (
                "id_last4_name_dob",
                [result.id_number_last4, result.display_name, result.dob],
                "corroborating",
            )
        )
    return [
        DerivedSignal(kind, identity_fingerprint(kind, parts, key), assurance)
        for kind, parts, assurance in raw
    ]


def safe_signal_summary(signals: list[DerivedSignal]) -> str:
    return json.dumps(sorted(signal.signal_type for signal in signals), separators=(",", ":"))
