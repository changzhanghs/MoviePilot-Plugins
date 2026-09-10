"""PT 数据统计的纯计算逻辑。

本模块不依赖 MoviePilot 运行时，便于对日期口径、十二大匹配与汇总结果做单元测试。
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from datetime import date, datetime, timedelta
from typing import Any

EXPORT_FIELDS: tuple[tuple[str, str], ...] = (
    ("site_name", "站点"),
    ("updated_day", "数据日期"),
    ("username", "用户名"),
    ("userid", "UID"),
    ("join_at", "加入时间"),
    ("user_level", "用户等级"),
    ("upload", "累计上传(B)"),
    ("download", "累计下载(B)"),
    ("daily_upload", "当日上传(B)"),
    ("daily_download", "当日下载(B)"),
    ("ratio", "分享率"),
    ("bonus", "魔力"),
    ("seeding", "做种数量"),
    ("seeding_size", "做种体积(B)"),
)

EXPORT_FIELD_LABELS = dict(EXPORT_FIELDS)
EXPORT_FIELD_KEYS = tuple(key for key, _ in EXPORT_FIELDS)


TWELVE_SITES: tuple[dict[str, Any], ...] = (
    {
        "key": "mteam",
        "name": "馒头",
        "aliases": ("馒头", "mteam", "m-team"),
    },
    {
        "key": "audiences",
        "name": "观众",
        "aliases": ("观众", "audiences", "audience"),
    },
    {
        "key": "rainbow",
        "name": "彩虹岛",
        "aliases": ("彩虹岛", "rainbow", "chdbits"),
    },
    {
        "key": "hhan",
        "name": "憨憨",
        "aliases": ("憨憨", "hhan", "hhanclub"),
    },
    {
        "key": "spring",
        "name": "春天",
        "aliases": ("春天", "spring", "spring-sunday"),
    },
    {
        "key": "sky",
        "name": "天空",
        "aliases": ("天空", "hdsky", "skyey"),
    },
    {
        "key": "pter",
        "name": "猫站",
        "aliases": ("猫站", "pter", "pterclub"),
    },
    {
        "key": "home",
        "name": "家园",
        "aliases": ("家园", "hdhome"),
    },
    {
        "key": "friends",
        "name": "朋友",
        "aliases": ("朋友", "friend", "friends"),
    },
    {
        "key": "u2",
        "name": "U2",
        "aliases": ("u2", "dmhy"),
    },
    {
        "key": "ttg",
        "name": "TTG",
        "aliases": ("ttg", "totheglory"),
    },
    {
        "key": "ourbits",
        "name": "我堡",
        "aliases": ("我堡", "ourbits", "ob"),
    },
)


GIB = 1024 ** 3

AUDIENCES_RETIREMENT_RULE: dict[str, Any] = {
    "retirement_level": "Extreme User",
    "levels": [
        {
            "name": "User",
            "description": "新用户的默认级别；可以请求续种。",
        },
        {
            "name": "Power User",
            "min_join_days": 35,
            "min_download": 120 * GIB,
            "min_ratio": 2,
            "min_ratio_strict": True,
            "min_seeding_points": 100_000,
            "description": "可以查看 NFO 文档、用户列表及其他用户的种子历史；可以编辑自己上传的种子，发布 10 分钟后可自行删除。",
        },
        {
            "name": "Elite User",
            "min_join_days": 105,
            "min_download": 240 * GIB,
            "min_ratio": 2.5,
            "min_ratio_strict": True,
            "min_seeding_points": 200_000,
            "description": "继承 Power User 权限；可以发送邀请。",
        },
        {
            "name": "Crazy User",
            "min_join_days": 168,
            "min_download": 400 * GIB,
            "min_ratio": 3,
            "min_ratio_strict": True,
            "min_seeding_points": 400_000,
            "description": "继承 Elite User 权限；可以查看排行榜。",
        },
        {
            "name": "Insane User",
            "min_join_days": 280,
            "min_download": 600 * GIB,
            "min_ratio": 3.4,
            "min_ratio_strict": True,
            "min_seeding_points": 640_000,
            "description": "继承 Crazy User 权限；可以查看其他用户的评论和帖子历史。",
        },
        {
            "name": "Veteran User",
            "min_join_days": 420,
            "min_download": 1024 * GIB,
            "min_ratio": 4,
            "min_ratio_strict": True,
            "min_seeding_points": 880_000,
            "description": "继承 Insane User 权限；可以更新过期的外部信息。",
        },
        {
            "name": "Extreme User",
            "min_join_days": 560,
            "min_download": 2048 * GIB,
            "min_ratio": 4.4,
            "min_ratio_strict": True,
            "min_seeding_points": 1_200_000,
            "description": "继承 Veteran User 权限；Extreme User 及以上永久保留账号。",
        },
        {
            "name": "Ultimate User",
            "min_join_days": 700,
            "min_download": 4096 * GIB,
            "min_ratio": 5,
            "min_ratio_strict": True,
            "min_seeding_points": 1_500_000,
            "description": "继承 Extreme User 权限。",
        },
        {
            "name": "Nexus Master",
            "min_join_days": 784,
            "min_download": 8192 * GIB,
            "min_ratio": 6,
            "min_ratio_strict": True,
            "min_seeding_points": 1_800_000,
            "description": "继承 Ultimate User 权限。",
        },
        {
            "name": "Rainbow",
            "min_join_days": 896,
            "min_download": 10240 * GIB,
            "min_ratio": 8,
            "min_ratio_strict": True,
            "min_seeding_points": 2_400_000,
            "description": "保持等级期间显示彩虹 ID；做种积分要求逐年增加，具体数值以站点通知为准。",
        },
    ],
}

MTEAM_RETIREMENT_RULE: dict[str, Any] = {
    "retirement_level": "Extreme User",
    "levels": [
        {
            "name": "User",
            "aliases": ("小卒",),
            "description": "可以发候选、发布趣味盒、兑换魔力。",
        },
        {
            "name": "Power User",
            "aliases": ("捕头",),
            "min_join_days": 28,
            "min_join_days_strict": True,
            "min_download": 200 * GIB,
            "min_download_strict": True,
            "min_ratio": 2,
            "min_ratio_strict": True,
            "description": "继承小卒 / User 权限。",
        },
        {
            "name": "Elite User",
            "aliases": ("知县",),
            "min_join_days": 56,
            "min_join_days_strict": True,
            "min_download": 400 * GIB,
            "min_download_strict": True,
            "min_ratio": 3,
            "min_ratio_strict": True,
            "description": "可以发送邀请。",
        },
        {
            "name": "Crazy User",
            "aliases": ("通判",),
            "min_join_days": 84,
            "min_join_days_strict": True,
            "min_download": 500 * GIB,
            "min_download_strict": True,
            "min_ratio": 4,
            "min_ratio_strict": True,
            "description": "继承知县 / Elite User 权限。",
        },
        {
            "name": "Insane User",
            "aliases": ("知州",),
            "min_join_days": 112,
            "min_join_days_strict": True,
            "min_download": 800 * GIB,
            "min_download_strict": True,
            "min_ratio": 5,
            "min_ratio_strict": True,
            "description": "继承知县 / Elite User 权限。",
        },
        {
            "name": "Veteran User",
            "aliases": ("府丞",),
            "min_join_days": 140,
            "min_join_days_strict": True,
            "min_download": 1000 * GIB,
            "min_download_strict": True,
            "min_ratio": 6,
            "min_ratio_strict": True,
            "description": "封存账号时永久保号。",
        },
        {
            "name": "Extreme User",
            "aliases": ("府尹",),
            "min_join_days": 168,
            "min_join_days_strict": True,
            "min_download": 2000 * GIB,
            "min_download_strict": True,
            "min_ratio": 7,
            "min_ratio_strict": True,
            "description": "永久保号。",
        },
        {
            "name": "Ultimate User",
            "aliases": ("总督", "總督"),
            "min_join_days": 196,
            "min_join_days_strict": True,
            "min_download": 2500 * GIB,
            "min_download_strict": True,
            "min_ratio": 8,
            "min_ratio_strict": True,
            "description": "继承府尹 / Extreme User 权限。",
        },
        {
            "name": "mTorrent Master",
            "aliases": ("大臣",),
            "min_join_days": 224,
            "min_join_days_strict": True,
            "min_download": 3000 * GIB,
            "min_download_strict": True,
            "min_ratio": 9,
            "min_ratio_strict": True,
            "description": "继承府尹 / Extreme User 权限。",
        },
    ],
}

DEFAULT_RETIREMENT_RULES: dict[str, Mapping[str, Any]] = {
    **{
        alias: AUDIENCES_RETIREMENT_RULE
        for alias in ("观众", "Audiences", "Audience")
    },
    **{
        alias: MTEAM_RETIREMENT_RULE
        for alias in ("馒头", "MTeam", "M-Team")
    },
}


def as_int(value: Any) -> int:
    """把宿主可能返回的整数、浮点或字符串统一成非异常整数。"""

    if value in (None, ""):
        return 0
    try:
        return int(float(value))
    except (TypeError, ValueError, OverflowError):
        return 0


def as_float(value: Any) -> float | None:
    """把可选数值转换为浮点数，无法转换时返回 ``None``。"""

    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return None


def as_text(value: Any) -> str:
    """把可选值转换为可存储文本。"""

    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def previous_day(day: str) -> str | None:
    """返回严格的前一服务器日期；非法日期不产生跨日猜测。"""

    try:
        parsed = date.fromisoformat(day)
    except (TypeError, ValueError):
        return None
    return (parsed - timedelta(days=1)).isoformat()


def compute_daily_delta(
    current: Mapping[str, Any],
    previous: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """按严格相邻日期计算站点日增量。

    缺少前一日、前一日失败或日期不连续时均视为基线不足。累计值下降通常表示
    站点重置了统计口径，负差值按零展示但保留 ``counter_reset`` 标记。
    """

    current_day = as_text(current.get("updated_day"))
    expected_previous = previous_day(current_day)
    if not previous or not expected_previous:
        return {
            "baseline_valid": False,
            "daily_upload": 0,
            "daily_download": 0,
            "counter_reset": False,
        }
    if as_text(previous.get("updated_day")) != expected_previous:
        return {
            "baseline_valid": False,
            "daily_upload": 0,
            "daily_download": 0,
            "counter_reset": False,
        }
    if as_text(previous.get("err_msg")).strip():
        return {
            "baseline_valid": False,
            "daily_upload": 0,
            "daily_download": 0,
            "counter_reset": False,
        }

    upload_delta = as_int(current.get("upload")) - as_int(previous.get("upload"))
    download_delta = as_int(current.get("download")) - as_int(previous.get("download"))
    return {
        "baseline_valid": True,
        "daily_upload": max(0, upload_delta),
        "daily_download": max(0, download_delta),
        "counter_reset": upload_delta < 0 or download_delta < 0,
    }


def build_hourly_traffic(
    snapshots: Iterable[Mapping[str, Any]],
    selected_day: str,
) -> dict[str, Any]:
    """把 MP 的站点累计采样转换为自然小时增量。

    MP 可能在同一天保存多次站点用户数据。这里按站点和采样时间排序，只使用
    同一自然日内相邻成功采样的累计值差额，并把增量记入后一条采样所在小时。
    当天首条记录不会与前一天的记录相减，避免把整日增量误记为某个小时的
    流量；累计值回退时相应差额按零处理。
    """

    points = [
        {"hour": f"{hour:02d}:00", "upload": 0, "download": 0, "samples": 0}
        for hour in range(24)
    ]
    grouped: dict[str, list[tuple[datetime, Mapping[str, Any]]]] = {}

    for snapshot in snapshots:
        if as_text(snapshot.get("err_msg")).strip():
            continue
        day = as_text(snapshot.get("updated_day"))[:10]
        time_text = as_text(snapshot.get("updated_time")).strip()
        source_text = as_text(snapshot.get("source_updated_at")).strip()
        parsed = None
        for candidate in (source_text, f"{day} {time_text}".strip(), day):
            if not candidate:
                continue
            try:
                parsed = datetime.fromisoformat(candidate)
                break
            except ValueError:
                continue
        if parsed is None or parsed.date().isoformat() > selected_day:
            continue
        key = as_text(snapshot.get("domain")) or as_text(snapshot.get("site_id"))
        if not key:
            continue
        grouped.setdefault(key, []).append((parsed, snapshot))

    valid_samples = 0
    for values in grouped.values():
        values.sort(key=lambda item: item[0])
        previous: tuple[datetime, Mapping[str, Any]] | None = None
        for timestamp, snapshot in values:
            timestamp_day = timestamp.date().isoformat()
            if timestamp_day != selected_day:
                continue
            if previous is not None:
                upload_delta = as_int(snapshot.get("upload")) - as_int(previous[1].get("upload"))
                download_delta = as_int(snapshot.get("download")) - as_int(previous[1].get("download"))
                bucket = points[timestamp.hour]
                bucket["upload"] += max(0, upload_delta)
                bucket["download"] += max(0, download_delta)
                bucket["samples"] += 1
                valid_samples += 1
            previous = (timestamp, snapshot)

    return {
        "baseline_valid": valid_samples > 0,
        "sample_count": valid_samples,
        "points": points,
    }


def estimate_bonus_hourly(
    current: Mapping[str, Any],
    previous: Mapping[str, Any] | None,
) -> float | None:
    """根据最近两次成功的 MP 每日快照估算每小时魔力增长。

    该值只用于展示趋势。样本不足、时间无效或累计魔力下降（通常表示兑换、
    消费或站点调整）时不猜测结果。
    """

    if not previous:
        return None
    current_bonus = as_float(current.get("bonus"))
    previous_bonus = as_float(previous.get("bonus"))
    if current_bonus is None or previous_bonus is None or current_bonus < previous_bonus:
        return None

    def snapshot_time(snapshot: Mapping[str, Any]) -> datetime | None:
        source_value = as_text(snapshot.get("source_updated_at")).strip()
        candidates = [source_value]
        day = as_text(snapshot.get("updated_day")).strip()
        updated_time = as_text(snapshot.get("updated_time")).strip()
        if day:
            candidates.append(f"{day} {updated_time}".strip())
            candidates.append(day)
        for candidate in candidates:
            if not candidate:
                continue
            try:
                return datetime.fromisoformat(candidate)
            except ValueError:
                continue
        return None

    current_time = snapshot_time(current)
    previous_time = snapshot_time(previous)
    if current_time is None or previous_time is None:
        return None
    elapsed_hours = (current_time - previous_time).total_seconds() / 3600
    if elapsed_hours <= 0:
        return None
    return round((current_bonus - previous_bonus) / elapsed_hours, 2)


def normalize_identity(value: Any) -> str:
    """移除展示差异，生成站点名称的匹配字符串。"""

    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", as_text(value).casefold())


def _match_named_rule(
    value: Any,
    rules: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    """匹配 MP 展示名称，兼容名称附带英文名或其它说明。"""

    identity = normalize_identity(value)
    if not identity:
        return None
    exact = rules.get(identity)
    if exact:
        return exact
    candidates = [
        (len(alias), rule)
        for alias, rule in rules.items()
        if alias and (alias in identity or identity in alias)
    ]
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


def _match_level_index(current_level: Any, levels: Iterable[Mapping[str, Any]]) -> int:
    """匹配 MP 等级文本，优先最长等级名以避免 User 误配 Power User。"""

    identity = normalize_identity(current_level)
    if not identity:
        return -1
    candidates: list[tuple[int, int]] = []
    for index, level in enumerate(levels):
        level_identities = [
            normalize_identity(value)
            for value in (level.get("name"), *(level.get("aliases") or ()))
            if normalize_identity(value)
        ]
        for level_identity in level_identities:
            if level_identity == identity:
                return index
            if level_identity in identity or identity in level_identity:
                candidates.append((len(level_identity), index))
    return max(candidates, default=(0, -1))[1]


def match_twelve_site(
    definition: Mapping[str, Any],
    configured_site: Mapping[str, Any],
) -> bool:
    """只按 MoviePilot 站点名称和别名判断十二大站点。"""

    name = normalize_identity(configured_site.get("name") or configured_site.get("site_name"))
    for candidate in definition.get("aliases") or ():
        normalized = normalize_identity(candidate)
        if normalized and (normalized in name or name == normalized):
            return True
    return False


def build_twelve_progress(
    configured_sites: Iterable[Mapping[str, Any]],
    latest_by_site_id: Mapping[int, Mapping[str, Any]],
) -> dict[str, Any]:
    """构建十二节点时间线；用户可见结果不包含站点域名。"""

    sites = list(configured_sites)
    items: list[dict[str, Any]] = []
    joined_count = 0

    for definition in TWELVE_SITES:
        matched = next(
            (
                site
                for site in sites
                if match_twelve_site(definition, site)
            ),
            None,
        )
        site_id = matched.get("id") if matched else None
        snapshot = latest_by_site_id.get(site_id) if isinstance(site_id, int) else None
        has_data = bool(snapshot and not as_text(snapshot.get("err_msg")).strip())
        if has_data:
            state = "joined"
            joined_count += 1
        elif matched:
            state = "waiting"
        else:
            state = "missing"
        items.append(
            {
                "key": definition["key"],
                "name": definition["name"],
                "state": state,
                "site_id": site_id,
                "join_at": as_text(snapshot.get("join_at")) if snapshot else "",
            }
        )

    def joined_at_sort_value(value: Any) -> float:
        """使用 MP 保存的完整加入时间排序，同日加入时也保持真实先后。"""

        raw = as_text(value).strip()
        if not raw:
            return float("inf")
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError, OSError):
            return float("inf")

    items.sort(
        key=lambda item: (
            item["state"] != "joined",
            joined_at_sort_value(item.get("join_at")),
            as_text(item.get("name")),
        )
    )

    return {
        "joined": joined_count,
        "total": len(TWELVE_SITES),
        "percent": round(joined_count * 100 / len(TWELVE_SITES)),
        "items": items,
    }


def _requirement_missing(level: Mapping[str, Any], snapshot: Mapping[str, Any]) -> list[str]:
    """返回当前数据距离指定等级门槛仍缺少的条件。"""

    missing: list[str] = []
    joined = as_text(snapshot.get("join_at"))[:10]
    current_day = as_text(snapshot.get("updated_day"))[:10]
    minimum_days = max(as_int(level.get("min_join_days")), 0)
    if minimum_days:
        try:
            actual_days = max(
                (date.fromisoformat(current_day) - date.fromisoformat(joined)).days,
                0,
            )
        except (TypeError, ValueError):
            actual_days = 0
        strict_days = bool(level.get("min_join_days_strict"))
        if actual_days <= minimum_days if strict_days else actual_days < minimum_days:
            required_days = minimum_days + (1 if strict_days else 0)
            missing.append(f"账号时间还差 {required_days - actual_days} 天")
    numeric_fields = (
        ("min_upload", "upload", "上传"),
        ("min_download", "download", "下载"),
        ("min_bonus", "bonus", "魔力"),
        ("min_seeding_points", "seeding_points", "做种积分"),
        ("min_seeding", "seeding", "做种数"),
    )
    for rule_key, data_key, label in numeric_fields:
        target = as_float(level.get(rule_key)) or 0
        current_value = as_float(snapshot.get(data_key))
        if target and data_key == "seeding_points" and current_value is None:
            missing.append(f"{label}数据未提供")
            continue
        current = current_value or 0
        strict = bool(level.get(f"{rule_key}_strict"))
        if current <= target if strict else current < target:
            difference = target - current
            if data_key in {"upload", "download"}:
                if strict and difference <= 0:
                    missing.append(f"{label}需大于 {format_bytes(target)}")
                else:
                    missing.append(f"{label}还差 {format_bytes(difference)}")
            else:
                formatted_difference = (
                    f"{int(difference):,}"
                    if difference.is_integer()
                    else f"{difference:,.2f}".rstrip("0").rstrip(".")
                )
                missing.append(f"{label}还差 {formatted_difference}")
    target_ratio = as_float(level.get("min_ratio"))
    current_ratio = as_float(snapshot.get("ratio"))
    ratio_strict = bool(level.get("min_ratio_strict"))
    ratio_missing = False
    if target_ratio is not None:
        ratio_missing = current_ratio is None or (
            current_ratio <= target_ratio
            if ratio_strict
            else current_ratio < target_ratio
        )
    if target_ratio is not None and ratio_missing:
        comparator = "大于" if ratio_strict else "达到"
        missing.append(f"分享率需{comparator} {target_ratio:g}")
    return missing


def _with_derived_upload(level: Mapping[str, Any]) -> dict[str, Any]:
    """根据下载量与分享率补全等级隐含的最低上传量。"""

    normalized = dict(level)
    explicit_upload = max(as_int(level.get("min_upload")), 0)
    minimum_download = max(as_int(level.get("min_download")), 0)
    minimum_ratio = as_float(level.get("min_ratio"))
    if explicit_upload or not minimum_download or minimum_ratio is None or minimum_ratio <= 0:
        return normalized
    normalized["min_upload"] = int(round(minimum_download * minimum_ratio))
    normalized["min_upload_strict"] = bool(
        level.get("min_download_strict") or level.get("min_ratio_strict")
    )
    return normalized


def _eligible_date(join_at: Any, minimum_days: Any, strict: bool = False) -> str:
    """按加入日期和等级账号天数计算最早达标日期。"""

    try:
        joined = date.fromisoformat(as_text(join_at)[:10])
        days = max(as_int(minimum_days), 0)
    except (TypeError, ValueError):
        return ""
    return (joined + timedelta(days=days + (1 if strict and days else 0))).isoformat()


def build_retirement_progress(
    snapshots: Iterable[Mapping[str, Any]],
    rules_by_name: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """构建全部站点升级与养老进度。

    MoviePilot 只提供当前等级和账户数值。找不到明确规则时必须返回
    ``rule_missing``，不能根据其它站点或等级名称猜测门槛。
    """

    source_rules = (
        DEFAULT_RETIREMENT_RULES if rules_by_name is None else rules_by_name
    )
    rules = {normalize_identity(key): value for key, value in source_rules.items()}
    sites: list[dict[str, Any]] = []
    counts = {"retired": 0, "upgrading": 0, "rule_missing": 0}
    for snapshot in snapshots:
        base = {
            "site_id": snapshot.get("site_id"),
            "site_name": as_text(snapshot.get("site_name")),
            "current_level": as_text(snapshot.get("user_level")),
            "next_level": "",
            "retirement_level": "",
            "status": "rule_missing",
            "join_at": as_text(snapshot.get("join_at")),
            "upload": as_int(snapshot.get("upload")),
            "download": as_int(snapshot.get("download")),
            "ratio": as_float(snapshot.get("ratio")),
            "bonus": as_float(snapshot.get("bonus")),
            "seeding_points": as_float(snapshot.get("seeding_points")),
            "estimated_bonus_hourly": as_float(
                snapshot.get("estimated_bonus_hourly")
            ),
            "seeding": as_int(snapshot.get("seeding")),
            "updated_day": as_text(snapshot.get("updated_day")),
            "levels_remaining": None,
            "route": [],
        }
        rule = _match_named_rule(snapshot.get("site_name"), rules)
        raw_levels = list(rule.get("levels") or []) if rule else []
        retirement_name = as_text(rule.get("retirement_level")) if rule else ""
        if not raw_levels or not retirement_name:
            sites.append(base)
            counts["rule_missing"] += 1
            continue

        retirement_identity = normalize_identity(retirement_name)
        current_index = _match_level_index(base["current_level"], raw_levels)
        retirement_index = next(
            (index for index, level in enumerate(raw_levels) if normalize_identity(level.get("name")) == retirement_identity),
            -1,
        )
        if retirement_index < 0:
            sites.append({**base, "retirement_level": retirement_name})
            counts["rule_missing"] += 1
            continue

        route: list[dict[str, Any]] = []
        for index, raw_level in enumerate(raw_levels):
            level = _with_derived_upload(raw_level)
            level_name = as_text(level.get("name"))
            route.append(
                {
                    "name": level_name,
                    "description": as_text(level.get("description")),
                    "min_join_days": max(as_int(level.get("min_join_days")), 0),
                    "min_join_days_strict": bool(level.get("min_join_days_strict")),
                    "min_upload": max(as_int(level.get("min_upload")), 0),
                    "min_upload_strict": bool(level.get("min_upload_strict")),
                    "min_download": max(as_int(level.get("min_download")), 0),
                    "min_download_strict": bool(level.get("min_download_strict")),
                    "min_ratio": as_float(level.get("min_ratio")),
                    "min_ratio_strict": bool(level.get("min_ratio_strict")),
                    "min_bonus": as_float(level.get("min_bonus")),
                    "min_seeding_points": as_float(level.get("min_seeding_points")),
                    "min_seeding": max(as_int(level.get("min_seeding")), 0),
                    "eligible_date": _eligible_date(
                        base["join_at"],
                        level.get("min_join_days"),
                        bool(level.get("min_join_days_strict")),
                    ),
                    "reached": index <= current_index,
                    "is_current": index == current_index,
                    "is_retirement": index == retirement_index,
                    "missing": [] if index <= current_index else _requirement_missing(level, snapshot),
                }
            )
        if current_index < 0:
            sites.append(
                {
                    **base,
                    "retirement_level": retirement_name,
                    "route": route,
                }
            )
            counts["rule_missing"] += 1
            continue

        retired = current_index >= retirement_index
        status = "retired" if retired else "upgrading"
        counts[status] += 1
        sites.append(
            {
                **base,
                "next_level": as_text(raw_levels[current_index + 1].get("name")) if current_index + 1 < len(raw_levels) else "",
                "retirement_level": retirement_name,
                "status": status,
                "levels_remaining": max(retirement_index - current_index, 0),
                "route": route,
            }
        )

    sites.sort(key=lambda item: (item["status"] == "rule_missing", item["status"] != "upgrading", item["site_name"]))
    return {"total": len(sites), **counts, "sites": sites}


def overall_ratio(upload: int, download: int) -> float | None:
    """计算汇总分享率，下载为零时返回空值。"""

    if download <= 0:
        return None
    return round(upload / download, 3)


def earliest_join_date(records: Iterable[Mapping[str, Any]]) -> str:
    """从站点加入时间中选取最早的有效日期。"""

    values: list[str] = []
    for record in records:
        raw = as_text(record.get("join_at"))[:10]
        try:
            values.append(date.fromisoformat(raw).isoformat())
        except (TypeError, ValueError):
            continue
    return min(values) if values else ""


def career_days(earliest: str, server_day: str) -> int | None:
    """计算从最早加入站点到服务器日期的自然日数量。"""

    if not earliest:
        return None
    try:
        start = date.fromisoformat(earliest[:10])
        end = date.fromisoformat(server_day[:10])
    except (TypeError, ValueError):
        return None
    return max((end - start).days + 1, 1)


def format_bytes(value: Any) -> str:
    """把字节数格式化为通知和导出图片共用的容量文本。"""

    number = float(max(as_int(value), 0))
    units = ("B", "KB", "MB", "GB", "TB", "PB", "EB")
    unit = units[0]
    for unit in units:
        if number < 1024 or unit == units[-1]:
            break
        number /= 1024
    if unit == "B":
        return f"{int(number)} {unit}"
    precision = 2 if number < 100 else 1
    return f"{number:.{precision}f} {unit}"


def selected_export_fields(raw_fields: str | None) -> list[str]:
    """校验并保持用户选择的导出字段顺序。"""

    if not raw_fields:
        return list(EXPORT_FIELD_KEYS)
    requested = [item.strip() for item in raw_fields.split(",") if item.strip()]
    allowed = set(EXPORT_FIELD_KEYS)
    selected = [item for item in requested if item in allowed]
    return selected or list(EXPORT_FIELD_KEYS)
