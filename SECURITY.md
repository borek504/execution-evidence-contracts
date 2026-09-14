# Security

This project is an experimental evidence-contract and local-evidence reference implementation, not a sandbox or execution-isolation product.

## Security-relevant non-goals

A successful validation does **not** establish that:

- tests actually ran or assertions were trustworthy,
- the verifier was independent or authenticated,
- files/logs referenced by digests were safely collected,
- a network or filesystem isolation policy was really enforced,
- a process tree, container, guest, or VM was actually terminated,
- the candidate could not tamper with its environment.

For the draft atomic evidence-store candidate, a successful local write also does
**not** establish that diagnostic content is true, independently observed,
authentic, or protected from an attacker who already controls the current OS
user, process, kernel, trusted parent path, or filesystem implementation. The
returned `content_sha256` is a byte binding, not a signature or trust assertion.

The atomic store is intentionally POSIX-only and assumes a dedicated private
leaf directory. Network/distributed filesystem durability semantics are not
claimed unless separately qualified.

## Reporting

Please avoid posting sensitive credentials, host information, private logs, or exploit material that could expose an unrelated system in a public issue. For a security-sensitive finding, contact the maintainer privately through an appropriate channel before public disclosure.

A useful report should identify the affected schema/storage rule, provide a minimal synthetic reproducer, and explain whether the issue can cause malformed/contradictory evidence to validate, a filesystem boundary to fail open, or persistence semantics to be misreported.
