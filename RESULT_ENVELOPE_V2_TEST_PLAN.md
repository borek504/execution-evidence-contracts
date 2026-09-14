# Result Envelope v2 test-first plan

Status: **implementation candidate present / executable tests blocking / not merge-authorized**.

This document freezes the initial API surface and deterministic limits enforced by
`test_result_envelope_v2_contract.py`. The contract tests were committed before
the implementation. A candidate `result_envelope_v2.py` now exists, and CI runs
the v2 suite as a real blocker on Python 3.12 and 3.13.

## Expected module API

The module is `result_envelope_v2.py` and exports:

- `build_result_envelope_v2(...) -> dict`
- `validate_result_envelope_v2(envelope) -> {"ok": bool, "issues": list[str]}`
- `validate_result_binding_v2(envelope, *, expected_attempt_id, expected_unit_id)`
- `decode_result_envelope_v2_json(text_or_bytes)`
- `canonical_bytes_v2(value) -> bytes`
- `hash_unsigned_envelope_v2(envelope) -> str`
- version/domain constants used by the test suite

The raw JSON decoder is a separate entry point because exact duplicate JSON keys
cannot be detected once a normal Python mapping has already been constructed.

## Pinned candidate limits

These limits are part of the reference profile and are not supplied by envelope
data:

- `MAX_CANONICAL_BYTES = 262144` (256 KiB)
- `MAX_NESTING_DEPTH = 16`
- `MAX_OBJECT_KEYS = 128` per object
- `MAX_COLLECTION_ITEMS = 256` per list
- `MAX_STRING_BYTES = 4096` for generic canonical strings
- identity strings remain separately constrained to 1..256 UTF-8 bytes

A future revision may change these numbers only through an explicit profile or
protocol version change. The implementation must not silently widen them.

## Test-first rule

`test_result_envelope_v2_contract.py` was committed before the implementation so
the desired fail-closed behavior was reviewable before code could make it green.

Now that `result_envelope_v2.py` exists, CI executes:

```text
python -B -m unittest -v test_result_envelope_v2_contract
```

Any failing v2 test is a real blocker. Tests must not be removed, weakened,
marked expected-failure, or skipped merely to make the build green.

The golden-vector checkpoint is separately executable:

```text
python -B -m unittest -v test_result_envelope_v2_golden_vectors
```

The frozen machine-readable vectors live in
`RESULT_ENVELOPE_V2_GOLDEN_VECTORS.json`. The golden-vector test contains a
second canonical encoder that independently reproduces the selected canonical
byte digests and domain-separated result hashes before checking the production
encoder against the same values.

## Negative behavior covered

The current contract test suite requires rejection of:

1. unknown and missing top-level fields,
2. finite floats, NaN and infinities,
3. malformed and timezone-naive timestamps,
4. wrong/empty identity types and invalid nullable IDs,
5. unknown protocol/hash versions,
6. invalid result-hash binding and missing domain separation,
7. duplicate JSON keys and NFC-normalized key collisions,
8. non-NFC wire strings,
9. malformed/unknown evidence-reference fields and digests,
10. duplicate/empty warning or limitation entries,
11. string/list/object/depth/total-size limit violations,
12. cross-attempt and cross-unit substitution through the explicit binding check,
13. v1 input supplied to the v2 validator,
14. adapter fallback fields supplied directly to the core validator,
15. lowercase wire status/kind that would require silent normalization,
16. validator input mutation or nondeterministic results.

## Golden-vector checkpoint

Three candidate vectors are frozen for review:

- `baseline_generic`
- `unicode_nested_research`
- `int64_and_utf8_ordering`

They cover the baseline envelope, NFC Unicode, nested canonical values, typed
references, signed integers including int64 endpoints, booleans/null, and UTF-8
object-key ordering. The vector file records canonical byte lengths,
`SHA256(canonical_bytes)`, and final domain-separated result hashes.

The vectors are not implementation-owned fixtures. Once accepted, changing an
expected digest merely to fit a changed encoder is prohibited; such a change
requires an explicit hash-protocol/version decision.

## Current implementation checkpoint

The implementation candidate passes the complete v2 contract suite and the
three golden-vector checks on both Python 3.12 and 3.13 together with the
existing v1 and execution-contract suites. That is conformance and selected
cross-implementation determinism evidence only; it is not final protocol
acceptance.

Still required before merge consideration:

- review binary canonicalization and resource-limit behavior,
- review duplicate-key / NFC parsing behavior,
- review invalid-envelope diagnostic hashing,
- perform independent security review,
- keep the PR in draft until those gates are complete.

## Important boundary

Passing these suites proves only conformance to the proposed v2 data contract and
deterministic agreement on selected vectors. It does not authenticate evidence,
prove independent observation, prove process termination or isolation, prevent
replay at the storage layer, or grant release authority.
