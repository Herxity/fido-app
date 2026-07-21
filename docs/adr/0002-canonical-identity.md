# ADR 0002: Canonical identity and factual history

Status: accepted.

Custody history belongs to a canonical Fido person, not a Clerk login or one identity document. Clerk authenticates sessions and organizations. Stripe Identity verifies documents and selfies; Fido derives versioned HMAC signals from server-retrieved verified outputs and supplies review evidence. Only a signed Stripe result with stable document evidence and no prior match may create a new canonical identity automatically. Alternate documents or ambiguous matches require human review. New credentials or identity documents do not erase history.

Fido stores provider identifiers, state, minimum display name, timestamps, and decision provenance. It does not store government-ID images or numbers, selfie images, biometric templates, raw reports, DOB, or address in the MVP. Fido records facts and disputes but never produces an owner score or adoption recommendation.
