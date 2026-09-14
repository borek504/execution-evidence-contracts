# Community review questions

These are draft questions for an initial technical review. They are not public issues yet.

1. **Trust boundary:** Is the separation between untrusted `record`, pre-committed `expected`, and independent `verifier_context` clear enough to prevent callers from treating simple field agreement as provenance/authentication?
2. **Negative tests:** Which malformed, ambiguous, substitution, replay, type-confusion, or partial-observation cases are still missing from the current synthetic suite?
3. **Generalization:** What is the safest way to separate the current pinned R14 profile (Python version and scope/network mapping) from the generic validation engine without introducing permissive defaults or downgrade paths?
