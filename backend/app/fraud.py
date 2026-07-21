import hashlib
import hmac
import re
import unicodedata
from dataclasses import dataclass

from .schemas import ManualIdentityEvidence


@dataclass(frozen=True)
class DerivedSignal:
    signal_type: str
    value_hash: str
    assurance: str


def normalized_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def _compact(value: str) -> str:
    return re.sub(r"[^\w]", "", normalized_text(value), flags=re.UNICODE)


def _phone(value: str) -> str:
    return re.sub(r"\D", "", value)


def _address(evidence: ManualIdentityEvidence) -> str:
    return "|".join(
        normalized_text(value or "")
        for value in (
            evidence.address_line1,
            evidence.address_line2,
            evidence.city,
            evidence.region,
            evidence.postal_code,
            evidence.country,
        )
    )


def _ngrams(value: str, size: int = 3) -> set[str]:
    compact = _compact(value)
    padded = f"^{compact}$"
    return {padded[index : index + size] for index in range(max(len(padded) - size + 1, 0))}


def identity_fingerprint(signal_type: str, parts: list[str], key: str) -> str:
    if len(key) < 32:
        raise RuntimeError("identity hash key must be at least 32 characters")
    canonical = "\0".join(
        ["fido.identity.v2", signal_type, *(normalized_text(part) for part in parts)]
    )
    return hmac.new(key.encode(), canonical.encode(), hashlib.sha256).hexdigest()


def verification_code_hash(code: str, key: str) -> str:
    if len(key) < 32:
        raise RuntimeError("identity hash key must be at least 32 characters")
    return hmac.new(
        key.encode(), f"fido.verification-code.v1\0{code}".encode(), hashlib.sha256
    ).hexdigest()


def derive_identity_signals(evidence: ManualIdentityEvidence, key: str) -> list[DerivedSignal]:
    dob = evidence.date_of_birth.isoformat()
    address = _address(evidence)
    raw: list[tuple[str, list[str], str]] = [
        (
            "document_semantic",
            [
                evidence.country,
                evidence.issuing_jurisdiction,
                evidence.document_type,
                evidence.document_number,
            ],
            "strong",
        ),
        ("name_dob", [evidence.full_name, dob], "corroborating"),
        ("address_dob", [address, dob], "corroborating"),
        ("dob", [dob], "weak"),
    ]
    if evidence.phone:
        raw.append(("phone", [_phone(evidence.phone)], "weak"))
    if evidence.government_id_last4:
        raw.append(
            (
                "id_last4_name_dob",
                [evidence.government_id_last4, evidence.full_name, dob],
                "corroborating",
            )
        )
    raw.extend(("name_ngram", [token], "fuzzy") for token in sorted(_ngrams(evidence.full_name)))
    raw.extend(("address_ngram", [token], "fuzzy") for token in sorted(_ngrams(address)))
    unique = {
        (kind, identity_fingerprint(kind, parts, key)): assurance for kind, parts, assurance in raw
    }
    return [DerivedSignal(kind, digest, assurance) for (kind, digest), assurance in unique.items()]
