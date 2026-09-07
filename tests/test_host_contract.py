from __future__ import annotations

import importlib
import sys
import types
import unittest
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import ClassVar
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins.v3"))


class PluginModelBase(DeclarativeBase):
    pass


class DummyPluginBase:
    pass


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
module("app.db")
module("app.db.oper")
module("app.db.oper.site", SiteOper=DummySiteOper)
module("app.plugins", _PluginBase=DummyPluginBase)
module("app.scheduler", Scheduler=DummyScheduler)
module("app.schemas", NotificationType=types.SimpleNamespace(SiteMessage="site"))
module("app.schemas.types", EventType=types.SimpleNamespace(SiteRefreshed="site-refreshed"))
module("app.sdk")
module("app.sdk.config", settings=types.SimpleNamespace(TZ="Asia/Shanghai"))
module("app.sdk.events", Event=DummyEvent, eventmanager=DummyEventManager())
module("app.sdk.logging", logger=DummyLogger())
module("app.sdk.database", plugin_declarative_base=lambda: PluginModelBase)

PTDataStatistics = importlib.import_module("ptdatastatistics").PTDataStatistics
SettingsData = importlib.import_module("ptdatastatistics.api_models").SettingsData
SiteSnapshotData = importlib.import_module("ptdatastatistics.api_models").SiteSnapshotData
models = importlib.import_module("ptdatastatistics.models")
PluginBase = models.PluginBase
PTSiteSnapshot = models.PTSiteSnapshot
SnapshotRepository = importlib.import_module("ptdatastatistics.repository").SnapshotRepository


class DatabaseHandle:
    def __init__(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        PluginBase.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine, expire_on_commit=False)

    @contextmanager
    def session(self):
        session = self.factory()
        try:
            yield session
        finally:
            session.close()


class HostContractTests(unittest.TestCase):
    def test_v3_render_and_api_contracts(self):
        plugin = PTDataStatistics.__new__(PTDataStatistics)
        plugin.init_plugin({"enabled": True})
        self.assertEqual(plugin.get_render_mode(), ("vue", "dist/assets"))
        self.assertEqual(plugin.get_database_models(), [PTSiteSnapshot])
        self.assertEqual(plugin.get_sidebar_nav()[0]["nav_key"], "main")
        self.assertEqual(plugin.get_sidebar_nav()[0]["section"], "discovery")
        paths = {(item["path"], tuple(item["methods"])) for item in plugin.get_api()}
        self.assertIn(("/overview", ("GET",)), paths)
        self.assertIn(("/distribution", ("GET",)), paths)
        self.assertIn(("/settings", ("POST",)), paths)
        self.assertNotIn(("/export/xlsx", ("GET",)), paths)

    def test_settings_are_clamped_and_modes_filtered(self):
        value = SettingsData(
            retention_days=999999,
            notification_cron="30 8 * * *",
            notification_modes=["today", "invalid", "all", "today"],
        )
        self.assertEqual(value.retention_days, 36500)
        self.assertNotIn("sync_interval_minutes", value.model_dump())
        self.assertEqual(value.notification_cron, "30 8 * * *")
        self.assertEqual(value.notification_modes, ["today", "all"])

    def test_public_snapshot_contract_never_exposes_domain(self):
        value = SiteSnapshotData.model_validate(
            {"site_id": 1, "site_name": "示例", "domain": "secret.example"}
        ).model_dump()
        self.assertNotIn("domain", value)

    def test_notification_uses_configured_cron_directly(self):
        plugin = PTDataStatistics.__new__(PTDataStatistics)
        plugin.init_plugin(
            {
                "enabled": True,
                "notification_enabled": True,
                "notification_cron": "30 8 * * *",
                "notification_modes": ["today"],
            }
        )
        services = {item["id"]: item for item in plugin.get_service()}
        trigger = services["PTDataStatistics.Notification"]["trigger"]
        self.assertEqual(str(trigger.fields[0]), "*")
        self.assertEqual(str(trigger.fields[5]), "8")
        self.assertEqual(str(trigger.fields[6]), "30")

    def test_service_ids_follow_runtime_instance_name(self):
        """虚拟分身不能与源插件共用同一组 APScheduler 任务 ID。"""

        clone_type = type("PTDataStatisticsClone1", (PTDataStatistics,), {})
        plugin = clone_type.__new__(clone_type)
        plugin.init_plugin({"enabled": True})
        service_ids = {item["id"] for item in plugin.get_service()}
        self.assertEqual(
            service_ids,
            {
                "PTDataStatisticsClone1.Cleanup",
            },
        )

    def test_date_range_uses_mp_server_timezone_clock(self):
        plugin = PTDataStatistics.__new__(PTDataStatistics)
        plugin._now = lambda: datetime(2026, 9, 5, 23, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
        self.assertEqual(plugin._date_range(None, None), ("2026-06-08", "2026-09-05"))

    def test_repository_history_and_archived_rows(self):
        repository = SnapshotRepository(DatabaseHandle())
        repository.upsert(
            [
                {
                    "domain": "example.test",
                    "site_name": "示例",
                    "updated_day": "2026-09-04",
                    "updated_time": "08:00",
                    "upload": 100,
                    "download": 50,
                    "bonus": 1234.5,
                    "is_active": True,
                },
                {
                    "domain": "example.test",
                    "site_name": "示例",
                    "updated_day": "2026-09-05",
                    "updated_time": "08:00",
                    "upload": 170,
                    "download": 80,
                    "bonus": 1357.5,
                    "is_active": True,
                },
            ]
        )
        records = repository.history(start_day="2026-09-05", end_day="2026-09-05")
        self.assertEqual(records[0]["daily_upload"], 70)
        self.assertEqual(records[0]["daily_download"], 30)
        self.assertEqual(records[0]["bonus"], 1357.5)
        repository.mark_active_domains(set())
        self.assertEqual(repository.latest(active_only=True), [])
        self.assertEqual(repository.latest(active_only=False)[0]["site_name"], "示例")

    def test_history_excludes_failed_snapshots(self):
        repository = SnapshotRepository(DatabaseHandle())
        repository.upsert(
            [
                {"domain": "example.test", "site_name": "示例", "updated_day": "2026-09-04", "upload": 100, "err_msg": ""},
                {"domain": "example.test", "site_name": "示例", "updated_day": "2026-09-05", "upload": 0, "err_msg": "刷新失败"},
            ]
        )
        records = repository.history(start_day="2026-09-04", end_day="2026-09-05")
        self.assertEqual([item["updated_day"] for item in records], ["2026-09-04"])

    def test_history_limit_returns_latest_rows_with_their_daily_baseline(self):
        repository = SnapshotRepository(DatabaseHandle())
        repository.upsert(
            [
                {
                    "domain": "example.test",
                    "site_name": "示例",
                    "updated_day": f"2026-09-0{day}",
                    "upload": day * 100,
                    "download": day * 10,
                }
                for day in range(1, 6)
            ]
        )
        records = repository.history(
            start_day="2026-09-01",
            end_day="2026-09-05",
            limit=2,
        )
        self.assertEqual(
            [item["updated_day"] for item in records],
            ["2026-09-05", "2026-09-04"],
        )
        self.assertTrue(all(item["baseline_valid"] for item in records))
        self.assertEqual(records[0]["daily_upload"], 100)

    def test_repository_returns_previous_successful_snapshot_per_site(self):
        repository = SnapshotRepository(DatabaseHandle())
        repository.upsert(
            [
                {"domain": "a.test", "updated_day": "2026-09-03", "bonus": 10},
                {"domain": "a.test", "updated_day": "2026-09-04", "bonus": 20},
                {"domain": "a.test", "updated_day": "2026-09-05", "bonus": 30},
                {"domain": "b.test", "updated_day": "2026-09-05", "bonus": 50},
            ]
        )
        latest = repository.latest(active_only=False)
        previous = repository.previous_successful(latest)
        self.assertEqual(previous["a.test"]["updated_day"], "2026-09-04")
        self.assertNotIn("b.test", previous)

    def test_distribution_aggregates_selected_month_and_day(self):
        repository = SnapshotRepository(DatabaseHandle())
        repository.upsert(
            [
                {"site_id": 7, "domain": "example.test", "site_name": "示例", "updated_day": "2026-09-04", "upload": 100, "download": 50, "is_active": True},
                {"site_id": 7, "domain": "example.test", "site_name": "示例", "updated_day": "2026-09-05", "upload": 170, "download": 80, "is_active": True},
            ]
        )
        plugin = PTDataStatistics.__new__(PTDataStatistics)
        plugin._ensure_history = lambda: None
        plugin._repository = lambda: repository
        plugin._now = lambda: datetime(2026, 9, 5, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
        result = plugin.api_distribution(month="2026-09", day="2026-09-05")
        self.assertEqual(result.monthly[0].upload, 70)
        self.assertEqual(result.daily[0].download, 30)

    def test_retirement_and_twelve_progress_include_inactive_sites_with_data(self):
        repository = SnapshotRepository(DatabaseHandle())
        repository.upsert(
            [
                {
                    "site_id": 7,
                    "domain": "inactive.test",
                    "site_name": "U2",
                    "updated_day": "2026-09-05",
                    "upload": 170,
                    "download": 80,
                    "is_active": False,
                }
            ]
        )
        plugin = PTDataStatistics.__new__(PTDataStatistics)
        plugin._ensure_history = lambda: None
        plugin._repository = lambda: repository
        plugin._configured_sites = lambda: [
            {"id": 7, "name": "U2", "domain": "inactive.test", "is_active": False}
        ]
        plugin._now = lambda: datetime(2026, 9, 5, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))

        result = plugin._build_overview()

        self.assertEqual(result.sites, [])
        self.assertEqual(result.retirement.total, 1)
        u2 = next(item for item in result.twelve.items if item.key == "u2")
        self.assertEqual(u2.state, "joined")

    def test_overview_today_sites_only_contains_positive_valid_deltas(self):
        repository = SnapshotRepository(DatabaseHandle())
        repository.upsert(
            [
                {"site_id": 1, "domain": "active.test", "site_name": "有流量", "updated_day": "2026-09-04", "upload": 100, "download": 50, "is_active": True},
                {"site_id": 1, "domain": "active.test", "site_name": "有流量", "updated_day": "2026-09-05", "upload": 180, "download": 70, "is_active": True},
                {"site_id": 2, "domain": "zero.test", "site_name": "零流量", "updated_day": "2026-09-04", "upload": 100, "download": 50, "is_active": True},
                {"site_id": 2, "domain": "zero.test", "site_name": "零流量", "updated_day": "2026-09-05", "upload": 100, "download": 50, "is_active": True},
                {"site_id": 3, "domain": "no-baseline.test", "site_name": "无基线", "updated_day": "2026-09-05", "upload": 500, "download": 100, "is_active": True},
            ]
        )
        plugin = PTDataStatistics.__new__(PTDataStatistics)
        plugin._ensure_history = lambda: None
        plugin._repository = lambda: repository
        plugin._configured_sites = lambda: [
            {"id": 1, "name": "有流量", "domain": "active.test", "is_active": True},
            {"id": 2, "name": "零流量", "domain": "zero.test", "is_active": True},
            {"id": 3, "name": "无基线", "domain": "no-baseline.test", "is_active": True},
        ]
        plugin._now = lambda: datetime(2026, 9, 5, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))

        result = plugin._build_overview()

        self.assertEqual([item.site_name for item in result.today_sites], ["有流量"])
        self.assertEqual(result.summary.today_upload, 80)
        self.assertEqual(result.summary.today_download, 20)

    def test_overview_estimates_hourly_bonus_from_latest_daily_snapshots(self):
        repository = SnapshotRepository(DatabaseHandle())
        repository.upsert(
            [
                {
                    "site_id": 1,
                    "domain": "active.test",
                    "site_name": "示例",
                    "updated_day": "2026-09-04",
                    "updated_time": "08:00:00",
                    "source_updated_at": "2026-09-04 08:00:00",
                    "bonus": 100,
                    "is_active": True,
                },
                {
                    "site_id": 1,
                    "domain": "active.test",
                    "site_name": "示例",
                    "updated_day": "2026-09-05",
                    "updated_time": "08:00:00",
                    "source_updated_at": "2026-09-05 08:00:00",
                    "bonus": 148,
                    "is_active": True,
                },
            ]
        )
        plugin = PTDataStatistics.__new__(PTDataStatistics)
        plugin._ensure_history = lambda: None
        plugin._repository = lambda: repository
        plugin._configured_sites = lambda: [
            {"id": 1, "name": "示例", "domain": "active.test", "is_active": True}
        ]
        plugin._now = lambda: datetime(2026, 9, 5, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))

        result = plugin._build_overview()

        self.assertEqual(result.sites[0].estimated_bonus_hourly, 2.0)
        self.assertEqual(result.retirement.sites[0].estimated_bonus_hourly, 2.0)

    def test_notification_excludes_empty_sites_and_sends_at_most_once_per_day(self):
        plugin = PTDataStatistics.__new__(PTDataStatistics)
        plugin._enabled = True
        plugin._notification_enabled = True
        plugin._notification_modes = ["all"]
        plugin._now = lambda: datetime(2026, 9, 5, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
        plugin.sync_from_mp = lambda full=False: None
        plugin._build_overview = lambda: types.SimpleNamespace(
            summary=types.SimpleNamespace(total_upload=100, total_download=50),
            today_sites=[],
            sites=[
                types.SimpleNamespace(site_name="有数据", upload=100, download=50),
                types.SimpleNamespace(site_name="无数据", upload=0, download=0),
            ],
        )
        state = {}
        plugin.get_data = lambda key: state.get(key)
        plugin.save_data = lambda key, value: state.__setitem__(key, value)
        messages = []
        plugin.post_message = lambda **kwargs: messages.append(kwargs)

        plugin._notification_tick()
        plugin._notification_tick()

        self.assertEqual(len(messages), 1)
        self.assertIn("有数据", messages[0]["text"])
        self.assertNotIn("无数据", messages[0]["text"])
        self.assertEqual(state["last_notification_day"], "2026-09-05")


if __name__ == "__main__":
    unittest.main()
