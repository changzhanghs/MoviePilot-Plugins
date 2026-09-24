import ast
import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }


class AdaptationTests(unittest.TestCase):
    def test_versions_and_manifests_match(self):
        v2_package = json.loads((ROOT / "package.v2.json").read_text(encoding="utf-8"))
        v3_package = json.loads((ROOT / "package.v3.json").read_text(encoding="utf-8"))
        self.assertEqual(v2_package["MediaServerNotifyPlus"]["version"], "2.0.10")
        self.assertFalse(v2_package["MediaServerNotifyPlus"]["v3"])
        self.assertEqual(v3_package["MediaServerNotifyPlus"]["version"], "3.0.10")
        self.assertEqual(v3_package["MediaServerNotifyPlus"]["system_version"], ">=3.0.0")
        for package in (v2_package, v3_package):
            metadata = package["MediaServerNotifyPlus"]
            self.assertEqual(metadata["description"], "极简配置可自定义的媒体库通知消息")
            self.assertEqual(metadata["author"], "cz")

    def test_v2_uses_v2_host_contracts(self):
        source = ROOT / "plugins.v2" / "mediaservernotifyplus" / "__init__.py"
        modules = imports(source)
        self.assertIn("app.core.event", modules)
        self.assertIn("app.helper.mediaserver", modules)
        self.assertNotIn("app.modules.themoviedb", modules)
        self.assertNotIn("app.sdk.media", modules)

    def test_v3_uses_public_sdk_and_unified_identity(self):
        source = ROOT / "plugins.v3" / "mediaservernotifyplus" / "__init__.py"
        modules = imports(source)
        self.assertIn("app.sdk.events", modules)
        self.assertIn("app.sdk.media", modules)
        self.assertIn("app.sdk.plugin", modules)
        self.assertNotIn("app.sdk.classification", modules)
        self.assertFalse(any(module.startswith("app.db.") for module in modules))
        text = source.read_text(encoding="utf-8")
        self.assertIn("resolve_media_identity", text)
        self.assertIn("media_source", text)
        self.assertIn("media_id", text)
        self.assertIn("MessageType", text)
        self.assertNotIn("NotificationType", text)

    def test_shared_core_is_identical(self):
        v2 = (ROOT / "plugins.v2" / "mediaservernotifyplus" / "core.py").read_bytes()
        v3 = (ROOT / "plugins.v3" / "mediaservernotifyplus" / "core.py").read_bytes()
        self.assertEqual(v2, v3)

    def test_both_versions_ship_vue_config_runtime(self):
        for generation in ("plugins.v2", "plugins.v3"):
            plugin = ROOT / generation / "mediaservernotifyplus"
            self.assertTrue((plugin / "src/components/Config.vue").is_file())
            self.assertTrue((plugin / "dist/assets/remoteEntry.js").is_file())
            source = (plugin / "src/components/Config.vue").read_text(encoding="utf-8")
            self.assertIn("可通知内容", source)
            self.assertIn("媒体服务器", source)
            self.assertIn("repeat(4", source)
            app_source = (plugin / "src/App.vue").read_text(encoding="utf-8")
            self.assertEqual(app_source.count("[...mediaFields]"), 7)
            self.assertNotIn("查询媒体元数据", source)
            self.assertNotIn("查询 IP 归属地", source)
            self.assertIn("消息渠道遵循 MoviePilot 全局设置", source)
            self.assertIn("通知类型固定为“媒体服务器”", source)
            self.assertIn("http://localhost:3000/api/v1/webhook?token=API_TOKEN&amp;source=媒体服务器名:3001", source)
            self.assertNotIn("localhost:3001", source)
            self.assertIn('<div class="info-panel" role="note">', source)
            self.assertIn('class="info-panel webhook-guide"', source)
            self.assertIn('需在所选媒体服务器中设置 Webhooks，并勾选对应的通知项。', source)
            self.assertNotIn('msnp-note-card', source)
            self.assertIn('v-if="row.key === \'server\'"', source)
            self.assertIn('v-model="draft.mediaservers"', source)
            self.assertIn('label="选择媒体服务器"', source)
            self.assertIn("<h1>媒体库通知</h1>", source)
            page = (plugin / "src/components/Page.vue").read_text(encoding="utf-8")
            self.assertIn("emit('switch')", page)
            self.assertIn("onMounted(() => emit('switch'))", page)
            self.assertNotIn("plugin/form/", page)
            self.assertNotIn("detail-grid", page)
            self.assertNotIn("@click=\"$emit('action')\"", page)
            shared = (plugin / "src/notificationModel.js").read_text(encoding="utf-8")
            self.assertIn("normalizeNotificationModel", source)
            self.assertIn("['client', 'year', 'channel', 'ip_location', 'play_link']", shared)

    def test_notification_type_is_fixed_to_media_server(self):
        v2 = (ROOT / "plugins.v2/mediaservernotifyplus/__init__.py").read_text(encoding="utf-8")
        v3 = (ROOT / "plugins.v3/mediaservernotifyplus/__init__.py").read_text(encoding="utf-8")
        self.assertIn("NotificationType.MediaServer", v2)
        self.assertIn("MessageType.MediaServer", v3)


if __name__ == "__main__":
    unittest.main()
