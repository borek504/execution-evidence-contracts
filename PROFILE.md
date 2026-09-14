# Reference profile

This candidate preserves the original v1 semantics instead of generalizing them during extraction.

## Closed schemas

The accepted versions are:

- `jarvis-r14-execution-record-v1`
- `jarvis-r14-execution-expectations-v1`
- `jarvis-r14-execution-verifier-context-v1`

Unknown versions and unknown keys fail closed. There is no compatibility fallback or input repair.

## Pinned policy values

The current profile requires evidence to declare Python `3.13.15` and binds these scope/network pairs:

| Qualification scope | Network policy |
| --- | --- |
| `CANDIDATE_QUALIFICATION` | `LOCAL_LOOPBACK_ONLY_SEATBELT` |
| `FINAL_REGRESSION` | `DENY_ALL` |

These values come from the reference profile. They are not presented as universal requirements for unrelated systems.

## Trust boundary

`record` is untrusted. `expected` must be fixed independently before execution. `verifier_context` must come from an observer outside candidate control.

The library compares data; it does not authenticate the caller or provenance, execute tests, inspect a host, verify log bytes, enforce network isolation, or terminate processes/VMs.

A valid contract result therefore cannot be treated as a security or release authorization token.
