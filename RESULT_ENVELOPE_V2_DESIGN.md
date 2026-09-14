# Result Envelope v2 design candidate

Status: **implementation candidate present — not stable, not merge-authorized**.

This document defines a versioned public replacement candidate for the permissive
`jarvis-result-envelope-v1` profile characterized in draft PR #4. It does not
change or reinterpret v1. The first implementation was written only after the
negative contract suite had been committed.

The executable contract and pinned resource limits are in
`RESULT_ENVELOPE_V2_TEST_PLAN.md` and `test_result_envelope_v2_contract.py`.
CI now executes the v2 contract suite on Python 3.12 and 3.13.

## Goals

v2 should be a small, fail-closed result container that is deterministic to hash,
explicit about execution identity, and difficult to misuse accidentally. It
should not claim that evidence is authentic, that a process actually ran, or
that a signature/receipt is trusted merely because a field is present.

## Versioning and migration

- v1 remains historical and unchanged.
- v2 uses a new protocol identifier; v1 input is never auto-upgraded.
- v1 and v2 validators are separate entry points.
- adapters are separately versioned and cannot silently widen the core schema.
- unknown protocol/hash versions fail closed.

Identifiers:

- `protocol_version = "execution-result-envelope-v2"`
- `envelope_version = 2`
- `hash_protocol = "execution-result-envelope-hash-v1"`

## Closed top-level schema

Every field is required unless explicitly nullable; unknown fields are rejected.

Exact fields:

- `protocol_version`
- `envelope_version`
- `hash_protocol`
- `result_kind`
- `result_id`
- `mission_id`
- `attempt_id`
- `unit_id`
- `task_id` (nullable)
- `execution_id` (nullable)
- `agent_id`
- `capability`
- `status`
- `started_at_utc`
- `finished_at_utc`
- `created_at_utc`
- `payload`
- `evidence_references`
- `provenance_references`
- `warnings`
- `limitations`
- `security_metadata`
- `injection_metadata`
- `resource_usage`
- `result_hash`

The v1 `signature_metadata` field is intentionally not in the initial v2 core. A
signature profile should be separately specified and actually verified rather
than represented as opaque metadata.

## Identity rules

`result_id`, `mission_id`, `attempt_id`, `unit_id`, `agent_id`, and `capability`
must be non-empty strings. No `str(...)` coercion is allowed. `task_id` and
`execution_id` are either non-empty strings or `null`.

Reference-profile limits:

- UTF-8 string length: 1..256 bytes for identities,
- no leading/trailing whitespace,
- no control characters,
- NFC-normalized wire strings.

`attempt_id` and `unit_id` are required so a result can be bound to the execution
evidence for the same attempt/unit. Replay detection remains the caller/store's
responsibility; v2 does not claim to solve replay by itself.

## Timestamp rules

Required timestamps must be supplied explicitly.

- invalid or missing timestamps fail,
- timezone-naive inputs fail,
- builders never substitute the current time for malformed data,
- accepted builder timestamps are normalized to UTC,
- ordering is `started_at_utc <= finished_at_utc <= created_at_utc`.

The builder accepts a timezone-aware `datetime` or an ISO-8601 string with an
explicit offset. Wire validation performs no time repair.

## Canonical data model

The candidate hash domain rejects values with unstable cross-language
representation.

Allowed canonical values:

- `null`
- booleans
- signed 64-bit integers
- UTF-8 strings normalized to Unicode NFC
- arrays of allowed canonical values
- objects with string keys normalized to NFC

The initial v2 candidate rejects floating-point values entirely, including finite
floats, `NaN`, and infinities. Metrics that require decimals should use integer
base units or an explicitly versioned decimal-string convention in a later
profile.

Duplicate object keys are rejected by the raw JSON decoder before a mapping is
constructed. NFC-normalized key collisions are also rejected.

## Hash protocol

`result_hash` is not included in its own hash input.

Domain separator:

```text
EXECUTION-EVIDENCE-CONTRACTS\x00RESULT-ENVELOPE\x00V2\x00
```

The candidate hash is SHA-256 over:

1. the exact domain-separator bytes,
2. deterministic binary canonical bytes of the unsigned envelope under
   `execution-result-envelope-hash-v1`.

The implementation currently includes a diagnostic fallback inside
`hash_unsigned_envelope_v2` so deliberately invalid envelopes can be re-hashed in
negative tests. Matching that diagnostic hash never makes invalid data valid.
This fallback itself requires review before the protocol can be considered
stable.

Golden vectors produced by this implementation and independently reproduced by a
second implementation are still required before merge consideration.

## Evidence and provenance references

The outer arrays are closed and typed. Each reference has exactly:

- `reference_id`: non-empty string,
- `reference_type`: one of a versioned closed vocabulary,
- `sha256`: 64 lowercase hex characters,
- `locator`: nullable string.

The first vocabulary is `ARTIFACT`, `LOG`, `SOURCE`, `RECEIPT`, `OTHER`.

A locator is descriptive only. A matching digest is still not proof that the
referenced object was collected independently or is trustworthy.

## Warnings and limitations

`warnings` and `limitations` are lists of unique non-empty strings subject to the
profile resource limits. They are hashed but do not alter result status
automatically.

## Metadata maps

`payload`, `security_metadata`, `injection_metadata`, and `resource_usage` remain
application-shaped mappings, but every nested value must satisfy the canonical
data model and size/depth limits. Their presence is not an authorization or
security attestation.

## Status and kind

Both are exact uppercase strings from versioned closed vocabularies. Wire
validation performs no case conversion or fallback.

## Adapter boundary

Compatibility behavior such as:

- `status` vs `execution_state`,
- `started_at_utc` vs `started_at` vs `timestamp_utc`,
- alternate result-id fields,
- alternate evidence/provenance keys,

belongs in separately versioned adapters. The v2 core builder/validator accepts
only the v2 contract.

## Resource limits

The candidate profile pins:

- maximum canonical envelope bytes: `262144`,
- maximum nesting depth: `16`,
- maximum object keys: `128`,
- maximum list length: `256`,
- maximum generic string bytes: `4096`,
- maximum identity bytes: `256`.

Exceeding a limit fails closed. Limits are part of the profile and cannot be
supplied by untrusted envelope data.

## Test-first acceptance contract

`test_result_envelope_v2_contract.py` was committed before
`result_envelope_v2.py`. It requires rejection of:

1. unknown top-level fields,
2. missing top-level fields,
3. all floats and non-finite numbers,
4. malformed, missing, or timezone-naive timestamps,
5. wrong identity types and empty identities,
6. unknown protocol/hash versions,
7. wrong domain/hash binding,
8. duplicate JSON keys and normalized-key collisions,
9. malformed evidence/provenance reference objects,
10. oversized/deep inputs,
11. cross-attempt/unit substitution,
12. v1 input presented to the v2 validator,
13. adapter fallback behavior presented directly to the core validator,
14. lowercase wire status/kind,
15. mutation/nondeterminism during validation.

The first implementation candidate passes this suite on Python 3.12 and 3.13.
That is conformance evidence only; it is not final protocol acceptance.

## Non-goals

v2 validation alone does not prove:

- that tests or workloads ran,
- that an observer is independent,
- that evidence was collected honestly,
- that isolation succeeded,
- that a process/VM terminated,
- that a signature is authentic,
- that a result is not a replay.

Those guarantees require the surrounding execution-evidence/supervisor system.

## Current acceptance sequence

Completed in the draft branch:

1. v1 behavior characterized,
2. v2 design candidate published,
3. negative v2 tests committed before implementation,
4. first v2 implementation added,
5. real v2 tests enabled in CI on Python 3.12 and 3.13.

Still required:

6. freeze golden hash vectors,
7. reproduce those vectors with an independent second implementation,
8. independent security review of canonicalization, limits, parser behavior and
   diagnostic invalid-envelope hashing,
9. resolve review findings without weakening the committed contract tests,
10. only then decide whether v2 is ready for merge to `main`.
