"""Demo regressions; all inputs are synthetic and no workload is executed."""
from io import StringIO
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import demo_execution_contract as demo
from r14_execution_contract import ContractValidation, validate_execution_record

ROOT = Path(__file__).resolve().parent


class DemoTests(unittest.TestCase):
    def test_three_cases_have_exact_outcomes_and_no_authority(self):
        cases = demo.demo_cases()
        self.assertEqual(len(cases), 3)
        for case, valid, errors in zip(cases, (True, False, False), (
            (), ("record.bindings.attempt_id:MISMATCH",),
            ("record.tests:INVENTORY_MISMATCH",),
        )):
            with self.subTest(case=case.name):
                result = validate_execution_record(
                    case.record, expected=case.expected, verifier_context=case.context,
                )
                self.assertIs(result.valid, valid)
                self.assertEqual(result.errors, errors)
                self.assertEqual(case.expected_errors, errors)
                self.assertIs(result.qualification_authorized, False)
                self.assertEqual(result.evidence_kind, "SYNTHETIC")

    def test_fixture_inputs_are_fresh_and_do_not_share_mutable_bindings(self):
        record, expected, context = demo.build_inputs()
        record["bindings"]["attempt_id"] = "changed"
        record["execution"]["exit_code"] = 99
        self.assertEqual(expected["bindings"]["attempt_id"], "demo-attempt")
        self.assertEqual(context["bindings"]["attempt_id"], "demo-attempt")
        self.assertEqual(context["execution"]["exit_code"], 0)
        self.assertEqual(demo.build_inputs()[0]["bindings"]["attempt_id"], "demo-attempt")

    def test_demo_reports_actual_results_and_success(self):
        stream = StringIO()
        self.assertEqual(demo.run_demo(stream), 0)
        text = stream.getvalue()
        self.assertEqual(text.count("qualification_authorized=False"), 3)
        self.assertIn("Demo checks: 3/3 matched the expected outcomes.", text)
        self.assertNotIn("UNEXPECTED RESULT", text)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.startswith("["):
                self.assertIn(line, readme)

    def test_unexpected_acceptance_is_a_failure(self):
        with patch.object(demo, "validate_execution_record", return_value=ContractValidation(True, (), "SYNTHETIC")):
            self.assertEqual(demo.run_demo(StringIO()), 1)

    def test_wrong_rejection_reason_is_a_failure(self):
        with patch.object(demo, "validate_execution_record", return_value=ContractValidation(False, ("wrong:REASON",), "SYNTHETIC")):
            self.assertEqual(demo.run_demo(StringIO()), 1)

    def test_authorizing_result_is_a_failure(self):
        fake = SimpleNamespace(valid=True, errors=(), evidence_kind="SYNTHETIC", qualification_authorized=True)
        with patch.object(demo, "validate_execution_record", return_value=fake):
            stream = StringIO()
            self.assertEqual(demo.run_demo(stream), 1)
            self.assertIn("UNEXPECTED RESULT", stream.getvalue())

    def test_documented_command_works_and_optimization_keeps_failure_gate(self):
        run = subprocess.run(
            [sys.executable, "-B", "demo_execution_contract.py"], cwd=ROOT,
            capture_output=True, text=True, timeout=10, check=False,
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("Demo checks: 3/3", run.stdout)
        code = (
            "from io import StringIO; from unittest.mock import patch; "
            "import demo_execution_contract as demo; "
            "from r14_execution_contract import ContractValidation; "
            "p=patch.object(demo, 'validate_execution_record', "
            "return_value=ContractValidation(True, (), 'SYNTHETIC')); "
            "p.start(); raise SystemExit(demo.run_demo(StringIO()))"
        )
        run = subprocess.run(
            [sys.executable, "-O", "-B", "-c", code], cwd=ROOT,
            capture_output=True, text=True, timeout=10, check=False,
        )
        self.assertEqual(run.returncode, 1, run.stderr)
        self.assertEqual(run.stderr, "")


if __name__ == "__main__":
    unittest.main()
