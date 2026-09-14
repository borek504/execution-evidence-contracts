# Project profile

`execution-evidence-contracts` is an experimental, standard-library-only Python project focused on fail-closed validation of execution evidence and result-data contracts for automated/agentic systems.

## Published main profile

The public `main` branch contains the execution-evidence validator built around three independently supplied inputs:

- an untrusted execution record,
- expectations fixed before execution,
- independent verifier observations.

The validator checks consistency only. It does not authenticate provenance or grant execution/release authority.

## Draft Result Envelope work

Draft PR #4 characterizes the historical v1 Result Envelope and develops a separate v2 candidate using a negative-tests-first process. The first v2 implementation passes its committed contract tests on Python 3.12 and 3.13, but it remains review-only.

Pending gates include deterministic golden hash vectors, independent reproduction, and security review of canonicalization, parser behavior, resource limits, and diagnostic hashing.

## Contribution focus

Useful reviews include:

- trust-boundary misuse cases,
- adversarial validation fixtures,
- canonicalization/hash protocol review,
- schema/profile versioning,
- replay/substitution boundaries,
- documentation and test consistency.

See `CONTRIBUTING.md` and `SECURITY.md` before submitting changes.
