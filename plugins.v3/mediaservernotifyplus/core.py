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
        self._renderer = SafeTemplateRenderer(DEFAULT_TEMPLATES)
        self._host_initialize()

    def init_plugin(self, config: Optional[dict] = None) -> None:
        """可重复调用地读取配置并重建运行状态。"""
        self._quiesce(flush=False)
        config = config or {}
        templates: Dict[str, Dict[str, str]] = {}
        for action, defaults in DEFAULT_TEMPLATES.items():
            title_key = f"title_template_{action}"
            body_key = f"body_template_{action}"
            title = str(config[title_key]) if title_key in config else defaults["title"]
            body = str(config[body_key]) if body_key in config else defaults["body"]
            try:
                renderer = SafeTemplateRenderer({action: {"title": title, "body": body}})
                templates[action] = renderer._templates[action]
            except TemplateError as error:
                self._log_warning(f"{ACTION_LABELS[action]} 模板无效，已回退默认模板：{error}")
                templates[action] = dict(defaults)
        with self._condition:
            self._enabled = bool(config.get("enabled"))
            self._types = list(config.get("types") or [])
            self._mediaservers = list(config.get("mediaservers") or [])
            self._add_play_link = bool(config.get("add_play_link", False))
            self._lookup_ip = bool(config.get("lookup_ip", False))
            self._fetch_metadata = bool(config.get("fetch_metadata", True))
            self._aggregate_enabled = bool(config.get("aggregate_enabled", True))
            self._aggregate_time = max(1, int(config.get("aggregate_time") or self.DEFAULT_AGGREGATE_TIME))
            self._dedupe_library = max(0, int(config.get("dedupe_library") or self.DEFAULT_DEDUPE_TIME))
            self._dedupe_playback = max(0, int(config.get("dedupe_playback") or self.DEFAULT_DEDUPE_TIME))
            self._flush_on_stop = bool(config.get("flush_on_stop", False))
            self._renderer = SafeTemplateRenderer(templates)
            self._accepting_events = True
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
        return [{
            "component": "VAlert",
            "props": {
                "type": "info",
                "variant": "tonal",
                "text": "可在配置页中为每种事件分别设置标题和正文模板。",
            },
        }]

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """构建通用配置页，模板使用展开面板按事件分类。"""
        type_items = [{"title": label, "value": action} for action, label in ACTION_LABELS.items()]
        panels = []
        for action, label in ACTION_LABELS.items():
            panels.append({
                "component": "VExpansionPanel",
                "content": [
                    {"component": "VExpansionPanelTitle", "text": label},
                    {
                        "component": "VExpansionPanelText",
                        "content": [
                            {
                                "component": "VTextField",
                                "props": {
                                    "model": f"title_template_{action}",
                                    "label": f"{label}标题模板",
                                    "clearable": True,
                                },
                            },
                            {
                                "component": "VTextarea",
                                "props": {
                                    "model": f"body_template_{action}",
                                    "label": f"{label}正文模板",
                                    "rows": 8,
                                    "auto-grow": True,
                                    "clearable": True,
                                },
                            },
                        ],
                    },
                ],
            })
        base_settings = [
            {
                "component": "VRow",
                "content": [
                    {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [
                        {"component": "VSwitch", "props": {"model": "enabled", "label": "启用插件"}},
                    ]},
                    {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [
                        {"component": "VSwitch", "props": {"model": "add_play_link", "label": "添加播放链接"}},
                    ]},
                    {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [
                        {"component": "VSwitch", "props": {"model": "fetch_metadata", "label": "查询媒体元数据"}},
                    ]},
                    {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [
                        {"component": "VSwitch", "props": {"model": "lookup_ip", "label": "查询 IP 归属地"}},
                    ]},
                ],
            },
            {
                "component": "VSelect",
                "props": {
                    "model": "mediaservers", "label": "媒体服务器", "multiple": True,
                    "chips": True, "clearable": True, "items": self._server_options(),
                },
            },
            {
                "component": "VSelect",
                "props": {
                    "model": "types", "label": "通知类型", "multiple": True,
                    "chips": True, "clearable": True, "items": type_items,
                },
            },
            {
                "component": "VRow",
                "content": [
                    {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [
                        {"component": "VSwitch", "props": {"model": "aggregate_enabled", "label": "聚合剧集入库"}},
                    ]},
                    {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [
                        {"component": "VTextField", "props": {"model": "aggregate_time", "label": "聚合窗口（秒）", "type": "number", "min": 1}},
                    ]},
                    {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [
                        {"component": "VSwitch", "props": {"model": "flush_on_stop", "label": "停止时发送待聚合消息"}},
                    ]},
                ],
            },
            {
                "component": "VRow",
                "content": [
                    {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [
                        {"component": "VTextField", "props": {"model": "dedupe_library", "label": "入库/删除去重窗口（秒）", "type": "number", "min": 0}},
                    ]},
                    {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [
                        {"component": "VTextField", "props": {"model": "dedupe_playback", "label": "播放事件去重窗口（秒）", "type": "number", "min": 0}},
                    ]},
                ],
            },
        ]
        template_settings = [
            {
                "component": "VAlert",
                "props": {
                    "type": "info", "variant": "tonal",
                    "text": "标题和正文均可自由排版。支持 Markdown、Emoji 和换行；正文中含空占位符的整行会自动隐藏。",
                },
            },
            {
                "component": "VRow",
                "content": [
                    {"component": "VCol", "props": {"cols": 12, "md": 8}, "content": [
                        {"component": "VSelect", "props": {
                            "model": "preview_type", "label": "测试模板类型", "items": type_items,
                        }},
                    ]},
                    {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [
                        {"component": "VSwitch", "props": {
                            "model": "send_test", "label": "保存时发送模板测试",
                        }},
                    ]},
                ],
            },
            {
                "component": "VAlert",
                "props": {
                    "type": "info", "variant": "outlined",
                    "text": "占位符：" + "、".join(f"{{{field}}}" for field in TEMPLATE_FIELDS)
                            + "。条件行示例：[[overview]]剧情简介。",
                },
            },
            {"component": "VExpansionPanels", "props": {"multiple": True}, "content": panels},
        ]
        form = [{
            "component": "VForm",
            "content": [
                {
                    "component": "VTabs",
                    "props": {"model": "_settings_tab", "fixed-tabs": True},
                    "content": [
                        {"component": "VTab", "props": {"value": "basic"}, "text": "基础设置"},
                        {"component": "VTab", "props": {"value": "templates"}, "text": "通知模板设置"},
                    ],
                },
                {
                    "component": "VWindow",
                    "props": {"model": "_settings_tab"},
                    "content": [
                        {"component": "VWindowItem", "props": {"value": "basic"}, "content": base_settings},
                        {"component": "VWindowItem", "props": {"value": "templates"}, "content": template_settings},
                    ],
                },
            ],
        }]
        defaults: Dict[str, Any] = {
            "enabled": False,
            "mediaservers": [],
            "types": list(ACTION_LABELS),
            "add_play_link": False,
            "lookup_ip": False,
            "fetch_metadata": True,
            "aggregate_enabled": True,
            "aggregate_time": self.DEFAULT_AGGREGATE_TIME,
            "dedupe_library": self.DEFAULT_DEDUPE_TIME,
            "dedupe_playback": self.DEFAULT_DEDUPE_TIME,
            "flush_on_stop": False,
            "preview_type": "library_added",
            "send_test": False,
            "_settings_tab": "basic",
        }
        for action, template in DEFAULT_TEMPLATES.items():
            defaults[f"title_template_{action}"] = template["title"]
            defaults[f"body_template_{action}"] = template["body"]
        return form, defaults

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
            item.get("SeriesName") or raw.get("SeriesName") or item.get("Name")
            or raw.get("Name") or getattr(info, "item_name", None) or "未知媒体"
        )
        year = item.get("ProductionYear") or raw.get("Year") or item.get("year") or ""
        season = item.get("ParentIndexNumber")
        episode = item.get("IndexNumber")
        season = season if season is not None else getattr(info, "season_id", None)
        episode = episode if episode is not None else getattr(info, "episode_id", None)
        season_episode = ""
        if season is not None and episode is not None:
            try:
                season_episode = f"S{int(season):02d}E{int(episode):02d}"
            except (TypeError, ValueError):
                season_episode = f"S{season}E{episode}"
            episode_name = item.get("Name") or raw.get("Name")
            if episode_name and str(episode_name) not in str(title):
                season_episode += f" - {episode_name}"
        client = getattr(info, "client", None) or raw.get("ClientName") or ""
        device_name = getattr(info, "device_name", None) or raw.get("DeviceName") or ""
        device = " ".join(str(value).strip() for value in (client, device_name) if value).strip()
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
            "category": "",
            "season_episode": season_episode,
            "rating": "",
            "region": "",
            "status": "",
            "genres": "",
            "actors": "",
            "overview": getattr(info, "overview", "") or raw.get("Overview") or item.get("Overview") or "",
            "user": getattr(info, "user_name", "") or raw.get("NotificationUsername") or "",
            "device": device,
            "client": client,
            "ip": getattr(info, "ip", "") or raw.get("RemoteEndPoint") or "",
            "progress": progress,
            "tmdb_id": "",
            "tmdb_url": "",
            "media_source": "",
            "media_id": "",
            "file_count": "",
            "album": item.get("Album") or raw.get("Album") or "",
            "artist": ", ".join(item.get("Artists") or []) if isinstance(item.get("Artists"), list) else item.get("Artist", ""),
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
        title, body = self._renderer.render(action, context)
        if self._add_play_link and not context.get("_link"):
            try:
                context["_link"] = self._play_link(context)
            except Exception as error:
                self._log_debug(f"生成播放链接失败：{error}")
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
            "device": "MoviePilot 测试设备", "client": "Emby", "ip": "192.0.2.1",
            "progress": "36%", "tmdb_id": "1", "tmdb_url": "https://www.themoviedb.org/movie/1",
            "media_source": "themoviedb", "media_id": "1", "file_count": "3",
            "album": "示例专辑", "artist": "示例歌手", "_image": None, "_link": None,
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
