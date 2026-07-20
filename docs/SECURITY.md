# Security operations

Secrets are supplied at runtime through the root-owned `/etc/fido/fido.env` file (mode `0600`) or GitHub environment secrets; they are never baked into images or frontend bundles. Production builds fail closed without Clerk configuration, and provider webhook signatures are mandatory.

AWS deployments use GitHub OIDC or an assumable non-root operator role. The original Lightsail instance is out of scope and must not be modified or retired without separate approval. New infrastructure starts WAF rules in count mode. Enabling block mode requires sampled-request review and a recorded false-positive decision.

Security events are structured and redact sensitive fields. Operators should alert on repeated authorization failures, webhook verification failures, QR abuse, identity-review spikes, deployment failure, host health, database health, WAF anomalies, and expiring certificates. Rotate access after personnel changes and test restore and incident procedures at least quarterly during the pilot.
