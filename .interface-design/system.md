# Fido Interface System

## Direction

Fido is a calm, warm, factual workspace for shelter staff at intake desks and owners checking records on phones. It borrows language and structure from custody chains, kennel cards, intake ledgers, microchip records, signed handoffs, source-shelter stamps, and corrections. It must never visually imply that an owner has a score.

The signature pattern is the **care journey**: a vertical, cross-shelter custody timeline with a physical source stamp on every event and visible correction/dispute relationships. It appears in owner history, authorized shelter lookup, pet context, correction review, and access/audit views.

Rejected defaults:

- Generic dashboard metrics are replaced by an active-record queue organized around incomplete handoffs.
- Generic pet-card grids are replaced by a registry/detail split that preserves list context while opening a kennel card.
- Red/green owner scoring is replaced by a neutral evidence ledger with provenance.

## Tokens

- Canvas (`--exam-cream`): `#f3eee3`
- Primary surface (`--exam-paper`): `#faf7ef`
- Raised surface (`--exam-raised`): `#fffdf8`
- Inset control (`--exam-inset`): `#ece6da`
- Primary ink (`--kennel-slate`): `#263a44`
- Strong action (`--leash-navy`): `#17384b`
- Source/provenance (`--id-brass`): `#ad7b2b`
- Confirmed operational state (`--chart-green`): `#47745d`
- Error/correction attention (`--rust`): `#9a513d`

All other colors derive from these primitives. Rust means errors or review attention, never owner quality. Chart green confirms system or pet state, never owner eligibility.

## Depth and Shape

- Use surface-color shifts only; never decorative shadows.
- Side navigation shares the canvas with the page and uses a soft separator.
- Inputs are inset and slightly darker than their parent surface.
- Border progression uses 12%, 20%, and 40% kennel-slate opacity.
- Radius scale: 6px controls, 10px cards, 16px large panels.

## Typography and Spacing

- Display and record headings use locally available Charter/Bitstream Charter with Georgia fallback, giving records a humane ledger character without a network font request.
- Interface text uses Aptos/Segoe UI/system sans for fast scanning.
- Dates and countdowns use tabular numerals.
- Base spacing unit is 4px. Use 4/8/12/16/20/24/32/48/64 multiples only.

## Reusable Patterns

- **Top context bar:** organization or owner context plus account control; no decorative utilities.
- **Primary navigation:** same-colored canvas, icon plus task label, brass inset marker for current location; bottom navigation on mobile.
- **Care journey:** 34px navy custody pin, brass correction pin, quiet connecting rail, source stamp, neutral reason text, correction/dispute links.
- **Active-record row:** work type, exact task, record metadata, and one directional affordance; no vanity totals.
- **Registry/detail split:** searchable ledger on the left, selected kennel card on the right; stacks on narrow screens.
- **Owner pass:** centered one-time QR, explicit countdown, expiration state, and plain-language privacy note.
- **Status pill:** neutral by default; green for completed operational state, rust-tinted for attention. Never a person score.
- **State panel:** every data surface defines loading, empty, recoverable error, and permission behavior.

## Interaction and Accessibility

- All controls have at least a 42px target; mobile navigation targets are 54px tall.
- Use a 3px brass focus outline with 3px offset and a visible skip link.
- Keep WCAG AA contrast for text and controls.
- Respect reduced-motion preferences; motion is short deceleration only.
- Protected history remains in TanStack Query memory and is never written to localStorage.
- Authorization errors must clear protected caches at the application boundary when backend error handling is added.
- Owner pass QR content disappears on expiration or redemption.
