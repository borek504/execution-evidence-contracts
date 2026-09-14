# Result Envelope candidate review

This branch contains an **exact extraction** of the current `core_result_envelope.py` v1 profile from the private parent project, plus standalone characterization/red-team suites and a separate v2 candidate.

The branch is still **review-only and not approved for merge**.

## v1 characterization

The extracted v1 code intentionally keeps the original `jarvis-result-envelope-v1` identifier and current semantics. A focused red-team suite reproduces eight current behaviors without changing them:

1. unknown top-level fields can validate after rehashing,
2. non-finite floats can be serialized and validated,
3. malformed timestamps may be repaired by the builder,
4. naive timestamp strings are interpreted as UTC,
5. identity values can be coerced with `str(...)`,
6. a non-string identity can validate after rehashing,
7. evidence/provenance item contents are mostly opaque,
8. the hash is raw SHA-256 over canonical JSON without a separate domain/version.

These are characterization results, not endorsed public semantics.

## v2 candidate

The versioned redesign lives in:

- `RESULT_ENVELOPE_V2_DESIGN.md`
- `RESULT_ENVELOPE_V2_TEST_PLAN.md`
- `test_result_envelope_v2_contract.py`
- `result_envelope_v2.py`

The negative v2 contract tests were committed before the implementation. CI now executes them as real blockers on Python 3.12 and 3.13. The first implementation candidate passes the v2 contract together with the existing execution-contract and v1 suites.

## Remaining blockers before any merge decision

- freeze deterministic golden hash vectors,
- reproduce those vectors with an independent second implementation,
- review the binary canonical encoding and resource limits,
- review duplicate-key/NFC handling,
- review diagnostic hashing for deliberately invalid envelopes,
- perform an independent security review,
- resolve findings without weakening or skipping the committed contract tests.

No code in this branch grants execution, validation, qualification, or release authority. A structurally valid envelope is still only a data-contract result, not proof that work ran or that evidence is authentic.
