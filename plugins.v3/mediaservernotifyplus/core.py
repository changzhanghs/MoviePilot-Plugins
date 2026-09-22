"""MoviePilot V2/V3 共用的媒体服务器通知业务核心。

本模块只使用 Python 标准库，宿主差异由各代 ``__init__.py`` 中的适配方法处理。
"""

from __future__ import annotations

import re
import string
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple


ACTION_LABELS: Dict[str, str] = {
    "library_added": "已入库",
    "library_deleted": "已删除",
    "playback_started": "开始播放",
    "playback_stopped": "停止播放",
    "playback_paused": "暂停播放",
    "playback_resumed": "继续播放",
    "auth_success": "登录成功",
    "auth_failed": "登录失败",
    "rated": "已标记",
    "test": "测试",
}

ACTION_ICONS: Dict[str, str] = {
    "library_added": "📂",
    "library_deleted": "🗑️",
    "playback_started": "▶️",
    "playback_stopped": "⏹️",
    "playback_paused": "⏸️",
    "playback_resumed": "▶️",
    "auth_success": "🔐",
    "auth_failed": "⚠️",
    "rated": "⭐",
    "test": "🧪",
}

ACTION_DESCRIPTIONS: Dict[str, str] = {
    "library_added": "媒体文件加入媒体库时通知",
    "library_deleted": "媒体文件从媒体库移除时通知",
    "playback_started": "用户开始播放媒体时通知",
    "playback_stopped": "用户停止播放媒体时通知",
    "playback_paused": "用户暂停播放媒体时通知",
    "playback_resumed": "用户继续播放媒体时通知",
    "auth_success": "用户成功登录媒体服务器时通知",
    "auth_failed": "媒体服务器登录失败时通知",
    "rated": "用户标记已看、未看或评分时通知",
    "test": "用于检查当前通知样式",
}

FIELD_CATALOG: Dict[str, Dict[str, str]] = {
    "time": {"label": "时间", "icon": "🕐"},
    "server": {"label": "服务器", "icon": "🖥️"},
    "library": {"label": "媒体库", "icon": "🗂️"},
    "media_type": {"label": "媒体类型", "icon": "🎞️"},
    "category": {"label": "分类", "icon": "📁"},
    "season_episode": {"label": "季集", "icon": "📺"},
    "file_count": {"label": "文件数量", "icon": "📄"},
    "rating": {"label": "评分", "icon": "⭐"},
    "region": {"label": "地区", "icon": "🏳️"},
    "status": {"label": "状态", "icon": "📌"},
    "genres": {"label": "类型", "icon": "🎭"},
    "actors": {"label": "演员", "icon": "🎬"},
    "overview": {"label": "剧情简介", "icon": "📖", "style": "block"},
    "user": {"label": "用户", "icon": "👤"},
    "device": {"label": "设备", "icon": "📱"},
    "ip": {"label": "IP", "icon": "🌐"},
    "ip_location": {"label": "IP 归属地", "icon": "📍"},
    "progress": {"label": "播放进度", "icon": "⏱️"},
    "media_source": {"label": "媒体来源", "icon": "🔎"},
    "media_id": {"label": "媒体 ID", "icon": "🆔"},
    "album": {"label": "专辑", "icon": "💿"},
    "artist": {"label": "歌手", "icon": "🎤"},
    "play_link": {"label": "播放链接", "icon": "🔗", "style": "link"},
}

ACTION_FIELDS: Dict[str, Tuple[str, ...]] = {
    "library_added": (
        "season_episode", "library", "category", "file_count", "media_type",
        "rating", "region", "status", "genres", "actors", "overview", "server",
        "time", "media_source", "media_id", "album", "artist",
    ),
    "library_deleted": (
        "season_episode", "library", "media_type", "overview", "server", "time",
        "media_source", "media_id", "album", "artist",
    ),
    "playback_started": (
        "season_episode", "user", "device", "ip", "ip_location", "progress", "overview", "library",
        "media_type", "server", "time", "play_link",
    ),
    "playback_stopped": (
        "season_episode", "user", "device", "ip", "ip_location", "progress", "overview", "library",
        "media_type", "server", "time", "play_link",
    ),
    "playback_paused": (
        "season_episode", "user", "device", "ip", "ip_location", "progress", "overview", "library",
        "server", "time", "play_link",
    ),
    "playback_resumed": (
        "season_episode", "user", "device", "ip", "ip_location", "progress", "overview", "library",
        "server", "time", "play_link",
    ),
    "auth_success": ("user", "device", "ip", "ip_location", "server", "time"),
    "auth_failed": ("user", "device", "ip", "ip_location", "server", "time"),
    "rated": (
        "season_episode", "user", "library", "media_type", "rating", "overview", "server",
        "time", "media_source", "media_id",
    ),
    "test": ("server", "time"),
}

DEFAULT_ENABLED_FIELDS: Dict[str, Tuple[str, ...]] = {
    "library_added": ("season_episode", "category", "file_count", "rating", "server", "time", "overview"),
    "library_deleted": ("season_episode", "library", "server", "time"),
    "playback_started": ("season_episode", "user", "device", "ip", "progress", "server", "time"),
    "playback_stopped": ("season_episode", "user", "device", "ip", "progress", "server", "time"),
    "playback_paused": ("season_episode", "user", "device", "ip", "progress", "time"),
    "playback_resumed": ("season_episode", "user", "device", "ip", "progress", "time"),
    "auth_success": ("user", "device", "ip", "server", "time"),
    "auth_failed": ("user", "device", "ip", "server", "time"),
    "rated": ("season_episode", "user", "rating", "server", "time"),
    "test": ("server", "time"),
}

ACTION_ALIASES: Dict[str, str] = {
    "library.new": "library_added",
    "itemadded": "library_added",
    "library.deleted": "library_deleted",
    "itemdeleted": "library_deleted",
    "playback.start": "playback_started",
    "playbackstart": "playback_started",
    "media.play": "playback_started",
    "playback.stop": "playback_stopped",
    "playbackstop": "playback_stopped",
    "media.stop": "playback_stopped",
    "playback.pause": "playback_paused",
    "media.pause": "playback_paused",
    "playback.unpause": "playback_resumed",
    "media.resume": "playback_resumed",
    "user.authenticated": "auth_success",
    "authenticationsuccess": "auth_success",
    "user.authenticationfailed": "auth_failed",
    "authenticationfailure": "auth_failed",
    "item.rate": "rated",
    "item.markplayed": "rated",
    "item.markunplayed": "rated",
    "system.webhooktest": "test",
    "system.notificationtest": "test",
}

TEMPLATE_FIELDS: Tuple[str, ...] = (
    "action", "event", "channel", "server", "title", "item_name",
    "display_name", "title_link", "media_type", "year", "time", "category",
    "season_episode", "rating", "region", "status", "genres", "actors",
    "overview", "user", "device", "client", "ip", "progress", "tmdb_id",
    "tmdb_url", "media_source", "media_id", "file_count", "album", "artist",
)

DEFAULT_TEMPLATES: Dict[str, Dict[str, str]] = {
    "library_added": {
        "title": "{action}{media_type} {title_link}",
        "body": (
            "服务器：{server}\n"
            "季集：{season_episode}\n"
            "文件数：{file_count}\n"
            "时间：{time}\n"
            "{overview}"
        ),
    },
    "library_deleted": {
        "title": "{action}{media_type} {title_link}",
        "body": "服务器：{server}\n季集：{season_episode}\n时间：{time}",
    },
    "playback_started": {
        "title": "{action} {title_link}",
        "body": "用户：{user}\n设备：{device}\nIP：{ip}\n进度：{progress}\n服务器：{server}\n时间：{time}",
    },
    "playback_stopped": {
        "title": "{action} {title_link}",
        "body": "用户：{user}\n设备：{device}\n进度：{progress}\n服务器：{server}\n时间：{time}",
    },
    "playback_paused": {
        "title": "{action} {title_link}",
        "body": "用户：{user}\n设备：{device}\n进度：{progress}\n时间：{time}",
    },
    "playback_resumed": {
        "title": "{action} {title_link}",
        "body": "用户：{user}\n设备：{device}\n进度：{progress}\n时间：{time}",
    },
    "auth_success": {
        "title": "{user} {action}",
        "body": "设备：{device}\nIP：{ip}\n服务器：{server}\n时间：{time}",
    },
    "auth_failed": {
        "title": "{user} {action}",
        "body": "设备：{device}\nIP：{ip}\n服务器：{server}\n时间：{time}",
    },
    "rated": {
        "title": "{action} {title_link}",
        "body": "用户：{user}\n服务器：{server}\n时间：{time}",
    },
    "test": {
        "title": "媒体服务器通知测试",
        "body": "服务器：{server}\n状态：连接正常\n时间：{time}",
    },
}


def default_field_configs() -> Dict[str, List[Dict[str, Any]]]:
    """返回可直接序列化的默认字段顺序、名称和启用状态。"""
    result: Dict[str, List[Dict[str, Any]]] = {}
    for action, fields in ACTION_FIELDS.items():
        enabled = set(DEFAULT_ENABLED_FIELDS[action])
        result[action] = [
            {
                "key": field,
                "label": FIELD_CATALOG[field]["label"],
                "enabled": field in enabled,
            }
            for field in fields
        ]
    return result


def normalize_field_configs(value: Any) -> Dict[str, List[Dict[str, Any]]]:
    """清洗前端字段配置，拒绝未知字段并补齐新版本增加的字段。"""
    defaults = default_field_configs()
    if not isinstance(value, dict):
        return defaults
    normalized: Dict[str, List[Dict[str, Any]]] = {}
    for action, default_rows in defaults.items():
        allowed = {row["key"] for row in default_rows}
        source_rows = value.get(action)
        source_rows = source_rows if isinstance(source_rows, list) else []
        rows: List[Dict[str, Any]] = []
        seen = set()
        for row in source_rows:
            if not isinstance(row, dict):
                continue
            key = str(row.get("key") or "")
            if key not in allowed or key in seen:
                continue
            label = str(row.get("label") or FIELD_CATALOG[key]["label"]).strip()
            if key == "device" and label in {"设备 / 客户端", "设备/客户端"}:
                label = FIELD_CATALOG[key]["label"]
            rows.append({
                "key": key,
                "label": (label or FIELD_CATALOG[key]["label"])[:30],
                "enabled": bool(row.get("enabled")),
            })
            seen.add(key)
        for row in default_rows:
            if row["key"] not in seen:
                rows.append(dict(row))
        normalized[action] = rows
    return normalized


class FieldTemplateRenderer:
    """按照用户选择的字段顺序生成通知正文。"""

    def __init__(self, field_configs: Mapping[str, List[Mapping[str, Any]]]) -> None:
        self._field_configs = normalize_field_configs(dict(field_configs))

    def render(self, action: str, context: Mapping[str, Any]) -> Tuple[str, str]:
        if action not in ACTION_LABELS:
            raise TemplateError(f"未知通知类型：{action}")
        title = self._event_heading(action, context)
        lines: List[str] = []
        display_name = str(context.get("display_name") or "").strip()
        if display_name and action not in {"auth_success", "auth_failed", "test"}:
            lines.append(display_name)
        detail_lines: List[str] = []
        for row in self._field_configs[action]:
            if not row.get("enabled"):
                continue
            key = str(row["key"])
            value = str(context.get(key) or "").strip()
            if not value:
                continue
            meta = FIELD_CATALOG[key]
            label = str(row.get("label") or meta["label"]).strip()
            if meta.get("style") == "block":
                detail_lines.append(f"{meta['icon']} {label}\n{value}")
            elif meta.get("style") == "link":
                detail_lines.append(f"{meta['icon']} [{label}]({value})")
            else:
                detail_lines.append(f"{meta['icon']} {label}：{value}")
        if detail_lines:
            if lines:
                lines.append("")
            lines.extend(detail_lines)
        return title, "\n".join(lines).strip()

    @staticmethod
    def _event_heading(action: str, context: Mapping[str, Any]) -> str:
        label = ACTION_LABELS[action]
        if action == "library_added":
            count = str(context.get("file_count") or "1").strip()
            label = f"已入库 {count} 个文件"
        return f"{ACTION_ICONS[action]} {label}"


class TemplateError(ValueError):
    """通知模板不合法。"""


class SafeTemplateRenderer:
    """仅允许简单字段占位符的安全模板渲染器。"""

    _condition_re = re.compile(r"^\[\[([a-z_][a-z0-9_]*)\]\](.*)$", re.DOTALL)

    def __init__(self, templates: Mapping[str, Mapping[str, str]]) -> None:
        self._templates = {
            action: {"title": values["title"], "body": values["body"]}
            for action, values in templates.items()
        }
        for action, values in self._templates.items():
            self.validate(values["title"], max_length=500)
            self.validate(values["body"], max_length=8000)
            if action not in ACTION_LABELS:
                raise TemplateError(f"未知模板类型：{action}")

    @staticmethod
    def validate(template: str, max_length: int = 8000) -> None:
        """检查占位符，禁止属性访问、下标、转换和格式表达式。"""
        if not isinstance(template, str):
            raise TemplateError("模板必须是字符串")
        if len(template) > max_length:
            raise TemplateError(f"模板长度不能超过 {max_length}")
        formatter = string.Formatter()
        try:
            parsed = formatter.parse(template)
            for _literal, field_name, format_spec, conversion in parsed:
                if field_name is None:
                    continue
                if field_name not in TEMPLATE_FIELDS:
                    raise TemplateError(f"未知字段：{field_name}")
                if format_spec or conversion:
                    raise TemplateError("不支持格式表达式或转换操作")
        except ValueError as error:
            raise TemplateError(f"模板花括号不匹配：{error}") from error
        for line in template.splitlines():
            matched = SafeTemplateRenderer._condition_re.match(line)
            if matched and matched.group(1) not in TEMPLATE_FIELDS:
                raise TemplateError(f"未知条件字段：{matched.group(1)}")

    @staticmethod
    def _string_context(context: Mapping[str, Any]) -> Dict[str, str]:
        return {
            field: "" if context.get(field) is None else str(context.get(field)).strip()
            for field in TEMPLATE_FIELDS
        }

    @classmethod
    def _render_body(cls, template: str, context: Mapping[str, str]) -> str:
        rendered: List[str] = []
        formatter = string.Formatter()
        for source_line in template.splitlines():
            line = source_line
            condition = cls._condition_re.match(line)
            if condition:
                if not context.get(condition.group(1)):
                    continue
                line = condition.group(2)
            fields = [name for _, name, _, _ in formatter.parse(line) if name]
            if fields and any(not context.get(name, "") for name in fields):
                continue
            rendered.append(line.format_map(context).rstrip())
        return "\n".join(rendered).strip()

    def render(self, action: str, context: Mapping[str, Any]) -> Tuple[str, str]:
        """渲染指定事件类型的标题和正文。"""
        if action not in self._templates:
            raise TemplateError(f"未配置模板类型：{action}")
        values = self._string_context(context)
        title = self._templates[action]["title"].format_map(values).strip()
        title = re.sub(r"\s+", " ", title)
        body = self._render_body(self._templates[action]["body"], values)
        if not title:
            title = f"媒体服务器通知：{ACTION_LABELS[action]}"
        return title, body


@dataclass
class PendingMessage:
    """待聚合的单条媒体通知。"""

    event_info: Any
    context: Dict[str, Any]


class MediaServerNotifyCore:
    """V2/V3 共用的事件路由、去重、聚合和模板逻辑。"""

    DEFAULT_AGGREGATE_TIME = 15
    DEFAULT_DEDUPE_TIME = 30
    SHUTDOWN_TIMEOUT = 3.0

    def _initialize_core(self) -> None:
        self._condition = threading.Condition(threading.RLock())
        self._accepting_events = False
        self._active_operations = 0
        self._owned_timers: set[threading.Timer] = set()
        self._aggregate_timers: Dict[str, threading.Timer] = {}
        self._pending_messages: Dict[str, List[PendingMessage]] = {}
        self._dedupe_cache: Dict[str, float] = {}
        self._enabled = False
        self._types: List[str] = []
        self._mediaservers: List[str] = []
        self._libraries: List[str] = []
        self._library_records: List[Dict[str, Any]] = []
        self._field_configs = default_field_configs()
        self._renderer = FieldTemplateRenderer(self._field_configs)
        self._host_initialize()

    def init_plugin(self, config: Optional[dict] = None) -> None:
        """可重复调用地读取配置并重建运行状态。"""
        self._quiesce(flush=False)
        config = config or {}
        field_configs = normalize_field_configs(config.get("field_configs"))
        with self._condition:
            self._enabled = bool(config.get("enabled"))
            if "types" in config:
                self._types = [item for item in list(config.get("types") or []) if item in ACTION_LABELS]
            else:
                self._types = [
                    action for action in ACTION_LABELS
                    if bool(config.get(f"event_enabled_{action}", True))
                ]
            self._mediaservers = list(config.get("mediaservers") or [])
            # 新版界面按媒体服务器筛选；旧版具体媒体库配置不再参与过滤。
            self._libraries = []
            self._add_play_link = bool(config.get("add_play_link", True))
            self._lookup_ip = True
            self._fetch_metadata = True
            self._aggregate_enabled = bool(config.get("aggregate_enabled", True))
            self._aggregate_time = max(1, int(config.get("aggregate_time") or self.DEFAULT_AGGREGATE_TIME))
            self._dedupe_library = max(0, int(config.get("dedupe_library") or self.DEFAULT_DEDUPE_TIME))
            self._dedupe_playback = max(0, int(config.get("dedupe_playback") or self.DEFAULT_DEDUPE_TIME))
            self._flush_on_stop = bool(config.get("flush_on_stop", False))
            self._field_configs = field_configs
            self._renderer = FieldTemplateRenderer(field_configs)
            self._accepting_events = True
        self._refresh_library_records()
        if config.get("send_test"):
            self._send_template_test(str(config.get("preview_type") or "library_added"))
            saved_config = dict(config)
            saved_config["send_test"] = False
            self.update_config(saved_config)

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        return []

    def get_page(self) -> List[dict]:
        # 非空返回值兼容通过页面内容判断插件卡片是否可点击的 V2 前端。
        return [{"component": "div", "text": "媒体库通知"}]

    @staticmethod
    def get_render_mode() -> Tuple[str, str]:
        """使用 Vue 联邦组件实现卡片、弹窗和拖动排序。"""
        return "vue", "dist/assets"

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """Vue 配置组件读取默认值、字段元数据和媒体服务器列表。"""
        defaults: Dict[str, Any] = {
            "enabled": False,
            "mediaservers": [],
            "types": list(ACTION_LABELS),
            "field_configs": default_field_configs(),
            "_default_field_configs": default_field_configs(),
            "add_play_link": True,
            "lookup_ip": False,
            "fetch_metadata": True,
            "aggregate_enabled": True,
            "aggregate_time": self.DEFAULT_AGGREGATE_TIME,
            "dedupe_library": self.DEFAULT_DEDUPE_TIME,
            "dedupe_playback": self.DEFAULT_DEDUPE_TIME,
            "flush_on_stop": False,
            "preview_type": "library_added",
            "send_test": False,
            "_server_options": self._server_options(),
            "_action_meta": {
                action: {
                    "label": label,
                    "description": ACTION_DESCRIPTIONS[action],
                    "icon": ACTION_ICONS[action],
                }
                for action, label in ACTION_LABELS.items()
            },
            "_field_catalog": {key: dict(value) for key, value in FIELD_CATALOG.items()},
        }
        return [], defaults

    def _refresh_library_records(self) -> None:
        try:
            records = self._discover_libraries()
            if isinstance(records, list):
                self._library_records = records
        except Exception as error:
            self._log_debug(f"读取具体媒体库失败：{error}")

    def _match_library(self, info: Any, context: Dict[str, Any]) -> Optional[str]:
        """从事件中的库 ID 或文件路径匹配配置页列出的具体媒体库。"""
        raw = self._raw_object(info)
        item = self._raw_item(info)
        candidates = {
            str(value)
            for value in (
                item.get("CollectionFolderId"), item.get("LibrarySectionId"),
                item.get("librarySectionID"), item.get("topParentId"),
                raw.get("CollectionFolderId"), raw.get("LibrarySectionId"),
                raw.get("librarySectionID"), raw.get("topParentId"),
            )
            if value not in (None, "")
        }
        item_path = str(
            getattr(info, "item_path", "") or item.get("Path") or raw.get("Path") or ""
        ).replace("\\", "/").rstrip("/").lower()
        server_name = str(context.get("server") or "")
        for record in self._library_records:
            if server_name and str(record.get("server") or "") != server_name:
                continue
            if str(record.get("id") or "") in candidates:
                context["library"] = str(record.get("name") or "")
                return str(record.get("value") or "")
            paths = record.get("paths") or []
            if isinstance(paths, str):
                paths = [paths]
            for path in paths:
                normalized = str(path or "").replace("\\", "/").rstrip("/").lower()
                if item_path and normalized and (
                    item_path == normalized or item_path.startswith(normalized + "/")
                ):
                    context["library"] = str(record.get("name") or "")
                    return str(record.get("value") or "")
        return None

    def _library_allowed(self, info: Any, action: str, context: Dict[str, Any]) -> bool:
        if action in {"auth_success", "auth_failed", "test"}:
            return True
        matched = self._match_library(info, context)
        return not self._libraries or bool(matched and matched in self._libraries)

    def _field_enabled(self, action: str, field: str) -> bool:
        return any(
            row.get("key") == field and row.get("enabled")
            for row in self._field_configs.get(action, [])
        )

    def handle_webhook(self, event: Any) -> None:
        """标准化并处理 MoviePilot WebhookMessage 事件。"""
        if not self._begin_operation():
            return
        try:
            if not self._enabled:
                return
            info = getattr(event, "event_data", None)
            raw_event = str(getattr(info, "event", "") or "")
            action = ACTION_ALIASES.get(raw_event.lower())
            if not info or not action or action not in self._types:
                return
            if not self._service_allowed(info):
                return
            context = self._base_context(info, action)
            if not self._library_allowed(info, action, context):
                return
            if self._is_duplicate(info, action, context):
                return
            try:
                self._enrich_context(info, context)
            except Exception as error:
                self._log_debug(f"元数据增强失败，将使用 Webhook 原始字段：{error}")
            context["title_link"] = self._title_link(context)
            if self._should_aggregate(info, action):
                self._queue_aggregate(info, context)
                return
            self._send_context(action, context)
        except Exception as error:
            self._log_error(f"处理 Webhook 失败：{error}")
        finally:
            self._finish_operation()

    def _begin_operation(self) -> bool:
        with self._condition:
            if not self._accepting_events:
                return False
            self._active_operations += 1
            return True

    def _finish_operation(self) -> None:
        with self._condition:
            self._active_operations = max(0, self._active_operations - 1)
            self._condition.notify_all()

    @staticmethod
    def _raw_object(info: Any) -> dict:
        raw = getattr(info, "json_object", None)
        return raw if isinstance(raw, dict) else {}

    @classmethod
    def _raw_item(cls, info: Any) -> dict:
        raw = cls._raw_object(info)
        item = raw.get("Item") or raw.get("Metadata") or {}
        return item if isinstance(item, dict) else {}

    @classmethod
    def _base_context(cls, info: Any, action: str) -> Dict[str, Any]:
        raw = cls._raw_object(info)
        item = cls._raw_item(info)
        title = (
            item.get("SeriesName") or item.get("grandparentTitle") or raw.get("SeriesName")
            or item.get("Name") or item.get("title") or raw.get("Name")
            or getattr(info, "item_name", None) or "未知媒体"
        )
        year = item.get("ProductionYear") or raw.get("Year") or item.get("year") or ""
        season = item.get("ParentIndexNumber", item.get("parentIndex"))
        episode = item.get("IndexNumber", item.get("index"))
        season = season if season is not None else getattr(info, "season_id", None)
        episode = episode if episode is not None else getattr(info, "episode_id", None)
        season_episode = ""
        if season is not None and episode is not None:
            try:
                season_episode = f"S{int(season):02d}E{int(episode):02d}"
            except (TypeError, ValueError):
                season_episode = f"S{season}E{episode}"
            episode_name = item.get("Name") or item.get("title") or raw.get("Name")
            if episode_name and str(episode_name) not in str(title):
                season_episode += f" - {episode_name}"
        client = getattr(info, "client", None) or raw.get("ClientName") or ""
        device_name = getattr(info, "device_name", None) or raw.get("DeviceName") or ""
        percentage = getattr(info, "percentage", None)
        progress = ""
        if percentage is not None:
            try:
                progress = f"{float(percentage):.2f}".rstrip("0").rstrip(".") + "%"
            except (TypeError, ValueError):
                progress = str(percentage)
        item_type = str(getattr(info, "item_type", "") or "")
        media_type = {"TV": "剧集", "SHOW": "剧集", "MOV": "电影", "AUD": "音乐"}.get(item_type, item_type)
        raw_server = raw.get("Server")
        raw_server_name = raw_server.get("Name", "") if isinstance(raw_server, dict) else ""
        return {
            "_action": action,
            "action": ACTION_LABELS[action],
            "event": getattr(info, "event", ""),
            "channel": getattr(info, "channel", ""),
            "server": getattr(info, "server_name", "") or raw.get("ServerName") or raw_server_name,
            "title": title,
            "item_name": getattr(info, "item_name", "") or title,
            "display_name": f"{title} ({year})" if year and str(year) not in str(title) else title,
            "title_link": title,
            "media_type": media_type,
            "year": year,
            "time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            "library": "",
            "category": "",
            "season_episode": season_episode,
            "rating": "",
            "region": "",
            "status": "",
            "genres": "",
            "actors": "",
            "overview": getattr(info, "overview", "") or raw.get("Overview") or item.get("Overview") or "",
            "user": getattr(info, "user_name", "") or raw.get("NotificationUsername") or "",
            "device": " · ".join(
                value for value in (str(device_name).strip(), str(client).strip()) if value
            ),
            "client": client,
            "ip": getattr(info, "ip", "") or raw.get("RemoteEndPoint") or "",
            "ip_location": "",
            "progress": progress,
            "tmdb_id": "",
            "tmdb_url": "",
            "media_source": "",
            "media_id": "",
            "file_count": "",
            "album": item.get("Album") or item.get("parentTitle") or raw.get("Album") or "",
            "artist": (
                ", ".join(item.get("Artists") or [])
                if isinstance(item.get("Artists"), list)
                else item.get("Artist") or item.get("grandparentTitle") or ""
            ),
            "play_link": "",
            "_image": getattr(info, "image_url", None),
            "_link": None,
            "_item_id": getattr(info, "item_id", None),
        }

    @staticmethod
    def _title_link(context: Mapping[str, Any]) -> str:
        title = str(context.get("display_name") or context.get("title") or "未知媒体")
        url = str(context.get("tmdb_url") or "").strip()
        return f"[{title}]({url})" if url else title

    def _dedupe_key(self, info: Any, action: str, context: Mapping[str, Any]) -> str:
        raw = self._raw_object(info)
        raw_session = raw.get("Session")
        raw_session_id = raw_session.get("Id") if isinstance(raw_session, dict) else None
        session = getattr(info, "session_id", None) or raw_session_id
        parts = [
            context.get("server"), context.get("channel"), action,
            getattr(info, "item_id", None),
        ]
        if action.startswith("playback_"):
            parts.extend([session, context.get("user"), context.get("client"), context.get("device")])
        return "|".join(str(part or "") for part in parts)

    def _is_duplicate(self, info: Any, action: str, context: Mapping[str, Any]) -> bool:
        ttl = self._dedupe_playback if action.startswith("playback_") else self._dedupe_library
        if ttl <= 0:
            return False
        key = self._dedupe_key(info, action, context)
        now = time.monotonic()
        with self._condition:
            expired = [item for item, expiry in self._dedupe_cache.items() if expiry <= now]
            for item in expired:
                self._dedupe_cache.pop(item, None)
            if self._dedupe_cache.get(key, 0) > now:
                return True
            self._dedupe_cache[key] = now + ttl
        return False

    def _should_aggregate(self, info: Any, action: str) -> bool:
        return bool(
            self._aggregate_enabled
            and action == "library_added"
            and str(getattr(info, "item_type", "")) in {"TV", "SHOW"}
        )

    def _aggregate_key(self, info: Any, context: Mapping[str, Any]) -> str:
        item = self._raw_item(info)
        series_id = item.get("SeriesId") or item.get("grandparentRatingKey")
        identity = series_id or context.get("media_id") or item.get("SeriesName") or context.get("title")
        return "|".join(str(value or "") for value in (
            context.get("server"), context.get("channel"), context.get("media_source"), identity,
        ))

    def _queue_aggregate(self, info: Any, context: Dict[str, Any]) -> None:
        key = self._aggregate_key(info, context)
        with self._condition:
            if not self._accepting_events:
                return
            self._owned_timers = {timer for timer in self._owned_timers if timer.is_alive()}
            self._pending_messages.setdefault(key, []).append(PendingMessage(info, dict(context)))
            previous = self._aggregate_timers.get(key)
            if previous:
                previous.cancel()
            timer = threading.Timer(self._aggregate_time, self._aggregate_timer_callback, [key])
            timer.daemon = True
            self._aggregate_timers[key] = timer
            self._owned_timers.add(timer)
            timer.start()

    def _aggregate_timer_callback(self, key: str) -> None:
        timer = threading.current_thread()
        try:
            with self._condition:
                if not self._accepting_events or self._aggregate_timers.get(key) is not timer:
                    return
            self._flush_aggregate(key)
        finally:
            with self._condition:
                if self._aggregate_timers.get(key) is timer:
                    self._aggregate_timers.pop(key, None)
                self._condition.notify_all()

    def _flush_aggregate(self, key: str) -> None:
        with self._condition:
            messages = self._pending_messages.pop(key, [])
        if not messages:
            return
        context = dict(messages[0].context)
        episodes = []
        for message in messages:
            value = str(message.context.get("season_episode") or "").strip()
            if value and value not in episodes:
                episodes.append(value)
        context["season_episode"] = "、".join(episodes)
        context["file_count"] = str(len(messages))
        self._send_context("library_added", context)

    def _send_context(self, action: str, context: Dict[str, Any]) -> None:
        if self._add_play_link and not context.get("play_link"):
            try:
                context["play_link"] = self._play_link(context) or ""
            except Exception as error:
                self._log_debug(f"生成播放链接失败：{error}")
        title, body = self._renderer.render(action, context)
        # 登录和测试通知不属于媒体卡片，不附带 TMDB 跳转。
        if action in {"auth_success", "auth_failed", "test"}:
            context["_link"] = None
        else:
            # MoviePilot 的 link 会让整张消息卡片可点击；优先跳转 TMDB。
            context["_link"] = context.get("tmdb_url") or context.get("_link")
        self.post_message(
            mtype=self._notification_type,
            title=title,
            text=body,
            image=context.get("_image"),
            link=context.get("_link"),
        )

    def _send_template_test(self, action: str) -> None:
        """使用稳定的示例字段测试指定类型，便于边改模板边查看效果。"""
        if action not in ACTION_LABELS:
            action = "library_added"
        sample = {
            "action": ACTION_LABELS[action], "event": "preview", "channel": "emby",
            "server": "家庭媒体库", "title": "示例影片", "item_name": "示例影片",
            "display_name": "示例影片 (2026)", "title_link": "[示例影片 (2026)](https://www.themoviedb.org/movie/1)",
            "media_type": "电影", "year": "2026", "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "category": "电影/科幻", "season_episode": "S01E02 - 示例集",
            "rating": "8.6/10", "region": "中国大陆", "status": "连载中",
            "genres": "剧情、科幻", "actors": "演员甲、演员乙",
            "overview": "这是一段用于检查自定义通知排版的示例简介。", "user": "测试用户",
            "device": "MoviePilot 测试设备 · Emby", "client": "Emby", "ip": "192.0.2.1",
            "ip_location": "中国 上海",
            "progress": "36%", "tmdb_id": "1", "tmdb_url": "https://www.themoviedb.org/movie/1",
            "media_source": "themoviedb", "media_id": "1", "file_count": "3",
            "library": "电影库", "album": "示例专辑", "artist": "示例歌手",
            "play_link": "https://media.example/item/1", "_image": None, "_link": None,
            "_item_id": None,
        }
        self._send_context(action, sample)

    def _quiesce(self, flush: Optional[bool] = None) -> bool:
        if not hasattr(self, "_condition"):
            return True
        should_flush = self._flush_on_stop if flush is None and hasattr(self, "_flush_on_stop") else bool(flush)
        deadline = time.monotonic() + self.SHUTDOWN_TIMEOUT
        with self._condition:
            self._accepting_events = False
            timers = set(self._owned_timers) | set(self._aggregate_timers.values())
            pending_keys = list(self._pending_messages)
            for timer in timers:
                timer.cancel()
        for timer in timers:
            if timer is threading.current_thread():
                continue
            try:
                timer.join(timeout=max(0.0, deadline - time.monotonic()))
            except RuntimeError:
                pass
        if should_flush:
            for key in pending_keys:
                self._flush_aggregate(key)
        with self._condition:
            while self._active_operations:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._condition.wait(remaining)
            alive = {timer for timer in timers if timer.is_alive()}
            if alive or self._active_operations:
                self._owned_timers = alive
                return False
            self._owned_timers.clear()
            self._aggregate_timers.clear()
            self._pending_messages.clear()
            self._dedupe_cache.clear()
        return True

    def close(self) -> bool:
        return self._quiesce()

    def stop_service(self) -> bool:
        return self._quiesce()

    # 以下方法由 V2/V3 适配入口实现。
    def _host_initialize(self) -> None:
        raise NotImplementedError

    def _server_options(self) -> List[Dict[str, str]]:
        raise NotImplementedError

    def _discover_libraries(self) -> List[Dict[str, Any]]:
        return []

    def _service_allowed(self, info: Any) -> bool:
        raise NotImplementedError

    def _enrich_context(self, info: Any, context: Dict[str, Any]) -> None:
        raise NotImplementedError

    def _play_link(self, context: Mapping[str, Any]) -> Optional[str]:
        raise NotImplementedError

    def _log_debug(self, message: str) -> None:
        raise NotImplementedError

    def _log_warning(self, message: str) -> None:
        raise NotImplementedError

    def _log_error(self, message: str) -> None:
        raise NotImplementedError
