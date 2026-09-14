# Result Envelope v2 design candidate

Status: **design only — not implemented, not merge-authorized**.

This document proposes a versioned public replacement for the permissive `jarvis-result-envelope-v1` profile characterized in draft PR #4. It does not change or reinterpret v1.

The executable test-first contract and pinned candidate resource limits are in `RESULT_ENVELOPE_V2_TEST_PLAN.md` and `test_result_envelope_v2_contract.py`. The test file is intentionally syntax-checked but not executed until the v2 implementation exists.

## Goals

v2 should be a small, fail-closed result container that is deterministic to hash, explicit about execution identity, and difficult to misuse accidentally. It should not claim that evidence is authentic, that a process actually ran, or that a signature/receipt is trusted merely because a field is present.

## Versioning and migration

- v1 remains historical and unchanged.
- v2 uses a new protocol identifier; v1 input is never auto-upgraded.
- v1 and v2 validators are separate entry points.
- adapters are separately versioned and cannot silently widen the core schema.
- unknown protocol/hash versions fail closed.

Proposed identifiers:

- `protocol_version = "execution-result-envelope-v2"`
- `envelope_version = 2`
- `hash_protocol = "execution-result-envelope-hash-v1"`

## Closed top-level schema

Every field is required unless explicitly nullable; unknown fields are rejected.

Proposed exact fields:

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

The v1 `signature_metadata` field is intentionally not in the initial v2 core. A signature profile should be separately specified and actually verified rather than represented as opaque metadata.

## Identity rules

`result_id`, `mission_id`, `attempt_id`, `unit_id`, `agent_id`, and `capability` must be non-empty strings. No `str(...)` coercion is allowed. `task_id` and `execution_id` are either non-empty strings or `null`.

Recommended reference-profile limits:

- UTF-8 string length: 1..256 bytes for identities,
- no leading/trailing whitespace,
- no control characters.

`attempt_id` and `unit_id` are required so a result can be bound to the execution evidence for the same attempt/unit. Replay detection remains the caller/store's responsibility; v2 does not claim to solve replay by itself.

## Timestamp rules

Required timestamps must be supplied explicitly.

- invalid or missing timestamps fail,
- timezone-naive inputs fail,
- builders never substitute the current time for malformed data,
- accepted timestamps are normalized to UTC,
- ordering is `started_at_utc <= finished_at_utc <= created_at_utc`.

A builder may accept a timezone-aware `datetime` or an RFC 3339/ISO-8601 string with an explicit offset, but validation operates on the normalized wire representation only.

## Canonical data model

To keep hashing portable and fail-closed, the initial v2 hash domain should reject values with unstable cross-language representation.

Allowed canonical values:

- `null`
- booleans
- signed 64-bit integers
- UTF-8 strings normalized to Unicode NFC
- arrays of allowed canonical values
- objects with string keys normalized to NFC

Initial v2 should reject floating-point values entirely, including finite floats, `NaN`, and infinities. Metrics that require decimals should use integer base units or an explicitly versioned decimal-string convention in a later profile.

Duplicate object keys must be rejected by the decoder before a mapping is constructed. NFC-normalized key collisions must also be rejected.

## Hash protocol

`result_hash` is not included in its own hash input.

Proposed domain separator:

```text
EXECUTION-EVIDENCE-CONTRACTS\x00RESULT-ENVELOPE\x00V2\x00
```

The hash is SHA-256 over:

1. the exact domain-separator bytes,
2. canonical bytes of the unsigned envelope under `execution-result-envelope-hash-v1`.

The canonical byte algorithm must be specified independently from ordinary display JSON. A normal `json.dumps(...)` call is not by itself the protocol definition.

The implementation should publish golden vectors produced by an independent second implementation before v2 is considered stable.

## Evidence and provenance references

The outer arrays are closed and typed. Each reference uses the exact object shape:

- `reference_id`: non-empty string,
- `reference_type`: one of a versioned closed vocabulary,
- `sha256`: 64 lowercase hex characters,
- `locator`: nullable string.

A locator is descriptive only. A matching digest is still not proof that the referenced object was collected independently or is trustworthy.

The first vocabulary can remain deliberately small, for example `ARTIFACT`, `LOG`, `SOURCE`, `RECEIPT`, `OTHER`.

## Warnings and limitations

`warnings` and `limitations` are lists of unique non-empty strings with explicit count/size limits. They are hashed but do not alter result status automatically.

## Metadata maps

`payload`, `security_metadata`, `injection_metadata`, and `resource_usage` may remain application-shaped mappings, but every nested value must satisfy the canonical data model and size/depth limits. Their presence is not an authorization or security attestation.

A future profile may close any of these mappings without changing the generic core.

## Status and kind

Both are exact uppercase strings from versioned closed vocabularies. Builders may provide separate convenience normalization outside the wire validator, but wire validation performs no case conversion or fallback.

## Adapter boundary

Compatibility behavior such as:

- `status` vs `execution_state`,
- `started_at_utc` vs `started_at` vs `timestamp_utc`,
- alternate result-id fields,
- alternate evidence/provenance keys,

belongs in separately versioned adapters. The v2 core builder/validator accepts only the v2 contract.

## Resource limits

The initial public reference-profile candidate pins:

- maximum canonical envelope bytes: `262144` (256 KiB),
- maximum nesting depth: `16`,
- maximum object keys per object: `128`,
- maximum list length: `256`,
- maximum generic canonical string bytes: `4096`,
- maximum identity string bytes: `256`.

Exceeding a limit fails closed. Limits are part of the profile and cannot be supplied by untrusted envelope data. Changing them after acceptance requires an explicit profile/protocol version decision.

## Required negative tests before implementation acceptance

At minimum v2 tests must reject:

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
13. adapter fallback behavior presented directly to the core validator.

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

## Proposed acceptance sequence

1. freeze this design after public review,
2. add failing v2 negative tests first,
3. implement a new v2 module without editing v1 semantics,
4. add golden hash vectors and an independent implementation check,
5. run CI on supported Python versions,
6. perform independent security review,
7. only then decide whether v2 is ready for merge to `main`.
