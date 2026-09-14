# Execution Evidence Contracts

Experimental reference implementation for **fail-closed validation of execution evidence**.

The project validates consistency between three independently supplied inputs:

1. an untrusted execution `record`,
2. `expected` identities and test policy fixed before execution,
3. a `verifier_context` representing independent observations.

It is intentionally small and uses only the Python standard library.

> **Important:** `valid=True` means only that the supplied data satisfy this contract. It is **not** proof that tests actually ran, that the observer is authentic, that isolation succeeded, or that a process/VM really terminated. The result never grants release or qualification authority.

## Current status

`main` contains the first public execution-evidence validator profile.

Draft PR #4 additionally contains two Result Envelope tracks:

- an exact characterization of the historical `jarvis-result-envelope-v1` profile,
- a separate `execution-result-envelope-v2` candidate with negative-tests-first development.

The v2 candidate is **not stable and not merge-authorized**. Its committed contract tests execute in CI on Python 3.12 and 3.13 and pass against the first implementation candidate. Three golden hash vectors are now frozen and reproduced by a second independently written canonical encoder as well as the production encoder. Binary canonicalization, parser/resource-boundary review and independent security review remain required before merge consideration.

Golden-vector material in the draft branch:

- `RESULT_ENVELOPE_V2_GOLDEN_VECTORS.json`
- `RESULT_ENVELOPE_V2_GOLDEN_VECTORS.md`
- `test_result_envelope_v2_golden_vectors.py`

## Execution evidence validator

The published validator rejects unknown schema versions and keys, mismatched identities, incomplete or duplicate test inventories, unauthorized skips, failed or incomplete execution states, missing isolation-check/log inventories, report substitution, and termination data that does not bind to the expected attempt/unit/supervisor.

`ContractValidation.qualification_authorized` is always `False`, and converting a result directly to `bool` raises `TypeError`. Callers must inspect `.valid` explicitly.

## Minimal synthetic example

```python
from hashlib import sha256
import json

from r14_execution_contract import validate_execution_record


def bindings():
    return {
        "attempt_id": "demo-attempt",
        "unit_id": "demo-unit",
        "candidate_identity_sha256": "1" * 64,
        "source_commit": "2" * 40,
        "source_manifest_sha256": "3" * 64,
        "qualification_scope": "FINAL_REGRESSION",
        "supervisor_sha256": "4" * 64,
        "interpreter_sha256": "5" * 64,
        "python_version": "3.13.15",
        "dependency_manifest_sha256": "6" * 64,
        "policy_sha256": "7" * 64,
        "network_policy": "DENY_ALL",
        "inventory_version": "demo-v1",
        "host_identity_sha256": "8" * 64,
        "guest_identity_sha256": None,
    }


def execution():
    return {
        "terminal_state": "SUCCEEDED",
        "exit_code": 0,
        "report_complete": True,
        "timed_out": False,
        "cancelled": False,
    }


record = {
    "schema_version": "jarvis-r14-execution-record-v1",
    "bindings": bindings(),
    "tests": [{
        "test_id": "demo.test",
        "outcome": "PASS",
        "skip_reason": None,
        "skip_condition_id": None,
    }],
    "execution": execution(),
    "isolation_checks": [{"check_id": "network", "outcome": "PASS"}],
    "logs": [{"log_id": "stdout", "sha256": "9" * 64}],
}

expected = {
    "schema_version": "jarvis-r14-execution-expectations-v1",
    "bindings": bindings(),
    "tests": [{
        "test_id": "demo.test",
        "allowed_outcomes": ["PASS"],
        "required_native": False,
        "skip_exception": None,
    }],
    "required_isolation_checks": ["network"],
    "log_ids": ["stdout"],
}

context = {
    "schema_version": "jarvis-r14-execution-verifier-context-v1",
    "evidence_kind": "SYNTHETIC",
    "record_sha256": sha256(json.dumps(
        record,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")).hexdigest(),
    "bindings": bindings(),
    "execution": execution(),
    "isolation_checks": [{"check_id": "network", "outcome": "PASS"}],
    "logs": [{"log_id": "stdout", "sha256": "9" * 64}],
    "satisfied_skip_conditions": [],
    "termination": {
        "attempt_id": "demo-attempt",
        "unit_id": "demo-unit",
        "supervisor_sha256": "4" * 64,
        "state": "TERMINATED",
        "receipt_sha256": "a" * 64,
    },
}

result = validate_execution_record(record, expected=expected, verifier_context=context)
print(result.valid)
```

## Review and contribution

Open issues intentionally ask for outside review of trust boundaries, adversarial cases, safe profile generalization and Result Envelope v2 hardening. See `CONTRIBUTING.md`, `SECURITY.md`, and the review issues before proposing security-sensitive changes.

## License

Apache License 2.0.
