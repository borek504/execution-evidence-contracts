"""Three synthetic examples of the existing execution-record contract.

Run from a repository checkout: python -B demo_execution_contract.py
No test workload, agent, supervisor, network call or file write is performed.
This is example data, NOT an evidence collector or an authorization adapter.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import sys
from typing import TextIO

from r14_execution_contract import validate_execution_record


@dataclass(frozen=True)
class DemoCase:
    name: str
    explanation: str
    record: dict
    expected: dict
    context: dict
    expected_errors: tuple[str, ...]


def _bindings() -> dict:
    # These are fixture values, not measurements of this computer or interpreter.
    return {
        "attempt_id": "demo-attempt", "unit_id": "demo-unit",
        "candidate_identity_sha256": "1" * 64, "source_commit": "2" * 40,
        "source_manifest_sha256": "3" * 64,
        "qualification_scope": "FINAL_REGRESSION", "network_policy": "DENY_ALL",
        "supervisor_sha256": "4" * 64, "interpreter_sha256": "5" * 64,
        "python_version": "3.13.15", "dependency_manifest_sha256": "6" * 64,
        "policy_sha256": "7" * 64, "inventory_version": "demo-v1",
        "host_identity_sha256": "8" * 64, "guest_identity_sha256": None,
    }


def _execution() -> dict:
    return {
        "terminal_state": "SUCCEEDED", "exit_code": 0,
        "report_complete": True, "timed_out": False, "cancelled": False,
    }


def _observe_synthetic_report(record: dict, context: dict) -> None:
    # Simulate receiving these exact report contents, even in the rejection cases.
    # Updating ONLY this digest isolates the identity/inventory checks from a
    # stale-digest error. Expectations and observation bindings stay unchanged.
    # In real use, trusted observations must NOT be reconstructed from a report.
    context["record_sha256"] = sha256(json.dumps(
        record, sort_keys=True, ensure_ascii=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("ascii")).hexdigest()


def build_inputs() -> tuple[dict, dict, dict]:
    """Return fresh fixtures with fixed expectations and observation bindings."""
    record = {
        "schema_version": "jarvis-r14-execution-record-v1",
        "bindings": _bindings(),
        "tests": [
            {"test_id": name, "outcome": "PASS", "skip_reason": None,
             "skip_condition_id": None}
            for name in ("demo.value", "demo.required")
        ],
        "execution": _execution(),
        "isolation_checks": [{"check_id": "network", "outcome": "PASS"}],
        "logs": [{"log_id": "stdout", "sha256": "9" * 64}],
    }
    expected = {
        "schema_version": "jarvis-r14-execution-expectations-v1",
        "bindings": _bindings(),
        "tests": [
            {"test_id": name, "allowed_outcomes": ["PASS"],
             "required_native": False, "skip_exception": None}
            for name in ("demo.value", "demo.required")
        ],
        "required_isolation_checks": ["network"], "log_ids": ["stdout"],
    }
    context = {
        "schema_version": "jarvis-r14-execution-verifier-context-v1",
        "evidence_kind": "SYNTHETIC",
        "bindings": _bindings(), "execution": _execution(),
        "isolation_checks": [{"check_id": "network", "outcome": "PASS"}],
        "logs": [{"log_id": "stdout", "sha256": "9" * 64}],
        "satisfied_skip_conditions": [],
        "termination": {
            "attempt_id": "demo-attempt", "unit_id": "demo-unit",
            "supervisor_sha256": "4" * 64, "state": "TERMINATED",
            "receipt_sha256": "a" * 64,
        },
    }
    _observe_synthetic_report(record, context)
    return record, expected, context


def demo_cases() -> tuple[DemoCase, ...]:
    record, expected, context = build_inputs()
    consistent = DemoCase(
        "Consistent report",
        "The supplied data agree; this does not prove that tests ran.",
        record, expected, context, (),
    )

    record, expected, context = build_inputs()
    record["bindings"]["attempt_id"] = "different-attempt"
    _observe_synthetic_report(record, context)
    wrong_attempt = DemoCase(
        "Wrong attempt",
        "The report claims a different attempt_id than the fixed expectations.",
        record, expected, context, ("record.bindings.attempt_id:MISMATCH",),
    )

    record, expected, context = build_inputs()
    record["tests"] = [record["tests"][0]]
    _observe_synthetic_report(record, context)
    missing_test = DemoCase(
        "Missing required test",
        "The report omits demo.required, which is still in the expected inventory.",
        record, expected, context, ("record.tests:INVENTORY_MISMATCH",),
    )
    return consistent, wrong_attempt, missing_test


def run_demo(stream: TextIO | None = None) -> int:
    """Print actual results; exit nonzero if any example behaves unexpectedly."""
    stream = sys.stdout if stream is None else stream
    print("Execution Evidence Contracts - synthetic demo", file=stream)
    print("No real test workload is executed; no authority is granted.\n", file=stream)
    cases = demo_cases()
    matched = 0
    for index, case in enumerate(cases, start=1):
        result = validate_execution_record(
            case.record, expected=case.expected, verifier_context=case.context,
        )
        label = "ACCEPTED (data only)" if result.valid else "REJECTED"
        print(f"[{index}] {case.name}: {label}", file=stream)
        print(f"    valid={result.valid}; qualification_authorized={result.qualification_authorized}", file=stream)
        print(f"    {case.explanation}", file=stream)
        for error in result.errors:
            print(f"    {error}", file=stream)
        # Explicit checks, not assert: python -O must not disable the exit gate.
        if (result.valid is (not case.expected_errors)
                and result.errors == case.expected_errors
                and result.qualification_authorized is False
                and result.evidence_kind == "SYNTHETIC"):
            matched += 1
        else:
            print("    UNEXPECTED RESULT: demo check failed.", file=stream)
        print(file=stream)
    print(f"Demo checks: {matched}/{len(cases)} matched the expected outcomes.", file=stream)
    return 0 if matched == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(run_demo())
