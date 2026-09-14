# Security policy

This repository contains experimental validation contracts. Passing validation does not authenticate provenance, prove that work ran, prove isolation, or establish process/VM termination.

## Reporting

Please open a GitHub issue for design-level security questions that can be discussed safely with synthetic examples.

Do **not** post secrets, private credentials, personal data, production host details, or unrelated exploit material in public issues.

For a vulnerability that requires sensitive reproduction material, contact the maintainer privately before publishing details.

## Current review focus

Draft Result Envelope v2 work is intentionally not stable or merge-authorized. Security review is especially requested for:

- canonical byte encoding and domain-separated hashing,
- duplicate JSON key and Unicode normalization handling,
- resource-limit bypasses,
- timestamp and identity validation,
- cross-attempt/unit substitution boundaries,
- the diagnostic fallback used to hash deliberately invalid envelopes in tests,
- any path where invalid data could become authoritative merely because its hash matches.

A successful validator result is never an authorization token.
