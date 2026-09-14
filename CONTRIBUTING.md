# Contributing

Thanks for reviewing this experiment. The most useful contributions are narrow, reproducible, and preserve the fail-closed boundary.

Please include:

- the exact behavior or ambiguity being addressed,
- a focused test that fails before the change and passes after it,
- an explanation of any trust-boundary impact,
- confirmation that a change does not turn `valid=True` into release/qualification authority.

For semantic changes, prefer opening a design discussion before changing schema versions or policy rules. Do not silently relax the closed schemas, skip policy, identity bindings, or scope/network mapping merely to make an example pass.

Keep tests self-contained and synthetic. Contributions should not require private credentials, private hosts, external APIs, privileged runners, or access to another project.
