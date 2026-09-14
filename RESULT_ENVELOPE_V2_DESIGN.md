# Result Envelope v2 design candidate

Status: **design + implementation candidate — not merge-authorized**.

This document proposes a versioned public replacement for the permissive `jarvis-result-envelope-v1` profile characterized in draft PR #4. It does not change or reinterpret v1.

The executable contract and pinned reference-profile limits are in `RESULT_ENVELOPE_V2_TEST_PLAN.md` and `test_result_envelope_v2_contract.py`. The first implementation candidate is `result_envelope_v2.py`.

The hash checkpoint is frozen separately in `RESULT_ENVELOPE_V2_GOLDEN_VECTORS.json` and documented in `RESULT_ENVELOPE_V2_GOLDEN_VECTORS.md`. A second canonical encoder in `test_result_envelope_v2_golden_vectors.py` independently reproduces the selected canonical-byte digests and domain-separated result hashes.

## Goals

v2 should be a small, fail-closed result container that is deterministic to hash, explicit about execution identity, and difficult to misuse accidentally. It should not claim that evidence is authentic, that a process actually ran, or that a signature/receipt is trusted merely because a field is present.

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

The v1 `signature_metadata` field is intentionally not in the initial v2 core. A signature profile should be separately specified and actually verified rather than represented as opaque metadata.

## Identity rules

`result_id`, `mission_id`, `attempt_id`, `unit_id`, `agent_id`, and `capability` must be non-empty strings. No `str(...)` coercion is allowed. `task_id` and `execution_id` are either non-empty strings or `null`.

Reference-profile limits:

- UTF-8 string length: 1..256 bytes for identities,
- no leading/trailing whitespace,
- no control characters,
- NFC-normalized wire strings only.

`attempt_id` and `unit_id` are required so a result can be bound to the execution evidence for the same attempt/unit. Replay detection remains the caller/store's responsibility; v2 does not claim to solve replay by itself.

## Timestamp rules

Required timestamps must be supplied explicitly.

- invalid or missing timestamps fail,
- timezone-naive inputs fail,
- builders never substitute the current time for malformed data,
- accepted timestamps are normalized to UTC,
- ordering is `started_at_utc <= finished_at_utc <= created_at_utc`.

A builder may accept a timezone-aware `datetime` or an ISO-8601 string with an explicit offset, but validation operates on the normalized wire representation only.

## Canonical data model

The initial v2 hash domain accepts only:

- `null`
- booleans
- signed 64-bit integers
- UTF-8 strings normalized to Unicode NFC
- arrays of allowed canonical values
- objects with string keys normalized to NFC

Floating-point values are rejected entirely, including finite floats, `NaN`, and infinities. Metrics that require decimals should use integer base units or an explicitly versioned decimal-string convention in a later profile.

Duplicate object keys must be rejected by the decoder before a mapping is constructed. NFC-normalized key collisions must also be rejected.

## Hash protocol

`result_hash` is not included in its own hash input.

Domain separator:

```text
EXECUTION-EVIDENCE-CONTRACTS\x00RESULT-ENVELOPE\x00V2\x00
```

The hash is SHA-256 over:

1. the exact domain-separator bytes,
2. canonical bytes of the unsigned envelope under `execution-result-envelope-hash-v1`.

The canonical byte algorithm is binary and distinct from ordinary display JSON. The selected golden vectors are frozen in `RESULT_ENVELOPE_V2_GOLDEN_VECTORS.json` and reproduced by both the production encoder and a second independently written encoder in CI.

Changing an accepted vector digest to follow an implementation change is not allowed; that requires an explicit protocol/version decision.

## Evidence and provenance references

The outer arrays are closed and typed. Each reference uses exactly:

- `reference_id`: non-empty string,
- `reference_type`: one of `ARTIFACT`, `LOG`, `SOURCE`, `RECEIPT`, `OTHER`,
- `sha256`: 64 lowercase hex characters,
- `locator`: nullable string.

A locator is descriptive only. A matching digest is still not proof that the referenced object was collected independently or is trustworthy.

## Warnings and limitations

`warnings` and `limitations` are lists of unique non-empty strings with explicit size limits. They are hashed but do not alter result status automatically.

## Metadata maps

`payload`, `security_metadata`, `injection_metadata`, and `resource_usage` remain application-shaped mappings, but every nested value must satisfy the canonical data model and resource limits. Their presence is not an authorization or security attestation.

## Status and kind

Both are exact uppercase strings from closed vocabularies. Wire validation performs no case conversion or fallback.

## Adapter boundary

Compatibility behavior such as:

- `status` vs `execution_state`,
- `started_at_utc` vs `started_at` vs `timestamp_utc`,
- alternate result-id fields,
- alternate evidence/provenance keys,

belongs in separately versioned adapters. The v2 core builder/validator accepts only the v2 contract.

## Resource limits

The reference-profile candidate pins:

- maximum canonical envelope bytes: `262144` (256 KiB),
- maximum nesting depth: `16`,
- maximum object keys per object: `128`,
- maximum list length: `256`,
- maximum generic canonical string bytes: `4096`,
- maximum identity string bytes: `256`.

Exceeding a limit fails closed. Limits are part of the profile and cannot be supplied by untrusted envelope data. Changing them after acceptance requires an explicit profile/protocol version decision.

## Golden-vector checkpoint

The first frozen set contains:

1. `baseline_generic`
2. `unicode_nested_research`
3. `int64_and_utf8_ordering`

The vectors cover baseline framing, NFC Unicode, typed references, nested structures, nullable values, booleans, signed integers including int64 endpoints, and UTF-8 key ordering.

The independent encoder and the production encoder reproduce the same frozen canonical byte lengths, canonical-byte SHA-256 values and final domain-separated hashes in CI on Python 3.12 and 3.13.

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

## Remaining acceptance sequence

1. review binary canonicalization and resource-limit behavior,
2. review duplicate-key / NFC parsing behavior,
3. review invalid-envelope diagnostic hashing,
4. perform an independent security review,
5. resolve findings without weakening the committed contract or golden vectors,
6. only then decide whether v2 is ready for merge to `main`.
