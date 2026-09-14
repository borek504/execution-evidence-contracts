# Result Envelope candidate review

This branch contains an **exact extraction** of the current `core_result_envelope.py` profile from the private parent project, plus a new standalone characterization suite.

It is a review candidate only. It is **not approved for merge** into the public reference profile yet.

## Why this component is interesting

The module provides a small standard-library-only result envelope with:

- explicit result status and result-kind vocabularies,
- result/mission/agent/capability identity fields,
- start/finish/create timestamps,
- evidence and provenance references,
- warnings and limitations,
- security, injection, resource and signature metadata,
- a canonical JSON SHA-256 binding,
- a typed-result adapter for normalizing upstream result shapes.

That makes it a natural companion to the execution-evidence contract already published in this repository.

## Important current-profile boundaries

The extracted code intentionally keeps the original `jarvis-result-envelope-v1` identifier and current semantics. No claim is made that these semantics are already suitable as a generic public protocol.

## Review blockers / design questions before merge

The following items should be decided explicitly rather than changed silently during extraction:

1. **Unknown top-level fields are currently accepted.** `validate_result_envelope` checks missing required fields but does not reject extra keys. Should a public security-oriented profile use a closed schema?
2. **Canonical JSON currently uses Python's default non-finite-float behavior.** `json.dumps` can serialize `NaN`/`Infinity` unless `allow_nan=False` is specified. Should non-standard JSON numbers be rejected?
3. **Builder timestamp repair is permissive.** An invalid or missing timestamp can fall through `_iso()` to the current UTC time. Should malformed required timestamps fail instead of being repaired?
4. **Naive timestamps are interpreted as UTC.** Should a security-oriented envelope require explicit timezone information instead?
5. **Several identities are coerced with `str(...)`.** Should wrong input types fail rather than normalize?
6. **The digest has no explicit domain separator or hash-protocol version distinct from the envelope version.** Is a separate canonicalization/hash version warranted?
7. **Nested evidence/provenance/reference contents are largely opaque.** Which structures, if any, should be closed or typed without making the envelope application-specific?
8. **Typed-result adaptation has multiple fallback field names.** Which compatibility behavior belongs in a generic core versus separately versioned adapters?

## Acceptance direction

Before merging this component, the preferred path is:

- characterize current behavior,
- reproduce each security-relevant ambiguity with focused tests,
- decide a versioned public contract,
- harden fail-closed behavior without silently reinterpreting the original v1 profile,
- run both the existing execution-contract suite and the new result-envelope suite on Python 3.12 and 3.13.

External review is welcome, especially around canonicalization, schema closure, timestamp semantics, replay/substitution resistance, and separation between a generic envelope core and profile-specific adapters.
