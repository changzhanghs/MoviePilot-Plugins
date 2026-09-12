from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_V2 = ROOT / "plugins.v2" / "ptdatastatistics"
PLUGIN_V3 = ROOT / "plugins.v3" / "ptdatastatistics"


class DummyPluginBase:
    def get_data_path(self) -> Path:
        return self._test_data_path

    def update_config(self, config):
        self._saved_config = config
        return True

    def save_data(self, key, value):
        self._saved_data[key] = value

    def get_data(self, key=None):
        return self._saved_data.get(key) if key else dict(self._saved_data)

    def post_message(self, **_kwargs):
        return None


class DummySiteOper:
    def list(self):
        return []


class DummyScheduler:
    def update_plugin_job(self, _plugin_id):
        return None


class DummyLogger:
    def __getattr__(self, _name):
        return lambda *_args, **_kwargs: None


class DummyEventManager:
    @staticmethod
    def register(_event_type):
        return lambda function: function


class DummyEvent:
    event_data: ClassVar[dict] = {}


def module(name: str, **attributes):
    value = types.ModuleType(name)
    for key, item in attributes.items():
        setattr(value, key, item)
    sys.modules[name] = value
    return value


module("app")
module("app.core")
module("app.core.config", settings=SimpleNamespace(TZ="Asia/Shanghai"))
module("app.core.event", Event=DummyEvent, eventmanager=DummyEventManager())
module("app.db")
module("app.db.site_oper", SiteOper=DummySiteOper)
module("app.log", logger=DummyLogger())
module("app.plugins", _PluginBase=DummyPluginBase)
module("app.scheduler", Scheduler=DummyScheduler)
module("app.schemas", NotificationType=SimpleNamespace(SiteMessage="site"))
module("app.schemas.types", EventType=SimpleNamespace(SiteRefreshed="site-refreshed"))

spec = importlib.util.spec_from_file_location(
    "ptdatastatistics_v2",
    PLUGIN_V2 / "__init__.py",
    submodule_search_locations=[str(PLUGIN_V2)],
)
assert spec and spec.loader
package = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = package
spec.loader.exec_module(package)

PTDataStatisticsV2 = package.PTDataStatistics


class V2ContractTests(unittest.TestCase):
    def create_plugin(self, data_path: Path, config: dict | None = None):
        plugin = PTDataStatisticsV2.__new__(PTDataStatisticsV2)
        plugin._test_data_path = data_path
        plugin._saved_data = {}
        plugin.init_plugin(config or {"enabled": True})
        return plugin

    def test_v2_uses_its_own_index_and_excludes_v3_fallback(self):
        meta = json.loads((ROOT / "package.v2.json").read_text(encoding="utf-8"))[
            "PTDataStatistics"
        ]
        source = (PLUGIN_V2 / "__init__.py").read_text(encoding="utf-8")
        frontend_meta = json.loads(
            (PLUGIN_V2 / "package.json").read_text(encoding="utf-8")
        )

        self.assertEqual(meta["version"], "1.2.4")
        self.assertEqual(meta["system_version"], ">=2.12.0,<3.0.0")
        self.assertIs(meta["v3"], False)
        self.assertEqual(meta["history"], {"v1.2.4": "兼容v2及v3"})
        self.assertIn('plugin_version = "1.2.4"', source)
        self.assertEqual(frontend_meta["version"], "1.2.4")
        for path in PLUGIN_V2.glob("*.py"):
            self.assertNotIn("app.sdk", path.read_text(encoding="utf-8"), path.name)

    def test_v2_exposes_the_same_ui_and_api_surface(self):
        with tempfile.TemporaryDirectory() as directory:
            plugin = self.create_plugin(Path(directory))
            self.assertEqual(plugin.get_render_mode(), ("vue", "dist/assets"))
            self.assertEqual(plugin.get_sidebar_nav()[0]["nav_key"], "main")
            paths = {(item["path"], tuple(item["methods"])) for item in plugin.get_api()}
            self.assertIn(("/overview", ("GET",)), paths)
            self.assertIn(("/settings", ("POST",)), paths)
            self.assertIn(("/cookiecloud/update", ("POST",)), paths)
            plugin.stop_service()

    def test_v2_sqlite_history_survives_plugin_reinitialization(self):
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory)
            plugin = self.create_plugin(data_path)
            plugin._repository().upsert(
                [
                    {
                        "site_id": 7,
                        "domain": "example.test",
                        "site_name": "示例",
                        "updated_day": "2026-09-12",
                        "upload": 100,
                        "download": 50,
                    }
                ]
            )
            plugin.init_plugin({"enabled": True})

            rows = plugin._repository().latest(active_only=False)

            self.assertEqual(rows[0]["domain"], "example.test")
            self.assertEqual(rows[0]["upload"], 100)
            self.assertTrue((data_path / "ptdatastatistics.db").is_file())
            plugin.stop_service()

    def test_shared_business_and_frontend_files_do_not_drift(self):
        shared_files = [
            "api_models.py",
            "core.py",
            "ptd_cookiecloud.py",
            "repository.py",
            "vite.config.js",
        ]
        shared_files.extend(
            path.relative_to(PLUGIN_V3).as_posix()
            for root in (PLUGIN_V3 / "src", PLUGIN_V3 / "dist" / "assets")
            for path in root.rglob("*")
            if path.is_file()
        )
        for relative in shared_files:
            with self.subTest(relative=relative):
                self.assertEqual(
                    (PLUGIN_V2 / relative).read_bytes(),
                    (PLUGIN_V3 / relative).read_bytes(),
                )


if __name__ == "__main__":
    unittest.main()
