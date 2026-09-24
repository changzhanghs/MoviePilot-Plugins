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

    def _server_options(self):
        return []

    def _service_allowed(self, info):
        return True

    def _enrich_context(self, info, context):
        pass

    def post_message(self, **kwargs):
        self.messages.append(kwargs)

    def update_config(self, config):
        self.saved_config = config

    def _log_debug(self, message):
        pass

    def _log_error(self, message):
        raise AssertionError(message)


class TemplateTests(unittest.TestCase):
    def test_vue_config_exposes_card_editor_metadata(self):
        plugin = FakePlugin()
        form, defaults = plugin.get_form()
        self.assertIsNone(form)
        self.assertEqual(plugin.get_render_mode(), ("vue", "dist/assets"))
        self.assertIn("library_added", defaults["field_configs"])
        self.assertIn("library_added", defaults["_action_meta"])
        self.assertIn("ip", defaults["_field_catalog"])
        self.assertNotIn("ip_location", defaults["_field_catalog"])
        self.assertIn("_server_options", defaults)
        self.assertTrue(plugin.get_page())
        self.assertNotIn("notification_type", defaults)

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

    def test_aggregate_keeps_only_contexts_and_combines_episodes(self):
        plugin = FakePlugin()
        plugin._pending_messages["series"] = [
            {"display_name": "光阴之外 (2025)", "season_episode": "S01E21"},
            {"display_name": "光阴之外 (2025)", "season_episode": "S01E22"},
        ]
        plugin._flush_aggregate("series")
        message = plugin.messages[-1]
        self.assertEqual(message["title"], "📂 已入库 2 个文件\n光阴之外 (2025)")
        self.assertIn("S01E21、S01E22", message["text"])
        self.assertNotIn("series", plugin._pending_messages)

    def test_library_fields_exclude_playback_details(self):
        configs = CORE.default_field_configs()
        expected = [
            "season_episode", "user", "device", "progress", "server", "library",
            "rating", "actors", "region", "ip", "time", "overview",
        ]
        for action in ("library_added", "library_deleted"):
            self.assertEqual(
                [row["key"] for row in configs[action]],
                [key for key in expected if key not in {"user", "device", "progress", "ip"}],
            )
        for action in (
            "playback_started", "playback_stopped", "playback_paused", "playback_resumed", "rated",
        ):
            self.assertEqual([row["key"] for row in configs[action]], expected)
        playback_keys = [row["key"] for row in configs["playback_started"]]
        self.assertNotIn("client", playback_keys)
        self.assertNotIn("media_type", playback_keys)
        self.assertNotIn("play_link", playback_keys)
        self.assertEqual(CORE.FIELD_CATALOG["device"]["label"], "设备")
        self.assertEqual(
            [row["key"] for row in configs["auth_success"]],
            ["user", "device", "ip", "server", "time"],
        )
        self.assertEqual([row["key"] for row in configs["test"]], ["server", "time"])

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
        self.assertTrue(plugin._match_library(info, context))
        self.assertEqual(context["library"], "动漫")

        name_context = {"server": "cz"}
        name_info = SimpleNamespace(
            item_path="", json_object={"Item": {"librarySectionTitle": "动漫"}},
        )
        self.assertTrue(plugin._match_library(name_info, name_context))
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
        self.assertEqual(set(CORE.FIELD_CATALOG), set(CORE.COMMON_MEDIA_FIELDS))

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
                {"key": "user", "label": "用户", "enabled": True},
                {"key": "device", "label": "设备", "enabled": True},
                {"key": "progress", "label": "播放进度", "enabled": True},
                {"key": "ip", "label": "IP", "enabled": True},
            ],
            "library_deleted": [
                {"key": "user", "label": "用户", "enabled": True},
                {"key": "device", "label": "设备", "enabled": True},
                {"key": "progress", "label": "播放进度", "enabled": True},
                {"key": "ip", "label": "IP", "enabled": True},
            ],
        })
        rows = normalized["playback_started"]
        self.assertEqual(next(row for row in rows if row["key"] == "device")["label"], "设备")
        self.assertTrue({row["key"] for row in rows}.isdisjoint({"client", "year", "channel", "ip_location", "play_link"}))
        self.assertIn("overview", {row["key"] for row in rows})
        library_rows = {row["key"]: row for row in normalized["library_added"]}
        self.assertEqual(library_rows["library"]["label"], "媒体库分类")
        self.assertNotIn("category", library_rows)
        for action in ("library_added", "library_deleted"):
            self.assertTrue(
                {row["key"] for row in normalized[action]}.isdisjoint({"user", "device", "progress", "ip"})
            )

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
