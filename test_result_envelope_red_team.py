from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import unittest

from core_result_envelope import (
    build_result_envelope,
    canonical_json,
    hash_value,
    validate_result_envelope,
)


class ResultEnvelopeRedTeamCharacterizationTests(unittest.TestCase):
    """Characterize known v1 permissive behavior before any v2 redesign.

    These tests intentionally assert CURRENT v1 behavior. Passing them does not
    mean the behavior is desirable. They exist so a future v2 can change these
    semantics explicitly instead of silently reinterpreting v1.
    """

    def build(self, **overrides):
        values = dict(
            result_kind="GENERIC",
            result_id="result-1",
            mission_id="mission-1",
            agent_id="agent-1",
            capability="example",
            status="SUCCEEDED",
            payload={"value": 1},
            started_at_utc=datetime(2026, 9, 14, 18, 0, tzinfo=timezone.utc),
            finished_at_utc=datetime(2026, 9, 14, 18, 0, 1, tzinfo=timezone.utc),
        )
        values.update(overrides)
        return build_result_envelope(**values)

    @staticmethod
    def rehash(envelope):
        unsigned = {key: value for key, value in envelope.items() if key != "result_hash"}
        envelope["result_hash"] = hash_value(unsigned)

    def test_unknown_top_level_field_is_accepted_after_rehash(self):
        envelope = self.build()
        envelope["future_authority"] = "candidate-controlled"
        self.rehash(envelope)
        self.assertTrue(validate_result_envelope(envelope)["ok"])

    def test_non_finite_float_is_serialized_and_accepted(self):
        envelope = self.build(payload={"score": float("nan")})
        self.assertIn("NaN", canonical_json(envelope))
        self.assertTrue(validate_result_envelope(envelope)["ok"])

    def test_invalid_timestamp_strings_are_repaired_to_current_time(self):
        envelope = self.build(
            started_at_utc="not-a-timestamp",
            finished_at_utc="also-not-a-timestamp",
        )
        self.assertNotEqual(envelope["started_at_utc"], "not-a-timestamp")
        self.assertNotEqual(envelope["finished_at_utc"], "also-not-a-timestamp")
        self.assertTrue(validate_result_envelope(envelope)["ok"])

    def test_naive_timestamp_strings_are_interpreted_as_utc(self):
        envelope = self.build(
            started_at_utc="2026-09-14T18:00:00",
            finished_at_utc="2026-09-14T18:00:01",
        )
        self.assertTrue(envelope["started_at_utc"].endswith("+00:00"))
        self.assertTrue(envelope["finished_at_utc"].endswith("+00:00"))
        self.assertTrue(validate_result_envelope(envelope)["ok"])

    def test_builder_coerces_wrong_identity_types_to_strings(self):
        envelope = self.build(
            result_id=123,
            mission_id=True,
            agent_id={"id": 7},
            capability=42,
        )
        self.assertEqual(envelope["result_id"], "123")
        self.assertEqual(envelope["mission_id"], "True")
        self.assertEqual(envelope["agent_id"], "{'id': 7}")
        self.assertEqual(envelope["capability"], "42")
        self.assertTrue(validate_result_envelope(envelope)["ok"])

    def test_validator_accepts_non_string_identity_after_rehash(self):
        envelope = self.build()
        envelope["result_id"] = {"nested": "identity"}
        self.rehash(envelope)
        self.assertTrue(validate_result_envelope(envelope)["ok"])

    def test_evidence_and_provenance_contents_are_opaque(self):
        envelope = self.build(
            evidence_references=[{"arbitrary": ["nested", 1]}, 42, True],
            provenance_references=[{"source": {"shape": "unchecked"}}],
        )
        self.assertTrue(validate_result_envelope(envelope)["ok"])

    def test_hash_is_raw_sha256_of_canonical_json_without_domain_prefix(self):
        value = {"same": "bytes"}
        expected = sha256(canonical_json(value).encode("utf-8")).hexdigest()
        self.assertEqual(hash_value(value), expected)


if __name__ == "__main__":
    unittest.main()
