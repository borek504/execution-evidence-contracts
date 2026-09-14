# Result Envelope v2 test-first plan

Status: **tests first / implementation absent / not merge-authorized**.

This document freezes the initial API surface and deterministic limits that the
new `test_result_envelope_v2_contract.py` expects. The goal is to make the
fail-closed contract reviewable before implementation exists.

## Expected module API

The future module is `result_envelope_v2.py` and must export:

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

`test_result_envelope_v2_contract.py` intentionally imports a module that does
not exist yet. Until the implementation commit lands, CI only syntax-compiles
that test file and does **not** execute it. This preserves green regression CI
for v1 while keeping the future v2 acceptance contract visible in the PR.

When implementation starts, the workflow must be changed in the same PR to run:

```text
python -B -m unittest -v test_result_envelope_v2_contract
```

At that point any failing v2 test is a real blocker; tests must not be removed,
weakened, marked expected-failure, or skipped merely to make the build green.

## Negative behavior covered

The initial contract test suite requires rejection of:

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

## Important boundary

Passing this suite will prove only conformance to the proposed v2 data contract.
It will not authenticate evidence, prove independent observation, prove process
termination or isolation, prevent replay at the storage layer, or grant release
authority.
