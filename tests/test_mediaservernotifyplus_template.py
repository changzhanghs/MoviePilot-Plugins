import importlib.util
import pathlib
import sys
import unittest
from types import SimpleNamespace


ROOT = pathlib.Path(__file__).resolve().parents[1]
CORE_PATH = ROOT / "plugins.v2" / "mediaservernotifyplus" / "core.py"
SPEC = importlib.util.spec_from_file_location("mediaservernotifyplus_core", CORE_PATH)
CORE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = CORE
SPEC.loader.exec_module(CORE)


class FakePlugin(CORE.MediaServerNotifyCore):
    _notification_type = "media"

    def __init__(self):
        self.messages = []
        self.saved_config = None
        self._initialize_core()

    def _host_initialize(self):
        pass

    def _server_options(self):
        return []

    def _service_allowed(self, info):
        return True

    def _enrich_context(self, info, context):
        pass

    def _play_link(self, context):
        return None

    def post_message(self, **kwargs):
        self.messages.append(kwargs)

    def update_config(self, config):
        self.saved_config = config

    def _log_debug(self, message):
        pass

    def _log_warning(self, message):
        pass

    def _log_error(self, message):
        raise AssertionError(message)


class TemplateTests(unittest.TestCase):
    def test_vue_config_exposes_card_editor_metadata(self):
        plugin = FakePlugin()
        form, defaults = plugin.get_form()
        self.assertEqual(form, [])
        self.assertEqual(plugin.get_render_mode(), ("vue", "dist/assets"))
        self.assertIn("library_added", defaults["field_configs"])
        self.assertIn("library_added", defaults["_action_meta"])
        self.assertIn("ip", defaults["_field_catalog"])
        self.assertNotIn("ip_location", defaults["_field_catalog"])
        self.assertIn("_server_options", defaults)
        self.assertTrue(plugin.get_page())
        self.assertNotIn("notification_type", defaults)

    def test_arbitrary_layout_and_field_order(self):
        renderer = CORE.SafeTemplateRenderer({
            "library_added": {
                "title": "{server} :: {title}",
                "body": "演员={actors}\n先简介：{overview}\n后时间：{time}",
            }
        })
        title, body = renderer.render("library_added", {
            "server": "Emby", "title": "电影", "actors": "甲、乙",
            "overview": "简介", "time": "12:00",
        })
        self.assertEqual(title, "Emby :: 电影")
        self.assertEqual(body, "演员=甲、乙\n先简介：简介\n后时间：12:00")

    def test_empty_field_line_and_conditional_line_are_hidden(self):
        renderer = CORE.SafeTemplateRenderer({
            "library_added": {
                "title": "{title}",
                "body": "⭐ {rating}\n[[overview]]---\n{overview}\n始终显示",
            }
        })
        _, body = renderer.render("library_added", {"title": "电影"})
        self.assertEqual(body, "始终显示")

    def test_unsafe_or_unknown_fields_are_rejected(self):
        with self.assertRaises(CORE.TemplateError):
            CORE.SafeTemplateRenderer({
                "library_added": {"title": "{title.__class__}", "body": "x"}
            })
        with self.assertRaises(CORE.TemplateError):
            CORE.SafeTemplateRenderer({
                "library_added": {"title": "{unknown}", "body": "x"}
            })

    def test_custom_field_order_label_and_switch_are_loaded_per_event(self):
        plugin = FakePlugin()
        configs = CORE.default_field_configs()
        configs["auth_failed"] = [
            {"key": "ip", "label": "IP地址", "enabled": True},
            {"key": "user", "label": "用户", "enabled": False},
        ]
        plugin.init_plugin({
            "enabled": True,
            "field_configs": configs,
        })
        plugin._send_context("auth_failed", {"user": "alice", "ip": "192.0.2.1"})
        self.assertEqual(plugin.messages[-1]["title"], "⚠️ 登录失败")
        self.assertEqual(plugin.messages[-1]["text"], "🌐 IP地址：192.0.2.1")

    def test_save_time_preview_uses_selected_type_and_resets_switch(self):
        plugin = FakePlugin()
        plugin.init_plugin({
            "enabled": True,
            "preview_type": "playback_started",
            "send_test": True,
        })
        self.assertEqual(plugin.messages[-1]["title"], "▶️ 开始播放\n示例影片 (2026)")
        self.assertNotIn("示例影片 (2026)", plugin.messages[-1]["text"])
        self.assertIn("36%", plugin.messages[-1]["text"])
        self.assertTrue(plugin.messages[-1]["image"].startswith("https://image.tmdb.org/"))
        self.assertFalse(plugin.saved_config["send_test"])

    def test_library_added_uses_fixed_heading_and_clickable_tmdb_card(self):
        plugin = FakePlugin()
        plugin.init_plugin({"enabled": True})
        plugin._send_context("library_added", {
            "display_name": "兰香如故 (2026)",
            "file_count": "1",
            "season_episode": "S01E21",
            "tmdb_url": "https://www.themoviedb.org/tv/1",
        })
        message = plugin.messages[-1]
        self.assertEqual(message["title"], "📂 已入库 1 个文件\n兰香如故 (2026)")
        self.assertNotIn("兰香如故 (2026)", message["text"])
        self.assertEqual(message["link"], "https://www.themoviedb.org/tv/1")

    def test_playback_fields_merge_device_client_and_offer_overview(self):
        configs = CORE.default_field_configs()
        expected = [
            "season_episode", "user", "device", "progress", "ip", "library",
            "region", "rating", "actors", "time", "overview", "server",
        ]
        for action in (
            "playback_started", "playback_stopped", "playback_paused", "playback_resumed",
        ):
            self.assertEqual([row["key"] for row in configs[action]], expected)
        playback_keys = [row["key"] for row in configs["playback_started"]]
        self.assertNotIn("client", playback_keys)
        self.assertNotIn("media_type", playback_keys)
        self.assertNotIn("play_link", playback_keys)
        self.assertEqual(CORE.FIELD_CATALOG["device"]["label"], "设备")

        info = SimpleNamespace(
            json_object={"Item": {"SeriesName": "兰香如故", "Name": "交个朋友吧?"}},
            item_type="TV", season_id=1, episode_id=12, device_name="Apple TV", client="VidHub",
        )
        context = CORE.MediaServerNotifyCore._base_context(info, "playback_started")
        self.assertEqual(context["display_name"], "兰香如故")
        self.assertEqual(context["device"], "Apple TV · VidHub")
        self.assertEqual(context["season_episode"], "S01E12 - 交个朋友吧?")

    def test_library_records_merge_virtual_paths_and_match_real_library(self):
        libraries = [SimpleNamespace(id="lib-tv", name="动漫", path=None, type="TV")]
        virtual_libraries = [{
            "Id": "lib-tv", "Name": "动漫", "Path": ["/media/anime", "/mnt/anime"],
        }]
        records = CORE.build_library_records("cz", libraries, virtual_libraries)
        self.assertEqual(records[0]["paths"], ["/media/anime", "/mnt/anime"])

        plugin = FakePlugin()
        plugin._library_records = records
        context = {"server": "cz"}
        info = SimpleNamespace(
            item_path="/media/anime/Show/Season 01/episode.mkv",
            json_object={"Item": {"Path": "/media/anime/Show/Season 01/episode.mkv"}},
        )
        self.assertEqual(plugin._match_library(info, context), "cz::lib-tv")
        self.assertEqual(context["library"], "动漫")

        name_context = {"server": "cz"}
        name_info = SimpleNamespace(
            item_path="", json_object={"Item": {"librarySectionTitle": "动漫"}},
        )
        self.assertEqual(plugin._match_library(name_info, name_context), "cz::lib-tv")
        self.assertEqual(name_context["library"], "动漫")

    def test_ip_field_also_contains_location_without_a_second_option(self):
        configs = CORE.default_field_configs()
        playback_keys = [row["key"] for row in configs["playback_started"]]
        self.assertIn("ip", playback_keys)
        self.assertNotIn("ip_location", playback_keys)
        self.assertEqual(
            CORE.merge_ip_location("192.0.2.1", "中国 上海"),
            "192.0.2.1 中国 上海",
        )
        self.assertEqual(
            CORE.merge_ip_location("192.0.2.1 中国 上海", "中国 上海"),
            "192.0.2.1 中国 上海",
        )
    def test_retired_fields_are_removed_and_media_events_offer_overview(self):
        configs = CORE.default_field_configs()
        for rows in configs.values():
            keys = {row["key"] for row in rows}
            self.assertTrue(keys.isdisjoint({"client", "year", "channel", "ip_location", "play_link"}))
        for action in (
            "library_added", "library_deleted", "playback_started", "playback_stopped",
            "playback_paused", "playback_resumed", "rated",
        ):
            self.assertIn("overview", {row["key"] for row in configs[action]})
        self.assertNotIn("client", CORE.FIELD_CATALOG)
        self.assertNotIn("year", CORE.FIELD_CATALOG)
        self.assertNotIn("channel", CORE.FIELD_CATALOG)
        self.assertNotIn("ip_location", CORE.FIELD_CATALOG)
        self.assertNotIn("play_link", CORE.FIELD_CATALOG)
        self.assertEqual(CORE.FIELD_CATALOG["library"]["label"], "媒体库分类")
        self.assertEqual(CORE.FIELD_CATALOG["category"]["label"], "媒体类别")

    def test_legacy_field_config_is_migrated_before_sending(self):
        normalized = CORE.normalize_field_configs({
            "playback_started": [
                {"key": "device", "label": "设备 / 客户端", "enabled": True},
                {"key": "client", "label": "客户端", "enabled": True},
                {"key": "year", "label": "年份", "enabled": True},
                {"key": "channel", "label": "媒体服务", "enabled": True},
                {"key": "ip_location", "label": "IP 归属地", "enabled": True},
                {"key": "play_link", "label": "播放链接", "enabled": True},
            ],
            "library_added": [
                {"key": "library", "label": "媒体类别", "enabled": True},
                {"key": "category", "label": "分类", "enabled": True},
            ],
        })
        rows = normalized["playback_started"]
        self.assertEqual(next(row for row in rows if row["key"] == "device")["label"], "设备")
        self.assertTrue({row["key"] for row in rows}.isdisjoint({"client", "year", "channel", "ip_location", "play_link"}))
        self.assertIn("overview", {row["key"] for row in rows})
        library_rows = {row["key"]: row for row in normalized["library_added"]}
        self.assertEqual(library_rows["library"]["label"], "媒体库分类")
        self.assertEqual(library_rows["category"]["label"], "媒体类别")

    def test_login_and_test_notifications_never_link_to_tmdb(self):
        plugin = FakePlugin()
        plugin.init_plugin({"enabled": True})
        for action in ("auth_success", "auth_failed", "test"):
            plugin._send_context(action, {
                "user": "alice", "server": "Emby", "time": "12:00",
                "tmdb_url": "https://www.themoviedb.org/tv/1",
            })
            self.assertIsNone(plugin.messages[-1]["link"])


if __name__ == "__main__":
    unittest.main()
