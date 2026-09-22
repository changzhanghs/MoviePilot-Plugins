import importlib.util
import pathlib
import sys
import unittest


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
        self.assertEqual(plugin.messages[-1]["title"], "▶️ 开始播放")
        self.assertIn("示例影片 (2026)", plugin.messages[-1]["text"])
        self.assertIn("36%", plugin.messages[-1]["text"])
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
        self.assertEqual(message["title"], "📂 已入库 1 个文件")
        self.assertTrue(message["text"].startswith("兰香如故 (2026)"))
        self.assertEqual(message["link"], "https://www.themoviedb.org/tv/1")


if __name__ == "__main__":
    unittest.main()
