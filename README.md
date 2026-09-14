# Execution Evidence Contracts

Experimental reference implementation for **fail-closed validation of execution evidence**.

The project validates consistency between three independently supplied inputs:

1. an untrusted execution `record`,
2. `expected` identities and test policy fixed before execution,
3. a `verifier_context` representing independent observations.

It is intentionally small and uses only the Python standard library.

> **Important:** `valid=True` means only that the supplied data satisfy this contract. It is **not** proof that tests actually ran, that the observer is authentic, that isolation succeeded, or that a process/VM really terminated. The result never grants release or qualification authority.

## Current status

This is an experimental reference profile. The current schema names retain their original `jarvis-r14-*` identifiers so the first public version does not silently change semantics.

The profile currently pins:

- `python_version == "3.13.15"` inside the validated evidence,
- `CANDIDATE_QUALIFICATION -> LOCAL_LOOPBACK_ONLY_SEATBELT`,
- `FINAL_REGRESSION -> DENY_ALL`.

Those are **profile rules**, not a claim that every user or every execution system should use those exact settings. Generalizing the profile is a separate design task.

## What the validator checks

The validator rejects unknown schema versions and keys, mismatched identities, incomplete or duplicate test inventories, unauthorized skips, failed or incomplete execution states, missing isolation-check/log inventories, report substitution, and termination data that does not bind to the expected attempt/unit/supervisor.

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
print(result.valid)                    # True
print(result.qualification_authorized) # False
```

This example is synthetic. It does not authenticate `expected` or `verifier_context` and does not prove execution or isolation.

## Run the focused tests

From this directory:

```bash
python -B -m unittest -v test_r14_execution_contract
```

The suite uses synthetic data and does not start a supervisor, VM, agent, network service, or private runtime.

## Design boundary

The validator is deliberately not an execution engine. A real deployment still needs a trusted component that establishes the origin of expectations and observations, safely collects artifacts, and proves whole-unit termination. Copying candidate-controlled values into the supposedly independent inputs defeats the intended trust boundary.

See [PROFILE.md](PROFILE.md) for the current reference profile and [SECURITY.md](SECURITY.md) for security reporting and non-goals.

## License

Licensed under the **Apache License 2.0**. See [LICENSE](LICENSE).
