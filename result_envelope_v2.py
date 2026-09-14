"""Fail-closed Result Envelope v2 reference contract.

This module defines only a deterministic data contract. A valid envelope does not
prove that work ran, evidence is authentic, isolation succeeded, or a process
terminated. Those guarantees belong to the surrounding execution-evidence system.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
import struct
import unicodedata
from typing import Any, Mapping


PROTOCOL_VERSION_V2 = "execution-result-envelope-v2"
ENVELOPE_VERSION_V2 = 2
HASH_PROTOCOL_V2 = "execution-result-envelope-hash-v1"
HASH_DOMAIN_V2 = b"EXECUTION-EVIDENCE-CONTRACTS\x00RESULT-ENVELOPE\x00V2\x00"

MAX_CANONICAL_BYTES = 262_144
MAX_JSON_INPUT_BYTES = 1_048_576
MAX_NESTING_DEPTH = 16
MAX_OBJECT_KEYS = 128
MAX_COLLECTION_ITEMS = 256
MAX_STRING_BYTES = 4_096
MAX_IDENTITY_BYTES = 256

RESULT_STATUSES_V2 = frozenset(
    {"SUCCEEDED", "PARTIAL", "FAILED", "REJECTED", "CANCELLED", "TIMED_OUT"}
)
RESULT_KINDS_V2 = frozenset({"RESEARCH", "BUSINESS", "TRADING", "COMPOSITE", "GENERIC"})
REFERENCE_TYPES_V2 = frozenset({"ARTIFACT", "LOG", "SOURCE", "RECEIPT", "OTHER"})
REFERENCE_FIELDS_V2 = frozenset({"reference_id", "reference_type", "sha256", "locator"})

REQUIRED_FIELDS_V2 = frozenset(
    {
        "protocol_version",
        "envelope_version",
        "hash_protocol",
        "result_kind",
        "result_id",
        "mission_id",
        "attempt_id",
        "unit_id",
        "task_id",
        "execution_id",
        "agent_id",
        "capability",
        "status",
        "started_at_utc",
        "finished_at_utc",
        "created_at_utc",
        "payload",
        "evidence_references",
        "provenance_references",
        "warnings",
        "limitations",
        "security_metadata",
        "injection_metadata",
        "resource_usage",
        "result_hash",
    }
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class _CanonicalError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def _check_string(value: Any, *, identity: bool = False, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if type(value) is not str:
        raise TypeError("IDENTITY_TYPE_INVALID" if identity else "STRING_TYPE_INVALID")
    if not value or value != value.strip():
        raise ValueError("IDENTITY_INVALID" if identity else "STRING_INVALID")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError("IDENTITY_INVALID" if identity else "STRING_INVALID")
    if _nfc(value) != value:
        raise ValueError("IDENTITY_NFC_INVALID" if identity else "STRING_NFC_INVALID")
    limit = MAX_IDENTITY_BYTES if identity else MAX_STRING_BYTES
    if len(value.encode("utf-8")) > limit:
        raise ValueError("IDENTITY_LIMIT" if identity else "STRING_LIMIT")
    return value


def _parse_explicit_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif type(value) is str:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("TIMESTAMP_INVALID") from exc
    else:
        raise TypeError("TIMESTAMP_TYPE_INVALID")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("TIMESTAMP_TIMEZONE_REQUIRED")
    return parsed


def _timestamp_wire(value: Any) -> str:
    parsed = _parse_explicit_timestamp(value)
    return parsed.astimezone(timezone.utc).isoformat()


def _parse_wire_timestamp(value: Any) -> tuple[datetime | None, str | None]:
    if type(value) is not str:
        return None, "TIME_TYPE_INVALID"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None, "TIME_INVALID"
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None, "TIMEZONE_REQUIRED"
    if _nfc(value) != value:
        return None, "TIME_NFC_INVALID"
    if len(value.encode("utf-8")) > MAX_STRING_BYTES:
        return None, "STRING_LIMIT"
    normalized = parsed.astimezone(timezone.utc)
    if value != normalized.isoformat():
        return None, "TIME_CANONICAL_INVALID"
    return normalized, None


def _u64(value: int) -> bytes:
    return struct.pack(">Q", value)


def _canonical_encode(value: Any, *, depth: int) -> bytes:
    if depth > MAX_NESTING_DEPTH:
        raise _CanonicalError("DEPTH_LIMIT")
    if value is None:
        return b"N"
    if type(value) is bool:
        return b"T" if value else b"F"
    if type(value) is int:
        if value < -(2**63) or value > 2**63 - 1:
            raise _CanonicalError("INTEGER_RANGE")
        return b"I" + struct.pack(">q", value)
    if type(value) is float:
        raise _CanonicalError("FLOAT_NOT_ALLOWED")
    if type(value) is str:
        normalized = _nfc(value)
        if normalized != value:
            raise _CanonicalError("NFC_REQUIRED")
        data = value.encode("utf-8")
        if len(data) > MAX_STRING_BYTES:
            raise _CanonicalError("STRING_LIMIT")
        return b"S" + _u64(len(data)) + data
    if type(value) is list:
        if len(value) > MAX_COLLECTION_ITEMS:
            raise _CanonicalError("COLLECTION_LIMIT")
        parts = [b"L", _u64(len(value))]
        for item in value:
            parts.append(_canonical_encode(item, depth=depth + 1))
        return b"".join(parts)
    if type(value) is dict:
        if len(value) > MAX_OBJECT_KEYS:
            raise _CanonicalError("OBJECT_KEY_LIMIT")
        normalized_keys: dict[str, str] = {}
        for key in value:
            if type(key) is not str:
                raise _CanonicalError("OBJECT_KEY_TYPE")
            normalized = _nfc(key)
            previous = normalized_keys.get(normalized)
            if previous is not None and previous != key:
                raise _CanonicalError("NORMALIZED_KEY_COLLISION")
            normalized_keys[normalized] = key
        for normalized, original in normalized_keys.items():
            if normalized != original:
                raise _CanonicalError("NFC_REQUIRED")
        ordered = sorted(value, key=lambda key: key.encode("utf-8"))
        parts = [b"O", _u64(len(ordered))]
        for key in ordered:
            parts.append(_canonical_encode(key, depth=depth + 1))
            parts.append(_canonical_encode(value[key], depth=depth + 1))
        return b"".join(parts)
    raise _CanonicalError("UNSUPPORTED_CANONICAL_TYPE")


def canonical_bytes_v2(value: Any) -> bytes:
    """Return deterministic binary canonical bytes for accepted v2 data."""
    encoded = _canonical_encode(value, depth=0)
    if len(encoded) > MAX_CANONICAL_BYTES:
        raise _CanonicalError("ENVELOPE_SIZE_LIMIT")
    return encoded


def hash_unsigned_envelope_v2(envelope: Mapping[str, Any]) -> str:
    """Return the protocol hash only for canonical v2-shaped data.

    There is intentionally no invalid-data fallback. Noncanonical data does not
    receive a protocol hash under this API.
    """
    if not isinstance(envelope, Mapping):
        raise TypeError("RESULT_ENVELOPE_MAPPING_REQUIRED")
    unsigned = {key: value for key, value in dict(envelope).items() if key != "result_hash"}
    payload = canonical_bytes_v2(unsigned)
    return sha256(HASH_DOMAIN_V2 + payload).hexdigest()


def _json_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    normalized_seen: dict[str, str] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_JSON_KEY")
        normalized = _nfc(key)
        if normalized in normalized_seen and normalized_seen[normalized] != key:
            raise ValueError("NORMALIZED_KEY_COLLISION")
        normalized_seen[normalized] = key
        result[key] = value
    return result


def decode_result_envelope_v2_json(text_or_bytes: str | bytes) -> Any:
    if isinstance(text_or_bytes, bytes):
        if len(text_or_bytes) > MAX_JSON_INPUT_BYTES:
            raise ValueError("JSON_INPUT_SIZE_LIMIT")
        try:
            text = text_or_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("INVALID_UTF8") from exc
    elif type(text_or_bytes) is str:
        if len(text_or_bytes) > MAX_JSON_INPUT_BYTES:
            raise ValueError("JSON_INPUT_SIZE_LIMIT")
        encoded = text_or_bytes.encode("utf-8")
        if len(encoded) > MAX_JSON_INPUT_BYTES:
            raise ValueError("JSON_INPUT_SIZE_LIMIT")
        text = text_or_bytes
    else:
        raise TypeError("JSON_TEXT_REQUIRED")

    def reject_constant(value: str) -> None:
        raise ValueError(f"NONFINITE_JSON_NUMBER:{value}")

    try:
        value = json.loads(
            text,
            object_pairs_hook=_json_object_pairs,
            parse_constant=reject_constant,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        if isinstance(exc, ValueError) and not isinstance(exc, json.JSONDecodeError):
            raise
        raise ValueError("INVALID_JSON") from exc
    return value


def _builder_identity(value: Any, field: str, *, nullable: bool = False) -> str | None:
    try:
        return _check_string(value, identity=True, nullable=nullable)
    except (TypeError, ValueError) as exc:
        exc.args = (f"{field}:{exc.args[0]}",)
        raise


def build_result_envelope_v2(
    *,
    result_kind: str,
    result_id: str,
    mission_id: str,
    attempt_id: str,
    unit_id: str,
    task_id: str | None,
    execution_id: str | None,
    agent_id: str,
    capability: str,
    status: str,
    started_at_utc: datetime | str,
    finished_at_utc: datetime | str,
    created_at_utc: datetime | str,
    payload: Mapping[str, Any],
    evidence_references: list[Any],
    provenance_references: list[Any],
    warnings: list[Any],
    limitations: list[Any],
    security_metadata: Mapping[str, Any],
    injection_metadata: Mapping[str, Any],
    resource_usage: Mapping[str, Any],
) -> dict[str, Any]:
    if type(result_kind) is not str or result_kind not in RESULT_KINDS_V2:
        raise ValueError("RESULT_KIND_INVALID")
    if type(status) is not str or status not in RESULT_STATUSES_V2:
        raise ValueError("STATUS_INVALID")

    normalized_started = _timestamp_wire(started_at_utc)
    normalized_finished = _timestamp_wire(finished_at_utc)
    normalized_created = _timestamp_wire(created_at_utc)
    started_dt = _parse_explicit_timestamp(normalized_started)
    finished_dt = _parse_explicit_timestamp(normalized_finished)
    created_dt = _parse_explicit_timestamp(normalized_created)
    if not (started_dt <= finished_dt <= created_dt):
        raise ValueError("TIME_ORDER_INVALID")

    envelope: dict[str, Any] = {
        "protocol_version": PROTOCOL_VERSION_V2,
        "envelope_version": ENVELOPE_VERSION_V2,
        "hash_protocol": HASH_PROTOCOL_V2,
        "result_kind": result_kind,
        "result_id": _builder_identity(result_id, "result_id"),
        "mission_id": _builder_identity(mission_id, "mission_id"),
        "attempt_id": _builder_identity(attempt_id, "attempt_id"),
        "unit_id": _builder_identity(unit_id, "unit_id"),
        "task_id": _builder_identity(task_id, "task_id", nullable=True),
        "execution_id": _builder_identity(execution_id, "execution_id", nullable=True),
        "agent_id": _builder_identity(agent_id, "agent_id"),
        "capability": _builder_identity(capability, "capability"),
        "status": status,
        "started_at_utc": normalized_started,
        "finished_at_utc": normalized_finished,
        "created_at_utc": normalized_created,
        "payload": deepcopy(dict(payload)),
        "evidence_references": deepcopy(list(evidence_references)),
        "provenance_references": deepcopy(list(provenance_references)),
        "warnings": deepcopy(list(warnings)),
        "limitations": deepcopy(list(limitations)),
        "security_metadata": deepcopy(dict(security_metadata)),
        "injection_metadata": deepcopy(dict(injection_metadata)),
        "resource_usage": deepcopy(dict(resource_usage)),
    }
    envelope["result_hash"] = hash_unsigned_envelope_v2(envelope)
    return envelope


def _add(issues: list[str], code: str) -> None:
    if code not in issues:
        issues.append(code)


def _identity_issue(value: Any, field: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if type(value) is not str:
        return f"IDENTITY_TYPE_INVALID:{field}"
    if not value or value != value.strip() or any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        return f"IDENTITY_INVALID:{field}"
    if _nfc(value) != value:
        return f"IDENTITY_NFC_INVALID:{field}"
    if len(value.encode("utf-8")) > MAX_IDENTITY_BYTES:
        return f"IDENTITY_LIMIT:{field}"
    return None


def _validate_reference_list(value: Any, field: str, issues: list[str]) -> None:
    if type(value) is not list:
        _add(issues, f"REFERENCE_LIST_INVALID:{field}")
        return
    for index, ref in enumerate(value):
        prefix = f"{field}[{index}]"
        if type(ref) is not dict or set(ref) != REFERENCE_FIELDS_V2:
            _add(issues, f"REFERENCE_SHAPE_INVALID:{prefix}")
            continue
        identity_issue = _identity_issue(ref.get("reference_id"), prefix + ".reference_id")
        if identity_issue:
            _add(issues, "REFERENCE_ID_INVALID:" + prefix)
        reference_type = ref.get("reference_type")
        if type(reference_type) is not str or reference_type not in REFERENCE_TYPES_V2:
            _add(issues, "REFERENCE_TYPE_INVALID:" + prefix)
        digest = ref.get("sha256")
        if type(digest) is not str or _SHA256_RE.fullmatch(digest) is None:
            _add(issues, "SHA256_INVALID:" + prefix)
        locator = ref.get("locator")
        if locator is not None:
            if type(locator) is not str:
                _add(issues, "REFERENCE_LOCATOR_INVALID:" + prefix)
            else:
                if _nfc(locator) != locator:
                    _add(issues, "NFC_REQUIRED:" + prefix + ".locator")
                if len(locator.encode("utf-8")) > MAX_STRING_BYTES:
                    _add(issues, "STRING_LIMIT:" + prefix + ".locator")


def _validate_text_list(value: Any, field: str, issues: list[str]) -> None:
    if type(value) is not list:
        _add(issues, f"{field.upper()}_INVALID")
        return
    seen: set[str] = set()
    for item in value:
        if type(item) is not str or not item or item != item.strip():
            _add(issues, f"{field.upper()}_INVALID")
            continue
        if item in seen:
            _add(issues, f"{field.upper()}_DUPLICATE")
        seen.add(item)
        if _nfc(item) != item:
            _add(issues, f"{field.upper()}_NFC_INVALID")
        if len(item.encode("utf-8")) > MAX_STRING_BYTES:
            _add(issues, f"STRING_LIMIT:{field}")


def _map_canonical_error(code: str) -> str:
    if code == "FLOAT_NOT_ALLOWED":
        return "FLOAT_NOT_ALLOWED"
    if code == "NFC_REQUIRED":
        return "NFC_REQUIRED"
    if code == "NORMALIZED_KEY_COLLISION":
        return "NORMALIZED_KEY_COLLISION"
    if code == "STRING_LIMIT":
        return "STRING_LIMIT"
    if code == "COLLECTION_LIMIT":
        return "COLLECTION_LIMIT"
    if code == "OBJECT_KEY_LIMIT":
        return "OBJECT_KEY_LIMIT"
    if code == "DEPTH_LIMIT":
        return "DEPTH_LIMIT"
    if code == "ENVELOPE_SIZE_LIMIT":
        return "ENVELOPE_SIZE_LIMIT"
    return "CANONICAL_DATA_INVALID:" + code


def validate_result_envelope_v2(envelope: Any) -> dict[str, Any]:
    issues: list[str] = []
    if type(envelope) is not dict:
        return {"ok": False, "issues": ["RESULT_ENVELOPE_INVALID"]}

    string_keys: set[str] = set()
    for key in envelope:
        if type(key) is not str:
            _add(issues, "TOP_LEVEL_KEY_TYPE_INVALID")
        else:
            string_keys.add(key)
    for key in sorted(string_keys - REQUIRED_FIELDS_V2):
        _add(issues, f"UNKNOWN_FIELD:{key}")
    for key in sorted(REQUIRED_FIELDS_V2 - string_keys):
        _add(issues, f"MISSING_FIELD:{key}")

    if envelope.get("protocol_version") != PROTOCOL_VERSION_V2:
        _add(issues, "PROTOCOL_VERSION_UNSUPPORTED")
    if type(envelope.get("envelope_version")) is not int or envelope.get("envelope_version") != ENVELOPE_VERSION_V2:
        _add(issues, "ENVELOPE_VERSION_UNSUPPORTED")
    if envelope.get("hash_protocol") != HASH_PROTOCOL_V2:
        _add(issues, "HASH_PROTOCOL_UNSUPPORTED")
    result_kind = envelope.get("result_kind")
    if type(result_kind) is not str or result_kind not in RESULT_KINDS_V2:
        _add(issues, "RESULT_KIND_INVALID")
    status = envelope.get("status")
    if type(status) is not str or status not in RESULT_STATUSES_V2:
        _add(issues, "STATUS_INVALID")

    for field in ("result_id", "mission_id", "attempt_id", "unit_id", "agent_id", "capability"):
        issue = _identity_issue(envelope.get(field), field)
        if issue:
            _add(issues, issue)
    for field in ("task_id", "execution_id"):
        issue = _identity_issue(envelope.get(field), field, nullable=True)
        if issue:
            _add(issues, issue)

    parsed_times: dict[str, datetime] = {}
    for field in ("started_at_utc", "finished_at_utc", "created_at_utc"):
        parsed, issue = _parse_wire_timestamp(envelope.get(field))
        if issue:
            _add(issues, f"{issue}:{field}")
        elif parsed is not None:
            parsed_times[field] = parsed
    if len(parsed_times) == 3:
        if not (
            parsed_times["started_at_utc"]
            <= parsed_times["finished_at_utc"]
            <= parsed_times["created_at_utc"]
        ):
            _add(issues, "TIME_ORDER_INVALID")

    for field in ("payload", "security_metadata", "injection_metadata", "resource_usage"):
        if type(envelope.get(field)) is not dict:
            _add(issues, f"MAPPING_INVALID:{field}")

    _validate_reference_list(envelope.get("evidence_references"), "evidence_references", issues)
    _validate_reference_list(envelope.get("provenance_references"), "provenance_references", issues)
    _validate_text_list(envelope.get("warnings"), "warnings", issues)
    _validate_text_list(envelope.get("limitations"), "limitations", issues)

    unsigned = {key: value for key, value in envelope.items() if key != "result_hash"}
    canonical_ok = True
    try:
        canonical_bytes_v2(unsigned)
    except _CanonicalError as exc:
        canonical_ok = False
        _add(issues, _map_canonical_error(exc.code))

    result_hash = envelope.get("result_hash")
    if type(result_hash) is not str or _SHA256_RE.fullmatch(result_hash) is None:
        _add(issues, "HASH_FORMAT_INVALID")
    elif canonical_ok:
        try:
            expected_hash = hash_unsigned_envelope_v2(envelope)
        except (TypeError, ValueError):
            _add(issues, "HASH_INPUT_INVALID")
        else:
            if result_hash != expected_hash:
                _add(issues, "HASH_BINDING_INVALID")

    return {"ok": not issues, "issues": issues}


def validate_result_binding_v2(
    envelope: Any,
    *,
    expected_attempt_id: str,
    expected_unit_id: str,
) -> dict[str, Any]:
    issues: list[str] = []
    try:
        _check_string(expected_attempt_id, identity=True)
        _check_string(expected_unit_id, identity=True)
    except (TypeError, ValueError):
        return {"ok": False, "issues": ["EXPECTED_BINDING_INVALID"]}

    validation = validate_result_envelope_v2(envelope)
    if not validation["ok"]:
        return {
            "ok": False,
            "issues": ["ENVELOPE_INVALID"] + list(validation["issues"]),
        }

    if envelope.get("attempt_id") != expected_attempt_id:
        _add(issues, "ATTEMPT_BINDING_MISMATCH")
    if envelope.get("unit_id") != expected_unit_id:
        _add(issues, "UNIT_BINDING_MISMATCH")
    return {"ok": not issues, "issues": issues}
