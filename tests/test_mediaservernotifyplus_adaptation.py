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
        self.assertEqual(v2_package["MediaServerNotifyPlus"]["version"], "2.0.0")
        self.assertFalse(v2_package["MediaServerNotifyPlus"]["v3"])
        self.assertEqual(v3_package["MediaServerNotifyPlus"]["version"], "3.0.0")
        self.assertEqual(v3_package["MediaServerNotifyPlus"]["system_version"], ">=3.0.0")

    def test_v2_uses_v2_host_contracts(self):
        source = ROOT / "plugins.v2" / "mediaservernotifyplus" / "__init__.py"
        modules = imports(source)
        self.assertIn("app.core.event", modules)
        self.assertIn("app.helper.mediaserver", modules)
        self.assertIn("app.modules.themoviedb", modules)
        self.assertNotIn("app.sdk.media", modules)

    def test_v3_uses_public_sdk_and_unified_identity(self):
        source = ROOT / "plugins.v3" / "mediaservernotifyplus" / "__init__.py"
        modules = imports(source)
        self.assertIn("app.sdk.events", modules)
        self.assertIn("app.sdk.media", modules)
        self.assertIn("app.sdk.plugin", modules)
        self.assertIn("app.sdk.classification", modules)
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


if __name__ == "__main__":
    unittest.main()
