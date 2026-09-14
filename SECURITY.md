# Security

This project is an experimental data-consistency validator, not a sandbox or execution-isolation product.

## Security-relevant non-goals

A successful validation does **not** establish that:

- tests actually ran or assertions were trustworthy,
- the verifier was independent or authenticated,
- files/logs referenced by digests were safely collected,
- a network or filesystem isolation policy was really enforced,
- a process tree, container, guest, or VM was actually terminated,
- the candidate could not tamper with its environment.

## Reporting

Please avoid posting sensitive credentials, host information, private logs, or exploit material that could expose an unrelated system in a public issue. For a security-sensitive finding, contact the maintainer privately through an appropriate channel before public disclosure.

A useful report should identify the affected schema/validation rule, provide a minimal synthetic reproducer, and explain whether the issue can cause malformed or contradictory evidence to validate.
