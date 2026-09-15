# Execution Evidence Contracts

Experimental reference implementation for **fail-closed validation of execution evidence**.

The project validates consistency between three independently supplied inputs:

1. an untrusted execution `record`,
2. `expected` identities and test policy fixed before execution,
3. a `verifier_context` representing independent observations.

It is intentionally small and uses only the Python standard library.

> **Important:** `valid=True` means only that the supplied data satisfy this contract. It is **not** proof that tests actually ran, that the observer is authentic, that isolation succeeded, or that a process/VM really terminated. The result never grants release or qualification authority.

## Quick Start

Use **Python 3.12 or 3.13**. There are no third-party dependencies, API keys or
installation steps. In a new checkout:

```bash
git clone https://github.com/borek504/execution-evidence-contracts.git
cd execution-evidence-contracts
python -B demo_execution_contract.py
```

The demo prints these three results, followed by explanations and error codes:

```text
[1] Consistent report: ACCEPTED (data only)
[2] Wrong attempt: REJECTED
[3] Missing required test: REJECTED
```

Every case prints `qualification_authorized=False`. The final line should be
`Demo checks: 3/3 matched the expected outcomes.` Exit code 0 means the demo
matched all three expected results, **including both rejections**; it does not
mean three reports were accepted. An unexpected result exits with code 1.

See [demo_execution_contract.py](demo_execution_contract.py) for complete,
editable inputs and calls to `validate_execution_record`. The demo constructs
example data in memory and prints to the terminal; it does not run the test
workload described by those data or write evidence files.

**What the rejection cases teach:** the wrong-attempt report keeps the expected
identity fixed, and the incomplete report keeps the required test inventory
fixed. Only the synthetic observed-report digest is refreshed to simulate receipt
of each changed report. Matching that digest is not enough to pass validation.
This fixture is not an evidence collector: a real integration must establish
expectations and observations independently, not copy them from a candidate's
report.

## Current status

This is an experimental reference profile. The current schema names retain their original `jarvis-r14-*` identifiers so the first public version does not silently change semantics.

The profile currently pins:

- `python_version == "3.13.15"` inside the validated evidence,
- `CANDIDATE_QUALIFICATION -> LOCAL_LOOPBACK_ONLY_SEATBELT`,
- `FINAL_REGRESSION -> DENY_ALL`.

The `python_version` value is a synthetic evidence-profile field, not a reading
of your installed interpreter version.

Those are **profile rules**, not a claim that every user or every execution system should use those exact settings. Generalizing the profile is a separate design task.

## What the validator checks

The validator rejects unknown schema versions and keys, mismatched identities, incomplete or duplicate test inventories, unauthorized skips, failed or incomplete execution states, missing isolation-check/log inventories, report substitution, and termination data that does not bind to the expected attempt/unit/supervisor.

`ContractValidation.qualification_authorized` is always `False`, and converting a result directly to `bool` raises `TypeError`. Callers must inspect `.valid` explicitly.

## Run the tests

```bash
python -B -m unittest -v test_r14_execution_contract test_demo_execution_contract
```

The existing 33 contract tests remain unchanged. Seven additional demo tests
check the expected outcomes, error explanations, lack of authority and the
nonzero exit gate. CI also runs the exact Quick Start demo command separately.
All test data are synthetic; no supervisor, VM, agent, network service or private
runtime is started.

## Design boundary

For key definitions, see the [Glossary](docs/glossary.md).


The validator is deliberately not an execution engine. A real deployment still needs a trusted component that establishes the origin of expectations and observations, safely collects artifacts, and proves whole-unit termination. Copying candidate-controlled values into the supposedly independent inputs defeats the intended trust boundary.

See [PROFILE.md](PROFILE.md) for the current reference profile and [SECURITY.md](SECURITY.md) for security reporting and non-goals.

## License

Licensed under the **Apache License 2.0**. See [LICENSE](LICENSE).
