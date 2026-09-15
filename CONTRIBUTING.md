# Contributing

Thanks for reviewing this experiment. The most useful contributions are narrow, reproducible, and preserve the fail-closed boundary.

## Your first contribution

You do not need to audit the whole project to help. Choose one small task and
comment before starting so contributors do not duplicate work:

- [Check Quick Start on one macOS or Windows setup (#13)](https://github.com/borek504/execution-evidence-contracts/issues/13): a sanitized report is enough; no code change is required.
- [Write a short glossary (#14)](https://github.com/borek504/execution-evidence-contracts/issues/14): explain six existing terms without changing their meaning.
- [Test nested-list isolation in the demo fixtures (#15)](https://github.com/borek504/execution-evidence-contracts/issues/15): add one or two focused tests, not a new protocol.

Read each issue's scope and completion criteria. Check whether it is still open;
the [open good first issues](https://github.com/borek504/execution-evidence-contracts/issues?q=is%3Aissue%20is%3Aopen%20label%3A%22good%20first%20issue%22)
list is the current starting point. These are invitations, not assignments or
claims that someone has already volunteered.

For local examples, follow [Quick Start](README.md#quick-start) with Python 3.12
or 3.13. Use a fresh checkout and synthetic inputs; no API keys are needed:

```bash
python -B demo_execution_contract.py
python -B -m unittest -v test_r14_execution_contract test_demo_execution_contract
```

Use `python3` where that is the command for your selected interpreter. In a
report, include the exact commit and the command actually used. Report failures
or skipped checks honestly rather than changing a check to obtain a pass.

## Reporting a problem

Use the bug-report template when opening an issue. Include the version,
reproduction, expected behavior and actual output. A proposed fix is optional.
For sensitive findings, read [SECURITY.md](SECURITY.md) before public disclosure.
Do not upload credentials, private logs, personal paths or unrelated system data.
Blank issues remain available for documentation questions and design proposals.

## Proposing a change

For behavior changes, please include:

- the exact behavior or ambiguity being addressed,
- a focused test that fails before the change and passes after it,
- an explanation of any trust-boundary impact,
- confirmation that a change does not turn `valid=True` into release/qualification authority.

Documentation-only contributions do not need a failing test: explain what
becomes clearer and check the links and examples. Coverage-only test additions
should explain the previously untested behavior; do not invent a production bug.
Keep pull requests small and link the issue they address.

For semantic changes, prefer opening a design discussion before changing schema versions or policy rules. Do not silently relax the closed schemas, skip policy, identity bindings, or scope/network mapping merely to make an example pass.

Keep tests self-contained and synthetic. Contributions should not require private credentials, private hosts, external APIs, privileged runners, or access to another project.

## Specialist review is separate

The Result Envelope v2 review in [#9](https://github.com/borek504/execution-evidence-contracts/issues/9)
and Atomic Evidence Store review in [#11](https://github.com/borek504/execution-evidence-contracts/issues/11)
are not beginner tasks. A documentation improvement, demo run or passing test
does not replace independent review or approve either candidate for merge.
