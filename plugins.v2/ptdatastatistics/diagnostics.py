"""等级规则排障导出；只接受插件投影的数据，不导出认证信息或域名。"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from .core import as_text, build_retirement_progress, match_retirement_rule

_PRIVATE_KEYS = {
    "domain", "domains", "username", "userid", "cookie", "password", "encrypted",
    "authorization", "headers", "ptd_cookiecloud_uuid", "ptd_cookiecloud_password",
    "ptd_cookiecloud_headers", "ptd_site_mappings", "wealthy_retirement_sites",
    "token", "passkey", "api_key", "apikey", "api-key", "x-api-key", "access_token", "accesstoken",
}
_URL = re.compile(r"(?:https?|wss?)://[^\s<>\"']+", re.IGNORECASE)
_HOST = re.compile(r"(?<![\w-])(?:[\w-]+\.)+[a-z]{2,63}(?::\d+)?(?![\w-])", re.IGNORECASE)
_CREDENTIAL = re.compile(
    r"\b(?:cookie|authorization)\s*[:=]\s*[^\r\n]+"
    r"|\b(?:(?:x-)?api[-_]?key|token|passkey|password|uuid)\s*[:=]\s*(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)",
    re.IGNORECASE,
)


def _sanitizer(settings: dict[str, Any], records: list[dict[str, Any]]):
    """递归删除私密字段，并清理错误信息和规则说明中的链接及凭据。"""

    secrets = {
        as_text(settings.get(key)) for key in ("ptd_cookiecloud_uuid", "ptd_cookiecloud_password")
    }
    for line in as_text(settings.get("ptd_cookiecloud_headers")).splitlines():
        if ":" in line:
            secrets.add(line.split(":", 1)[1].strip())
    identities = set()
    for record in records:
        secrets.add(as_text(record.get("domain")))
        identities.update(as_text(record.get(key)) for key in ("username", "userid"))
    secrets.discard("")
    identities.discard("")
    replacements = sorted(secrets, key=len, reverse=True)

    def clean(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {
                clean(str(key)): clean_error(item) if str(key) == "err_msg" else clean(item)
                for key, item in value.items()
                if str(key).casefold() not in _PRIVATE_KEYS
            }
        if isinstance(value, (list, tuple)):
            return [clean(item) for item in value]
        if isinstance(value, str):
            value = _URL.sub("[链接已移除]", value)
            value = _CREDENTIAL.sub("[凭据已移除]", value)
            value = _HOST.sub("[域名已移除]", value)
            for secret in replacements:
                # 短数字用户 ID 只清理独立词，避免破坏日期、版本与数值文本。
                if len(secret) >= 4:
                    value = value.replace(secret, "[已移除]")
                else:
                    value = re.sub(r"(?<!\w)" + re.escape(secret) + r"(?!\w)", "[已移除]", value)
            return value
        return value

    def clean_error(value: Any) -> Any:
        if isinstance(value, str):
            for identity in sorted(identities, key=len, reverse=True):
                value = value.replace(identity, "[账号已移除]")
        return clean(value)

    return clean


def build_diagnostic_export(
    *, plugin_version: str, generated_at: str, timezone: str,
    configured_sites: list[dict[str, Any]], raw_records: list[dict[str, Any]],
    daily_records: list[dict[str, Any]], calculation_inputs: list[dict[str, Any]],
    ptd_metrics: dict[str, dict[str, Any]], settings: dict[str, Any],
    rules: dict[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """保留三类数据，以及同一批输入对应的规则匹配与计算结果。"""

    all_records = [*configured_sites, *raw_records, *ptd_metrics.values()]
    clean = _sanitizer(settings, all_records)
    # 旧域名可能已经没有 MP 站点 ID，以导出内的序号关联历史，避免泄露域名。
    references: dict[str, str] = {}
    for record in all_records:
        domain = as_text(record.get("domain"))
        if domain not in references:
            references[domain] = f"site-{len(references) + 1}"

    def with_ref(record: Mapping[str, Any]) -> dict[str, Any]:
        return {**record, "site_ref": references.get(as_text(record.get("domain")), "")}

    progress = build_retirement_progress(
        calculation_inputs, rules, settings.get("wealthy_retirement_sites") or [],
    )
    results = {as_text(item.get("domain")): item for item in progress["sites"]}
    latest_mp = {
        (as_text(item.get("domain")), as_text(item.get("updated_day"))): item
        for item in daily_records
    }
    inputs = []
    for snapshot in calculation_inputs:
        domain = as_text(snapshot.get("domain"))
        ptd = ptd_metrics.get(domain)
        mp = latest_mp.get((domain, as_text(snapshot.get("updated_day"))), {})
        sources = {
            key: "moviepilot" if snapshot.get(key) is not None else "unavailable"
            for key in (
                "join_at", "user_level", "upload", "download", "ratio", "bonus", "seeding",
                "seeding_size", "updated_day",
            )
        }
        if not as_text(mp.get("user_level")):
            sources["user_level"] = "ptd" if as_text(snapshot.get("user_level")) else "unavailable"
        for key in ("seeding_points", "seeding_points_hourly", "torrent_uploads", "estimated_bonus_hourly"):
            sources[key] = (
                "unavailable" if snapshot.get(key) is None
                else "ptd" if ptd is not None else "moviepilot_estimate"
            )
        sources["average_seeding_time_days"] = "unavailable"
        inputs.append({
            **with_ref(snapshot), "field_sources": sources,
            "ptd_source_updated_at": ptd.get("source_updated_at", "") if ptd else "",
        })

    inputs_by_domain = {as_text(item.get("domain")): item for item in calculation_inputs}
    matches = []
    for site in configured_sites:
        snapshot = inputs_by_domain.get(as_text(site.get("domain"))) or {
            **site, "site_id": site.get("id"), "site_name": site.get("name"),
        }
        matched = match_retirement_rule(snapshot, rules)
        result = results.get(as_text(site.get("domain")))
        matches.append({
            **with_ref({"site_id": site.get("id"), "site_name": site.get("name"), "domain": site.get("domain")}),
            "rule_key": matched["rule_key"],
            "rule_source": matched["source"],
            "matched_by": matched["matched_by"],
            "effective_rule": matched["rule"],
            "calculation_status": "calculated" if result else "inactive" if not site.get("is_active") else "no_successful_snapshot",
            "result": result,
        })

    return clean({
        "manifest": {
            "schema_version": 1, "plugin_version": plugin_version,
            "generated_at": generated_at, "timezone": timezone,
            "settings_scope": "saved", "raw_record_count": len(raw_records),
            "daily_record_count": len(daily_records),
            "limitations": ["域名及认证信息已移除；域名匹配仅保留结果，不能离线完整重放。"],
        },
        "sites": [with_ref(site) for site in configured_sites],
        "accounts_and_history": {
            "raw_daily_records": [with_ref(item) for item in raw_records],
            "daily_records": [with_ref(item) for item in daily_records],
            "calculation_inputs": inputs,
            "ptd_metrics": [with_ref(item) for item in ptd_metrics.values()],
        },
        "settings_and_rules": {
            "settings": settings,
            "manual_ptd_mapping_configured": bool(settings.get("ptd_site_mappings")),
            "manual_wealthy_site_refs": [
                references[domain] for domain, result in results.items()
                if result.get("wealthy_retirement_manual")
            ],
            "site_rules": matches,
        },
    })
