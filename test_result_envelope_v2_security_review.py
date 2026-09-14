from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from result_envelope_v2 import (
    MAX_JSON_INPUT_BYTES,
    build_result_envelope_v2,
    decode_result_envelope_v2_json,
    hash_unsigned_envelope_v2,
    validate_result_binding_v2,
    validate_result_envelope_v2,
)


class ResultEnvelopeV2SecurityReviewTests(unittest.TestCase):
    def setUp(self):
        started = datetime(2026, 9, 14, 18, 0, tzinfo=timezone.utc)
        finished = started + timedelta(seconds=5)
        created = finished + timedelta(seconds=1)
        self.envelope = build_result_envelope_v2(
            result_kind="GENERIC",
            result_id="result-security-1",
            mission_id="mission-security-1",
            attempt_id="attempt-security-1",
            unit_id="unit-security-1",
            task_id=None,
            execution_id=None,
            agent_id="agent-security-1",
            capability="SECURITY_REVIEW",
            status="SUCCEEDED",
            started_at_utc=started,
            finished_at_utc=finished,
            created_at_utc=created,
            payload={"value": 1},
            evidence_references=[{
                "reference_id": "log-security-1",
                "reference_type": "LOG",
                "sha256": "a" * 64,
                "locator": None,
            }],
            provenance_references=[{
                "reference_id": "source-security-1",
                "reference_type": "SOURCE",
                "sha256": "b" * 64,
                "locator": None,
            }],
            warnings=[],
            limitations=[],
            security_metadata={},
            injection_metadata={},
            resource_usage={},
        )

    def test_validator_never_raises_for_unhashable_closed_vocabulary_values(self):
        cases = (
            ("status", []),
            ("result_kind", {}),
        )
        for field, value in cases:
            with self.subTest(field=field):
                envelope = dict(self.envelope)
                envelope[field] = value
                result = validate_result_envelope_v2(envelope)
                self.assertFalse(result["ok"], result)

        envelope = dict(self.envelope)
        envelope["evidence_references"] = [dict(self.envelope["evidence_references"][0])]
        envelope["evidence_references"][0]["reference_type"] = []
        result = validate_result_envelope_v2(envelope)
        self.assertFalse(result["ok"], result)

    def test_validator_never_raises_for_non_string_top_level_key(self):
        envelope = dict(self.envelope)
        envelope[1] = True
        result = validate_result_envelope_v2(envelope)
        self.assertFalse(result["ok"], result)
        self.assertTrue(any("TOP_LEVEL_KEY" in issue for issue in result["issues"]), result)

    def test_binding_check_requires_a_valid_envelope(self):
        envelope = dict(self.envelope)
        envelope["status"] = "NOT_A_STATUS"
        envelope["result_hash"] = hash_unsigned_envelope_v2(envelope)
        result = validate_result_binding_v2(
            envelope,
            expected_attempt_id="attempt-security-1",
            expected_unit_id="unit-security-1",
        )
        self.assertFalse(result["ok"], result)
        self.assertTrue(any("ENVELOPE_INVALID" in issue for issue in result["issues"]), result)

    def test_protocol_hash_api_rejects_noncanonical_data(self):
        envelope = dict(self.envelope)
        envelope["payload"] = {"ratio": 1.25}
        with self.assertRaises(ValueError):
            hash_unsigned_envelope_v2(envelope)

    def test_json_decoder_rejects_oversized_wire_input_before_parse(self):
        oversized = " " * (MAX_JSON_INPUT_BYTES + 1)
        with self.assertRaises(ValueError) as ctx:
            decode_result_envelope_v2_json(oversized)
        self.assertIn("JSON_INPUT_SIZE", str(ctx.exception))

    def test_wire_timestamps_require_builder_canonical_utc_spelling(self):
        envelope = dict(self.envelope)
        envelope["started_at_utc"] = "2026-09-14T20:00:00+02:00"
        envelope["result_hash"] = hash_unsigned_envelope_v2(envelope)
        result = validate_result_envelope_v2(envelope)
        self.assertFalse(result["ok"], result)
        self.assertTrue(any("TIME_CANONICAL" in issue for issue in result["issues"]), result)


if __name__ == "__main__":
    unittest.main()
