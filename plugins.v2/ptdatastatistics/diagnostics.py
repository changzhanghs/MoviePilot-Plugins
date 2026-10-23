"""等级规则排障导出；只接受插件投影的数据，不导出认证信息或域名。"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from .core import _match_level_index, as_text, match_retirement_rule, normalize_identity

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


def _level_names(levels) -> list[dict[str, Any]]:
    """仅保留等级匹配所需的名称和别名。"""

    return [
        {"name": level.get("name", ""), **({"aliases": list(level["aliases"])} if level.get("aliases") else {})}
        for level in levels
    ]


def build_diagnostic_export(
    *, plugin_version: str, generated_at: str,
    configured_sites: list[dict[str, Any]], latest_successful: list[dict[str, Any]],
    latest_records: list[dict[str, Any]], ptd_metrics: dict[str, dict[str, Any]],
    settings: dict[str, Any], rules: dict[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """每个启用站点仅导出一条匹配诊断，便于核对误匹配。"""

    successful = {item["domain"]: item for item in latest_successful}
    latest = {item["domain"]: item for item in latest_records}
    manually_wealthy = {normalize_identity(value) for value in settings.get("wealthy_retirement_sites") or []}
    records = []
    active_sites = [site for site in configured_sites if site.get("is_active")]
    for site in active_sites:
        domain = as_text(site.get("domain"))
        mp = successful.get(domain)
        base = {"site_id": site.get("id"), "site_name": site.get("name", "")}
        if mp is None:
            row = latest.get(domain, {})
            records.append({
                **base, "status": "no_data", "reason": "没有成功的 MoviePilot 站点数据，未进入养老进度计算",
                "mp_updated_at": row.get("source_updated_at", ""),
                "err_msg": row.get("err_msg", ""),
            })
            continue

        ptd_level = as_text(ptd_metrics.get(domain, {}).get("user_level"))
        mp_level = as_text(mp.get("user_level"))
        effective_level = mp_level or ptd_level
        snapshot = {**mp, "user_level": effective_level}
        match = match_retirement_rule(snapshot, rules)
        rule = match["rule"] or {}
        levels = list(rule.get("levels") or [])
        vip_levels = list(rule.get("vip_levels") or [])
        retirement = as_text(rule.get("retirement_level"))
        manual_wealthy = any(
            normalize_identity(value) in manually_wealthy
            for value in (domain, site.get("id"), snapshot.get("site_name"))
            if normalize_identity(value)
        )
        vip_index = _match_level_index(effective_level, vip_levels)
        current_index = _match_level_index(effective_level, levels)
        special_member = manual_wealthy or vip_index >= 0
        reason = ""
        if not levels:
            if not special_member:
                reason = "未匹配到站点规则" if match["rule"] is None else "命中规则但没有普通等级列表"
        elif retirement and _match_level_index(retirement, levels, exact_only=True) < 0:
            reason = "规则中的保号等级不在等级列表中"
        elif not special_member and current_index < 0:
            reason = "当前等级未提供" if not effective_level else "当前等级无法匹配规则中的等级名称或别名"
        record = {
            **base, "status": "unmatched" if reason else "matched", "reason": reason,
            "mp_updated_at": mp.get("source_updated_at", ""),
            "mp_level": mp_level, "ptd_level": ptd_level,
            "effective_level": effective_level,
            "level_source": "moviepilot" if mp_level else "ptd" if ptd_level else "unavailable",
            "rule_match": {
                "name": match["rule_key"], "source": match["source"], "matched_by": match["matched_by"],
                "matched_level": (
                    vip_levels[vip_index].get("name", "") if vip_index >= 0
                    else levels[current_index].get("name", "") if current_index >= 0 else ""
                ),
            },
        }
        if manual_wealthy:
            record["manual_wealthy"] = True
        if vip_index >= 0:
            record["vip_matched"] = True
        if rule:
            record["rule_match"].update({
                "retirement_level": retirement,
                "levels": _level_names(levels), "vip_levels": _level_names(vip_levels),
            })
        records.append(record)

    payload = {
        "manifest": {
            "schema_version": 3, "plugin_version": plugin_version, "generated_at": generated_at,
            "checked_sites": len(active_sites),
            "failed_sites": sum(record["status"] != "matched" for record in records),
        },
        "sites": records,
    }
    # 无法命中规则时，仅补充自定义站点名称及别名以核对覆盖配置。
    if any(item.get("rule_match", {}).get("matched_by") == "unmatched" for item in records):
        custom_names = [
            {"name": name, "aliases": list(rule.get("aliases") or [])}
            for name, rule in rules.items() if rule.get("_custom_rule")
        ]
        if custom_names:
            payload["custom_rule_names"] = custom_names
    return _sanitizer(settings, [*configured_sites, *latest_successful, *latest_records])(payload)
