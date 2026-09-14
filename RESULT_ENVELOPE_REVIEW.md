# Result Envelope candidate review

This branch contains an exact extraction of the historical `core_result_envelope.py` v1 profile, its characterization/red-team suites, and a separately versioned v2 candidate.

It remains a review candidate only. It is **not approved for merge** into `main`.

## v1 findings

The historical v1 profile is preserved rather than silently changed. Characterization tests reproduce the observed permissive behaviors: unknown top-level fields after rehashing, non-finite floats, timestamp repair, naive timestamp UTC interpretation, identity coercion, non-string identity acceptance after rehash, opaque evidence/provenance item shapes, and raw SHA-256 canonical hashing without a separate domain/version.

## v2 candidate

The v2 contract was designed and tested negative-first before implementation. It now has:

- closed top-level schema,
- strict attempt/unit and identity binding,
- explicit-timezone timestamps with no repair,
- a float-free canonical data model,
- NFC and duplicate-key protections,
- typed evidence/provenance references,
- deterministic resource limits,
- a separate hash protocol and domain separator,
- no automatic v1 migration or adapter fallbacks in core validation.

## Golden-vector checkpoint

Three machine-readable candidate vectors are frozen in `RESULT_ENVELOPE_V2_GOLDEN_VECTORS.json` and documented in `RESULT_ENVELOPE_V2_GOLDEN_VECTORS.md`.

`test_result_envelope_v2_golden_vectors.py` contains a second canonical encoder. Its independent computation path does not call the production encoder. The test then separately verifies that the production encoder reproduces the same canonical byte lengths, canonical-byte SHA-256 values and final domain-separated hashes.

This checkpoint is now part of CI on Python 3.12 and 3.13.

## Remaining blockers before merge consideration

1. Review the binary canonical encoding itself: type tags, framing, UTF-8 key ordering and int64 boundaries.
2. Review resource-limit semantics, especially nesting and total canonical-size enforcement.
3. Review duplicate-key and NFC-normalized-key collision behavior at the raw JSON decoder boundary.
4. Review `_fallback_invalid_bytes` / diagnostic hashing so malformed data cannot acquire unintended semantic meaning.
5. Perform an independent security review of the full v2 code + tests + vectors.
6. Resolve findings without weakening/skipping the committed v2 contract tests or regenerating golden values to fit code changes.

## Non-authority boundary

Even a fully valid v2 envelope proves only conformance to this data contract. It does not authenticate evidence, prove execution, prove observer independence, prove isolation or process termination, prevent replay, or grant qualification/release authority.

External review is welcome, especially around canonicalization portability, parser ambiguity, resource-boundary edge cases and hash-domain separation.
