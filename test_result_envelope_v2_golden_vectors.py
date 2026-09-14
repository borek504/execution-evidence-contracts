from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import struct
import unicodedata
import unittest

from result_envelope_v2 import canonical_bytes_v2, hash_unsigned_envelope_v2, validate_result_envelope_v2


VECTOR_FILE = Path(__file__).with_name("RESULT_ENVELOPE_V2_GOLDEN_VECTORS.json")
INDEPENDENT_DOMAIN = b"EXECUTION-EVIDENCE-CONTRACTS\x00RESULT-ENVELOPE\x00V2\x00"


def _u64(value: int) -> bytes:
    return struct.pack(">Q", value)


def independent_canonical_bytes(value) -> bytes:
    """Second implementation of hash-v1 canonical bytes.

    This intentionally does not import or call the production encoder.
    """
    kind = type(value)
    if value is None:
        return b"N"
    if kind is bool:
        return b"T" if value else b"F"
    if kind is int:
        if not -(2**63) <= value <= 2**63 - 1:
            raise ValueError("INTEGER_RANGE")
        return b"I" + struct.pack(">q", value)
    if kind is float:
        raise ValueError("FLOAT_NOT_ALLOWED")
    if kind is str:
        if unicodedata.normalize("NFC", value) != value:
            raise ValueError("NFC_REQUIRED")
        raw = value.encode("utf-8")
        return b"S" + _u64(len(raw)) + raw
    if kind is list:
        return b"L" + _u64(len(value)) + b"".join(
            independent_canonical_bytes(item) for item in value
        )
    if kind is dict:
        keys = list(value)
        if any(type(key) is not str for key in keys):
            raise ValueError("OBJECT_KEY_TYPE")
        normalized = [unicodedata.normalize("NFC", key) for key in keys]
        if len(set(normalized)) != len(normalized):
            raise ValueError("NORMALIZED_KEY_COLLISION")
        if normalized != keys:
            raise ValueError("NFC_REQUIRED")
        keys.sort(key=lambda key: key.encode("utf-8"))
        payload = [b"O", _u64(len(keys))]
        for key in keys:
            payload.append(independent_canonical_bytes(key))
            payload.append(independent_canonical_bytes(value[key]))
        return b"".join(payload)
    raise ValueError("UNSUPPORTED_CANONICAL_TYPE")


def load_vectors():
    return json.loads(VECTOR_FILE.read_text(encoding="utf-8"))


class ResultEnvelopeV2GoldenVectorTests(unittest.TestCase):
    def test_independent_encoder_reproduces_frozen_vectors(self):
        document = load_vectors()
        self.assertEqual(document["vector_set"], "execution-result-envelope-v2-golden-v1")
        self.assertEqual(document["hash_protocol"], "execution-result-envelope-hash-v1")
        for vector in document["vectors"]:
            with self.subTest(vector=vector["name"]):
                unsigned = vector["unsigned_envelope"]
                canonical = independent_canonical_bytes(unsigned)
                self.assertEqual(len(canonical), vector["expected_canonical_length"])
                self.assertEqual(
                    sha256(canonical).hexdigest(),
                    vector["expected_canonical_sha256"],
                )
                self.assertEqual(
                    sha256(INDEPENDENT_DOMAIN + canonical).hexdigest(),
                    vector["expected_result_hash"],
                )

    def test_primary_encoder_reproduces_same_frozen_vectors(self):
        document = load_vectors()
        for vector in document["vectors"]:
            with self.subTest(vector=vector["name"]):
                unsigned = vector["unsigned_envelope"]
                canonical = canonical_bytes_v2(unsigned)
                self.assertEqual(len(canonical), vector["expected_canonical_length"])
                self.assertEqual(
                    sha256(canonical).hexdigest(),
                    vector["expected_canonical_sha256"],
                )
                self.assertEqual(
                    hash_unsigned_envelope_v2(unsigned),
                    vector["expected_result_hash"],
                )

    def test_vectors_form_valid_full_envelopes(self):
        document = load_vectors()
        for vector in document["vectors"]:
            with self.subTest(vector=vector["name"]):
                envelope = dict(vector["unsigned_envelope"])
                envelope["result_hash"] = vector["expected_result_hash"]
                result = validate_result_envelope_v2(envelope)
                self.assertTrue(result["ok"], result)


if __name__ == "__main__":
    unittest.main()
