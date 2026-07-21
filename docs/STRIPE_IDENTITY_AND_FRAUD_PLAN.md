# Stripe Identity and Fraud Verification Plan

## Outcome

Stripe Identity performs document capture, authenticity checks, live capture, selfie comparison, and optional ID-number checks. Fido binds each Stripe VerificationSession to one authenticated Clerk owner, accepts verification state only from a signed Stripe webhook, retrieves sensitive results only on the server, converts the minimum necessary values into versioned HMAC-SHA-256 signals, and discards the raw values.

Stripe verification is evidence, not a final suitability decision. Fido never assigns an owner quality score. Identity conflicts open a review; they do not automatically label a person fraudulent or unsuitable to adopt.

## Implemented architecture

1. The authenticated owner requests `POST /api/v1/identity/inquiries`.
2. FastAPI creates or resumes one Stripe VerificationSession. The server fixes the verification options and supplies a non-PII internal reference.
3. The API returns only the single-use `client_secret`; it is never stored, logged, embedded in a URL, or returned to another owner.
4. React loads Stripe.js from Stripe and calls `stripe.verifyIdentity(clientSecret)`.
5. Browser completion only means the collection flow was submitted. It never activates the owner.
6. Stripe sends a signed lifecycle event to `POST /api/v1/webhooks/stripe`.
7. Fido verifies the raw body with the official Stripe SDK, stores the event ID for replay protection, retrieves the latest session/report server-side, and checks the immutable `client_reference_id` binding.
8. Fido derives HMAC signals in memory, discards raw PII, evaluates prior matches, and either activates a new canonical person or opens manual review.

The implementation uses Stripe's documented VerificationSession lifecycle and webhook events. See [VerificationSessions](https://docs.stripe.com/identity/verification-sessions), [document verification](https://docs.stripe.com/identity/verify-identity-documents), and [webhook security](https://docs.stripe.com/webhooks).

## Stripe client contract

The internal `LiveStripeIdentityClient`:

- uses the official pinned `stripe-python` SDK;
- retries transient network failures twice;
- creates document sessions with passport, ID card, and driver's-license support;
- requires live document capture and a matching selfie;
- optionally requires an ID-number check for an approved US-specific flow;
- uses a stable server-side idempotency key;
- resumes an incomplete session without persisting its client secret;
- retrieves `verified_outputs` and the last VerificationReport with a restricted key;
- exposes a redaction operation for deletion workflows; and
- has a fake provider used only in explicit development/test modes.

Stripe states that client secrets are single-use, expire after 24 hours, and must not be stored or logged. Only the client secret is exposed to the browser. [Stripe document-verification guide](https://docs.stripe.com/identity/verify-identity-documents)

## Signal derivation

Every digest is:

`HMAC-SHA-256(identity_pepper, "fido.identity.v1" || signal_type || canonical_parts)`

The pepper is a dedicated secret, separate from database, QR, encryption, Clerk, and Stripe keys. Each stored signal carries a key version for dual-read/dual-write rotation. Raw values are held only long enough to canonicalize and compute the digest.

| Signal | Canonical input | Assurance | Use |
|---|---|---:|---|
| `document_semantic` | issuing country + document type + normalized document number | Strong | Same semantic document across accounts always opens review |
| `name_dob` | normalized verified name + full verified DOB | Corroborating | Match opens review; never auto-links or rejects alone |
| `address_dob` | normalized verified address + full DOB | Corroborating | Supports review; shared households are expected |
| `id_last4_name_dob` | ID last four + verified name + full DOB | Corroborating | Supports review; last four is never stored or used alone |
| `phone` | normalized E.164-like digits | Weak | Context only; numbers are recycled and shared |

Document-image byte hashing is deliberately excluded: cropping, encoding, and recompression make it unstable. Stripe's document tuple and Stripe's own document/selfie systems are the appropriate evidence. Stripe documents verified name, DOB, address, phone, ID-number and report fields in [Access verification results](https://docs.stripe.com/identity/access-verification-results).

## Decision policy

### Automatic activation

All of the following must be true:

- signed event type is `identity.verification_session.verified`;
- server retrieval confirms the stored session and internal reference;
- Stripe reports a stable document number, document type, and issuing country;
- no strong or corroborating HMAC signal matches an existing canonical person; and
- no Stripe error or internal consistency failure is present.

Fido then creates or updates one canonical person and attaches the derived signals to it.

### Manual review

Any of the following opens review and keeps history inaccessible:

- the same semantic document appears on another account;
- the same verified name and DOB appears on another canonical person, even with a different document such as a passport instead of a driver's license;
- another corroborating composite matches an existing person;
- stable document fields are unavailable because restricted-result access is missing or the document did not expose them;
- the session reference does not bind to the stored inquiry;
- provider results conflict, are incomplete, or arrive out of order; or
- an operator requests additional evidence.

A reviewer can link to the existing canonical person, approve a new person, decline the attempt, or request more information. Every decision requires an explanation and produces an audit event. A match is evidence of possible duplication, not proof of fraud.

### Provider failure

`requires_input` remains pending so the owner can resume the same bounded session. `canceled` closes the attempt and requires a new session. The UI should show a safe machine-mapped reason without exposing provider internals. Rate limits and one pending session per account limit cost abuse.

## Stripe capabilities and boundaries

Stripe documents five check families: document, selfie, ID number, phone, and address. Phone and address are invite-only in relevant markets, and standalone ID-number coverage is limited. Document checks include authenticity, barcode/MRZ consistency, fraudulent-template detection, and presentation-attack defenses; selfie checks cover face match and manipulation. [Verification checks](https://docs.stripe.com/identity/verification-checks)

Stripe also documents duplicate-selfie and network-risk Insights and Dashboard blocklists. Those detailed Insights are not documented as a stable VerificationSession or VerificationReport API contract. Fido must not depend on receiving a proprietary duplicate score. Stripe's verified/unverified state, reports, built-in blocking, and manual Dashboard review complement—not replace—Fido's canonical-person and HMAC matching.

## Security and privacy controls

- Store Stripe secret, restricted, and webhook keys only in encrypted runtime secret storage; never in Git, frontend variables, images, or logs.
- Use an IP-restricted restricted key for sensitive verification output access. A publishable key is the only Stripe key allowed in the browser.
- Never put names, DOB, addresses, phone numbers, document numbers, SSN fragments, or images in Stripe metadata.
- Verify raw webhook bytes with `Stripe-Signature`, a five-minute tolerance, unique event IDs, and monotonic state transitions.
- Do not return verified outputs, reports, hashes, or duplicate-match detail to the owner or shelter frontend.
- Redact Stripe sessions for applicable deletion/retention events and remove Fido-derived signals according to the approved legal schedule. Stripe redaction removes related reports, events, logs, and files and can take up to four days. [Stripe redaction](https://docs.stripe.com/api/identity/verification_sessions/redact)
- Treat biometric consent, retention, adverse-action language, accessibility, manual alternatives, and minor handling as legal launch gates.

## Rollout and verification

1. Complete Stripe Identity business activation and use-case approval.
2. Create a restricted API key limited to Identity read access and restrict it to the Lightsail egress IP.
3. Create the webhook destination for verified, requires-input, processing, canceled, and explicitly redacted events.
4. Store test keys and a new random identity HMAC pepper in the staging secret store.
5. Run Stripe test-mode verified and failed flows; Stripe test mode simulates outcomes but does not perform real checks.
6. Verify duplicate event delivery, out-of-order events, expired client secrets, retry caps, reference mismatch, provider outage, and redaction.
7. Verify same document, alternate document with same name/DOB, shared address, recycled phone, and last-four collision scenarios.
8. Conduct privacy/legal review and reviewer training before live keys.
9. Enable live mode only after webhook, retention, incident-response, and manual-review evidence is signed off.

## Future improvements

- Persist a structured match-evidence table so reviewers see signal categories and provenance without seeing hashes or raw PII.
- Add key rotation with active and previous HMAC versions.
- Compare Clerk-verified phone/email with Stripe verified outputs server-side, recording only match/mismatch/absent outcomes.
- Add a bounded fuzzy-name candidate generator only after measuring false positives; fuzzy matches must never auto-link.
- Add a background queue so webhooks can acknowledge quickly while result retrieval and decisioning happen asynchronously.
- Add automated Stripe redaction after the legally approved retention interval.
