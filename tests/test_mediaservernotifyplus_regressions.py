"""Exercise event handling and lifecycle behavior against both shipped cores."""

import hashlib
import importlib.util
import pathlib
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_core(generation):
    path = ROOT / generation / "mediaservernotifyplus" / "core.py"
    spec = importlib.util.spec_from_file_location(f"regression_{generation}", path)
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)
    return core


def plugin_class(core):
    class FakePlugin(core.MediaServerNotifyCore):
        _notification_type = "media"

        def __init__(self):
            self.messages = []
            self._initialize_core()

        def _service_allowed(self, info):
            return True

        def _enrich_context(self, info, context):
            pass

        def post_message(self, **kwargs):
            self.messages.append(kwargs)

        def update_config(self, config):
            pass

        def _log_debug(self, message):
            pass

        def _log_error(self, message):
            raise AssertionError(message)

    return FakePlugin


def webhook(name="playback.start", **values):
    fields = dict(
        event=name, server_name="家庭媒体库", channel="emby", item_id="episode-1",
        item_name="示例剧集", item_type="TV", season_id=1, episode_id=1,
        user_name="alice", ip="192.0.2.1", client="Emby", device_name="Phone",
        session_id="session-1", json_object={},
    )
    fields.update(values)
    return SimpleNamespace(event_data=SimpleNamespace(**fields))


class RegressionCases:
    def make_plugin(self, **config):
        plugin = plugin_class(self.core)()
        plugin.SHUTDOWN_TIMEOUT = 0.02
        plugin.init_plugin({"enabled": True, "aggregate_time": 3600, **config})
        self.addCleanup(plugin.close)
        return plugin

    def test_zero_disables_deduplication_through_event_handler(self):
        for action in ("library.new", "playback.start"):
            with self.subTest(action=action):
                plugin = self.make_plugin(
                    dedupe_library=0, dedupe_playback=0, aggregate_enabled=False,
                )
                event = webhook(action)
                plugin.handle_webhook(event)
                plugin.handle_webhook(event)
                self.assertEqual(len(plugin.messages), 2)

    def test_missing_dedupe_settings_keep_defaults(self):
        for setting in ({}, {"dedupe_library": None, "dedupe_playback": ""}):
            with self.subTest(setting=setting):
                plugin = self.make_plugin(**setting)
                self.assertEqual(plugin._dedupe_library, plugin.DEFAULT_DEDUPE_TIME)
                self.assertEqual(plugin._dedupe_playback, plugin.DEFAULT_DEDUPE_TIME)
                event = webhook()
                plugin.handle_webhook(event)
                plugin.handle_webhook(event)
                self.assertEqual(len(plugin.messages), 1)

    def test_accounts_deduplicate_only_matching_user_and_source(self):
        variants = ({}, {"user_name": "bob"}, {"ip": "192.0.2.2"},
                    {"client": "Browser"}, {"device_name": "TV"},
                    {"session_id": "session-2"})
        for action in ("user.authenticated", "user.authenticationfailed"):
            with self.subTest(action=action):
                plugin = self.make_plugin()
                for count, changes in enumerate(variants, 1):
                    event = webhook(action, item_id=None, **changes)
                    plugin.handle_webhook(event)
                    plugin.handle_webhook(event)
                    self.assertEqual(len(plugin.messages), count, changes)

    def test_accounts_use_raw_identity_fallbacks(self):
        plugin = self.make_plugin()
        for user, ip in (("alice", "192.0.2.1"), ("bob", "192.0.2.1"), ("bob", "192.0.2.2")):
            event = SimpleNamespace(event_data=SimpleNamespace(
                event="user.authenticationfailed", channel="emby",
                json_object={"ServerName": "家庭媒体库", "Username": user,
                             "RemoteEndPoint": ip, "DeviceName": "Phone", "App": "Emby"},
            ))
            plugin.handle_webhook(event)
            plugin.handle_webhook(event)
        self.assertEqual(len(plugin.messages), 3)
        self.assertIn("bob", plugin.messages[-1]["text"])
        self.assertIn("192.0.2.2", plugin.messages[-1]["text"])

    def test_reload_flushes_only_when_requested_and_uses_old_template(self):
        for flush in (False, True):
            with self.subTest(flush=flush):
                configs = self.core.default_field_configs()
                next(row for row in configs["library_added"] if row["key"] == "server")["label"] = "旧服务器"
                plugin = self.make_plugin(flush_on_stop=flush, field_configs=configs)
                plugin.handle_webhook(webhook("library.new"))
                self.assertEqual(len(plugin._pending_messages), 1)
                plugin.init_plugin({"enabled": True, "aggregate_time": 3600})
                self.assertEqual(len(plugin.messages), int(flush))
                self.assertEqual(plugin._pending_messages, {})
                if flush:
                    self.assertIn("旧服务器", plugin.messages[0]["text"])
                plugin.close()
                self.assertEqual(len(plugin.messages), int(flush))

    def test_stop_flushes_once(self):
        plugin = self.make_plugin(flush_on_stop=True)
        plugin.handle_webhook(webhook("library.new"))
        self.assertTrue(plugin.stop_service())
        self.assertTrue(plugin.close())
        self.assertEqual(len(plugin.messages), 1)
        self.assertEqual(plugin._pending_messages, {})

    def test_inflight_events_cannot_send_or_queue_after_reload_timeout(self):
        for action in ("playback.start", "library.new"):
            for enabled in (False, True):
                with self.subTest(action=action, enabled=enabled):
                    plugin = self.make_plugin()
                    entered, release = threading.Event(), threading.Event()

                    def slow_enrich(info, context):
                        entered.set()
                        release.wait(3)

                    plugin._enrich_context = slow_enrich
                    event = webhook(action)
                    worker = threading.Thread(target=plugin.handle_webhook, args=(event,))
                    worker.start()
                    try:
                        self.assertTrue(entered.wait(1))
                        plugin.init_plugin({"enabled": enabled, "aggregate_time": 3600})
                        release.set()
                        worker.join(1)
                        self.assertFalse(worker.is_alive())
                        self.assertEqual(plugin.messages, [])
                        self.assertEqual(plugin._pending_messages, {})
                        if enabled:
                            plugin.handle_webhook(event)
                            if action == "library.new":
                                self.assertEqual(len(plugin._pending_messages), 1)
                            else:
                                self.assertEqual(len(plugin.messages), 1)
                    finally:
                        release.set()
                        worker.join(3)

    def test_inflight_event_cannot_send_after_stop_timeout(self):
        plugin = self.make_plugin(flush_on_stop=True)
        entered, release = threading.Event(), threading.Event()

        def slow_enrich(info, context):
            entered.set()
            release.wait(3)

        plugin._enrich_context = slow_enrich
        worker = threading.Thread(target=plugin.handle_webhook, args=(webhook(),))
        worker.start()
        try:
            self.assertTrue(entered.wait(1))
            self.assertFalse(plugin.stop_service())
            release.set()
            worker.join(1)
            self.assertFalse(worker.is_alive())
            self.assertEqual(plugin.messages, [])
            self.assertTrue(plugin.stop_service())
        finally:
            release.set()
            worker.join(3)

    def test_old_event_cannot_poison_new_dedupe_cache(self):
        plugin = self.make_plugin()
        entered, release = threading.Event(), threading.Event()

        def slow_service(info):
            entered.set()
            release.wait(3)
            return True

        plugin._service_allowed = slow_service
        event = webhook()
        worker = threading.Thread(target=plugin.handle_webhook, args=(event,))
        worker.start()
        try:
            self.assertTrue(entered.wait(1))
            plugin.init_plugin({"enabled": True})
            release.set()
            worker.join(1)
            self.assertFalse(worker.is_alive())
            self.assertEqual(plugin._dedupe_cache, {})
            plugin.handle_webhook(event)
            self.assertEqual(len(plugin.messages), 1)
        finally:
            release.set()
            worker.join(3)

    def test_old_timer_cannot_drain_new_generation(self):
        plugin = self.make_plugin()
        old_generation = plugin._generation
        plugin.init_plugin({"enabled": True, "aggregate_time": 3600})
        plugin.handle_webhook(webhook("library.new"))
        key = next(iter(plugin._pending_messages))
        plugin._flush_aggregate(key, expected_generation=old_generation)
        self.assertIn(key, plugin._pending_messages)
        self.assertEqual(plugin.messages, [])
        plugin._flush_aggregate(key, expected_generation=plugin._generation)
        self.assertEqual(len(plugin.messages), 1)

    def test_replaced_timer_cannot_flush_current_window_early(self):
        plugin = self.make_plugin()
        plugin.handle_webhook(webhook("library.new"))
        key = next(iter(plugin._pending_messages))
        old_timer = plugin._aggregate_timers[key]
        plugin.handle_webhook(webhook("library.new", item_id="episode-2", episode_id=2))
        new_timer = plugin._aggregate_timers[key]
        self.assertIsNot(old_timer, new_timer)
        plugin._flush_aggregate(key, expected_generation=plugin._generation, expected_timer=old_timer)
        self.assertEqual(plugin.messages, [])
        self.assertEqual(len(plugin._pending_messages[key]), 2)
        with patch.object(self.core.threading, "current_thread", return_value=new_timer):
            plugin._aggregate_timer_callback(key, plugin._generation)
        self.assertEqual(len(plugin.messages), 1)
        self.assertIn("已入库 2 个文件", plugin.messages[0]["title"])

    def test_reload_during_render_cancels_old_send(self):
        plugin = self.make_plugin()
        original_render = plugin._renderer.render

        def render_and_reload(action, context):
            result = original_render(action, context)
            plugin.init_plugin({"enabled": False})
            return result

        plugin._renderer.render = render_and_reload
        plugin.handle_webhook(webhook())
        self.assertEqual(plugin.messages, [])

    def test_missing_event_images_use_default_for_every_action(self):
        plugin = self.make_plugin()
        for action in self.core.ACTION_LABELS:
            for image in (None, "", "  "):
                with self.subTest(action=action, image=image):
                    plugin._send_context(action, {"_image": image})
                    self.assertEqual(plugin.messages[-1]["image"], self.core.DEFAULT_NOTIFICATION_IMAGE)

    def test_event_and_enriched_images_are_preserved(self):
        plugin = self.make_plugin()
        original = "https://media.example/episode.jpg"
        plugin.handle_webhook(webhook(image_url=original))
        self.assertEqual(plugin.messages[-1]["image"], original)

        def enrich(info, context):
            context["_image"] = "https://media.example/tmdb.jpg"

        plugin._enrich_context = enrich
        plugin.handle_webhook(webhook(item_id="episode-2"))
        self.assertEqual(plugin.messages[-1]["image"], "https://media.example/tmdb.jpg")

    def test_login_and_test_samples_use_default_image(self):
        plugin = self.make_plugin()
        for action in ("auth_success", "auth_failed", "test"):
            plugin._send_template_test(action)
            self.assertEqual(plugin.messages[-1]["image"], self.core.DEFAULT_NOTIFICATION_IMAGE)
            self.assertIsNone(plugin.messages[-1]["link"])


class V2Regressions(RegressionCases, unittest.TestCase):
    core = load_core("plugins.v2")


class V3Regressions(RegressionCases, unittest.TestCase):
    core = load_core("plugins.v3")


class DefaultImageResourceTests(unittest.TestCase):
    def test_default_image_is_the_supplied_original_and_url_matches_resource(self):
        relative = "icons/mediaservernotifyplus-default.jpg"
        image = ROOT / relative
        self.assertEqual(
            hashlib.sha256(image.read_bytes()).hexdigest(),
            "467ee7675bc3c4383f86e516efc0677fcc616dd9c629ceed80bda569312d6a5b",
        )
        for generation in ("plugins.v2", "plugins.v3"):
            self.assertEqual(
                load_core(generation).DEFAULT_NOTIFICATION_IMAGE,
                f"https://raw.githubusercontent.com/changzhanghs/MoviePilot-Plugins/main/{relative}",
            )


if __name__ == "__main__":
    unittest.main()
