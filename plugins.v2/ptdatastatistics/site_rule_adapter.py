"""Adapt bundled PTDepilerMp rules to PTDataStatistics' progress schema."""

from __future__ import annotations

import re
from typing import Any, Mapping

from .site_rules_builtin import SITE_LEVEL_RULES


_DURATION_RE = re.compile(
    r"^P(?:(?P<years>\d+)Y)?(?:(?P<months>\d+)M)?(?:(?P<weeks>\d+)W)?"
    r"(?:(?P<days>\d+)D)?(?:T?(?P<hours>\d+)H)?$",
    re.IGNORECASE,
)
_SIZE_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([KMGTPE]?I?B)\s*$", re.IGNORECASE)
_SIZE_FACTORS = {
    "B": 1,
    "KB": 1000,
    "MB": 1000**2,
    "GB": 1000**3,
    "TB": 1000**4,
    "PB": 1000**5,
    "EB": 1000**6,
    "KIB": 1024,
    "MIB": 1024**2,
    "GIB": 1024**3,
    "TIB": 1024**4,
    "PIB": 1024**5,
    "EIB": 1024**6,
}
_CONDITION_FIELDS = {
    "uploaded": "min_upload",
    "downloaded": "min_download",
    "ratio": "min_ratio",
    "bonus": "min_bonus",
    "seedingBonus": "min_seeding_points",
    "seeding": "min_seeding",
    "seedingSize": "min_seeding_size",
    "uploads": "min_torrent_uploads",
    "averageSeedingTime": "min_average_seeding_time_days",
}
_UNSUPPORTED_LABELS = {
    "snatches": "下载完成数",
    "seedingTime": "做种时间",
    "posts": "发帖数",
    "hnrUnsatisfied": "未解决 H&R 数",
    "totalTraffic": "总流量",
    "trueDownloaded": "真实下载量",
    "perfectFlacs": "Perfect FLAC 数",
    "adoptions": "领养数",
}
_LEVEL_SUFFIXES = (
    "User",
    "Power User",
    "Elite User",
    "Crazy User",
    "Insane User",
    "Veteran User",
    "Extreme User",
    "Ultimate User",
    "Nexus Master",
    "mTorrent Master",
)

# MoviePilot 部分站点返回本地化等级名，而固定来源规则只记录英文等级名。
# 这里仅补充已经在插件旧版中验证过的兼容别名，不修改上游门槛。
_LEVEL_COMPATIBILITY_ALIASES = {
    "馒头": {
        "User": ("小卒",),
        "Power User": ("捕头",),
        "Elite User": ("知县",),
        "Crazy User": ("通判",),
        "Insane User": ("知州",),
        "Veteran User": ("府丞",),
        "Extreme User": ("府尹",),
        "Ultimate User": ("总督", "總督"),
        "mTorrent Master": ("大臣",),
    },
}

_SITE_COMPATIBILITY_ALIASES = {
    "馒头": ("M-Team", "MTeam", "m-team"),
    "观众": ("Audiences", "Audience"),
    "彩虹岛": ("Rainbow", "CHDBits"),
    "憨憨": ("HHan", "HHanClub"),
    "春天": ("Spring", "Spring-Sunday"),
    "天空": ("HDSky", "Skyey"),
    "猫站": ("Pter", "PterClub"),
    "家园": ("HDHome",),
    "朋友": ("Friend", "Friends"),
    "皇后": ("OpenCD", "open.cd"),
    "听听歌": ("TTG", "ToTheGlory"),
    "我堡": ("OurBits", "OB"),
    "ilolicon": ("萝莉",),
}


def _downgrade_description(threshold: float) -> str:
    """生成仅用于说明的降级阈值；升级计算仍只使用升级条件。"""

    return f"分享率低于 {threshold:g} 时自动降级。"


def _level_patch(
    *,
    alias: str,
    ratio_strict: bool = False,
    points_strict: bool = False,
    downgrade_ratio: float | None = None,
    **requirements: Any,
) -> dict[str, Any]:
    patch = {
        "aliases": (alias,),
        "min_ratio_strict": ratio_strict,
        "min_seeding_points_strict": points_strict,
        **requirements,
    }
    if downgrade_ratio is not None:
        patch["description_suffix"] = _downgrade_description(downgrade_ratio)
    return patch


# 用户依据各站当前等级页校正的规则。上游生成文件保持原样，便于后续重新生成和审计。
_SITE_RULE_PATCHES: dict[str, dict[str, Any]] = {
    "春天": {
        "retirement_source_id": 5,
        "levels": {
            2: {
                "min_download_strict": True,
                "min_ratio_strict": True,
                "description_suffix": _downgrade_description(1.1),
                "alternatives": [
                    {"min_seeding_points": 100_000, "min_torrent_uploads": 1, "min_torrent_uploads_strict": True},
                    {"min_seeding_points": 150_000},
                ],
            },
            3: {
                "min_download_strict": True,
                "min_ratio_strict": True,
                "description_suffix": _downgrade_description(1.1),
                "alternatives": [
                    {"min_seeding_points": 500_000, "min_torrent_uploads": 100, "min_torrent_uploads_strict": True},
                    {"min_seeding_points": 1_000_000},
                ],
            },
            4: {
                "min_download_strict": True,
                "min_ratio_strict": True,
                "description_suffix": _downgrade_description(2),
                "alternatives": [
                    {"min_seeding_points": 1_200_000, "min_torrent_uploads": 300, "min_torrent_uploads_strict": True},
                    {"min_seeding_points": 2_400_000},
                ],
            },
            5: {
                "description_suffix": "每月最后一天按保种或发种两条路线评选。",
                "alternatives": [
                    {
                        "unsupported_requirements": [
                            {"key": "monthly_seeding_upload", "label": "当月保种上传", "target": "不少于 300 GB"},
                            {"key": "monthly_seeding_bonus_rank", "label": "当月做种积分排名", "target": "前 65 名"},
                        ],
                    },
                    {
                        "unsupported_requirements": [
                            {
                                "key": "monthly_qualified_upload_rank",
                                "label": "当月合规非中性活种发布数排名",
                                "target": "前 15 名",
                            },
                        ],
                    },
                ],
            },
        },
    },
    "ilolicon": {
        "levels": {
            3: _level_patch(alias="Power User", ratio_strict=True, downgrade_ratio=.95),
            4: _level_patch(alias="Elite User", ratio_strict=True, downgrade_ratio=1.45),
            5: _level_patch(alias="Crazy User", ratio_strict=True, downgrade_ratio=1.95),
            6: _level_patch(alias="Insane User", ratio_strict=True, downgrade_ratio=2.45),
            7: _level_patch(alias="Veteran User", ratio_strict=True, downgrade_ratio=2.95),
            8: _level_patch(alias="Extreme User", ratio_strict=True, downgrade_ratio=3.45),
            9: _level_patch(alias="Ultimate User", ratio_strict=True, downgrade_ratio=3.95),
            10: _level_patch(alias="Nexus Master", ratio_strict=True, downgrade_ratio=4.45),
        },
    },
    "天空": {
        "retirement_source_id": 6,
        "levels": {
            2: _level_patch(alias="Power User", ratio_strict=True, downgrade_ratio=1.9),
            3: _level_patch(alias="Elite User", ratio_strict=True, downgrade_ratio=2.4),
            4: _level_patch(alias="Crazy User", ratio_strict=True, downgrade_ratio=2.9),
            5: _level_patch(alias="Insane User", ratio_strict=True, downgrade_ratio=3.4),
            6: _level_patch(alias="Veteran User", ratio_strict=True, downgrade_ratio=3.9),
            7: _level_patch(alias="Extreme User", ratio_strict=True, downgrade_ratio=4.4),
            8: _level_patch(alias="Ultimate User", ratio_strict=True, downgrade_ratio=4.9),
            9: _level_patch(alias="Nexus Master", ratio_strict=True, downgrade_ratio=5.4),
        },
    },
    "音乐乌托邦": {
        "retirement_source_id": 7,
        "levels": {
            3: _level_patch(alias="Power User", ratio_strict=True, points_strict=True, downgrade_ratio=.95),
            4: _level_patch(alias="Elite User", ratio_strict=True, points_strict=True, downgrade_ratio=1.45),
            5: _level_patch(alias="Crazy User", ratio_strict=True, points_strict=True, downgrade_ratio=1.95),
            6: _level_patch(alias="Insane User", ratio_strict=True, points_strict=True, downgrade_ratio=2.45),
            7: _level_patch(alias="Veteran User", ratio_strict=True, points_strict=True, downgrade_ratio=2.95),
            8: _level_patch(alias="Extreme User", ratio_strict=True, points_strict=True, downgrade_ratio=3.45),
            9: _level_patch(alias="Ultimate User", ratio_strict=True, points_strict=True, downgrade_ratio=3.95),
            10: _level_patch(alias="Nexus Master", ratio_strict=True, points_strict=True, downgrade_ratio=4.45),
        },
    },
    "Depth Studio": {
        "levels": {
            3: _level_patch(alias="Power User", ratio_strict=True, points_strict=True, downgrade_ratio=1.2, min_ratio=1.2),
            4: _level_patch(alias="Elite User", ratio_strict=True, points_strict=True, downgrade_ratio=2.55, min_ratio=2.55),
            5: _level_patch(alias="Crazy User", ratio_strict=True, points_strict=True, downgrade_ratio=2.55, min_ratio=2.55),
            6: _level_patch(alias="Insane User", ratio_strict=True, points_strict=True, downgrade_ratio=3.2, min_ratio=3.2),
            7: _level_patch(alias="Veteran User", ratio_strict=True, points_strict=True, downgrade_ratio=4.05, min_ratio=4.05),
            8: _level_patch(alias="Extreme User", ratio_strict=True, points_strict=True, downgrade_ratio=5, min_ratio=5),
            9: _level_patch(alias="Ultimate User", ratio_strict=True, points_strict=True, downgrade_ratio=6, min_ratio=6),
            10: _level_patch(alias="Nexus Master", ratio_strict=True, points_strict=True, downgrade_ratio=7, min_ratio=7),
        },
    },
    "GGPT": {
        "levels": {
            1: _level_patch(alias="Power User", points_strict=True, downgrade_ratio=1.9),
            2: _level_patch(alias="Elite User", points_strict=True, downgrade_ratio=2.4),
            3: _level_patch(alias="Crazy User", points_strict=True, downgrade_ratio=2.9),
            4: _level_patch(alias="Insane User", points_strict=True, downgrade_ratio=3.4),
            5: _level_patch(alias="Veteran User", points_strict=True, downgrade_ratio=3.9),
            6: _level_patch(alias="Extreme User", points_strict=True, downgrade_ratio=4.4),
            7: _level_patch(alias="Ultimate User", points_strict=True, downgrade_ratio=4.9),
            8: _level_patch(alias="Nexus Master", points_strict=True, downgrade_ratio=5.4),
        },
    },
}


_ZIMIAO_LEVELS = (
    ("Power User", 4, 50, 1, 40_000, 1, 1),
    ("Elite User", 8, 100, 2, 100_000, 5, .5),
    ("Crazy User", 15, 150, 3, 300_000, 10, 1.5),
    ("Insane User", 25, 200, 4, 500_000, 20, 2),
    ("Veteran User", 40, 250, 5, 1_000_000, 40, 2.5),
    ("Extreme User", 60, 300, 6, 1_500_000, 80, 3),
    ("Ultimate User", 80, 350, 7, 2_000_000, 150, 3.5),
    ("Nexus Master", 100, 400, 8, 5_000_000, 200, 4),
)


def _zimiao_rule() -> dict[str, Any]:
    """构造用户提供的梓喵等级表；以最高固定等级作为完整路线目标。"""

    levels: list[dict[str, Any]] = [{"name": "User", "aliases": (), "description": "新用户默认等级。"}]
    for name, weeks, download_gb, ratio, points, uploads, downgrade_ratio in _ZIMIAO_LEVELS:
        levels.append({
            "name": name,
            "aliases": (),
            "description": _downgrade_description(downgrade_ratio),
            "min_join_days": weeks * 7,
            "min_download": download_gb * 1000**3,
            "min_ratio": ratio,
            "min_ratio_strict": True,
            "min_seeding_points": points,
            "min_seeding_points_strict": True,
            "min_torrent_uploads": uploads,
        })
    return {
        "site": "梓喵",
        "aliases": ("Zimiao",),
        "domains": (),
        "retirement_level": "Nexus Master",
        "levels": levels,
        "vip_levels": [],
        "source": "user-provided",
    }


def _unique_aliases(values: list[str], *, primary: str = "") -> tuple[str, ...]:
    """按与运行时相同的展示归一化规则去重别名。"""

    seen = {re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", primary.casefold())}
    result: list[str] = []
    for value in values:
        identity = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", value.casefold())
        if not identity or identity in seen:
            continue
        seen.add(identity)
        result.append(value)
    return tuple(result)


def _duration_days(value: Any) -> float | None:
    if not isinstance(value, str):
        return None
    matched = _DURATION_RE.fullmatch(value.strip())
    if not matched:
        return None
    parts = {key: int(raw or 0) for key, raw in matched.groupdict().items()}
    return (
        parts["years"] * 365
        + parts["months"] * 30
        + parts["weeks"] * 7
        + parts["days"]
        + parts["hours"] / 24
    )


def _size_bytes(value: Any) -> int | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return max(int(value), 0)
    if not isinstance(value, str):
        return None
    matched = _SIZE_RE.fullmatch(value)
    if not matched:
        return None
    return max(int(float(matched.group(1)) * _SIZE_FACTORS[matched.group(2).upper()]), 0)


def _converted_value(source_key: str, value: Any) -> int | float | None:
    if source_key in {"uploaded", "downloaded", "seedingSize"}:
        return _size_bytes(value)
    if source_key == "averageSeedingTime":
        return _duration_days(value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    return None


def _adapt_condition(raw: Mapping[str, Any]) -> dict[str, Any]:
    condition: dict[str, Any] = {}
    unsupported: list[dict[str, Any]] = []
    for source_key, target_key in _CONDITION_FIELDS.items():
        if source_key not in raw:
            continue
        value = _converted_value(source_key, raw[source_key])
        if value is not None:
            condition[target_key] = value
    for source_key, label in _UNSUPPORTED_LABELS.items():
        if source_key in raw:
            unsupported.append({"key": source_key, "label": label, "target": raw[source_key]})
    if unsupported:
        condition["unsupported_requirements"] = unsupported
    return condition


def _adapt_level(raw: Mapping[str, Any], *, site_name: str = "") -> dict[str, Any]:
    name = str(raw.get("name") or "").strip()
    aliases = [str(item).strip() for item in raw.get("nameAka") or () if str(item).strip()]
    aliases.extend(_LEVEL_COMPATIBILITY_ALIASES.get(site_name, {}).get(name, ()))
    for suffix in sorted(_LEVEL_SUFFIXES, key=len, reverse=True):
        if name.casefold().endswith(suffix.casefold()):
            if name.casefold() != suffix.casefold():
                aliases.append(suffix)
            break
    level: dict[str, Any] = {
        "name": name,
        "aliases": tuple(dict.fromkeys(aliases)),
        "description": str(raw.get("privilege") or "").strip(),
        "source_id": raw.get("id"),
    }
    interval = _duration_days(raw.get("interval"))
    if interval is not None:
        level["min_join_days"] = int(interval)
    level.update(_adapt_condition(raw))
    alternatives = [
        adapted
        for item in raw.get("alternative") or ()
        if isinstance(item, Mapping) and (adapted := _adapt_condition(item))
    ]
    if alternatives:
        level["alternatives"] = alternatives
    return level


def _apply_level_patches(
    levels: list[dict[str, Any]],
    patches: Mapping[int, Mapping[str, Any]],
) -> None:
    """按上游稳定的等级 ID 应用站点校正，不改写生成源文件。"""

    for level in levels:
        patch = patches.get(level.get("source_id"))
        if not patch:
            continue
        aliases = [*level.get("aliases", ()), *patch.get("aliases", ())]
        suffix = str(patch.get("description_suffix") or "").strip()
        level.update({
            key: value
            for key, value in patch.items()
            if key not in {"aliases", "description_suffix"}
        })
        level["aliases"] = _unique_aliases(aliases, primary=level["name"])
        if suffix and suffix not in level["description"]:
            level["description"] = " ".join(item for item in (level["description"], suffix) if item)


def bundled_retirement_rules() -> dict[str, Mapping[str, Any]]:
    """Return live-site keep-account rules plus VIP-only rules for wealthy retirement."""

    result: dict[str, Mapping[str, Any]] = {}
    for raw_rule in SITE_LEVEL_RULES:
        if raw_rule.get("is_dead"):
            continue
        site_name = str(raw_rule.get("name") or "").strip()
        normal_levels = [
            level
            for level in raw_rule.get("levels") or ()
            if isinstance(level, Mapping) and level.get("groupType") not in {"vip", "manager"}
        ]
        kept = next((level for level in normal_levels if level.get("isKept") is True), None)
        levels = [_adapt_level(level, site_name=site_name) for level in normal_levels]
        levels = [level for level in levels if level["name"]]
        rule_patch = _SITE_RULE_PATCHES.get(site_name, {})
        _apply_level_patches(levels, rule_patch.get("levels", {}))
        vip_levels = [
            _adapt_level(level, site_name=site_name)
            for level in raw_rule.get("levels") or ()
            if isinstance(level, Mapping) and level.get("groupType") == "vip"
        ]
        vip_levels = [level for level in vip_levels if level["name"]]
        retirement_name = str(kept.get("name") or "").strip() if kept else ""
        retirement_source_id = rule_patch.get("retirement_source_id")
        if retirement_source_id is not None:
            retirement_name = next(
                (
                    level["name"]
                    for level in levels
                    if level.get("source_id") == retirement_source_id
                ),
                retirement_name,
            )
        if not vip_levels and (not levels or not retirement_name):
            continue
        aliases = [str(raw_rule.get("source_key") or "").strip()]
        aliases.extend(str(item).strip() for item in raw_rule.get("aliases") or ())
        aliases.extend(_SITE_COMPATIBILITY_ALIASES.get(site_name, ()))
        domains = [str(item).strip() for item in raw_rule.get("domains") or ()]
        for field in ("domain", "url"):
            if raw_rule.get(field):
                domains.append(str(raw_rule[field]).strip())
        result[site_name] = {
            "site": site_name,
            "aliases": _unique_aliases([item for item in aliases if item], primary=site_name),
            "domains": tuple(dict.fromkeys(item for item in domains if item)),
            "retirement_level": retirement_name,
            "levels": levels,
            "vip_levels": vip_levels,
            "source": "PTDepilerMp",
        }
    result["梓喵"] = _zimiao_rule()
    return result
