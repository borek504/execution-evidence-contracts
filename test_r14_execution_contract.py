"""Synthetic package-A tests; no JARVIS imports or native qualification."""

from copy import deepcopy
from hashlib import sha256
import json
import unittest

from r14_execution_contract import validate_execution_record


def bindings():
    return {
        "attempt_id": "synthetic-attempt-1", "unit_id": "synthetic-unit-1",
        "candidate_identity_sha256": "1" * 64, "source_commit": "2" * 40,
        "source_manifest_sha256": "3" * 64,
        "qualification_scope": "FINAL_REGRESSION", "network_policy": "DENY_ALL",
        "supervisor_sha256": "4" * 64, "interpreter_sha256": "5" * 64,
        "python_version": "3.13.15", "dependency_manifest_sha256": "6" * 64,
        "policy_sha256": "7" * 64, "inventory_version": "synthetic-inventory-v1",
        "host_identity_sha256": "8" * 64, "guest_identity_sha256": None,
    }


def execution():
    return dict(terminal_state="SUCCEEDED", exit_code=0, report_complete=True,
                timed_out=False, cancelled=False)


def checks():
    return [dict(check_id=x, outcome="PASS") for x in ("filesystem", "network", "process")]


def logs():
    return [dict(log_id="stdout", sha256="9" * 64), dict(log_id="stderr", sha256="a" * 64)]


def seal(record, context):
    # The fixture simulates independent receipt of a complete report. No digest
    # implementation or fixture builder is imported from the module under test.
    context["record_sha256"] = sha256(json.dumps(
        record, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False,
    ).encode("ascii")).hexdigest()


def case():
    # Construct expectations/observations independently, not from record fields.
    record = {
        "schema_version": "jarvis-r14-execution-record-v1", "bindings": bindings(),
        "tests": [dict(test_id=x, outcome="PASS", skip_reason=None, skip_condition_id=None)
                  for x in ("suite.value", "suite.native", "suite.optional")],
        "execution": execution(), "isolation_checks": checks(), "logs": logs(),
    }
    expected = {
        "schema_version": "jarvis-r14-execution-expectations-v1", "bindings": bindings(),
        "tests": [
            dict(test_id="suite.value", allowed_outcomes=["PASS"], required_native=False, skip_exception=None),
            dict(test_id="suite.native", allowed_outcomes=["PASS"], required_native=True, skip_exception=None),
            dict(test_id="suite.optional", allowed_outcomes=["PASS"], required_native=False,
                 skip_exception=dict(reason="Optional service not requested", condition_id="OPTIONAL_DISABLED")),
        ],
        "required_isolation_checks": ["filesystem", "network", "process"],
        "log_ids": ["stdout", "stderr"],
    }
    context = {
        "schema_version": "jarvis-r14-execution-verifier-context-v1", "evidence_kind": "SYNTHETIC",
        "bindings": bindings(), "execution": execution(), "isolation_checks": checks(), "logs": logs(),
        "satisfied_skip_conditions": [],
        "termination": dict(attempt_id="synthetic-attempt-1", unit_id="synthetic-unit-1",
                            supervisor_sha256="4" * 64, state="TERMINATED", receipt_sha256="b" * 64),
    }
    seal(record, context)
    return record, expected, context


def validate(values):
    r, e, c = values
    return validate_execution_record(r, expected=e, verifier_context=c)


class ExecutionContractTests(unittest.TestCase):
    def assertRejected(self, values, *, reseal=True):
        if reseal:
            try:
                seal(values[0], values[2])
            except (TypeError, ValueError):
                pass  # A malformed JSON-shaped input must still be rejected.
        result = validate(values)
        self.assertFalse(result.valid)
        self.assertTrue(result.errors)
        self.assertFalse(result.qualification_authorized)
        return result

    def test_positive_synthetic_record_has_no_authority(self):
        result = validate(case())
        self.assertTrue(result.valid, result.errors)
        self.assertEqual(result.errors, ())
        self.assertEqual(result.evidence_kind, "SYNTHETIC")
        self.assertFalse(result.qualification_authorized)
        with self.assertRaises(TypeError):
            bool(result)

    def test_positive_candidate_scope_and_guest_identity(self):
        values = case()
        for item in values:
            item["bindings"]["qualification_scope"] = "CANDIDATE_QUALIFICATION"
            item["bindings"]["network_policy"] = "LOCAL_LOOPBACK_ONLY_SEATBELT"
            item["bindings"]["guest_identity_sha256"] = "c" * 64
        seal(values[0], values[2])
        self.assertTrue(validate(values).valid)

    def test_supervisor_label_does_not_authorize_qualification(self):
        values = case(); values[2]["evidence_kind"] = "SUPERVISOR_OBSERVATION"
        result = validate(values)
        self.assertTrue(result.valid)
        self.assertFalse(result.qualification_authorized)

    def test_closed_top_level_schemas(self):
        for index in range(3):
            for key in case()[index]:
                with self.subTest(input=index, missing=key):
                    values = case(); del values[index][key]
                    self.assertRejected(values, reseal=False)
            with self.subTest(input=index, extra=True):
                values = case(); values[index]["new_authority"] = True
                self.assertRejected(values)
            for wrong in (None, [], "record", 0, True):
                with self.subTest(input=index, wrong=wrong):
                    values = list(case()); values[index] = wrong
                    self.assertRejected(values, reseal=False)

    def test_unknown_or_wrong_type_versions(self):
        for index in range(3):
            for version in ("v0", "v99", 1, True, None):
                with self.subTest(input=index, version=version):
                    values = case(); values[index]["schema_version"] = version
                    self.assertRejected(values)

    def test_closed_nested_schemas(self):
        paths = [(i, ("bindings",)) for i in range(3)]
        paths += [(i, ("execution",)) for i in (0, 2)]
        paths += [(i, ("logs", 0)) for i in (0, 2)]
        paths += [(i, ("isolation_checks", 0)) for i in (0, 2)]
        paths += [(0, ("tests", 0)), (1, ("tests", 0)), (2, ("termination",)),
                  (1, ("tests", 2, "skip_exception"))]
        for index, path in paths:
            for change in ("missing", "extra"):
                with self.subTest(input=index, path=path, change=change):
                    values = case(); obj = values[index]
                    for key in path:
                        obj = obj[key]
                    if change == "missing":
                        obj.pop(next(iter(obj)))
                    else:
                        obj["unexpected"] = True
                    self.assertRejected(values)

    def test_all_bindings_are_compared_in_each_input(self):
        for index in range(3):
            for key, old in bindings().items():
                with self.subTest(input=index, key=key):
                    values = case()
                    replacement = ("d" * 64 if key.endswith("_sha256") else
                                   "e" * 40 if key == "source_commit" else str(old) + "-other")
                    values[index]["bindings"][key] = replacement
                    self.assertRejected(values)

    def test_binding_types_and_digest_format(self):
        for key, bad in (("source_commit", "a" * 64), ("policy_sha256", "G" * 64),
                         ("host_identity_sha256", ""), ("guest_identity_sha256", 1),
                         ("attempt_id", "  attempt"), ("unit_id", "unit\n"),
                         ("inventory_version", True)):
            with self.subTest(key=key, bad=bad):
                values = case(); values[0]["bindings"][key] = bad
                self.assertRejected(values)

    def test_network_scope_cannot_be_relaxed_even_in_all_inputs(self):
        for scope, network in (("FINAL_REGRESSION", "LOCAL_LOOPBACK_ONLY_SEATBELT"),
                               ("CANDIDATE_QUALIFICATION", "DENY_ALL"), ("NEW_SCOPE", "DENY_ALL")):
            with self.subTest(scope=scope, network=network):
                values = case()
                for obj in values:
                    obj["bindings"].update(qualification_scope=scope, network_policy=network)
                self.assertRejected(values)

    def test_python_requirement_cannot_be_changed_by_agreement(self):
        values = case()
        for obj in values:
            obj["bindings"]["python_version"] = "3.12.14"
        self.assertRejected(values)

    def test_empty_missing_duplicate_and_extra_test_inventory(self):
        for index in (0, 1):
            for change in ("empty", "missing", "duplicate", "extra"):
                with self.subTest(input=index, change=change):
                    values = case(); rows = values[index]["tests"]
                    if change == "empty": rows.clear()
                    elif change == "missing": rows.pop()
                    elif change == "duplicate": rows.append(deepcopy(rows[0]))
                    else:
                        new = deepcopy(rows[0]); new["test_id"] = "unrequested.test"; rows.append(new)
                    self.assertRejected(values)

    def test_invalid_test_inventory_types(self):
        for index in (0, 1):
            for bad in (None, {}, "tests", [None]):
                with self.subTest(input=index, bad=bad):
                    values = case(); values[index]["tests"] = bad
                    self.assertRejected(values)

    def test_failure_error_unexpected_success_and_unknown_outcomes(self):
        for outcome in ("FAIL", "ERROR", "UNEXPECTED_SUCCESS", "EXPECTED_FAILURE", "unknown", None, True):
            with self.subTest(outcome=outcome):
                values = case(); values[0]["tests"][0]["outcome"] = outcome
                self.assertRejected(values)

    def test_expected_failure_requires_exact_test_exception(self):
        values = case(); values[1]["tests"][0]["allowed_outcomes"] = ["EXPECTED_FAILURE"]
        values[0]["tests"][0]["outcome"] = "EXPECTED_FAILURE"; seal(values[0], values[2])
        self.assertTrue(validate(values).valid)
        values[0]["tests"][0]["outcome"] = "PASS"
        self.assertRejected(values)

    def test_invalid_allowed_outcomes_and_native_expectations(self):
        for outcomes in ([], ["FAIL"], ["SKIP"], ["PASS", "PASS"], "PASS", [True]):
            with self.subTest(outcomes=outcomes):
                values = case(); values[1]["tests"][0]["allowed_outcomes"] = outcomes
                self.assertRejected(values)
        for key, value in (("allowed_outcomes", ["EXPECTED_FAILURE"]),
                           ("skip_exception", dict(reason="native unavailable", condition_id="NATIVE")),
                           ("required_native", 1)):
            with self.subTest(native_key=key):
                values = case(); values[1]["tests"][1][key] = value
                self.assertRejected(values)

    def test_positive_optional_skip_requires_independent_condition(self):
        values = case(); self.make_optional_skip(values)
        self.assertTrue(validate(values).valid)
        values[2]["satisfied_skip_conditions"] = []
        self.assertRejected(values)

    @staticmethod
    def make_optional_skip(values):
        values[0]["tests"][2].update(outcome="SKIP", skip_reason="Optional service not requested",
                                     skip_condition_id="OPTIONAL_DISABLED")
        values[2]["satisfied_skip_conditions"] = ["OPTIONAL_DISABLED"]
        seal(values[0], values[2])

    def test_skip_wrong_reason_condition_or_test_is_rejected(self):
        for change in ("reason", "condition", "native", "no_exception"):
            with self.subTest(change=change):
                values = case(); self.make_optional_skip(values)
                if change == "reason": values[0]["tests"][2]["skip_reason"] = "another reason"
                elif change == "condition": values[0]["tests"][2]["skip_condition_id"] = "another condition"
                elif change == "native":
                    values[0]["tests"][1].update(outcome="SKIP", skip_reason="unavailable", skip_condition_id="OPTIONAL_DISABLED")
                else: values[1]["tests"][2]["skip_exception"] = None
                self.assertRejected(values)

    def test_skip_fields_cannot_be_missing_or_attached_to_pass(self):
        for key in ("skip_reason", "skip_condition_id"):
            with self.subTest(key=key):
                values = case(); self.make_optional_skip(values); values[0]["tests"][2][key] = None
                self.assertRejected(values)
                values = case(); values[0]["tests"][0][key] = "unexpected"
                self.assertRejected(values)

    def test_all_authorized_skips_are_not_execution(self):
        values = case(); self.make_optional_skip(values)
        values[0]["tests"] = [values[0]["tests"][2]]
        values[1]["tests"] = [values[1]["tests"][2]]
        self.assertRejected(values)

    def test_skip_condition_inventory_is_closed_and_unique(self):
        for bad in (["unknown"], ["OPTIONAL_DISABLED", "OPTIONAL_DISABLED"], None, [True]):
            with self.subTest(bad=bad):
                values = case(); values[2]["satisfied_skip_conditions"] = bad
                self.assertRejected(values)

    def test_each_execution_failure_blocks_in_both_inputs(self):
        changes = {"terminal_state": "RUNNING", "exit_code": 1, "report_complete": False,
                   "timed_out": True, "cancelled": True}
        for index in (0, 2):
            for key, value in changes.items():
                with self.subTest(input=index, key=key):
                    values = case(); values[index]["execution"][key] = value
                    self.assertRejected(values)
        for key, value in changes.items():
            with self.subTest(agreed_failure=key):
                values = case()
                for index in (0, 2): values[index]["execution"][key] = value
                self.assertRejected(values)

    def test_execution_types_are_strict(self):
        for index in (0, 2):
            for key, value in (("exit_code", False), ("exit_code", 0.0), ("exit_code", "0"),
                               ("report_complete", 1), ("timed_out", 0), ("cancelled", "false")):
                with self.subTest(input=index, key=key, value=value):
                    values = case(); values[index]["execution"][key] = value
                    self.assertRejected(values)

    def test_checks_and_logs_have_exact_unique_nonempty_inventory(self):
        for index in (0, 2):
            for field, id_key in (("isolation_checks", "check_id"), ("logs", "log_id")):
                for change in ("empty", "missing", "duplicate", "extra"):
                    with self.subTest(input=index, field=field, change=change):
                        values = case(); rows = values[index][field]
                        if change == "empty": rows.clear()
                        elif change == "missing": rows.pop()
                        elif change == "duplicate": rows.append(deepcopy(rows[0]))
                        else:
                            row = deepcopy(rows[0]); row[id_key] = "other"; rows.append(row)
                        self.assertRejected(values)

    def test_check_and_log_expectations_are_validated(self):
        for field in ("required_isolation_checks", "log_ids"):
            for change in ("empty", "missing", "duplicate", "extra", "wrong_type"):
                with self.subTest(field=field, change=change):
                    values = case(); rows = values[1][field]
                    if change == "empty": rows.clear()
                    elif change == "missing": rows.pop()
                    elif change == "duplicate": rows.append(rows[0])
                    elif change == "extra": rows.append("other")
                    else: values[1][field] = "not a list"
                    self.assertRejected(values)

    def test_check_failures_and_log_substitution_in_both_inputs(self):
        for index in (0, 2):
            for outcome in ("FAIL", "SKIP", "UNKNOWN", True):
                with self.subTest(input=index, outcome=outcome):
                    values = case(); values[index]["isolation_checks"][0]["outcome"] = outcome
                    self.assertRejected(values)
            for digest in ("c" * 64, "not-a-digest", None):
                with self.subTest(input=index, digest=digest):
                    values = case(); values[index]["logs"][0]["sha256"] = digest
                    self.assertRejected(values)

    def test_termination_must_bind_whole_unit_and_attempt(self):
        for key, value in (("state", "UNKNOWN"), ("state", "RUNNING"), ("state", "PARENT_EXITED"),
                           ("attempt_id", "other-attempt"), ("unit_id", "other-unit"),
                           ("supervisor_sha256", "e" * 64), ("receipt_sha256", None),
                           ("receipt_sha256", "")):
            with self.subTest(key=key, value=value):
                values = case(); values[2]["termination"][key] = value
                self.assertRejected(values)

    def test_candidate_termination_claim_cannot_replace_observation(self):
        values = case(); values[2]["termination"]["state"] = "UNKNOWN"
        values[0]["terminated"] = True
        self.assertRejected(values)
        values = case(); values[2]["termination"] = {"surviving_descendants": 0}
        self.assertRejected(values)

    def test_full_record_digest_binds_even_otherwise_allowed_outcomes(self):
        values = case(); values[1]["tests"][0]["allowed_outcomes"] = ["PASS", "EXPECTED_FAILURE"]
        self.assertTrue(validate(values).valid)
        values[0]["tests"][0]["outcome"] = "EXPECTED_FAILURE"
        self.assertRejected(values, reseal=False)
        seal(values[0], values[2])
        self.assertTrue(validate(values).valid)

    def test_full_record_digest_binds_otherwise_authorized_skip(self):
        values = case(); old_digest = values[2]["record_sha256"]
        self.make_optional_skip(values)
        self.assertTrue(validate(values).valid)
        values[2]["record_sha256"] = old_digest
        self.assertRejected(values, reseal=False)

    def test_observed_record_digest_cannot_be_malformed_or_replaced(self):
        for value in (None, True, "d" * 64, "D" * 64, "abc"):
            with self.subTest(value=value):
                values = case(); values[2]["record_sha256"] = value
                self.assertRejected(values, reseal=False)

    def test_evidence_kind_is_explicit(self):
        for value in ("", "PASS", None, True):
            with self.subTest(value=value):
                values = case(); values[2]["evidence_kind"] = value
                self.assertRejected(values)

    def test_canonical_object_order_is_irrelevant_but_array_order_is_bound(self):
        values = list(case()); values[0] = dict(reversed(list(values[0].items())))
        self.assertTrue(validate(values).valid)
        values[0]["tests"].reverse()
        self.assertRejected(values, reseal=False)
        seal(values[0], values[2])
        self.assertTrue(validate(values).valid)

    def test_inputs_are_not_mutated_and_results_are_deterministic(self):
        for fail in (False, True):
            with self.subTest(fail=fail):
                values = case()
                if fail: values[2]["termination"]["state"] = "UNKNOWN"
                snapshot = deepcopy(values)
                first = validate(values); second = validate(values)
                self.assertEqual(first, second)
                self.assertEqual(values, snapshot)
                self.assertIsNot(values[0]["bindings"], values[1]["bindings"])
                self.assertIsNot(values[0]["execution"], values[2]["execution"])


if __name__ == "__main__":
    unittest.main()
