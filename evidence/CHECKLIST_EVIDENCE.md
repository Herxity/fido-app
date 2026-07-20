# Implementation checklist evidence

This file is the durable evidence index. `scripts/verify.sh` writes exact command results to `evidence/latest-verification.txt`; AWS deployment evidence is appended only after live inspection. An item is marked complete only when its stated evidence exists. External tenant configuration, legal review, production approval, DNS cutover, and stabilization are intentionally not self-certified by code.

See `IMPLEMENTATION_PLAN.md` for the authoritative checklist and acceptance tests.
