"""Pure, fail-closed validation of the proposed R14 execution record (package A).

This module does not import JARVIS, run tests, inspect processes, read artifacts,
or authorize a release. ``valid`` means only that the supplied data agree with
this contract. It is NOT proof of execution, isolation, or authentic provenance.

``expected`` must be fixed independently before execution. ``verifier_context``
must come from a future trusted supervisor, outside the candidate's control.
Neither input may be reconstructed from the candidate's report. Authentication,
artifact collection and whole-unit termination are outside this pure validator.
Tests use explicitly SYNTHETIC observations; P1 remains open.

Only ordinary JSON-shaped dict/list/scalar values are accepted. Unknown keys,
types and schema versions are rejected. There is no legacy fallback or repair.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re


RECORD_VERSION = "jarvis-r14-execution-record-v1"
EXPECTED_VERSION = "jarvis-r14-execution-expectations-v1"
CONTEXT_VERSION = "jarvis-r14-execution-verifier-context-v1"
REQUIRED_PYTHON_VERSION = "3.13.15"

_BINDING_KEYS = frozenset({
    "attempt_id", "candidate_identity_sha256", "source_commit",
    "source_manifest_sha256", "qualification_scope", "supervisor_sha256",
    "interpreter_sha256", "python_version", "dependency_manifest_sha256",
    "policy_sha256", "network_policy", "inventory_version", "unit_id",
    "host_identity_sha256", "guest_identity_sha256",
})
_EXECUTION_KEYS = frozenset({
    "terminal_state", "exit_code", "report_complete", "timed_out", "cancelled",
})
_NETWORK_BY_SCOPE = {
    "CANDIDATE_QUALIFICATION": "LOCAL_LOOPBACK_ONLY_SEATBELT",
    "FINAL_REGRESSION": "DENY_ALL",
}
_SUCCESS_OUTCOMES = frozenset({"PASS", "EXPECTED_FAILURE"})
_ALL_OUTCOMES = _SUCCESS_OUTCOMES | {"FAIL", "ERROR", "UNEXPECTED_SUCCESS", "SKIP"}


@dataclass(frozen=True)
class ContractValidation:
    """A data-validation result, never an authorization token."""

    valid: bool
    errors: tuple[str, ...]
    evidence_kind: str | None

    @property
    def qualification_authorized(self) -> bool:
        return False

    def __bool__(self) -> bool:
        raise TypeError("Inspect .valid; a contract result is not release authority")


class _Rejected(ValueError):
    pass


def _require(condition: bool, path: str, code: str) -> None:
    if not condition:
        raise _Rejected(f"{path}:{code}")


def _object(value: object, keys: set[str] | frozenset[str], path: str) -> dict:
    _require(type(value) is dict, path, "OBJECT_REQUIRED")
    _require(all(type(key) is str for key in value), path, "STRING_KEYS_REQUIRED")
    _require(set(value) == keys, path, "SCHEMA_KEYS_MISMATCH")
    return value


def _text(value: object, path: str) -> str:
    _require(type(value) is str and bool(value.strip()), path, "NONEMPTY_STRING_REQUIRED")
    _require(value == value.strip() and all(ord(c) >= 32 for c in value), path, "INVALID_STRING")
    return value


def _boolean(value: object, path: str) -> bool:
    _require(type(value) is bool, path, "BOOLEAN_REQUIRED")
    return value


def _digest(value: object, path: str, length: int = 64) -> str:
    _require(type(value) is str, path, "DIGEST_REQUIRED")
    _require(re.fullmatch(r"[0-9a-f]{" + str(length) + r"}", value) is not None,
             path, "INVALID_DIGEST")
    return value


def _strings(value: object, path: str, *, nonempty: bool = True) -> list[str]:
    _require(type(value) is list, path, "LIST_REQUIRED")
    _require(not nonempty or bool(value), path, "EMPTY_LIST")
    for item in value:
        _text(item, path)
    _require(len(set(value)) == len(value), path, "DUPLICATE_ID")
    return value


def _bindings(value: object, path: str) -> dict:
    value = _object(value, _BINDING_KEYS, path)
    for key, item in value.items():
        item_path = f"{path}.{key}"
        if key == "guest_identity_sha256" and item is None:
            continue  # An explicitly native execution has no guest identity.
        if key.endswith("_sha256"):
            _digest(item, item_path)
        elif key == "source_commit":
            _digest(item, item_path, 40)
        else:
            _text(item, item_path)
    scope = value["qualification_scope"]
    _require(scope in _NETWORK_BY_SCOPE, path, "UNKNOWN_QUALIFICATION_SCOPE")
    _require(value["network_policy"] == _NETWORK_BY_SCOPE[scope], path, "NETWORK_POLICY_MISMATCH")
    _require(value["python_version"] == REQUIRED_PYTHON_VERSION, path, "PYTHON_VERSION_MISMATCH")
    return value


def _execution(value: object, path: str) -> dict:
    value = _object(value, _EXECUTION_KEYS, path)
    _text(value["terminal_state"], path + ".terminal_state")
    _require(type(value["exit_code"]) is int, path + ".exit_code", "INTEGER_REQUIRED")
    for key in ("report_complete", "timed_out", "cancelled"):
        _boolean(value[key], path + "." + key)
    return value


def _rows(value: object, keys: set[str], id_key: str, path: str) -> dict[str, dict]:
    _require(type(value) is list, path, "LIST_REQUIRED")
    _require(bool(value), path, "EMPTY_LIST")
    result = {}
    for index, row in enumerate(value):
        row_path = f"{path}[{index}]"
        row = _object(row, keys, row_path)
        key = _text(row[id_key], row_path + "." + id_key)
        _require(key not in result, path, "DUPLICATE_ID")
        result[key] = row
    return result


def _logs(value: object, path: str) -> dict[str, dict]:
    rows = _rows(value, {"log_id", "sha256"}, "log_id", path)
    for key, row in rows.items():
        _digest(row["sha256"], f"{path}.{key}.sha256")
    return rows


def _checks(value: object, path: str) -> dict[str, dict]:
    rows = _rows(value, {"check_id", "outcome"}, "check_id", path)
    for key, row in rows.items():
        _text(row["outcome"], f"{path}.{key}.outcome")
    return rows


def _expected_tests(value: object) -> dict[str, dict]:
    path = "expected.tests"
    rows = _rows(value, {"test_id", "allowed_outcomes", "required_native", "skip_exception"},
                 "test_id", path)
    for key, row in rows.items():
        p = f"{path}.{key}"
        outcomes = _strings(row["allowed_outcomes"], p + ".allowed_outcomes")
        _require(set(outcomes) <= _SUCCESS_OUTCOMES, p, "INVALID_ALLOWED_OUTCOME")
        native = _boolean(row["required_native"], p + ".required_native")
        exception = row["skip_exception"]
        if exception is not None:
            exception = _object(exception, {"reason", "condition_id"}, p + ".skip_exception")
            _text(exception["reason"], p + ".skip_exception.reason")
            _text(exception["condition_id"], p + ".skip_exception.condition_id")
        _require(not native or (outcomes == ["PASS"] and exception is None),
                 p, "NATIVE_TEST_REQUIRES_PASS")
    return rows


def _reported_tests(value: object) -> dict[str, dict]:
    path = "record.tests"
    rows = _rows(value, {"test_id", "outcome", "skip_reason", "skip_condition_id"}, "test_id", path)
    for key, row in rows.items():
        p = f"{path}.{key}"
        outcome = _text(row["outcome"], p + ".outcome")
        _require(outcome in _ALL_OUTCOMES, p, "UNKNOWN_TEST_OUTCOME")
        if outcome == "SKIP":
            _text(row["skip_reason"], p + ".skip_reason")
            _text(row["skip_condition_id"], p + ".skip_condition_id")
        else:
            _require(row["skip_reason"] is None and row["skip_condition_id"] is None,
                     p, "UNEXPECTED_SKIP_DETAILS")
    return rows


def validate_execution_record(
    record: object, *, expected: object, verifier_context: object,
) -> ContractValidation:
    """Validate three independent inputs without side effects or release authority.

    The first schema error is returned; after shapes are valid, semantic errors
    are collected in deterministic order. All versions are closed and explicit.
    ``evidence_kind`` labels supplied observations; it does not authenticate them.
    The record digest covers canonical JSON, not original file bytes. Other
    digests are compared, not computed from files. A caller must establish the
    origins of expected/context, including the bound full-unit termination receipt.
    """
    try:
        return _validate(record, expected, verifier_context)
    except _Rejected as error:
        return ContractValidation(False, (str(error),), None)


def _validate(record: object, expected: object, context: object) -> ContractValidation:
    record = _object(record, {"schema_version", "bindings", "tests", "execution", "isolation_checks", "logs"}, "record")
    expected = _object(expected, {"schema_version", "bindings", "tests", "required_isolation_checks", "log_ids"}, "expected")
    context = _object(context, {"schema_version", "evidence_kind", "record_sha256", "bindings", "execution", "isolation_checks", "logs", "satisfied_skip_conditions", "termination"}, "context")
    for label, obj, version in (("record", record, RECORD_VERSION), ("expected", expected, EXPECTED_VERSION), ("context", context, CONTEXT_VERSION)):
        _require(type(obj["schema_version"]) is str and obj["schema_version"] == version,
                 label, "UNSUPPORTED_VERSION")
    kind = _text(context["evidence_kind"], "context.evidence_kind")
    _require(kind in {"SYNTHETIC", "SUPERVISOR_OBSERVATION"}, "context", "UNKNOWN_EVIDENCE_KIND")
    observed_record_digest = _digest(context["record_sha256"], "context.record_sha256")
    rb = _bindings(record["bindings"], "record.bindings")
    eb = _bindings(expected["bindings"], "expected.bindings")
    cb = _bindings(context["bindings"], "context.bindings")
    expected_tests = _expected_tests(expected["tests"])
    reported_tests = _reported_tests(record["tests"])
    checks_expected = set(_strings(expected["required_isolation_checks"], "expected.required_isolation_checks"))
    logs_expected = set(_strings(expected["log_ids"], "expected.log_ids"))
    conditions = set(_strings(context["satisfied_skip_conditions"], "context.satisfied_skip_conditions", nonempty=False))
    rexe = _execution(record["execution"], "record.execution")
    cexe = _execution(context["execution"], "context.execution")
    rchecks = _checks(record["isolation_checks"], "record.isolation_checks")
    cchecks = _checks(context["isolation_checks"], "context.isolation_checks")
    rlogs = _logs(record["logs"], "record.logs")
    clogs = _logs(context["logs"], "context.logs")
    termination = _object(context["termination"], {"attempt_id", "unit_id", "supervisor_sha256", "state", "receipt_sha256"}, "context.termination")
    for key in ("attempt_id", "unit_id", "state"):
        _text(termination[key], "context.termination." + key)
    for key in ("supervisor_sha256", "receipt_sha256"):
        _digest(termination[key], "context.termination." + key)

    errors = []

    def check(condition: bool, code: str) -> None:
        if not condition:
            errors.append(code)

    try:
        canonical_record = json.dumps(
            record, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False,
        ).encode("ascii")
    except (ValueError, TypeError, OverflowError):
        raise _Rejected("record:INVALID_CANONICAL_JSON") from None
    record_digest = sha256(canonical_record).hexdigest()
    check(record_digest == observed_record_digest, "record:OBSERVED_DIGEST_MISMATCH")
    for label, actual in (("record", rb), ("context", cb)):
        for key in sorted(_BINDING_KEYS):
            check(actual[key] == eb[key], f"{label}.bindings.{key}:MISMATCH")
    check(set(reported_tests) == set(expected_tests), "record.tests:INVENTORY_MISMATCH")
    executed = 0
    declared_conditions = {row["skip_exception"]["condition_id"] for row in expected_tests.values() if row["skip_exception"] is not None}
    check(conditions <= declared_conditions, "context.satisfied_skip_conditions:UNKNOWN_CONDITION")
    for key in sorted(set(reported_tests) & set(expected_tests)):
        reported = reported_tests[key]
        spec = expected_tests[key]
        outcome = reported["outcome"]
        if outcome == "SKIP":
            exception = spec["skip_exception"]
            allowed = (not spec["required_native"] and exception is not None
                       and reported["skip_reason"] == exception["reason"]
                       and reported["skip_condition_id"] == exception["condition_id"]
                       and exception["condition_id"] in conditions)
            check(allowed, f"record.tests.{key}:SKIP_NOT_AUTHORIZED")
        else:
            executed += 1
            check(outcome in spec["allowed_outcomes"], f"record.tests.{key}:OUTCOME_NOT_ALLOWED")
    check(executed > 0, "record.tests:NO_EXECUTED_TESTS")
    for label, execution in (("record", rexe), ("context", cexe)):
        check(execution["terminal_state"] == "SUCCEEDED", label + ".execution:NOT_SUCCEEDED")
        check(execution["exit_code"] == 0, label + ".execution:NONZERO_EXIT")
        check(execution["report_complete"], label + ".execution:INCOMPLETE_REPORT")
        check(not execution["timed_out"], label + ".execution:TIMED_OUT")
        check(not execution["cancelled"], label + ".execution:CANCELLED")
    check(rexe == cexe, "record.execution:OBSERVATION_MISMATCH")
    for label, checks in (("record", rchecks), ("context", cchecks)):
        check(set(checks) == checks_expected, label + ".isolation_checks:INVENTORY_MISMATCH")
        for key in sorted(checks):
            check(checks[key]["outcome"] == "PASS", f"{label}.isolation_checks.{key}:NOT_PASS")
    check(rchecks == cchecks, "record.isolation_checks:OBSERVATION_MISMATCH")
    for label, logs in (("record", rlogs), ("context", clogs)):
        check(set(logs) == logs_expected, label + ".logs:INVENTORY_MISMATCH")
    check(rlogs == clogs, "record.logs:OBSERVATION_MISMATCH")
    for key in ("attempt_id", "unit_id", "supervisor_sha256"):
        check(termination[key] == eb[key], f"context.termination.{key}:MISMATCH")
    check(termination["state"] == "TERMINATED", "context.termination:UNIT_NOT_TERMINATED")
    return ContractValidation(not errors, tuple(errors), kind)
