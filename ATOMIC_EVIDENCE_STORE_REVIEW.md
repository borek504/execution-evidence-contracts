# Atomic Evidence Store candidate review

Status: **draft candidate / not merge-authorized**.

This branch generalizes a local incident-snapshot persistence pattern into a small,
standard-library-only evidence-store primitive. Private runtime integration,
hard-coded paths, diagnostic collectors, agent identities, credentials, and host
configuration are intentionally not part of this candidate.

## Purpose

`atomic_evidence_store.py` stores small JSON snapshots so callers can bind later
validation or audit records to exact local bytes. It provides a narrow persistence
contract; it does not decide whether evidence is true or authoritative.

The public API is intentionally small:

- `capture_evidence_snapshot(...)`
- `list_recent_evidence(...)`
- `validate_evidence_snapshot(...)`

A successful capture returns the snapshot id, canonical capture time, final file
name/path, and SHA-256 of the exact persisted bytes.

## Storage invariants

The candidate currently requires all of the following:

- POSIX runtime with `O_NOFOLLOW`, `O_DIRECTORY`, directory-fd operations and
  hard-link publication support;
- a dedicated evidence directory owned by the current effective user;
- leaf evidence directory mode exactly `0700`;
- snapshot file mode exactly `0600`;
- closed `execution-evidence-snapshot-v1` envelope;
- timezone-aware capture time normalized to one UTC wire spelling;
- JSON that can be serialized with `allow_nan=False`;
- canonical sorted/compact UTF-8 bytes plus one final newline;
- maximum canonical snapshot size of 1 MiB;
- subject/issue/status text capped at 4096 UTF-8 bytes;
- deterministic generated file name bound to timestamp, subject, issue and
  evidence-id prefix;
- no-overwrite publication through same-directory hard-link creation;
- file `fsync` before publication and directory `fsync` after publication;
- no-follow reads through a directory fd;
- listing accepts only valid canonical bytes under the expected generated name.

## Crash and error semantics

The temp file is created with `O_CREAT | O_EXCL | O_NOFOLLOW`, mode `0600`, then
fully written and `fsync`ed. Publication links the already-synced inode to its
final name. If that name already exists, capture fails rather than replacing it.
The temp name is then removed and the directory is `fsync`ed.

There is one important consequence: a failure **after** the final hard link has
been created can return an error while leaving a valid final snapshot behind.
For example, directory `fsync` failure means durability is not confirmed; it does
not prove that the final file is absent. Callers must reconcile by evidence id or
returned/known naming inputs rather than treating every raised exception as an
all-or-nothing rollback.

## Threat boundary

This component hardens the leaf evidence directory and snapshot-file operations.
It does **not** defend against an attacker who already controls the process,
current OS user, kernel, filesystem implementation, or trusted parent path.
Parent path components are assumed to be administratively controlled; the module
does not walk and independently verify every ancestor directory.

The `content_sha256` value is a byte-binding convenience. It is not a signature,
MAC, timestamp authority, provenance proof, or evidence-authenticity claim. A
same-user attacker who can rewrite both a snapshot and all external bindings is
outside this primitive's protection model.

## Deliberate non-goals

This candidate does not provide:

- evidence collection or diagnostic truth checking;
- encryption at rest;
- signatures, MACs or key management;
- remote replication or upload;
- database transactions;
- automatic retention/deletion;
- replay prevention;
- release or qualification authority;
- guarantees for network/distributed filesystems whose hard-link/fsync semantics
  have not been independently qualified.

## Internal review already covered

The focused and red-team suites exercise, among other cases:

- final-name collision without overwrite;
- pre-created symlink collision;
- temp cleanup on publication failure;
- failures after publication (`unlink` / directory `fsync`);
- directory/file permission boundaries;
- leaf-directory and file symlink rejection;
- path-like subject/issue text without path traversal;
- invalid/non-finite/oversized JSON;
- canonical timestamp and closed-schema checks;
- exact canonical wire bytes;
- content-digest stability;
- malformed/deep JSON read failures without crashing listing;
- renamed snapshots and broadened file permissions being excluded from listing.

## Questions for external review

Before merge, useful review would focus on:

1. whether hard-link publication + file fsync + directory fsync has the intended
   crash-consistency semantics on supported local filesystems;
2. whether requiring exact `0700`/`0600` modes is too strict or appropriately
   fail-closed for a reference profile;
3. whether parent-path trust should remain an explicit boundary or be replaced by
   descriptor-by-descriptor ancestor traversal;
4. whether listing should remain filename-ordered or use a bounded index/store for
   very large evidence directories;
5. whether a separate signed receipt profile should bind `content_sha256` without
   coupling storage to trust/authentication policy;
6. whether any read/write race, symlink/hard-link, malformed-JSON, or error-path
   behavior still permits a silent fail-open result.

A useful contribution is a minimal synthetic reproducer plus a focused test. Do
not include private runtime data, credentials, or host-specific paths.
