# ADR 0002: Canonical identity and factual history

Status: accepted.

Custody history belongs to a canonical Fido person, not a Clerk login or one Persona document. Clerk authenticates sessions and organizations. Persona verifies identity, detects repeats, and supplies review signals. Only strong provider evidence plus an approved workflow may link automatically; ambiguous matches require human review. New credentials or identity documents do not erase history.

Fido stores provider identifiers, state, minimum display name, timestamps, and decision provenance. It does not store government-ID images or numbers, selfie images, biometric templates, raw reports, DOB, or address in the MVP. Fido records facts and disputes but never produces an owner score or adoption recommendation.
