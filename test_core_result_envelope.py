from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from core_result_envelope import (
    RESULT_ENVELOPE_PROTOCOL_VERSION,
    adapt_typed_result,
    build_result_envelope,
    hash_value,
    validate_result_envelope,
)


class ResultEnvelopeProfileTests(unittest.TestCase):
    def setUp(self):
        self.started = datetime(2026, 9, 14, 18, 0, tzinfo=timezone.utc)
        self.finished = self.started + timedelta(seconds=5)

    def build(self, **overrides):
        values = dict(
            result_kind="GENERIC",
            result_id="result-1",
            mission_id="mission-1",
            agent_id="agent-1",
            capability="example_capability",
            status="SUCCEEDED",
            payload={"value": 1},
            started_at_utc=self.started,
            finished_at_utc=self.finished,
            evidence_references=["evidence-1"],
            provenance_references=["source-1"],
            warnings=[],
            limitations=[],
            security_metadata={"reviewed": True},
            injection_metadata={"injection_suspected": False},
            resource_usage={"cpu_seconds": 1},
            signature_metadata={},
        )
        values.update(overrides)
        return build_result_envelope(**values)

    def test_build_and_validate_positive_envelope(self):
        envelope = self.build()
        self.assertEqual(envelope["protocol_version"], RESULT_ENVELOPE_PROTOCOL_VERSION)
        self.assertEqual(envelope["result_kind"], "GENERIC")
        self.assertEqual(envelope["capability"], "EXAMPLE_CAPABILITY")
        self.assertEqual(envelope["status"], "SUCCEEDED")
        self.assertTrue(validate_result_envelope(envelope)["ok"])

    def test_builder_normalizes_status_and_kind(self):
        envelope = self.build(result_kind="generic", status="succeeded")
        self.assertEqual(envelope["result_kind"], "GENERIC")
        self.assertEqual(envelope["status"], "SUCCEEDED")

    def test_builder_rejects_unknown_kind_and_status(self):
        with self.assertRaisesRegex(ValueError, "RESULT_KIND_INVALID"):
            self.build(result_kind="UNKNOWN")
        with self.assertRaisesRegex(ValueError, "RESULT_STATUS_INVALID"):
            self.build(status="UNKNOWN")

    def test_payload_mutation_breaks_hash_binding(self):
        envelope = self.build()
        envelope["payload"]["value"] = 2
        result = validate_result_envelope(envelope)
        self.assertFalse(result["ok"])
        self.assertIn("RESULT_ENVELOPE_HASH_INVALID", result["issues"])

    def test_missing_required_field_is_rejected(self):
        envelope = self.build()
        del envelope["provenance_references"]
        result = validate_result_envelope(envelope)
        self.assertFalse(result["ok"])
        self.assertTrue(any(issue.startswith("RESULT_ENVELOPE_FIELDS_MISSING:") for issue in result["issues"]))

    def test_empty_core_identities_are_rejected(self):
        for key in ("result_id", "mission_id", "agent_id", "capability"):
            with self.subTest(key=key):
                envelope = self.build()
                envelope[key] = ""
                unsigned = {name: value for name, value in envelope.items() if name != "result_hash"}
                envelope["result_hash"] = hash_value(unsigned)
                result = validate_result_envelope(envelope)
                self.assertFalse(result["ok"])
                self.assertIn("RESULT_ENVELOPE_IDENTITY_INVALID:" + key, result["issues"])

    def test_invalid_time_order_is_rejected(self):
        envelope = self.build()
        envelope["finished_at_utc"] = (self.started - timedelta(seconds=1)).isoformat()
        unsigned = {name: value for name, value in envelope.items() if name != "result_hash"}
        envelope["result_hash"] = hash_value(unsigned)
        result = validate_result_envelope(envelope)
        self.assertFalse(result["ok"])
        self.assertIn("RESULT_ENVELOPE_TIME_INVALID", result["issues"])

    def test_list_contracts_are_checked(self):
        for key in ("evidence_references", "provenance_references", "warnings", "limitations"):
            with self.subTest(key=key):
                envelope = self.build()
                envelope[key] = "not-a-list"
                unsigned = {name: value for name, value in envelope.items() if name != "result_hash"}
                envelope["result_hash"] = hash_value(unsigned)
                result = validate_result_envelope(envelope)
                self.assertFalse(result["ok"])
                self.assertIn("RESULT_ENVELOPE_LIST_INVALID:" + key, result["issues"])

    def test_mapping_contracts_are_checked(self):
        for key in ("payload", "security_metadata", "injection_metadata", "resource_usage", "signature_metadata"):
            with self.subTest(key=key):
                envelope = self.build()
                envelope[key] = []
                unsigned = {name: value for name, value in envelope.items() if name != "result_hash"}
                envelope["result_hash"] = hash_value(unsigned)
                result = validate_result_envelope(envelope)
                self.assertFalse(result["ok"])
                self.assertIn("RESULT_ENVELOPE_MAPPING_INVALID:" + key, result["issues"])

    def test_protocol_and_version_are_checked(self):
        envelope = self.build()
        envelope["protocol_version"] = "other"
        envelope["envelope_version"] = 2
        unsigned = {name: value for name, value in envelope.items() if name != "result_hash"}
        envelope["result_hash"] = hash_value(unsigned)
        result = validate_result_envelope(envelope)
        self.assertFalse(result["ok"])
        self.assertIn("RESULT_ENVELOPE_PROTOCOL_UNSUPPORTED", result["issues"])
        self.assertIn("RESULT_ENVELOPE_VERSION_UNSUPPORTED", result["issues"])

    def test_adapt_typed_result_maps_common_fields(self):
        source = {
            "status": "COMPLETED",
            "result_id": "typed-result",
            "mission_id": "typed-mission",
            "started_at_utc": self.started.isoformat(),
            "finished_at_utc": self.finished.isoformat(),
            "evidence_refs": ["e1"],
            "provenance_refs": ["p1"],
            "injection_suspected": True,
            "injection_flags": 2,
            "warnings": ["w1"],
            "limitations": ["l1"],
        }
        snapshot = deepcopy(source)
        envelope = adapt_typed_result(
            "GENERIC",
            source,
            agent_id="agent-1",
            capability="EXAMPLE_CAPABILITY",
        )
        self.assertEqual(source, snapshot)
        self.assertEqual(envelope["status"], "SUCCEEDED")
        self.assertEqual(envelope["evidence_references"], ["e1"])
        self.assertEqual(envelope["provenance_references"], ["p1"])
        self.assertEqual(envelope["injection_metadata"]["flag_count"], 2)
        self.assertTrue(validate_result_envelope(envelope)["ok"])

    def test_validator_rejects_non_mapping_input(self):
        self.assertEqual(
            validate_result_envelope(None),
            {"ok": False, "issues": ["RESULT_ENVELOPE_INVALID"]},
        )


if __name__ == "__main__":
    unittest.main()
