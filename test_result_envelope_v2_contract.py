from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import math
import unittest

from result_envelope_v2 import (
    HASH_DOMAIN_V2,
    HASH_PROTOCOL_V2,
    MAX_CANONICAL_BYTES,
    MAX_COLLECTION_ITEMS,
    MAX_NESTING_DEPTH,
    MAX_OBJECT_KEYS,
    MAX_STRING_BYTES,
    PROTOCOL_VERSION_V2,
    build_result_envelope_v2,
    canonical_bytes_v2,
    decode_result_envelope_v2_json,
    hash_unsigned_envelope_v2,
    validate_result_binding_v2,
    validate_result_envelope_v2,
)


class ResultEnvelopeV2ContractTests(unittest.TestCase):
    def setUp(self):
        self.started = datetime(2026, 9, 14, 18, 0, tzinfo=timezone.utc)
        self.finished = self.started + timedelta(seconds=5)
        self.created = self.finished + timedelta(seconds=1)

    def kwargs(self, **overrides):
        values = {
            "result_kind": "GENERIC",
            "result_id": "result-1",
            "mission_id": "mission-1",
            "attempt_id": "attempt-1",
            "unit_id": "unit-1",
            "task_id": None,
            "execution_id": None,
            "agent_id": "agent-1",
            "capability": "EXAMPLE_CAPABILITY",
            "status": "SUCCEEDED",
            "started_at_utc": self.started,
            "finished_at_utc": self.finished,
            "created_at_utc": self.created,
            "payload": {"value": 1},
            "evidence_references": [
                {
                    "reference_id": "log-1",
                    "reference_type": "LOG",
                    "sha256": "a" * 64,
                    "locator": None,
                }
            ],
            "provenance_references": [
                {
                    "reference_id": "source-1",
                    "reference_type": "SOURCE",
                    "sha256": "b" * 64,
                    "locator": "git:example",
                }
            ],
            "warnings": [],
            "limitations": [],
            "security_metadata": {"reviewed": True},
            "injection_metadata": {"suspected": False},
            "resource_usage": {"cpu_millis": 1000},
        }
        values.update(overrides)
        return values

    def build(self, **overrides):
        return build_result_envelope_v2(**self.kwargs(**overrides))

    def rehash(self, envelope):
        envelope["result_hash"] = hash_unsigned_envelope_v2(envelope)
        return envelope

    def assertInvalid(self, envelope, issue_fragment=None):
        result = validate_result_envelope_v2(envelope)
        self.assertFalse(result["ok"], result)
        self.assertTrue(result["issues"], result)
        if issue_fragment is not None:
            self.assertTrue(
                any(issue_fragment in issue for issue in result["issues"]),
                result,
            )
        return result

    def test_reference_envelope_is_valid_and_explicitly_versioned(self):
        envelope = self.build()
        self.assertEqual(envelope["protocol_version"], PROTOCOL_VERSION_V2)
        self.assertEqual(envelope["hash_protocol"], HASH_PROTOCOL_V2)
        self.assertEqual(envelope["envelope_version"], 2)
        self.assertTrue(validate_result_envelope_v2(envelope)["ok"])

    def test_unknown_top_level_field_rejected_even_after_rehash(self):
        envelope = self.build()
        envelope["future_authority"] = True
        self.rehash(envelope)
        self.assertInvalid(envelope, "UNKNOWN_FIELD")

    def test_missing_top_level_field_rejected_even_after_rehash(self):
        envelope = self.build()
        del envelope["security_metadata"]
        self.rehash(envelope)
        self.assertInvalid(envelope, "MISSING_FIELD")

    def test_finite_float_rejected(self):
        envelope = self.build()
        envelope["payload"] = {"ratio": 1.25}
        self.assertInvalid(envelope, "FLOAT")
        with self.assertRaises(ValueError):
            self.build(payload={"ratio": 1.25})

    def test_nan_and_infinities_rejected(self):
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                envelope = self.build()
                envelope["payload"] = {"value": value}
                self.assertInvalid(envelope, "FLOAT")
                with self.assertRaises(ValueError):
                    self.build(payload={"value": value})

    def test_builder_rejects_malformed_timestamp_instead_of_repairing(self):
        with self.assertRaises(ValueError):
            self.build(started_at_utc="not-a-timestamp")

    def test_builder_rejects_timezone_naive_datetime(self):
        with self.assertRaises(ValueError):
            self.build(started_at_utc=datetime(2026, 9, 14, 18, 0))

    def test_wire_validator_rejects_timezone_naive_timestamp(self):
        envelope = self.build()
        envelope["started_at_utc"] = "2026-09-14T18:00:00"
        self.rehash(envelope)
        self.assertInvalid(envelope, "TIMEZONE")

    def test_timestamp_order_is_started_then_finished_then_created(self):
        envelope = self.build()
        envelope["created_at_utc"] = "2026-09-14T17:59:59+00:00"
        self.rehash(envelope)
        self.assertInvalid(envelope, "TIME_ORDER")

    def test_wrong_identity_types_rejected_by_builder(self):
        for field, value in (
            ("result_id", 1),
            ("mission_id", True),
            ("attempt_id", ["attempt-1"]),
            ("unit_id", {"id": "unit-1"}),
            ("agent_id", 3.0),
            ("capability", None),
        ):
            with self.subTest(field=field, value=value):
                with self.assertRaises((TypeError, ValueError)):
                    self.build(**{field: value})

    def test_wrong_identity_types_rejected_by_wire_validator_after_rehash(self):
        for field, value in (("result_id", 1), ("attempt_id", True), ("unit_id", [])):
            with self.subTest(field=field):
                envelope = self.build()
                envelope[field] = value
                self.rehash(envelope)
                self.assertInvalid(envelope, "IDENTITY")

    def test_empty_whitespace_and_control_character_identities_rejected(self):
        for value in ("", " ", " leading", "trailing ", "line\nbreak"):
            with self.subTest(value=repr(value)):
                with self.assertRaises(ValueError):
                    self.build(result_id=value)

    def test_nullable_ids_must_be_null_or_nonempty_strings(self):
        for field in ("task_id", "execution_id"):
            for value in ("", " ", 7, False):
                with self.subTest(field=field, value=value):
                    with self.assertRaises((TypeError, ValueError)):
                        self.build(**{field: value})

    def test_unknown_protocol_version_rejected_after_rehash(self):
        envelope = self.build()
        envelope["protocol_version"] = "execution-result-envelope-v99"
        self.rehash(envelope)
        self.assertInvalid(envelope, "PROTOCOL")

    def test_unknown_hash_protocol_rejected_after_rehash(self):
        envelope = self.build()
        envelope["hash_protocol"] = "execution-result-envelope-hash-v99"
        self.rehash(envelope)
        self.assertInvalid(envelope, "HASH_PROTOCOL")

    def test_wrong_hash_binding_rejected(self):
        envelope = self.build()
        envelope["result_hash"] = "0" * 64
        self.assertInvalid(envelope, "HASH")

    def test_hash_protocol_is_domain_separated_from_plain_canonical_sha256(self):
        envelope = self.build()
        unsigned = {k: v for k, v in envelope.items() if k != "result_hash"}
        plain = sha256(canonical_bytes_v2(unsigned)).hexdigest()
        self.assertNotEqual(envelope["result_hash"], plain)
        self.assertTrue(HASH_DOMAIN_V2.endswith(b"\x00"))

    def test_duplicate_json_keys_rejected_before_mapping_construction(self):
        text = (
            '{"protocol_version":"execution-result-envelope-v2",'
            '"protocol_version":"execution-result-envelope-v2"}'
        )
        with self.assertRaises(ValueError):
            decode_result_envelope_v2_json(text)

    def test_nfc_normalized_key_collision_rejected(self):
        envelope = self.build()
        envelope["payload"] = {"é": 1, "e\u0301": 2}
        self.assertInvalid(envelope, "NORMALIZED_KEY_COLLISION")
        with self.assertRaises(ValueError):
            self.build(payload={"é": 1, "e\u0301": 2})

    def test_non_nfc_wire_string_rejected(self):
        envelope = self.build()
        envelope["payload"] = {"value": "e\u0301"}
        self.assertInvalid(envelope, "NFC")
        with self.assertRaises(ValueError):
            self.build(payload={"value": "e\u0301"})

    def test_evidence_reference_shape_is_closed(self):
        envelope = self.build()
        envelope["evidence_references"][0]["unexpected"] = True
        self.rehash(envelope)
        self.assertInvalid(envelope, "REFERENCE")

    def test_reference_type_vocabulary_is_closed(self):
        envelope = self.build()
        envelope["evidence_references"][0]["reference_type"] = "MAGIC"
        self.rehash(envelope)
        self.assertInvalid(envelope, "REFERENCE_TYPE")

    def test_reference_digest_is_lowercase_sha256(self):
        for digest in ("A" * 64, "a" * 63, "not-a-digest"):
            with self.subTest(digest=digest):
                envelope = self.build()
                envelope["evidence_references"][0]["sha256"] = digest
                self.rehash(envelope)
                self.assertInvalid(envelope, "SHA256")

    def test_warning_and_limitation_items_are_unique_nonempty_strings(self):
        for field, value in (
            ("warnings", ["dup", "dup"]),
            ("warnings", [""]),
            ("limitations", [1]),
        ):
            with self.subTest(field=field, value=value):
                envelope = self.build(**{field: value})
                self.assertInvalid(envelope, field.upper())

    def test_string_resource_limit_is_enforced(self):
        envelope = self.build()
        envelope["payload"] = {"s": "x" * (MAX_STRING_BYTES + 1)}
        self.assertInvalid(envelope, "STRING_LIMIT")
        with self.assertRaises(ValueError):
            self.build(payload={"s": "x" * (MAX_STRING_BYTES + 1)})

    def test_collection_resource_limit_is_enforced(self):
        envelope = self.build()
        envelope["payload"] = {"items": [0] * (MAX_COLLECTION_ITEMS + 1)}
        self.assertInvalid(envelope, "COLLECTION_LIMIT")
        with self.assertRaises(ValueError):
            self.build(payload={"items": [0] * (MAX_COLLECTION_ITEMS + 1)})

    def test_object_key_resource_limit_is_enforced(self):
        oversized = {f"k{i}": i for i in range(MAX_OBJECT_KEYS + 1)}
        envelope = self.build()
        envelope["payload"] = oversized
        self.assertInvalid(envelope, "OBJECT_KEY_LIMIT")
        with self.assertRaises(ValueError):
            self.build(payload=oversized)

    def test_nesting_resource_limit_is_enforced(self):
        value = 0
        for _ in range(MAX_NESTING_DEPTH + 1):
            value = [value]
        envelope = self.build()
        envelope["payload"] = {"deep": value}
        self.assertInvalid(envelope, "DEPTH_LIMIT")
        with self.assertRaises(ValueError):
            self.build(payload={"deep": value})

    def test_total_canonical_size_limit_is_enforced(self):
        oversized = {"blob": ["x" * MAX_STRING_BYTES for _ in range(70)]}
        envelope = self.build()
        envelope["payload"] = oversized
        self.assertInvalid(envelope, "ENVELOPE_SIZE")
        with self.assertRaises(ValueError):
            self.build(payload=oversized)

    def test_cross_attempt_and_unit_substitution_rejected_by_binding_check(self):
        envelope = self.build()
        ok = validate_result_binding_v2(
            envelope,
            expected_attempt_id="attempt-1",
            expected_unit_id="unit-1",
        )
        self.assertTrue(ok["ok"], ok)
        wrong_attempt = validate_result_binding_v2(
            envelope,
            expected_attempt_id="attempt-other",
            expected_unit_id="unit-1",
        )
        self.assertFalse(wrong_attempt["ok"], wrong_attempt)
        wrong_unit = validate_result_binding_v2(
            envelope,
            expected_attempt_id="attempt-1",
            expected_unit_id="unit-other",
        )
        self.assertFalse(wrong_unit["ok"], wrong_unit)

    def test_v1_input_is_not_accepted_by_v2_validator(self):
        v1_like = {
            "protocol_version": "jarvis-result-envelope-v1",
            "envelope_version": 1,
            "result_hash": "0" * 64,
        }
        self.assertInvalid(v1_like, "PROTOCOL")

    def test_adapter_fallback_fields_are_not_core_fields(self):
        envelope = self.build()
        envelope["execution_state"] = "SUCCEEDED"
        envelope["timestamp_utc"] = envelope["started_at_utc"]
        self.rehash(envelope)
        self.assertInvalid(envelope, "UNKNOWN_FIELD")

    def test_wire_status_and_kind_are_not_case_normalized(self):
        for field, value in (("status", "succeeded"), ("result_kind", "generic")):
            with self.subTest(field=field):
                envelope = self.build()
                envelope[field] = value
                self.rehash(envelope)
                self.assertInvalid(envelope, field.upper())

    def test_validation_does_not_mutate_input(self):
        envelope = self.build()
        snapshot = deepcopy(envelope)
        first = validate_result_envelope_v2(envelope)
        second = validate_result_envelope_v2(envelope)
        self.assertEqual(first, second)
        self.assertEqual(envelope, snapshot)


if __name__ == "__main__":
    unittest.main()
