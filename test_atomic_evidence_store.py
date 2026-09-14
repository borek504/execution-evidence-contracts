from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock

from atomic_evidence_store import (
    EVIDENCE_SCHEMA_VERSION,
    EvidenceStoreError,
    MAX_EVIDENCE_BYTES,
    capture_evidence_snapshot,
    list_recent_evidence,
    validate_evidence_snapshot,
)


class AtomicEvidenceStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.evidence_dir = self.root / "evidence"
        self.now = datetime(2026, 9, 14, 21, 30, tzinfo=timezone.utc)

    def tearDown(self):
        self.tmp.cleanup()

    def capture(self, **overrides):
        values = dict(
            evidence_dir=self.evidence_dir,
            subject_id="agent-1",
            issue="health-check",
            diagnostics={"state": "DEGRADED", "attempt": 1},
            reported_status="WARN",
            now=self.now,
            evidence_id="a" * 32,
        )
        values.update(overrides)
        return capture_evidence_snapshot(**values)

    def test_capture_writes_closed_valid_snapshot(self):
        result = self.capture()
        path = Path(result["path"])
        self.assertTrue(path.is_file())
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], EVIDENCE_SCHEMA_VERSION)
        self.assertEqual(payload["evidence_id"], "a" * 32)
        self.assertEqual(payload["subject_id"], "agent-1")
        self.assertTrue(validate_evidence_snapshot(payload)["ok"])
        self.assertEqual(result["filename"], path.name)
        self.assertEqual(result["captured_at_utc"], self.now.isoformat())

    def test_permissions_are_private_on_posix(self):
        result = self.capture()
        directory_mode = stat.S_IMODE(self.evidence_dir.stat().st_mode)
        file_mode = stat.S_IMODE(Path(result["path"]).stat().st_mode)
        self.assertEqual(directory_mode, 0o700)
        self.assertEqual(file_mode, 0o600)

    def test_temp_file_is_not_left_after_success(self):
        self.capture()
        self.assertEqual(list(self.evidence_dir.glob(".evidence-*.tmp")), [])

    def test_same_final_name_fails_without_overwriting(self):
        first = self.capture()
        first_bytes = Path(first["path"]).read_bytes()
        with self.assertRaisesRegex(EvidenceStoreError, "EVIDENCE_FILENAME_COLLISION"):
            self.capture(diagnostics={"state": "DIFFERENT"})
        self.assertEqual(Path(first["path"]).read_bytes(), first_bytes)
        self.assertEqual(list(self.evidence_dir.glob(".evidence-*.tmp")), [])

    def test_publish_failure_is_fail_closed_and_cleans_temp(self):
        with mock.patch("atomic_evidence_store.os.link", side_effect=OSError("no-link")):
            with self.assertRaisesRegex(EvidenceStoreError, "EVIDENCE_ATOMIC_PUBLISH_FAILED"):
                self.capture()
        self.assertEqual(list(self.evidence_dir.glob("*.json")), [])
        self.assertEqual(list(self.evidence_dir.glob(".evidence-*.tmp")), [])

    def test_symlink_evidence_directory_is_rejected(self):
        real_dir = self.root / "real"
        real_dir.mkdir()
        link = self.root / "linked"
        link.symlink_to(real_dir, target_is_directory=True)
        with self.assertRaisesRegex(EvidenceStoreError, "EVIDENCE_DIR_SYMLINK"):
            self.capture(evidence_dir=link)
        self.assertEqual(list(real_dir.iterdir()), [])

    def test_regular_file_as_directory_is_rejected(self):
        bad = self.root / "not-a-directory"
        bad.write_text("x", encoding="utf-8")
        with self.assertRaisesRegex(EvidenceStoreError, "EVIDENCE_DIR_NOT_DIRECTORY"):
            self.capture(evidence_dir=bad)

    def test_path_like_text_cannot_escape_generated_filename(self):
        result = self.capture(subject_id="../../agent", issue="../bad/issue")
        path = Path(result["path"])
        self.assertEqual(path.parent, self.evidence_dir)
        self.assertNotIn("..", path.name)
        self.assertNotIn("/", path.name)
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["subject_id"], "../../agent")
        self.assertEqual(payload["issue"], "../bad/issue")

    def test_nonfinite_json_is_rejected_before_any_write(self):
        with self.assertRaisesRegex(EvidenceStoreError, "EVIDENCE_NOT_CANONICAL_JSON"):
            self.capture(diagnostics={"value": float("nan")})
        self.assertFalse(self.evidence_dir.exists())

    def test_unsupported_json_value_is_rejected_before_any_write(self):
        with self.assertRaisesRegex(EvidenceStoreError, "EVIDENCE_NOT_CANONICAL_JSON"):
            self.capture(diagnostics={"value": object()})
        self.assertFalse(self.evidence_dir.exists())

    def test_evidence_size_limit_is_rejected_before_any_write(self):
        with self.assertRaisesRegex(EvidenceStoreError, "EVIDENCE_SIZE_LIMIT"):
            self.capture(diagnostics={"blob": "x" * MAX_EVIDENCE_BYTES})
        self.assertFalse(self.evidence_dir.exists())

    def test_naive_capture_time_is_rejected(self):
        with self.assertRaisesRegex(EvidenceStoreError, "CAPTURE_TIME_MUST_BE_TIMEZONE_AWARE"):
            self.capture(now=datetime(2026, 9, 14, 21, 30))
        self.assertFalse(self.evidence_dir.exists())

    def test_invalid_subject_issue_status_and_id_are_rejected(self):
        cases = [
            ({"subject_id": ""}, "SUBJECT_ID_INVALID"),
            ({"subject_id": 4}, "SUBJECT_ID_TYPE_INVALID"),
            ({"issue": " line\nbreak"}, "ISSUE_INVALID"),
            ({"reported_status": 3}, "REPORTED_STATUS_TYPE_INVALID"),
            ({"evidence_id": "not-hex"}, "EVIDENCE_ID_INVALID"),
        ]
        for overrides, code in cases:
            with self.subTest(code=code):
                with self.assertRaisesRegex(EvidenceStoreError, code):
                    self.capture(**overrides)

    def test_snapshot_validator_is_closed_and_canonical_time_only(self):
        self.capture()
        payload = json.loads(next(self.evidence_dir.glob("*.json")).read_text(encoding="utf-8"))

        extra = dict(payload)
        extra["authority"] = "release"
        result = validate_evidence_snapshot(extra)
        self.assertFalse(result["ok"])
        self.assertIn("EVIDENCE_FIELDS_INVALID", result["issues"])

        alternate_time = dict(payload)
        alternate_time["captured_at_utc"] = "2026-09-14T23:30:00+02:00"
        result = validate_evidence_snapshot(alternate_time)
        self.assertFalse(result["ok"])
        self.assertIn("EVIDENCE_TIMESTAMP_INVALID", result["issues"])

    def test_list_recent_returns_valid_snapshots_newest_first(self):
        first = self.capture(evidence_id="1" * 32, now=self.now)
        second = self.capture(
            evidence_id="2" * 32,
            now=self.now + timedelta(seconds=1),
            issue="second",
        )
        items = list_recent_evidence(self.evidence_dir)
        self.assertEqual([item["evidence_id"] for item in items], ["2" * 32, "1" * 32])
        self.assertEqual(items[0]["filename"], Path(second["path"]).name)
        self.assertEqual(items[1]["filename"], Path(first["path"]).name)

    def test_list_limit_is_bounded_and_bool_is_not_an_int(self):
        self.capture()
        for value in (0, 101, True, 1.5):
            with self.subTest(value=value):
                with self.assertRaisesRegex(EvidenceStoreError, "EVIDENCE_LIMIT_INVALID"):
                    list_recent_evidence(self.evidence_dir, limit=value)
        self.assertEqual(len(list_recent_evidence(self.evidence_dir, limit=1)), 1)

    def test_list_skips_corrupt_oversized_and_symlink_entries(self):
        valid = self.capture()
        (self.evidence_dir / "zz-corrupt.json").write_text("{", encoding="utf-8")
        (self.evidence_dir / "zz-large.json").write_bytes(b"x" * (MAX_EVIDENCE_BYTES + 2))
        external = self.root / "external.json"
        external.write_text(Path(valid["path"]).read_text(encoding="utf-8"), encoding="utf-8")
        (self.evidence_dir / "zz-link.json").symlink_to(external)
        items = list_recent_evidence(self.evidence_dir)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["evidence_id"], "a" * 32)

    def test_missing_directory_lists_as_empty_without_creating_it(self):
        missing = self.root / "missing"
        self.assertEqual(list_recent_evidence(missing), [])
        self.assertFalse(missing.exists())

    def test_listing_symlink_directory_is_rejected(self):
        real_dir = self.root / "real-list"
        real_dir.mkdir()
        link = self.root / "linked-list"
        link.symlink_to(real_dir, target_is_directory=True)
        with self.assertRaisesRegex(EvidenceStoreError, "EVIDENCE_DIR_INVALID"):
            list_recent_evidence(link)


if __name__ == "__main__":
    unittest.main()
