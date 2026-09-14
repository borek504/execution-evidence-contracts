from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from atomic_evidence_store import (
    EvidenceStoreError,
    capture_evidence_snapshot,
    list_recent_evidence,
)


class AtomicEvidenceStoreRedTeamTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.evidence_dir = self.root / "evidence"
        self.now = datetime(2026, 9, 14, 22, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.tmp.cleanup()

    def capture(self, *, evidence_dir=None, evidence_id="a" * 32, **overrides):
        values = dict(
            evidence_dir=evidence_dir or self.evidence_dir,
            subject_id="agent-1",
            issue="incident",
            diagnostics={"state": "WARN"},
            reported_status="WARN",
            now=self.now,
            evidence_id=evidence_id,
        )
        values.update(overrides)
        return capture_evidence_snapshot(**values)

    def test_unsupported_platform_fails_before_directory_creation(self):
        with mock.patch("atomic_evidence_store.os.name", "nt"):
            with self.assertRaisesRegex(EvidenceStoreError, "EVIDENCE_PLATFORM_UNSUPPORTED"):
                self.capture()
        self.assertFalse(self.evidence_dir.exists())

    def test_existing_private_directory_permissions_are_tightened_on_capture(self):
        self.evidence_dir.mkdir(mode=0o755)
        self.evidence_dir.chmod(0o755)
        self.capture()
        self.assertEqual(self.evidence_dir.stat().st_mode & 0o777, 0o700)

    def test_listing_rejects_directory_with_broadened_permissions(self):
        self.capture()
        self.evidence_dir.chmod(0o755)
        with self.assertRaisesRegex(EvidenceStoreError, "EVIDENCE_DIR_PERMISSIONS_INVALID"):
            list_recent_evidence(self.evidence_dir)

    def test_listing_skips_snapshot_with_broadened_file_permissions(self):
        result = self.capture()
        Path(result["path"]).chmod(0o644)
        self.assertEqual(list_recent_evidence(self.evidence_dir), [])

    def test_listing_rejects_renamed_snapshot_even_when_content_is_valid(self):
        result = self.capture()
        path = Path(result["path"])
        renamed = path.with_name("zz-" + path.name)
        path.rename(renamed)
        self.assertEqual(list_recent_evidence(self.evidence_dir), [])

    def test_deep_malformed_json_cannot_crash_listing(self):
        valid = self.capture()
        hostile = self.evidence_dir / "zz-hostile.json"
        hostile.write_text("[" * 2000 + "0" + "]" * 2000, encoding="utf-8")
        hostile.chmod(0o600)
        items = list_recent_evidence(self.evidence_dir)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["evidence_id"], valid["evidence_id"])

    def test_precreated_symlink_at_final_name_cannot_be_overwritten(self):
        scratch = self.root / "scratch"
        expected = self.capture(evidence_dir=scratch, evidence_id="b" * 32)

        self.evidence_dir.mkdir(mode=0o700)
        self.evidence_dir.chmod(0o700)
        target = self.root / "outside.txt"
        target.write_text("sentinel", encoding="utf-8")
        collision = self.evidence_dir / expected["filename"]
        collision.symlink_to(target)

        with self.assertRaisesRegex(EvidenceStoreError, "EVIDENCE_FILENAME_COLLISION"):
            self.capture(evidence_dir=self.evidence_dir, evidence_id="b" * 32)

        self.assertTrue(collision.is_symlink())
        self.assertEqual(target.read_text(encoding="utf-8"), "sentinel")
        self.assertEqual(list(self.evidence_dir.glob(".evidence-*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
