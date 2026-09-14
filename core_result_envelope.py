"""The single canonical Result Envelope V1 for all JARVIS result types."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Mapping


RESULT_ENVELOPE_PROTOCOL_VERSION = "jarvis-result-envelope-v1"
RESULT_ENVELOPE_VERSION = 1
RESULT_STATUSES = frozenset(
    {"SUCCEEDED", "PARTIAL", "FAILED", "REJECTED", "CANCELLED", "TIMED_OUT"}
)
RESULT_KINDS = frozenset({"RESEARCH", "BUSINESS", "TRADING", "COMPOSITE", "GENERIC"})

REQUIRED_FIELDS = frozenset(
    {
        "protocol_version",
        "envelope_version",
        "result_kind",
        "result_id",
        "mission_id",
        "task_id",
        "execution_id",
        "agent_id",
        "capability",
        "status",
        "started_at_utc",
        "finished_at_utc",
        "payload",
        "result_hash",
        "evidence_references",
        "provenance_references",
        "warnings",
        "limitations",
        "security_metadata",
        "injection_metadata",
        "resource_usage",
        "signature_metadata",
        "created_at_utc",
    }
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def hash_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _parse(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _iso(value: datetime | str | None) -> str:
    if isinstance(value, str):
        parsed = _parse(value)
    else:
        parsed = value
    if parsed is None:
        parsed = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        raise ValueError("RESULT_TIMESTAMP_MUST_BE_TIMEZONE_AWARE")
    return parsed.astimezone(timezone.utc).isoformat()


def build_result_envelope(
    *,
    result_kind: str,
    result_id: str,
    mission_id: str,
    agent_id: str,
    capability: str,
    status: str,
    payload: Mapping[str, Any],
    started_at_utc: datetime | str,
    finished_at_utc: datetime | str,
    task_id: str | None = None,
    execution_id: str | None = None,
    evidence_references: list[Any] | None = None,
    provenance_references: list[Any] | None = None,
    warnings: list[Any] | None = None,
    limitations: list[Any] | None = None,
    security_metadata: Mapping[str, Any] | None = None,
    injection_metadata: Mapping[str, Any] | None = None,
    resource_usage: Mapping[str, Any] | None = None,
    signature_metadata: Mapping[str, Any] | None = None,
    created_at_utc: datetime | str | None = None,
) -> dict[str, Any]:
    normalized_status = str(status).upper()
    if normalized_status not in RESULT_STATUSES:
        raise ValueError("RESULT_STATUS_INVALID")
    normalized_kind = str(result_kind).upper()
    if normalized_kind not in RESULT_KINDS:
        raise ValueError("RESULT_KIND_INVALID")
    envelope = {
        "protocol_version": RESULT_ENVELOPE_PROTOCOL_VERSION,
        "envelope_version": RESULT_ENVELOPE_VERSION,
        "result_kind": normalized_kind,
        "result_id": str(result_id),
        "mission_id": str(mission_id),
        "task_id": task_id,
        "execution_id": execution_id,
        "agent_id": str(agent_id),
        "capability": str(capability).upper(),
        "status": normalized_status,
        "started_at_utc": _iso(started_at_utc),
        "finished_at_utc": _iso(finished_at_utc),
        "payload": dict(payload),
        "evidence_references": list(evidence_references or []),
        "provenance_references": list(provenance_references or []),
        "warnings": list(warnings or []),
        "limitations": list(limitations or []),
        "security_metadata": dict(security_metadata or {}),
        "injection_metadata": dict(injection_metadata or {}),
        "resource_usage": dict(resource_usage or {}),
        "signature_metadata": dict(signature_metadata or {}),
        "created_at_utc": _iso(created_at_utc or finished_at_utc),
    }
    envelope["result_hash"] = hash_value(envelope)
    return envelope


def validate_result_envelope(envelope: Any) -> dict[str, Any]:
    issues: list[str] = []
    if not isinstance(envelope, Mapping):
        return {"ok": False, "issues": ["RESULT_ENVELOPE_INVALID"]}
    missing = REQUIRED_FIELDS - set(envelope)
    if missing:
        issues.append("RESULT_ENVELOPE_FIELDS_MISSING:" + ",".join(sorted(missing)))
    if envelope.get("protocol_version") != RESULT_ENVELOPE_PROTOCOL_VERSION:
        issues.append("RESULT_ENVELOPE_PROTOCOL_UNSUPPORTED")
    if envelope.get("envelope_version") != RESULT_ENVELOPE_VERSION:
        issues.append("RESULT_ENVELOPE_VERSION_UNSUPPORTED")
    if envelope.get("result_kind") not in RESULT_KINDS:
        issues.append("RESULT_ENVELOPE_KIND_INVALID")
    if envelope.get("status") not in RESULT_STATUSES:
        issues.append("RESULT_ENVELOPE_STATUS_INVALID")
    for key in ("result_id", "mission_id", "agent_id", "capability"):
        if not str(envelope.get(key) or ""):
            issues.append("RESULT_ENVELOPE_IDENTITY_INVALID:" + key)
    started = _parse(envelope.get("started_at_utc"))
    finished = _parse(envelope.get("finished_at_utc"))
    created = _parse(envelope.get("created_at_utc"))
    if started is None or finished is None or created is None or finished < started or created < started:
        issues.append("RESULT_ENVELOPE_TIME_INVALID")
    for key in ("evidence_references", "provenance_references", "warnings", "limitations"):
        if not isinstance(envelope.get(key), list):
            issues.append("RESULT_ENVELOPE_LIST_INVALID:" + key)
    for key in ("payload", "security_metadata", "injection_metadata", "resource_usage", "signature_metadata"):
        if not isinstance(envelope.get(key), Mapping):
            issues.append("RESULT_ENVELOPE_MAPPING_INVALID:" + key)
    unsigned = {key: value for key, value in envelope.items() if key != "result_hash"}
    if envelope.get("result_hash") != hash_value(unsigned):
        issues.append("RESULT_ENVELOPE_HASH_INVALID")
    return {"ok": not issues, "issues": list(dict.fromkeys(issues))}


def adapt_typed_result(
    result_kind: str,
    result: Mapping[str, Any],
    *,
    agent_id: str,
    capability: str,
    task_id: str | None = None,
    execution_id: str | None = None,
    signature_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize Research, Business, Trading or Composite output without mutating it."""

    status = str(result.get("status") or result.get("execution_state") or "FAILED").upper()
    status = {"COMPLETED": "SUCCEEDED", "TIMEOUT": "TIMED_OUT"}.get(status, status)
    started = result.get("started_at_utc") or result.get("started_at") or result.get("timestamp_utc")
    finished = result.get("finished_at_utc") or result.get("finished_at") or result.get("timestamp_utc") or started
    result_id = result.get("result_id") or result.get("mission_result_id") or result.get("composite_result_id")
    mission_id = result.get("mission_id") or result.get("parent_mission_id")
    injection = result.get("injection_metadata")
    if not isinstance(injection, Mapping):
        injection = {
            "injection_suspected": bool(result.get("injection_suspected")),
            "flag_count": int(result.get("injection_flags") or 0),
        }
    evidence = result.get("evidence_references") or result.get("evidence_refs") or []
    provenance = result.get("provenance_references") or result.get("provenance_refs") or []
    return build_result_envelope(
        result_kind=result_kind,
        result_id=str(result_id or ""),
        mission_id=str(mission_id or ""),
        agent_id=agent_id,
        capability=capability,
        status=status,
        payload={"typed_result": dict(result)},
        started_at_utc=started,
        finished_at_utc=finished,
        task_id=task_id,
        execution_id=execution_id,
        evidence_references=list(evidence),
        provenance_references=list(provenance),
        warnings=list(result.get("warnings") or []),
        limitations=list(result.get("limitations") or []),
        security_metadata=dict(result.get("security_metadata") or {}),
        injection_metadata=dict(injection),
        resource_usage=dict(result.get("resource_usage") or {}),
        signature_metadata=signature_metadata,
        created_at_utc=finished,
    )
