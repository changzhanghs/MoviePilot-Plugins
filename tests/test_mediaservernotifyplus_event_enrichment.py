"""Run the real V2/V3 adapters with isolated MoviePilot service stubs."""

import importlib.util
import pathlib
import sys
import types
import unittest
from enum import Enum
from types import SimpleNamespace
from unittest.mock import Mock, patch


ROOT = pathlib.Path(__file__).resolve().parents[1]


class MediaType(Enum):
    MOVIE = "电影"
    TV = "电视剧"


class MediaImageType(Enum):
    Poster = "poster_path"
    Backdrop = "backdrop_path"


class MediaSource(Enum):
    TMDB = "themoviedb"


def load_adapter(generation):
    def resolve_media_identity(media):
        media_id = getattr(media, "media_id", None) or getattr(media, "tmdb_id", None)
        return (MediaSource.TMDB, str(media_id)) if media_id else (None, None)

    logger = SimpleNamespace(debug=Mock(), error=Mock())
    modules = {}

    def module(name, **values):
        item = types.ModuleType(name)
        item.__path__ = []
        item.__dict__.update(values)
        modules[name] = item

    for name in ("app", "app.core", "app.helper", "app.schemas", "app.utils", "app.sdk"):
        module(name)
    events = dict(Event=object, eventmanager=SimpleNamespace(register=lambda event: lambda fn: fn))
    services = dict(MediaServerHelper=Mock())
    network = dict(WebUtils=SimpleNamespace(get_location=Mock(return_value="测试归属地")))
    module("app.schemas.types", EventType=SimpleNamespace(WebhookMessage="webhook"),
           MediaType=MediaType, MediaImageType=MediaImageType, MediaSource=MediaSource,
           NotificationType=SimpleNamespace(MediaServer="media"),
           MessageType=SimpleNamespace(MediaServer="media"))
    module("app.core.event", **events)
    module("app.helper.mediaserver", **services)
    module("app.log", logger=logger)
    module("app.plugins", _PluginBase=type("PluginBase", (), {}))
    module("app.utils.web", **network)
    module("app.sdk.events", **events)
    module("app.sdk.services", **services)
    module("app.sdk.logging", logger=logger)
    module("app.sdk.plugin", _PluginBase=type("PluginBase", (), {}))
    module("app.sdk.network", **network)
    module("app.sdk.media", MetaInfoPath=lambda path: SimpleNamespace(),
           resolve_media_identity=resolve_media_identity)
    directory = ROOT / generation / "mediaservernotifyplus"
    spec = importlib.util.spec_from_file_location(
        "event_adapter_" + generation.replace(".", "_"), directory / "__init__.py",
        submodule_search_locations=[str(directory)],
    )
    adapter = importlib.util.module_from_spec(spec)
    modules[spec.name] = adapter
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(adapter)
    return adapter


class EnrichmentCases:
    def setUp(self):
        self.adapter = load_adapter(self.generation)
        self.plugin = self.adapter.MediaServerNotifyPlus()
        self.plugin._service_allowed = Mock(return_value=True)
        self.plugin._service = Mock(return_value=None)
        self.plugin._discover_libraries = Mock(return_value=[])
        self.plugin.post_message = Mock()
        self.plugin.chain = SimpleNamespace(
            tmdb_info=Mock(return_value={}),
            obtain_specific_image=Mock(return_value="https://image.tmdb.org/t/p/w500/show.jpg"),
        )
        self.plugin.init_plugin({"enabled": True})
        self.addCleanup(self.plugin.close)

    def deletion(self, **fields):
        values = dict(
            event="library.deleted", server_name="cz", channel="emby", item_type="TV",
            item_id="deleted-series", season_id=1, episode_id=3,
            json_object={"Item": {"Name": "绑架游戏", "ProductionYear": 2026,
                                  "ProviderIds": {"Tmdb": "320513"}}},
        )
        values.update(fields)
        return SimpleNamespace(event_data=SimpleNamespace(**values))

    def auth_failure(self, raw, **fields):
        return SimpleNamespace(event_data=SimpleNamespace(
            event="user.authenticationfailed", server_name="cz", channel="emby",
            json_object=raw, **fields,
        ))

    def message(self):
        self.assertEqual(self.plugin.post_message.call_count, 1)
        return self.plugin.post_message.call_args.kwargs

    def test_deleted_series_gets_own_image_without_optional_metadata_fields(self):
        self.plugin.handle_webhook(self.deletion())
        message = self.message()
        self.assertEqual(message["image"], "https://image.tmdb.org/t/p/w500/show.jpg")
        self.assertIn("绑架游戏 (2026)", message["title"])
        self.assertEqual(message["link"], "https://www.themoviedb.org/tv/320513")
        self.plugin.chain.tmdb_info.assert_not_called()
        self.plugin.chain.obtain_specific_image.assert_called_once_with(
            mediaid="320513", mtype=MediaType.TV, image_type=MediaImageType.Backdrop,
            season=None, episode=None,
        )

    def test_deleted_series_replaces_expired_server_image(self):
        self.plugin.handle_webhook(self.deletion(
            image_url="https://emby.example/emby/Items/deleted-series/Images/Backdrop?tag=old",
        ))
        self.assertEqual(self.message()["image"], "https://image.tmdb.org/t/p/w500/show.jpg")

    def test_deleted_series_falls_back_to_poster_when_backdrop_is_missing(self):
        self.plugin.chain.obtain_specific_image.side_effect = [None, "https://image.tmdb.org/t/p/w500/poster.jpg"]
        self.plugin.handle_webhook(self.deletion())
        self.assertTrue(self.message()["image"].endswith("poster.jpg"))
        self.assertEqual(self.plugin.chain.obtain_specific_image.call_count, 2)
        self.assertEqual(
            self.plugin.chain.obtain_specific_image.call_args.kwargs["image_type"],
            MediaImageType.Poster,
        )

    def test_image_lookup_failure_still_tries_poster(self):
        self.plugin.chain.obtain_specific_image.side_effect = [RuntimeError("unavailable"), "https://image.tmdb.org/t/p/w500/poster.jpg"]
        self.plugin.handle_webhook(self.deletion())
        self.assertTrue(self.message()["image"].endswith("poster.jpg"))

    def test_expired_image_without_resolvable_identity_uses_default(self):
        self.plugin.handle_webhook(self.deletion(
            json_object={"Item": {"Name": "绑架游戏"}},
            image_url="https://emby.example/Items/deleted-series/Images/Backdrop",
        ))
        self.assertEqual(self.message()["image"], self.adapter.core.DEFAULT_NOTIFICATION_IMAGE)

    def test_episode_still_falls_back_to_series_image(self):
        self.plugin.chain.obtain_specific_image.side_effect = [None, "https://image.tmdb.org/t/p/w500/series.jpg"]
        event = self.deletion(event="playback.start")
        self.plugin.handle_webhook(event)
        self.assertTrue(self.message()["image"].endswith("series.jpg"))
        calls = self.plugin.chain.obtain_specific_image.call_args_list
        self.assertEqual((calls[0].kwargs["season"], calls[0].kwargs["episode"]), (1, 3))
        self.assertIsNone(calls[1].kwargs["season"])
        self.assertIsNone(calls[1].kwargs["episode"])

    def test_media_image_is_loaded_when_all_text_fields_are_disabled(self):
        configs = self.plugin._field_configs
        for rows in configs.values():
            for row in rows:
                row["enabled"] = False
        self.plugin.init_plugin({"enabled": True, "field_configs": configs})
        self.plugin.handle_webhook(self.deletion())
        self.assertEqual(self.message()["image"], "https://image.tmdb.org/t/p/w500/show.jpg")
        self.assertEqual(self.message()["text"], "")
        self.plugin.chain.tmdb_info.assert_not_called()

    def test_auth_failure_extracts_nested_user_and_session(self):
        self.plugin.handle_webhook(self.auth_failure({
            "User": {"Name": "alice"},
            "Session": {"RemoteEndPoint": "192.0.2.1", "DeviceName": "Phone", "Client": "Emby Web"},
            "Title": "Authentication failed for alice",
        }, user_name=None, ip=None, device_name=None, client=None))
        message = self.message()
        for text in ("用户：alice", "设备：Phone · Emby Web", "IP：192.0.2.1 测试归属地", "Authentication failed for alice"):
            self.assertIn(text, message["text"])
        self.plugin.chain.tmdb_info.assert_not_called()
        self.plugin.chain.obtain_specific_image.assert_not_called()
        self.plugin._service.assert_not_called()

    def test_auth_failure_preserves_server_message_when_identity_is_missing(self):
        self.plugin.handle_webhook(self.auth_failure({
            "Title": "登录尝试失败",
            "Description": "服务器拒绝了此次认证请求。",
            "Message": "服务器拒绝了此次认证请求。",
            "Password": "must-not-send",
        }))
        body = self.message()["text"]
        self.assertIn("📝 事件详情\n登录尝试失败\n服务器拒绝了此次认证请求。", body)
        self.assertEqual(body.count("服务器拒绝了此次认证请求。"), 1)
        self.assertNotIn("must-not-send", body)
        self.assertNotIn("👤 用户", body)
        self.assertNotIn("🌐 IP", body)

    def test_auth_failure_extracts_authentication_info(self):
        self.plugin.handle_webhook(self.auth_failure({
            "AuthenticationInfo": {"UserName": "alice", "RemoteEndPoint": "192.0.2.1", "DeviceName": "TV", "Client": "Emby"},
        }))
        body = self.message()["text"]
        for text in ("用户：alice", "IP：192.0.2.1", "设备：TV · Emby"):
            self.assertIn(text, body)

    def test_normalized_fields_take_priority_over_raw_fallbacks(self):
        self.plugin.handle_webhook(self.auth_failure({
            "User": {"Name": "raw-name"}, "Session": {"RemoteEndPoint": "192.0.2.2"},
        }, user_name="normalized-name", ip="192.0.2.1"))
        body = self.message()["text"]
        self.assertIn("normalized-name", body)
        self.assertIn("192.0.2.1", body)
        self.assertNotIn("raw-name", body)
        self.assertNotIn("192.0.2.2", body)

    def test_event_details_can_be_disabled(self):
        configs = self.plugin._field_configs
        next(row for row in configs["auth_failed"] if row["key"] == "event_details")["enabled"] = False
        self.plugin.init_plugin({"enabled": True, "field_configs": configs})
        self.plugin.handle_webhook(self.auth_failure({"Title": "should-be-hidden"}))
        self.assertNotIn("should-be-hidden", self.message()["text"])

    def test_screenshot_login_message_populates_selected_user_and_ip_fields(self):
        self.plugin.handle_webhook(self.auth_failure({
            "Title": "cz 上来自 cz 的登录尝试失败",
            "Description": "192.168.31.1",
        }))
        body = self.message()["text"]
        self.assertIn("👤 用户：cz", body)
        self.assertIn("🌐 IP：192.168.31.1 测试归属地", body)
        self.assertNotIn("📱 设备", body)
        self.assertIn("cz 上来自 cz 的登录尝试失败\n192.168.31.1", body)

    def test_real_login_text_obeys_custom_field_order_labels_and_switches(self):
        configs = self.plugin._field_configs
        configs["auth_failed"] = [
            {"key": "ip", "label": "来源地址", "enabled": True},
            {"key": "user", "label": "登录账号", "enabled": True},
            {"key": "server", "label": "节点", "enabled": True},
            {"key": "device", "label": "设备", "enabled": False},
            {"key": "time", "label": "时间", "enabled": False},
            {"key": "event_details", "label": "事件详情", "enabled": False},
        ]
        self.plugin.init_plugin({"enabled": True, "field_configs": configs})
        self.plugin.handle_webhook(self.auth_failure({
            "Title": "cz 上来自 测试 用户 的登录尝试失败",
            "Description": "192.168.31.1",
            "Session": {"DeviceName": "Phone"},
        }))
        self.assertEqual(self.message()["text"],
                         "🌐 来源地址：192.168.31.1 测试归属地\n👤 登录账号：测试 用户\n🖥️ 节点：cz")

    def test_structured_identity_has_priority_over_parsed_notification_text(self):
        self.plugin.handle_webhook(self.auth_failure({
            "Title": "cz 上来自 text-user 的登录尝试失败",
            "Description": "192.168.31.1",
            "User": {"Name": "structured-user"},
            "Session": {"RemoteEndPoint": "192.0.2.1"},
        }))
        body = self.message()["text"]
        self.assertIn("👤 用户：structured-user", body)
        self.assertIn("🌐 IP：192.0.2.1 测试归属地", body)
        self.assertNotIn("👤 用户：text-user", body)

    def test_notification_text_identity_handles_ipv6_endpoints_and_english_titles(self):
        for title, description, username, address in (
            ("Failed login attempt from alice on cz", "Remote IP: 192.0.2.5:8096", "alice", "192.0.2.5"),
            ("Authentication failed for Bob on cz", "[2001:db8::5]:8096", "Bob", "2001:db8::5"),
            ("cz 上来自 中文用户 的登录尝试失败", "远程地址：::1", "中文用户", "::1"),
        ):
            with self.subTest(description=description):
                user, ip = self.adapter.core.MediaServerNotifyCore._auth_text_identity({
                    "Title": title, "Description": description,
                })
                self.assertEqual((user, ip), (username, address))

    def test_notification_text_does_not_treat_dates_or_invalid_addresses_as_ip(self):
        user, ip = self.adapter.core.MediaServerNotifyCore._auth_text_identity({
            "Title": "登录尝试失败", "Description": "2026-10-22 00:12:01 999.168.31.1",
        })
        self.assertEqual((user, ip), ("", ""))

    def test_parsed_users_and_ips_are_distinct_for_deduplication(self):
        for user, address in (("alice", "192.0.2.1"), ("bob", "192.0.2.1"), ("bob", "192.0.2.2")):
            event = self.auth_failure({
                "Title": f"cz 上来自 {user} 的登录尝试失败", "Description": address,
            })
            self.plugin.handle_webhook(event)
            self.plugin.handle_webhook(event)
        self.assertEqual(self.plugin.post_message.call_count, 3)


class V2Enrichment(EnrichmentCases, unittest.TestCase):
    generation = "plugins.v2"


class V3Enrichment(EnrichmentCases, unittest.TestCase):
    generation = "plugins.v3"


if __name__ == "__main__":
    unittest.main()
