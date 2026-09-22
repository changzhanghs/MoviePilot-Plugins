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
    def test_template_settings_have_a_separate_tab(self):
        plugin = FakePlugin()
        form, defaults = plugin.get_form()

        def walk(nodes):
            for node in nodes if isinstance(nodes, list) else [nodes]:
                if not isinstance(node, dict):
                    continue
                yield node
                yield from walk(node.get("content", []))

        nodes = list(walk(form))
        tabs = [node for node in nodes if node.get("component") == "VTab"]
        self.assertEqual([node.get("text") for node in tabs], ["基础设置", "通知模板设置"])
        template_window = next(
            node for node in nodes
            if node.get("component") == "VWindowItem"
            and node.get("props", {}).get("value") == "templates"
        )
        template_models = {
            node.get("props", {}).get("model")
            for node in walk(template_window.get("content", []))
        }
        self.assertIn("preview_type", template_models)
        self.assertIn("send_test", template_models)
        self.assertIn("title_template_library_added", template_models)
        self.assertEqual(defaults["_settings_tab"], "basic")

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

    def test_custom_template_is_loaded_per_event(self):
        plugin = FakePlugin()
        plugin.init_plugin({
            "enabled": True,
            "title_template_auth_failed": "警告：{user}",
            "body_template_auth_failed": "来自 {ip}",
        })
        plugin._send_context("auth_failed", {"user": "alice", "ip": "192.0.2.1"})
        self.assertEqual(plugin.messages[-1]["title"], "警告：alice")
        self.assertEqual(plugin.messages[-1]["text"], "来自 192.0.2.1")

    def test_save_time_preview_uses_selected_type_and_resets_switch(self):
        plugin = FakePlugin()
        plugin.init_plugin({
            "enabled": True,
            "preview_type": "playback_started",
            "send_test": True,
            "title_template_playback_started": "预览 {user}",
            "body_template_playback_started": "进度 {progress}",
        })
        self.assertEqual(plugin.messages[-1]["title"], "预览 测试用户")
        self.assertEqual(plugin.messages[-1]["text"], "进度 36%")
        self.assertFalse(plugin.saved_config["send_test"])


if __name__ == "__main__":
    unittest.main()
