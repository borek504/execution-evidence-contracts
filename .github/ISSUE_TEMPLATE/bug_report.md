---
name: "Bug report (synthetic reproducer)"
about: "Report a reproducible error in the validator, demo or documentation."
title: "[Bug] "
---

> Public issue: use synthetic data only. Do not include credentials, personal
> paths, private logs or information exposing another system. For a sensitive
> finding, follow the [security policy](https://github.com/borek504/execution-evidence-contracts/blob/main/SECURITY.md)
> before public disclosure.

## Summary

<!-- What is wrong? Search existing issues first and link any related report. -->

## Version and environment

- Release tag and/or exact commit:
- Affected file or component (identify the branch/commit for an unreleased candidate):
- Python version and interpreter command:
- Operating system/version and architecture (omit personal identifiers):

## Minimal reproduction

<!-- Include the smallest self-contained code or exact commands and synthetic
     inputs needed to reproduce the problem. An existing test name is useful.
     Do not paste a complete private log or rely on a private service. -->

```python
# Minimal synthetic example, or replace this block with the commands you used.
```

## Expected behavior

<!-- Describe the expected result and the documented rule, if known. -->

## Actual behavior

<!-- Paste only relevant sanitized output/error codes and the exit status.
     For a validator result, include .valid, .errors and
     .qualification_authorized where available. State anything not tested. -->

## Scope and checks

- [ ] I identified the source version and checked for an existing report.
- [ ] The reproduction uses only synthetic, non-sensitive data.
- [ ] I distinguish what I observed from what I expect or have not tested.

<!-- A fix is welcome but not required. A matching digest or valid=True is not
     proof of execution, authenticity, isolation or authorization. -->
