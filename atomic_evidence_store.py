"""Fail-closed local persistence for small JSON evidence snapshots.

This is a storage primitive, not an authenticity primitive. A successfully
persisted snapshot proves only that these bytes were written by this process to
this directory. It does not prove that the diagnostic data are true,
independently observed, or authorized for release/qualification decisions.

The reference implementation is explicitly POSIX-only. It requires directory
file descriptors, fsync, O_NOFOLLOW, O_DIRECTORY and hard-link publication to
obtain private, no-overwrite atomic storage semantics. Parent path components
are assumed to be under the caller's administrative control; the leaf evidence
directory and evidence files themselves are opened with no-follow semantics.
"""

from __future__ import annotations

from datetime import datetime, timezone
import errno
from hashlib import sha256
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
MAX_TEXT_BYTES = 4_096
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


def _require_platform_support() -> None:
    required_flags = ("O_NOFOLLOW", "O_DIRECTORY")
    if os.name != "posix" or any(not hasattr(os, name) for name in required_flags):
        raise EvidenceStoreError("EVIDENCE_PLATFORM_UNSUPPORTED")
    if any(function not in os.supports_dir_fd for function in (os.open, os.link, os.unlink)):
        raise EvidenceStoreError("EVIDENCE_PLATFORM_UNSUPPORTED")
    if os.listdir not in os.supports_fd:
        raise EvidenceStoreError("EVIDENCE_PLATFORM_UNSUPPORTED")
    if os.link not in os.supports_follow_symlinks:
        raise EvidenceStoreError("EVIDENCE_PLATFORM_UNSUPPORTED")


def _require_text(value: Any, field: str) -> str:
    if type(value) is not str:
        raise EvidenceStoreError(f"{field.upper()}_TYPE_INVALID")
    if not value or value != value.strip():
        raise EvidenceStoreError(f"{field.upper()}_INVALID")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise EvidenceStoreError(f"{field.upper()}_INVALID")
    if len(value.encode("utf-8")) > MAX_TEXT_BYTES:
        raise EvidenceStoreError(f"{field.upper()}_SIZE_LIMIT")
    return value


def _optional_status(value: Any) -> str | None:
    if value is None:
        return None
    return _require_text(value, "reported_status")


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
    return cleaned[:MAX_COMPONENT_CHARS] or "unknown"


def _filename_for_snapshot(snapshot: Mapping[str, Any]) -> str:
    captured = datetime.fromisoformat(str(snapshot["captured_at_utc"]).replace("Z", "+00:00"))
    timestamp_prefix = captured.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    return (
        f"{timestamp_prefix}_{_safe_component(str(snapshot['subject_id']))}_"
        f"{_safe_component(str(snapshot['issue']))}_{str(snapshot['evidence_id'])[:8]}.json"
    )


def _canonical_json_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise EvidenceStoreError("EVIDENCE_NOT_CANONICAL_JSON") from exc
    data = text.encode("utf-8")
    if len(data) > MAX_EVIDENCE_BYTES:
        raise EvidenceStoreError("EVIDENCE_SIZE_LIMIT")
    return data


def _text_issue(value: Any, field: str) -> str | None:
    if type(value) is not str:
        return f"EVIDENCE_{field.upper()}_TYPE_INVALID"
    if not value or value != value.strip():
        return f"EVIDENCE_{field.upper()}_INVALID"
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        return f"EVIDENCE_{field.upper()}_INVALID"
    if len(value.encode("utf-8")) > MAX_TEXT_BYTES:
        return f"EVIDENCE_{field.upper()}_SIZE_LIMIT"
    return None


def validate_evidence_snapshot(snapshot: Any) -> dict[str, Any]:
    """Validate the closed snapshot envelope without mutating it."""

    issues: list[str] = []
    if type(snapshot) is not dict:
        return {"ok": False, "issues": ["EVIDENCE_SNAPSHOT_INVALID"]}

    if set(snapshot) != _EVIDENCE_FIELDS:
        issues.append("EVIDENCE_FIELDS_INVALID")
    if snapshot.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
        issues.append("EVIDENCE_SCHEMA_UNSUPPORTED")

    evidence_id = snapshot.get("evidence_id")
    if type(evidence_id) is not str or _EVIDENCE_ID_RE.fullmatch(evidence_id) is None:
        issues.append("EVIDENCE_ID_INVALID")
    if not _validate_canonical_timestamp(snapshot.get("captured_at_utc")):
        issues.append("EVIDENCE_TIMESTAMP_INVALID")

    for field in ("subject_id", "issue"):
        issue_code = _text_issue(snapshot.get(field), field)
        if issue_code:
            issues.append(issue_code)

    status_value = snapshot.get("reported_status")
    if status_value is not None:
        status_issue = _text_issue(status_value, "status")
        if status_issue:
            issues.append(status_issue)
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
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise EvidenceStoreError("EVIDENCE_DIR_OPEN_FAILED") from exc
    directory_stat = os.fstat(fd)
    if not stat.S_ISDIR(directory_stat.st_mode):
        os.close(fd)
        raise EvidenceStoreError("EVIDENCE_DIR_INVALID")
    if stat.S_IMODE(directory_stat.st_mode) != 0o700:
        os.close(fd)
        raise EvidenceStoreError("EVIDENCE_DIR_PERMISSIONS_INVALID")
    if hasattr(os, "geteuid") and directory_stat.st_uid != os.geteuid():
        os.close(fd)
        raise EvidenceStoreError("EVIDENCE_DIR_OWNER_INVALID")
    return fd


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    written = 0
    while written < len(view):
        count = os.write(fd, view[written:])
        if count <= 0:
            raise OSError("short write")
        written += count


def _read_limited(fd: int, maximum: int) -> bytes | None:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = os.read(fd, min(65_536, maximum + 1 - total))
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
        total += len(chunk)
        if total > maximum:
            return None


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
    """Persist one snapshot using same-directory, no-overwrite atomic publish.

    A failure after the final hard link is created (for example directory fsync
    failure) can leave a valid final snapshot even though this function raises.
    Callers must therefore treat raised errors as "durability not confirmed",
    not as proof that no file exists.
    """

    _require_platform_support()
    subject = _require_text(subject_id, "subject_id")
    issue_text = _require_text(issue, "issue")
    status_text = _optional_status(reported_status)
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
        "reported_status": status_text,
        "diagnostics": dict(diagnostics),
    }
    validation = validate_evidence_snapshot(payload)
    if not validation["ok"]:
        raise EvidenceStoreError(";".join(validation["issues"]))
    canonical = _canonical_json_bytes(payload)
    data = canonical + b"\n"
    content_digest = sha256(data).hexdigest()

    directory = Path(evidence_dir)
    _ensure_directory(directory)
    dir_fd = _open_directory_fd(directory)
    filename = _filename_for_snapshot(payload)
    temp_name = f".evidence-{secrets.token_hex(16)}.tmp"
    temp_fd: int | None = None
    temp_exists = False

    try:
        open_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        temp_fd = os.open(temp_name, open_flags, 0o600, dir_fd=dir_fd)
        temp_exists = True
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

        try:
            os.unlink(temp_name, dir_fd=dir_fd)
            temp_exists = False
        except OSError as exc:
            raise EvidenceStoreError("EVIDENCE_TEMP_CLEANUP_FAILED") from exc

        try:
            os.fsync(dir_fd)
        except OSError as exc:
            raise EvidenceStoreError("EVIDENCE_DIRECTORY_FSYNC_FAILED") from exc
    finally:
        if temp_fd is not None:
            try:
                os.close(temp_fd)
            except OSError:
                pass
        if temp_exists:
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
        "content_sha256": content_digest,
    }


def _read_snapshot_name(dir_fd: int, name: str) -> tuple[dict[str, Any], str] | None:
    flags = os.O_RDONLY | os.O_NOFOLLOW
    file_fd: int | None = None
    try:
        file_fd = os.open(name, flags, dir_fd=dir_fd)
        file_stat = os.fstat(file_fd)
        if not stat.S_ISREG(file_stat.st_mode):
            return None
        if stat.S_IMODE(file_stat.st_mode) != 0o600:
            return None
        if hasattr(os, "geteuid") and file_stat.st_uid != os.geteuid():
            return None
        if file_stat.st_size > MAX_EVIDENCE_BYTES + 1:
            return None
        data = _read_limited(file_fd, MAX_EVIDENCE_BYTES + 1)
        if data is None:
            return None
        payload = json.loads(data.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        return None
    finally:
        if file_fd is not None:
            try:
                os.close(file_fd)
            except OSError:
                pass

    validation = validate_evidence_snapshot(payload)
    if not validation["ok"]:
        return None
    try:
        expected_bytes = _canonical_json_bytes(payload) + b"\n"
        expected_name = _filename_for_snapshot(payload)
    except (EvidenceStoreError, KeyError, TypeError, ValueError, RecursionError):
        return None
    if data != expected_bytes or name != expected_name:
        return None
    return payload, sha256(data).hexdigest()


def list_recent_evidence(
    evidence_dir: str | os.PathLike[str],
    *,
    limit: int = MAX_RECENT_EVIDENCE,
) -> list[dict[str, Any]]:
    """Return summaries of valid snapshots only; no writes are performed."""

    _require_platform_support()
    if type(limit) is not int or isinstance(limit, bool) or not (1 <= limit <= MAX_LIST_LIMIT):
        raise EvidenceStoreError("EVIDENCE_LIMIT_INVALID")

    directory = Path(evidence_dir)
    if not directory.exists():
        return []
    if directory.is_symlink() or not directory.is_dir():
        raise EvidenceStoreError("EVIDENCE_DIR_INVALID")

    dir_fd = _open_directory_fd(directory)
    try:
        try:
            names = sorted(
                (
                    name
                    for name in os.listdir(dir_fd)
                    if type(name) is str and name.endswith(".json")
                ),
                reverse=True,
            )
        except OSError as exc:
            raise EvidenceStoreError("EVIDENCE_DIR_LIST_FAILED") from exc

        items: list[dict[str, Any]] = []
        for name in names:
            read_result = _read_snapshot_name(dir_fd, name)
            if read_result is None:
                continue
            payload, content_digest = read_result
            items.append(
                {
                    "evidence_id": payload["evidence_id"],
                    "captured_at_utc": payload["captured_at_utc"],
                    "subject_id": payload["subject_id"],
                    "issue": payload["issue"],
                    "reported_status": payload["reported_status"],
                    "content_sha256": content_digest,
                    "filename": name,
                    "path": str(directory / name),
                }
            )
            if len(items) >= limit:
                break
        return items
    finally:
        os.close(dir_fd)
