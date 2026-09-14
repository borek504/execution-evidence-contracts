# Security Policy

This repository contains experimental validation contracts. A successful validation means only that supplied data satisfy the implemented contract. It does **not** establish authentic provenance, independent observation, process execution, isolation, termination, replay resistance, or release authority.

## Reporting

Please do not publish real credentials, API keys, private host details, personal data, or exploit material from unrelated systems in issues or pull requests.

For ordinary design weaknesses or synthetic fail-open cases, open a focused issue with a minimal self-contained reproducer. For a vulnerability that would create an immediate security risk for users, use GitHub's private vulnerability reporting if available rather than posting sensitive details publicly.

## Security-sensitive contribution rules

Changes to trust boundaries, canonicalization, hashing, schema closure, identity binding, parser behavior, resource limits, termination semantics, or authorization-related fields require focused negative tests and review.

Do not:

- weaken or skip committed fail-closed tests just to make a change pass,
- silently reinterpret historical v1 semantics,
- regenerate accepted golden hashes merely to fit an implementation change,
- treat matching digests or metadata labels as proof of trustworthy provenance,
- add compatibility fallbacks to a core validator without explicit versioning.

## Result Envelope v2 review gate

Draft Result Envelope v2 remains non-authorizing and non-stable. Before merge consideration its binary canonicalization, resource limits, duplicate-key/NFC parser behavior and invalid-envelope diagnostic hashing must be reviewed independently. The frozen golden-vector set and second canonical encoder are regression evidence, not a substitute for security review.
