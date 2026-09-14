# Result Envelope v2 golden vectors

Status: **candidate protocol vectors — frozen for review, not merge-authorized**.

This checkpoint freezes three valid unsigned-envelope inputs for `execution-result-envelope-hash-v1` and records both the SHA-256 of the canonical bytes and the final domain-separated result hash.

The machine-readable source is `RESULT_ENVELOPE_V2_GOLDEN_VECTORS.json`.

## Hash domain

```text
EXECUTION-EVIDENCE-CONTRACTS\x00RESULT-ENVELOPE\x00V2\x00
```

`result_hash = SHA256(domain || canonical_bytes(unsigned_envelope))`.

## Frozen vectors

| Vector | Canonical bytes | SHA-256(canonical bytes) | Result hash |
| --- | ---: | --- | --- |
| `baseline_generic` | 1408 | `ac51e874cf300c70096af6123b4c15bc64db69731a46ac99b193e2c722dc9d7a` | `9182b4d6f5cf3e090f75eeba4b6add78a730a16104af2d7d01d55614a9b4a4e9` |
| `unicode_nested_research` | 1967 | `a1579de45018aa99293a47e4b8b3084460893358d9ed709058e1210c7cc6c845` | `d6b3015e6ff1cb8437628820eaaa086cf6900a24f8f3dcc89fd98c3878a1c669` |
| `int64_and_utf8_ordering` | 1044 | `57023b025f0d85d05bf8743881782d9218b85972679a1b2c77a32ba05aae1b7a` | `9b6dfbeea4f5b9cd4003ba748fd18d48c226a2bac94d2c31afb997d1d9c3308e` |

The vectors intentionally cover a plain reference envelope, NFC Unicode and nested values, nullable fields, typed references, signed integers, both booleans and null, the signed-64-bit endpoints, and UTF-8 object-key ordering.

## Independent reproduction

`test_result_envelope_v2_golden_vectors.py` contains a second canonical encoder. Its independent path does **not** import or call the production canonical encoder when deriving bytes and hashes. It implements the type tags, integer framing, string/list/object framing and UTF-8 key ordering separately, then compares the result with the frozen values above.

The same test module separately asks the production `canonical_bytes_v2` and `hash_unsigned_envelope_v2` functions to reproduce those values. Keeping those two paths distinct is intentional: a regression in the production encoder should not silently redefine the vectors.

## Freeze rule

Once accepted, changing any vector input, canonical length, canonical digest, domain separator or result hash requires an explicit hash-protocol/version decision. The vectors must not be regenerated merely to make a changed implementation pass.

This checkpoint demonstrates deterministic agreement on selected valid inputs only. It does not prove cross-language interoperability, evidence authenticity, replay resistance, process termination, isolation, or release authority.
