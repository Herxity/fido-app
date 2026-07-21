# Shelter Identity Verification and Reconciliation Plan

## Outcome and trust boundary

Authorized shelter employees verify owners in person without a paid identity provider. An owner creates a random, 24-hour verification code. A shelter employee enters that code, examines the physical ID and the person, and either scans the PDF417 barcode on a U.S./Canadian driver license or state ID or enters the fields manually. Passport verification remains manual.

The barcode reduces transcription errors; it does not prove authenticity. Employees must compare parsed fields with the printed card, inspect available physical security features, compare the portrait with the person present, and record consent. Fido does not upload or retain the barcode image or raw barcode payload.

## Architecture

1. An authenticated owner requests a verification code. Only an HMAC of the code is stored.
2. An authenticated `shelter_staff` or `shelter_admin` opens the Identity Desk.
3. A USB/Bluetooth scanner can type the PDF417 payload into the scanner field. Camera capture uses ZXing in the browser. `parse-usdl` parses the AAMVA payload locally.
4. Staff inspect and correct every populated field before submission.
5. FastAPI validates role, active shelter, request code, age, document expiration, field bounds, and three explicit attestations.
6. The request is locked and reconciled transactionally. Raw DOB, address, phone, last four, and document number exist only during processing.
7. Fido stores keyed exact hashes and keyed fuzzy blind-index tokens. It stores the verified display name, decision, shelter, employee, candidate categories, and audit record.
8. Clear new identities and high-confidence existing identities resolve automatically. Fuzzy or conflicting evidence opens a second-employee review.

The implementation follows the AAMVA DL/ID Card Design Standard's machine-readable PDF417 model and privacy emphasis. See [AAMVA DL/ID standards](https://www.aamva.org/topics/driver-license-and-identification-standards).

## Reconciliation signals

All digests use a dedicated pepper and domain-separated `HMAC-SHA-256`. The pepper is never stored in the database or browser.

| Signal | Input | Role |
|---|---|---|
| `document_semantic` | country + issuer + type + document number | Strong exact identifier |
| `name_dob` | normalized full name + DOB | Corroborating exact composite |
| `address_dob` | normalized full address + DOB | Corroborating; shared households remain possible |
| `id_last4_name_dob` | last four + name + DOB | Corroborating only; never use last four alone |
| `phone` | normalized digits | Weak context only |
| `dob` | DOB | Candidate generation only |
| `name_ngram` | keyed normalized name trigrams | Fuzzy candidate coverage |
| `address_ngram` | keyed normalized address trigrams | Fuzzy supporting coverage |

Unicode NFKC normalization, case folding, punctuation removal, whitespace collapse, and deterministic field ordering prevent easy formatting bypasses. Fuzzy matching operates on HMAC blind-index overlap, not plaintext or reversible search indexes.

## Decision matrix

### `new_identity` — automatic

No meaningful candidate matches. Create a new canonical person, attach signals, activate the owner account, and record the shelter/employee attestation.

### `exact_existing` — automatic

Exactly one canonical person has the same semantic document plus either exact name/DOB or sufficiently similar name with the same DOB, and no other candidate conflicts. Link the account to that person and retain all prior history.

### `fuzzy` — second review

Examples include exact name/DOB with a different document, a near-name match with the same DOB, the same document with a meaningful demographic difference, or an address/DOB composite with supporting name similarity. Store only evidence categories and confidence. A different employee must compare the physical evidence and choose a listed person, confirm a separate person, decline, or request more information.

### `conflict` — second review / escalation

Strong evidence points to one person while corroborating evidence points to another, or multiple strong candidates exist. Never auto-link. Platform escalation is appropriate if the shelter cannot resolve the conflict.

## Safety and privacy controls

- The barcode is an input convenience, not an authenticity service.
- Camera decoding occurs locally and camera tracks stop after capture, cancellation, or unmount.
- Raw barcode strings and images are never sent to the API, logs, analytics, local storage, or database.
- No ID image upload exists.
- Verification codes are random, rate-limited, valid for 24 hours, single-use, and stored only as HMACs.
- Entry and review require active Clerk organization membership. Reviews are shelter-scoped.
- The submitting employee cannot resolve their own ambiguous match.
- A reviewer can link only to a reconciliation-generated candidate.
- Exact/fuzzy outcomes are identity evidence, not fraud labels or adoption scores.
- Full SSNs are never requested. Optional last four is accepted only when independently provided and is immediately incorporated into a composite HMAC.
- Audit metadata contains classifications and counts, never entered identity values.

## Test and red-team matrix

### Expected matching

- New valid person with no candidates creates a new canonical person.
- Same document and same normalized name/DOB links the existing person.
- Case, punctuation, whitespace, and Unicode compatibility characters cannot bypass exact matching.
- Alternate document with exact name/DOB opens fuzzy review.
- Small name typo with exact DOB opens fuzzy review.
- Document candidate A plus demographic candidate B produces conflict and never auto-links.
- Shared address or recycled phone without DOB/name corroboration does not merge people.
- Last-four collision alone does not create a candidate.

### Authorization and workflow attacks

- Owner, read-only shelter user, wrong shelter, and inactive organization cannot submit verification.
- Invalid, expired, replayed, superseded, and brute-forced verification codes fail generically.
- Missing physical-document, likeness, or consent attestation fails closed.
- The submitting employee cannot resolve an ambiguous review.
- A reviewer cannot inject an arbitrary target person outside generated candidates.
- Concurrent submissions for one code serialize; only one can resolve.

### Input and privacy attacks

- Expired document, future DOB, minor owner, invalid country, invalid last four, oversized fields, and oversized barcode payload are rejected.
- Control characters, homoglyphs, punctuation, mixed case, whitespace, and SQL/HTML-like input are normalized or safely handled as data.
- Malformed or non-AAMVA barcodes fail without partial submission.
- Camera denial and unavailable camera fall back to hardware scanner/manual entry.
- Logs, API responses, database rows, frontend caches, and audit metadata contain no raw document number, DOB, address, phone, last four, barcode, or image.

## Remaining operational gates

Before production use, counsel must approve consent/retention language and the handling of minors and biometric-like manual comparisons. Shelter staff need document-inspection training, escalation guidance, and periodic access review. The pilot should measure false-positive rates by match category before changing thresholds. Threshold changes require versioning, regression tests, and a documented review because they affect identity linkage.
