"""Fail-closed local persistence for small JSON evidence snapshots.

This is a storage primitive, not an authenticity primitive. A successfully
persisted snapshot proves only that these bytes were written by this process to
this directory. It does not prove that the diagnostic data are true,
independently observed, or authorized for release/qualification decisions.

The reference implementation is POSIX-oriented because it relies on directory
file descriptors, fsync, no-follow opens, and hard-link publication to obtain a
no-overwrite atomic publish step.
"""

from __future__ import annotations

from datetime import datetime, timezone
import errno
import json
import os
from pathlib import Path
import re
import secrets
import stat
from typing import Any, Mapping
import uuid


EVIDENCE_SCHEMA_VERSION = "execution-evidence-snapshot-v1"
MAX_EVIDENCE_BYTES = 1_048_576
MAX_RECENT_EVIDENCE = 20
MAX_LIST_LIMIT = 100
MAX_COMPONENT_CHARS = 80

_EVIDENCE_FIELDS = frozenset(
    {
        "schema_version",
        "evidence_id",
        "captured_at_utc",
        "subject_id",
        "issue",
        "reported_status",
        "diagnostics",
    }
)
_EVIDENCE_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_SAFE_COMPONENT_RE = re.compile(r"[^A-Za-z0-9_.-]+")


class EvidenceStoreError(ValueError):
    """Fail-closed evidence-store contract error."""


def _require_text(value: Any, field: str) -> str:
    if type(value) is not str:
        raise EvidenceStoreError(f"{field.upper()}_TYPE_INVALID")
    if not value or value != value.strip():
        raise EvidenceStoreError(f"{field.upper()}_INVALID")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise EvidenceStoreError(f"{field.upper()}_INVALID")
    return value


def _canonical_utc(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise EvidenceStoreError("CAPTURE_TIME_MUST_BE_TIMEZONE_AWARE")
    return value.astimezone(timezone.utc).isoformat()


def _validate_canonical_timestamp(value: Any) -> bool:
    if type(value) is not str:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return False
    return parsed.astimezone(timezone.utc).isoformat() == value


def _safe_component(value: str) -> str:
    cleaned = _SAFE_COMPONENT_RE.sub("_", value).strip("._-")
    return (cleaned[:MAX_COMPONENT_CHARS] or "unknown")


def _canonical_json_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise EvidenceStoreError("EVIDENCE_NOT_CANONICAL_JSON") from exc
    data = text.encode("utf-8")
    if len(data) > MAX_EVIDENCE_BYTES:
        raise EvidenceStoreError("EVIDENCE_SIZE_LIMIT")
    return data


def validate_evidence_snapshot(snapshot: Any) -> dict[str, Any]:
    """Validate the closed snapshot envelope without mutating it."""

    issues: list[str] = []
    if type(snapshot) is not dict:
        return {"ok": False, "issues": ["EVIDENCE_SNAPSHOT_INVALID"]}

    keys = set(snapshot)
    if keys != _EVIDENCE_FIELDS:
        issues.append("EVIDENCE_FIELDS_INVALID")
    if snapshot.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
        issues.append("EVIDENCE_SCHEMA_UNSUPPORTED")

    evidence_id = snapshot.get("evidence_id")
    if type(evidence_id) is not str or _EVIDENCE_ID_RE.fullmatch(evidence_id) is None:
        issues.append("EVIDENCE_ID_INVALID")
    if not _validate_canonical_timestamp(snapshot.get("captured_at_utc")):
        issues.append("EVIDENCE_TIMESTAMP_INVALID")

    for field in ("subject_id", "issue"):
        value = snapshot.get(field)
        if type(value) is not str or not value or value != value.strip():
            issues.append(f"EVIDENCE_{field.upper()}_INVALID")
        elif any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
            issues.append(f"EVIDENCE_{field.upper()}_INVALID")

    status_value = snapshot.get("reported_status")
    if status_value is not None and type(status_value) is not str:
        issues.append("EVIDENCE_STATUS_INVALID")
    if type(snapshot.get("diagnostics")) is not dict:
        issues.append("EVIDENCE_DIAGNOSTICS_INVALID")

    try:
        _canonical_json_bytes(snapshot)
    except EvidenceStoreError as exc:
        if str(exc) not in issues:
            issues.append(str(exc))

    return {"ok": not issues, "issues": issues}


def _ensure_directory(path: Path) -> None:
    if path.is_symlink():
        raise EvidenceStoreError("EVIDENCE_DIR_SYMLINK")
    if path.exists() and not path.is_dir():
        raise EvidenceStoreError("EVIDENCE_DIR_NOT_DIRECTORY")
    if not path.exists():
        path.mkdir(parents=True, mode=0o700)
    if path.is_symlink() or not path.is_dir():
        raise EvidenceStoreError("EVIDENCE_DIR_INVALID")
    try:
        path.chmod(0o700)
    except OSError as exc:
        raise EvidenceStoreError("EVIDENCE_DIR_PERMISSION_FAILED") from exc


def _open_directory_fd(path: Path) -> int:
    flags = os.O_RDONLY
    flags |= getattr(os, "O_DIRECTORY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        return os.open(path, flags)
    except OSError as exc:
        raise EvidenceStoreError("EVIDENCE_DIR_OPEN_FAILED") from exc


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    written = 0
    while written < len(view):
        count = os.write(fd, view[written:])
        if count <= 0:
            raise OSError("short write")
        written += count


def capture_evidence_snapshot(
    *,
    evidence_dir: str | os.PathLike[str],
    subject_id: str,
    issue: str,
    diagnostics: Mapping[str, Any],
    reported_status: str | None = None,
    now: datetime | None = None,
    evidence_id: str | None = None,
) -> dict[str, str]:
    """Persist one snapshot using same-directory, no-overwrite atomic publish."""

    subject = _require_text(subject_id, "subject_id")
    issue_text = _require_text(issue, "issue")
    if reported_status is not None and type(reported_status) is not str:
        raise EvidenceStoreError("REPORTED_STATUS_TYPE_INVALID")
    if not isinstance(diagnostics, Mapping):
        raise EvidenceStoreError("DIAGNOSTICS_MAPPING_REQUIRED")

    captured = now or datetime.now(timezone.utc)
    captured_wire = _canonical_utc(captured)

    snapshot_id = evidence_id or uuid.uuid4().hex
    if type(snapshot_id) is not str or _EVIDENCE_ID_RE.fullmatch(snapshot_id) is None:
        raise EvidenceStoreError("EVIDENCE_ID_INVALID")

    payload = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "evidence_id": snapshot_id,
        "captured_at_utc": captured_wire,
        "subject_id": subject,
        "issue": issue_text,
        "reported_status": reported_status,
        "diagnostics": dict(diagnostics),
    }
    validation = validate_evidence_snapshot(payload)
    if not validation["ok"]:
        raise EvidenceStoreError(";".join(validation["issues"]))
    data = _canonical_json_bytes(payload) + b"\n"

    directory = Path(evidence_dir)
    _ensure_directory(directory)
    dir_fd = _open_directory_fd(directory)

    timestamp_prefix = captured.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    filename = (
        f"{timestamp_prefix}_{_safe_component(subject)}_"
        f"{_safe_component(issue_text)}_{snapshot_id[:8]}.json"
    )
    temp_name = f".evidence-{secrets.token_hex(16)}.tmp"
    temp_fd: int | None = None
    published = False

    try:
        open_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        open_flags |= getattr(os, "O_NOFOLLOW", 0)
        temp_fd = os.open(temp_name, open_flags, 0o600, dir_fd=dir_fd)
        os.fchmod(temp_fd, 0o600)
        _write_all(temp_fd, data)
        os.fsync(temp_fd)
        os.close(temp_fd)
        temp_fd = None

        # Hard-link publication is atomic and refuses to overwrite an existing
        # final name. This is intentionally fail-closed if the filesystem does
        # not support the required operation.
        try:
            os.link(
                temp_name,
                filename,
                src_dir_fd=dir_fd,
                dst_dir_fd=dir_fd,
                follow_symlinks=False,
            )
        except FileExistsError as exc:
            raise EvidenceStoreError("EVIDENCE_FILENAME_COLLISION") from exc
        except OSError as exc:
            raise EvidenceStoreError("EVIDENCE_ATOMIC_PUBLISH_FAILED") from exc
        published = True
        os.unlink(temp_name, dir_fd=dir_fd)
        os.fsync(dir_fd)
    finally:
        if temp_fd is not None:
            try:
                os.close(temp_fd)
            except OSError:
                pass
        if not published:
            try:
                os.unlink(temp_name, dir_fd=dir_fd)
            except OSError as exc:
                if exc.errno != errno.ENOENT:
                    pass
        os.close(dir_fd)

    return {
        "evidence_id": snapshot_id,
        "filename": filename,
        "path": str(directory / filename),
        "captured_at_utc": captured_wire,
    }


def _read_snapshot_file(path: Path) -> dict[str, Any] | None:
    if path.is_symlink() or not path.is_file():
        return None
    try:
        file_stat = path.stat()
        if not stat.S_ISREG(file_stat.st_mode):
            return None
        if file_stat.st_size > MAX_EVIDENCE_BYTES + 1:
            return None
        data = path.read_bytes()
        if len(data) > MAX_EVIDENCE_BYTES + 1:
            return None
        payload = json.loads(data.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    validation = validate_evidence_snapshot(payload)
    return payload if validation["ok"] else None


def list_recent_evidence(
    evidence_dir: str | os.PathLike[str],
    *,
    limit: int = MAX_RECENT_EVIDENCE,
) -> list[dict[str, Any]]:
    """Return summaries of valid snapshots only; no writes are performed."""

    if type(limit) is not int or isinstance(limit, bool) or not (1 <= limit <= MAX_LIST_LIMIT):
        raise EvidenceStoreError("EVIDENCE_LIMIT_INVALID")

    directory = Path(evidence_dir)
    if not directory.exists():
        return []
    if directory.is_symlink() or not directory.is_dir():
        raise EvidenceStoreError("EVIDENCE_DIR_INVALID")

    files = sorted(
        (path for path in directory.glob("*.json") if not path.is_symlink()),
        key=lambda path: path.name,
        reverse=True,
    )

    items: list[dict[str, Any]] = []
    for path in files:
        payload = _read_snapshot_file(path)
        if payload is None:
            continue
        items.append(
            {
                "evidence_id": payload["evidence_id"],
                "captured_at_utc": payload["captured_at_utc"],
                "subject_id": payload["subject_id"],
                "issue": payload["issue"],
                "reported_status": payload["reported_status"],
                "filename": path.name,
                "path": str(path),
            }
        )
        if len(items) >= limit:
            break
    return items
