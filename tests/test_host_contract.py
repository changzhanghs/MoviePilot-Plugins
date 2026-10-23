from __future__ import annotations

import importlib
import json
import sys
import tempfile
import types
import unittest
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import ClassVar
from types import SimpleNamespace
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from fastapi import HTTPException, Request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins.v2"))


class DummyPluginBase:
    def get_data_path(self):
        if not hasattr(self, "_test_data_path"):
            self._test_data_path = Path(tempfile.mkdtemp(prefix="ptstats-contract-"))
        return self._test_data_path

    def save_data(self, key, value):
        if not hasattr(self, "_saved_data"):
            self._saved_data = {}
        self._saved_data[key] = value

    def get_data(self, key=None):
        values = getattr(self, "_saved_data", {})
        return values.get(key) if key else dict(values)

    def update_config(self, _config):
        return True

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
module("app.core.config", settings=types.SimpleNamespace(TZ="Asia/Shanghai"))
module("app.core.event", Event=DummyEvent, eventmanager=DummyEventManager())
module("app.db")
module("app.db.site_oper", SiteOper=DummySiteOper)
module("app.log", logger=DummyLogger())
module("app.plugins", _PluginBase=DummyPluginBase)
module("app.scheduler", Scheduler=DummyScheduler)
module("app.schemas", NotificationType=types.SimpleNamespace(SiteMessage="site"))
module("app.schemas.types", EventType=types.SimpleNamespace(SiteRefreshed="site-refreshed"))

PTDataStatistics = importlib.import_module("ptdatastatistics").PTDataStatistics
plugin_module = importlib.import_module("ptdatastatistics")
SettingsData = importlib.import_module("ptdatastatistics.api_models").SettingsData
SiteSnapshotData = importlib.import_module("ptdatastatistics.api_models").SiteSnapshotData
CookieCloudUpdateData = importlib.import_module("ptdatastatistics.api_models").CookieCloudUpdateData
models = importlib.import_module("ptdatastatistics.models")
PluginBase = models.PluginBase
PTSiteHourlySnapshot = models.PTSiteHourlySnapshot
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
    def test_diagnostic_export_contains_one_match_per_site_and_no_history_or_metrics(self):
        plugin = PTDataStatistics.__new__(PTDataStatistics)
        plugin._apply_settings(SettingsData(
            enabled=True, ptd_cookiecloud_enabled=True,
            ptd_cookiecloud_uuid="private-uuid", ptd_cookiecloud_password="private-password",
            ptd_cookiecloud_headers="X-Token: private-header",
            custom_retirement_rules=[{
                "site": "测试规则", "domains": ["private.test"],
                "retirement_level": "Keeper", "levels": [
                    {"name": "User", "aliases": ["普通用户"]},
                    {"name": "Keeper", "min_upload": 500, "description": "无关说明"},
                ],
            }],
        ))
        site = SimpleNamespace(id=7, name="测试站点", domain="private.test", is_active=True)
        rows = [SimpleNamespace(
            domain="private.test", username="private-user", userid="999888",
            user_level="", upload=500, bonus=100, updated_day=day, updated_time="10:00:00",
        ) for day in ("2025-01-01", "2026-10-22", "2026-10-23")]
        plugin.save_data("ptd_latest_metrics_v1", {"metrics": [{
            "domain": "private.test", "user_level": "陌生等级", "seeding_points": 25,
        }]})
        plugin.save_data = Mock(side_effect=AssertionError("export must not write"))
        plugin.sync_from_mp = Mock(side_effect=AssertionError("export must not refresh"))
        plugin.sync_from_ptd = Mock(side_effect=AssertionError("export must not import"))
        with patch.object(plugin_module, "SiteOper") as oper:
            oper.return_value.list.return_value = [site]
            oper.return_value.get_userdata.return_value = rows
            data = plugin.api_export_diagnostics()
        self.assertEqual(set(data), {"manifest", "sites"})
        self.assertEqual(len(data["sites"]), 1)
        failure = data["sites"][0]
        self.assertEqual(failure["effective_level"], "陌生等级")
        self.assertEqual(failure["level_source"], "ptd")
        self.assertEqual(failure["mp_updated_at"], "2026-10-23 10:00:00")
        self.assertEqual(failure["rule_match"]["source"], "custom")
        self.assertEqual(failure["rule_match"]["matched_by"], "domain")
        self.assertEqual(failure["rule_match"]["levels"][0], {"name": "User", "aliases": ["普通用户"]})
        serialized = json.dumps(data, ensure_ascii=False)
        for excluded in (
            "2025-01-01", "2026-10-22", "upload", "bonus", "seeding_points", "min_upload",
            "raw_daily_records", "settings", "description", "无关说明", "private.test",
            "private-uuid", "private-password", "private-header", "private-user", "999888",
        ):
            self.assertNotIn(excluded, serialized)
        plugin.save_data.assert_not_called()
        plugin.sync_from_mp.assert_not_called()
        plugin.sync_from_ptd.assert_not_called()
        route = next(item for item in plugin.get_api() if item["path"] == "/diagnostics/export")
        self.assertEqual(route["auth"], "bear")
        self.assertFalse(route.get("allow_anonymous", False))

    def test_diagnostic_export_omits_inactive_and_archived_sites_and_sanitizes_errors(self):
        plugin = PTDataStatistics.__new__(PTDataStatistics)
        plugin._apply_settings(SettingsData())
        with patch.object(plugin_module, "SiteOper") as oper:
            oper.return_value.list.return_value = []
            oper.return_value.get_userdata.return_value = []
            self.assertEqual(plugin.api_export_diagnostics()["sites"], [])
        sites = [SimpleNamespace(id=i, name=f"Unlisted{i}", domain=f"site{i}.invalid", is_active=i != 2)
                 for i in (1, 2, 3)]
        rows = [SimpleNamespace(domain=domain, user_level="User", updated_day="2026-10-23")
                for domain in ("site1.invalid", "site2.invalid", "archived.invalid")]
        rows.append(SimpleNamespace(
            domain="site3.invalid", username="private-user", userid="999888", updated_day="2026-10-23",
            err_msg="用户private-user登录失败 999888 https://site3.invalid/?token=secret Authorization: Bearer unseen-auth",
        ))
        with patch.object(plugin_module, "SiteOper") as oper:
            oper.return_value.list.return_value = sites
            oper.return_value.get_userdata.return_value = rows
            data = plugin.api_export_diagnostics()
        self.assertEqual(data["manifest"]["checked_sites"], 2)
        self.assertEqual([item["site_id"] for item in data["sites"]], [1, 3])
        self.assertEqual(data["sites"][0]["reason"], "未匹配到站点规则")
        self.assertIn("没有成功", data["sites"][1]["reason"])
        serialized = json.dumps(data, ensure_ascii=False)
        for excluded in ("site3.invalid", "private-user", "999888", "secret", "unseen-auth", "archived.invalid"):
            self.assertNotIn(excluded, serialized)

    def test_matching_diagnostic_reasons_follow_retirement_status_including_vip_and_overrides(self):
        diagnostics = importlib.import_module("ptdatastatistics.diagnostics")
        core = importlib.import_module("ptdatastatistics.core")
        base_rule = {"levels": [{"name": "User"}, {"name": "Keeper"}], "retirement_level": "Keeper"}
        cases = [
            ("normal", "User", "", base_rule, [], False),
            ("unknown", "Other", "", base_rule, [], True),
            ("empty_level", "", "", base_rule, [], True),
            ("unmatched_site", "User", "", None, [], True),
            ("empty_rule", "User", "", {}, [], True),
            ("invalid_target", "User", "", {**base_rule, "retirement_level": "Other"}, [], True),
            ("vip", "VIP", "", {**base_rule, "vip_levels": [{"name": "VIP"}]}, [], False),
            ("manual_without_rule", "Other", "", None, ["7"], False),
            ("invalid_target_with_manual", "User", "", {**base_rule, "retirement_level": "Other"}, ["7"], True),
            ("ptd_fallback", "", "User", base_rule, [], False),
            ("mp_precedes_ptd", "Other", "User", base_rule, [], True),
        ]
        for label, mp_level, ptd_level, rule, manual, failed in cases:
            with self.subTest(label=label):
                site = {"id": 7, "name": "测试站点", "domain": "private.test", "is_active": True}
                mp = {"site_id": 7, "site_name": "测试站点", "domain": "private.test", "user_level": mp_level}
                rules = {"测试站点": rule} if rule is not None else {}
                data = diagnostics.build_diagnostic_export(
                    plugin_version="test", generated_at="2026-10-23", configured_sites=[site],
                    latest_successful=[mp], latest_records=[mp], ptd_metrics={"private.test": {"user_level": ptd_level}},
                    settings={"wealthy_retirement_sites": manual}, rules=rules,
                )
                expected = core.build_retirement_progress([{**mp, "user_level": mp_level or ptd_level}], rules, manual)
                self.assertEqual(len(data["sites"]), 1)
                self.assertEqual(data["sites"][0]["status"] == "unmatched", failed)
                self.assertEqual(data["manifest"]["failed_sites"], int(expected["sites"][0]["status"] == "rule_missing"))

    def test_diagnostic_export_keeps_all_eleven_sites_even_when_no_match_failed(self):
        diagnostics = importlib.import_module("ptdatastatistics.diagnostics")
        sites = [{"id": index, "name": f"示例站点{index}", "domain": f"site{index}.invalid", "is_active": True}
                 for index in range(1, 12)]
        snapshots = [{"site_id": site["id"], "site_name": site["name"], "domain": site["domain"], "user_level": "PU"}
                     for site in sites]
        rules = {site["name"]: {
            "levels": [{"name": "User"}, {"name": "Power User", "aliases": ["PU"]}, {"name": "Keeper"}],
            "retirement_level": "Keeper",
        } for site in sites}
        data = diagnostics.build_diagnostic_export(
            plugin_version="test", generated_at="2026-10-23", configured_sites=sites,
            latest_successful=snapshots, latest_records=snapshots, ptd_metrics={}, settings={}, rules=rules,
        )
        self.assertEqual(data["manifest"]["checked_sites"], 11)
        self.assertEqual(data["manifest"]["failed_sites"], 0)
        self.assertEqual(len(data["sites"]), 11)
        self.assertEqual({item["site_id"] for item in data["sites"]}, set(range(1, 12)))
        for item in data["sites"]:
            self.assertEqual(item["status"], "matched")
            self.assertEqual(item["mp_level"], "PU")
            self.assertEqual(item["rule_match"]["matched_level"], "Power User")
            self.assertEqual(item["rule_match"]["name"], item["site_name"])

    def test_diagnostic_export_supports_all_or_selected_active_sites_without_fallback(self):
        plugin = PTDataStatistics.__new__(PTDataStatistics)
        plugin._apply_settings(SettingsData(custom_retirement_rules=[{
            "site": "无关的自定义站点", "retirement_level": "Keeper",
            "levels": [{"name": "User"}, {"name": "Keeper"}],
        }]))
        sites = [SimpleNamespace(id=index, name=f"Unlisted{index}", domain=f"site{index}.invalid", is_active=index != 3)
                 for index in (1, 2, 3)]
        rows = [SimpleNamespace(domain=site.domain, user_level="User", updated_day="2026-10-23") for site in sites]
        with patch.object(plugin_module, "SiteOper") as oper:
            oper.return_value.list.return_value = sites
            oper.return_value.get_userdata.return_value = rows
            all_sites = plugin.api_export_diagnostics()
            self.assertEqual({item["site_id"] for item in all_sites["sites"]}, {1, 2})
            self.assertIn("custom_rule_names", all_sites)
            for query, expected in (("1", {1}), ("2,1", {1, 2}), ("1,1", {1})):
                data = plugin.api_export_diagnostics(site_ids=query)
                self.assertEqual({item["site_id"] for item in data["sites"]}, expected)
                self.assertEqual(data["manifest"]["checked_sites"], len(expected))
                self.assertNotIn("custom_rule_names", data)
                if expected == {1}:
                    self.assertNotIn("Unlisted2", json.dumps(data))
            for invalid in ("", "0", "abc", "3", "999", "1,999"):
                with self.subTest(invalid=invalid):
                    with self.assertRaises(HTTPException) as error:
                        plugin.api_export_diagnostics(site_ids=invalid)
                    self.assertEqual(error.exception.status_code, 422)

    def test_site_projection_exposes_priority_without_credentials(self):
        site = SimpleNamespace(
            id=7,
            name="示例站点",
            domain="Example.Test",
            is_active=True,
            pri=3,
            cookie="secret",
        )

        value = PTDataStatistics._site_dict(site)

        self.assertEqual(value["site_priority"], 3)
        self.assertEqual(value["domain"], "example.test")
        self.assertNotIn("cookie", value)

    def test_shared_v2_v3_render_and_api_contracts(self):
        plugin = PTDataStatistics.__new__(PTDataStatistics)
        plugin.init_plugin({"enabled": True})
        self.assertEqual(plugin.get_render_mode(), ("vue", "dist/assets"))
        self.assertEqual(plugin.get_sidebar_nav()[0]["nav_key"], "main")
        self.assertEqual(plugin.get_sidebar_nav()[0]["section"], "discovery")
        paths = {(item["path"], tuple(item["methods"])) for item in plugin.get_api()}
        self.assertIn(("/overview", ("GET",)), paths)
        self.assertIn(("/distribution", ("GET",)), paths)
        self.assertIn(("/settings", ("POST",)), paths)
        self.assertIn(("/rules/template", ("GET",)), paths)
        self.assertIn(("/cookiecloud", ("GET",)), paths)
        self.assertIn(("/cookiecloud/update", ("POST",)), paths)
        receiver_routes = [item for item in plugin.get_api() if item["path"].startswith("/cookiecloud")]
        self.assertTrue(all(item.get("allow_anonymous") is True for item in receiver_routes))
        self.assertNotIn(("/sync", ("POST",)), paths)
        self.assertNotIn(("/export/csv", ("GET",)), paths)
        self.assertNotIn(("/export/xlsx", ("GET",)), paths)

        template = plugin.api_rule_template()
        self.assertEqual(template["rules"][0]["site"], "馒头")
        self.assertEqual(template["rules"][0]["retirement_level"], "Extreme User")
        self.assertEqual(len(template["rules"][0]["levels"]), 9)
        self.assertTrue(template["_comment"])
        self.assertEqual(len(SettingsData(custom_retirement_rules=template["rules"]).custom_retirement_rules), 1)

        plugin._configured_sites = lambda: [{"id": 7, "name": "馒头", "domain": "kp.m-team.cc"}]
        self.assertEqual(plugin.api_settings().rule_sites, ["馒头"])

    def test_site_refresh_event_updates_plugin_snapshot(self):
        plugin = PTDataStatistics.__new__(PTDataStatistics)
        plugin.init_plugin({"enabled": True})
        calls = []
        plugin.sync_from_mp = lambda *, full=False, site_id=None: calls.append((full, site_id))

        plugin.on_site_refreshed(SimpleNamespace(event_data={"site_id": "7"}))

        self.assertEqual(calls, [(False, 7)])

    def test_settings_are_clamped_and_modes_filtered(self):
        value = SettingsData(
            retention_days=999999,
            notification_cron="30 8 * * *",
            notification_modes=["today", "invalid", "all", "today"],
            wealthy_retirement_sites=["KP.M-Team.CC", "kp.m-team.cc", " 7 "],
        )
        self.assertEqual(value.retention_days, 36500)
        self.assertNotIn("sync_interval_minutes", value.model_dump())
        legacy_prefix = "ptd_" + "web" + "dav"
        self.assertFalse(any(key.startswith(legacy_prefix) for key in value.model_dump()))
        self.assertNotIn("ptd_cookiecloud_address", value.model_dump())
        self.assertNotIn("ptd_cookiecloud_verify_ssl", value.model_dump())
        self.assertEqual(value.notification_cron, "30 8 * * *")
        self.assertEqual(value.notification_modes, ["today", "all"])
        self.assertEqual(value.wealthy_retirement_sites, ["kp.m-team.cc", "7"])

    def test_uploaded_level_rules_are_validated_and_override_builtins(self):
        value = SettingsData(custom_retirement_rules=[{
            "site": "红豆饭",
            "aliases": ["HDFans"],
            "domains": ["hdfans.org"],
            "retirement_level": "Keeper",
            "levels": [
                {"name": "User"},
                {
                    "name": "Keeper",
                    "min_join_days": 30,
                    "min_upload": 1024,
                    "min_seeding_size": 2048,
                    "min_torrent_uploads": 3,
                    "min_average_seeding_time_days": 7,
                    "alternatives": [{"min_download": 4096}, {"min_ratio": 2}],
                },
            ],
            "vip_levels": [{"name": "VIP", "aliases": ["Donor"]}],
        }])
        plugin = PTDataStatistics.__new__(PTDataStatistics)
        with patch.object(plugin_module.logger, "info") as log_info:
            plugin.init_plugin(value.model_dump())

        self.assertTrue(any(
            "自定义等级规则已加载：1 个站点（红豆饭）" in str(call.args[0])
            for call in log_info.call_args_list
        ))

        rules = plugin._retirement_rules()

        self.assertEqual(rules["红豆饭"]["retirement_level"], "Keeper")
        self.assertEqual(rules["红豆饭"]["levels"][1]["min_upload"], 1024)
        self.assertEqual(rules["红豆饭"]["levels"][1]["min_seeding_size"], 2048)
        self.assertEqual(rules["红豆饭"]["levels"][1]["alternatives"][1]["min_ratio"], 2)
        self.assertEqual(rules["红豆饭"]["domains"], ["hdfans.org"])
        self.assertEqual(rules["红豆饭"]["vip_levels"][0]["aliases"], ["Donor"])
        self.assertIn("观众", rules)
        progress = importlib.import_module("ptdatastatistics.core").build_retirement_progress(
            [{"site_name": "红豆饭", "user_level": "User", "updated_day": "2026-09-12"}],
            rules,
        )
        self.assertEqual(progress["sites"][0]["retirement_level"], "Keeper")
        self.assertEqual([item["name"] for item in progress["sites"][0]["route"]], ["User", "Keeper"])
        self.assertEqual(progress["sites"][0]["route"][1]["aliases"], [])

        decorated = importlib.import_module("ptdatastatistics.core").build_retirement_progress(
            [{"site_name": "红豆饭 HDFans", "user_level": "User", "updated_day": "2026-09-12"}],
            rules,
        )
        self.assertEqual(decorated["sites"][0]["retirement_level"], "Keeper")

    def test_uploaded_level_rule_requires_retirement_level_in_route(self):
        with self.assertRaisesRegex(ValueError, "保号等级不在等级路线中"):
            SettingsData(custom_retirement_rules=[{
                "site": "示例站",
                "retirement_level": "Extreme User",
                "levels": [{"name": "User"}],
            }])

    def test_uploaded_retirement_aliases_use_each_sites_actual_target(self):
        build_progress = importlib.import_module("ptdatastatistics.core").build_retirement_progress
        for site_name, level_name, alias in (
            ("示例甲", "Keeper", "保号"),
            ("示例乙", "Veteran User", "老兵"),
            ("示例丙", "Nexus Master", "最高保号"),
        ):
            with self.subTest(site=site_name):
                value = SettingsData(custom_retirement_rules=[{
                    "site": site_name, "retirement_level": alias,
                    "levels": [{"name": "User"}, {"name": level_name, "aliases": [alias]}],
                }])
                rule = value.custom_retirement_rules[0].model_dump()
                for current, status, remaining in (("User", "upgrading", 1), (alias, "retired", 0)):
                    result = build_progress(
                        [{"site_name": site_name, "user_level": current}], {site_name: rule},
                    )["sites"][0]
                    self.assertEqual(result["retirement_level"], level_name)
                    self.assertEqual(result["status"], status)
                    self.assertEqual(result["levels_remaining"], remaining)
                    self.assertTrue(result["route"][1]["is_retirement"])

    def test_downloaded_template_roundtrips_localized_retirement_target(self):
        template = PTDataStatistics.api_rule_template()
        comments = "\n".join(template["_comment"])
        self.assertIn("该站实际保号等级", comments)
        self.assertIn("不要照搬", comments)
        rule = template["rules"][0]
        target = next(level for level in rule["levels"] if level["name"] == rule["retirement_level"])
        self.assertTrue(target["aliases"])
        rule["retirement_level"] = target["aliases"][0]
        value = SettingsData(custom_retirement_rules=[rule])
        result = importlib.import_module("ptdatastatistics.core").build_retirement_progress(
            [{"site_name": rule["site"], "user_level": target["aliases"][0]}],
            {rule["site"]: value.custom_retirement_rules[0].model_dump()},
        )["sites"][0]
        self.assertEqual(result["retirement_level"], target["name"])
        self.assertEqual(result["status"], "retired")


    @staticmethod
    def _request(headers: list[tuple[bytes, bytes]] | None = None) -> Request:
        return Request({"type": "http", "method": "GET", "path": "/", "headers": headers or []})

    def test_saved_ptd_metrics_gain_ptd_hourly_fallback_without_new_backup(self):
        plugin = PTDataStatistics.__new__(PTDataStatistics)
        plugin.init_plugin({"enabled": True, "ptd_cookiecloud_enabled": True})
        plugin.get_data = lambda key: {
            "metrics": [{
                "domain": "audiences.me",
                "seeding_points": 70_260,
                "estimated_bonus_hourly": 42.85,
                "seeding_points_hourly": None,
            }]
        } if key == "ptd_latest_metrics_v1" else None

        metric = plugin._ptd_metrics_by_domain()["audiences.me"]

        self.assertEqual(metric["seeding_points_hourly"], 42.85)

    def test_ptd_receiver_replaces_the_single_latest_payload(self):
        plugin = PTDataStatistics.__new__(PTDataStatistics)
        plugin.init_plugin(
            {
                "enabled": True,
                "ptd_cookiecloud_enabled": True,
                "ptd_cookiecloud_uuid": "receiver123",
                "ptd_cookiecloud_password": "secret",
            }
        )
        stored = {}
        plugin.save_data = lambda key, value: stored.__setitem__(key, value)
        plugin.get_data = lambda key: stored.get(key)
        plugin._configured_sites = lambda: [{"id": 1, "name": "观众", "domain": "audiences.me"}]
        backup = SimpleNamespace(
            name="PTD_backup_latest",
            metrics=[{"ptd_site": "audiences", "seeding_points": 12}],
            metadata={},
        )
        matched = [{"domain": "audiences.me", "site_name": "观众", "seeding_points": 12}]

        with (
            patch.object(plugin_module, "parse_backup_response", return_value=backup),
            patch.object(plugin_module, "match_metrics", return_value=matched),
        ):
            first = plugin.api_cookiecloud_update(
                CookieCloudUpdateData(uuid="receiver123", encrypted="first"),
                self._request(),
            )
            second = plugin.api_cookiecloud_update(
                CookieCloudUpdateData(uuid="receiver123", encrypted="second"),
                self._request(),
            )

        self.assertEqual(first.action, "done")
        self.assertEqual(second.action, "done")
        self.assertEqual(stored["ptd_cookiecloud_payload_v1"]["encrypted"], "second")
        self.assertEqual(stored["ptd_latest_metrics_v1"]["metrics"], matched)
        self.assertEqual(plugin.api_cookiecloud_get("receiver123", self._request()).encrypted, "second")

    def test_ptd_receiver_checks_uuid_and_optional_headers(self):
        plugin = PTDataStatistics.__new__(PTDataStatistics)
        plugin.init_plugin(
            {
                "enabled": True,
                "ptd_cookiecloud_enabled": True,
                "ptd_cookiecloud_uuid": "receiver123",
                "ptd_cookiecloud_password": "secret",
                "ptd_cookiecloud_headers": "X-PTD-Token: expected",
            }
        )
        with self.assertRaises(HTTPException) as missing_header:
            plugin.api_cookiecloud_ping(self._request())
        self.assertEqual(missing_header.exception.status_code, 403)

        response = plugin.api_cookiecloud_ping(
            self._request([(b"x-ptd-token", b"expected")])
        )
        self.assertIn("Hello World!API ROOT =", response.body.decode())

        with self.assertRaises(HTTPException) as wrong_uuid:
            plugin._require_ptd_receiver(
                request=self._request([(b"x-ptd-token", b"expected")]),
                uuid="different123",
            )
        self.assertEqual(wrong_uuid.exception.status_code, 404)

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

    def test_repository_captures_distinct_mp_refreshes_for_hourly_traffic(self):
        repository = SnapshotRepository(DatabaseHandle())
        first = {
            "site_id": 7,
            "domain": "example.test",
            "site_name": "示例",
            "updated_day": "2026-09-08",
            "updated_time": "09:00:00",
            "source_updated_at": "2026-09-08 09:00:00",
            "upload": 100,
            "download": 50,
            "err_msg": "",
        }
        second = {
            **first,
            "updated_time": "10:00:00",
            "source_updated_at": "2026-09-08 10:00:00",
            "upload": 140,
            "download": 60,
        }

        self.assertEqual(repository.capture_hourly([first, second]), 2)
        self.assertEqual(repository.capture_hourly([second]), 0)
        rows = repository.hourly_for_day("2026-09-08", site_id=7)
        self.assertEqual([row["upload"] for row in rows], [100, 140])
        self.assertEqual(rows[1]["source_updated_at"], "2026-09-08 10:00:00")

    def test_hourly_snapshots_follow_history_retention(self):
        repository = SnapshotRepository(DatabaseHandle())
        repository.capture_hourly(
            [{
                "site_id": 7,
                "domain": "example.test",
                "updated_day": day,
                "updated_time": "09:00:00",
                "source_updated_at": f"{day} 09:00:00",
                "upload": 100,
            } for day in ("2026-06-10", "2026-09-08")]
        )

        deleted = repository.cleanup(retention_days=90, server_day="2026-09-08")

        self.assertEqual(deleted, 1)
        self.assertEqual(repository.hourly_for_day("2026-06-10"), [])
        self.assertEqual(len(repository.hourly_for_day("2026-09-08")), 1)

    def test_hourly_api_reads_plugin_refresh_snapshots(self):
        repository = SnapshotRepository(DatabaseHandle())
        repository.capture_hourly(
            [
                {
                    "site_id": 7,
                    "domain": "example.test",
                    "site_name": "示例",
                    "updated_day": "2026-09-08",
                    "updated_time": "09:00:00",
                    "source_updated_at": "2026-09-08 09:00:00",
                    "upload": 100,
                    "download": 50,
                },
                {
                    "site_id": 7,
                    "domain": "example.test",
                    "site_name": "示例",
                    "updated_day": "2026-09-08",
                    "updated_time": "10:00:00",
                    "source_updated_at": "2026-09-08 10:00:00",
                    "upload": 140,
                    "download": 60,
                },
            ]
        )
        plugin = PTDataStatistics.__new__(PTDataStatistics)
        plugin._repository = lambda: repository
        plugin._configured_sites = lambda: [
            {"id": 7, "name": "示例", "domain": "example.test", "is_active": True}
        ]

        result = plugin.api_hourly_traffic(day="2026-09-08", site_id=7)

        self.assertTrue(result.baseline_valid)
        self.assertEqual(result.points[10].upload, 40)
        self.assertEqual(result.points[10].download, 10)

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

    def test_only_twelve_progress_includes_inactive_sites_with_data(self):
        repository = SnapshotRepository(DatabaseHandle())
        repository.upsert(
            [
                {
                    "site_id": 7,
                    "domain": "open.cd",
                    "site_name": "皇后",
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
            {"id": 7, "name": "皇后", "domain": "open.cd", "is_active": False, "site_priority": 6}
        ]
        plugin._now = lambda: datetime(2026, 9, 5, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))

        result = plugin._build_overview()

        self.assertEqual(result.sites, [])
        self.assertEqual(result.retirement.total, 0)
        self.assertEqual(result.retirement.sites, [])
        queen = next(item for item in result.twelve.items if item.key == "queen")
        self.assertEqual(queen.state, "joined")

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
        plugin._ptd_metrics_by_domain = lambda: {
            "active.test": {
                "estimated_bonus_hourly": 2.0,
                "torrent_uploads": 12,
                "user_level": "Power User",
            }
        }
        plugin._now = lambda: datetime(2026, 9, 5, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))

        result = plugin._build_overview()

        self.assertEqual(result.sites[0].estimated_bonus_hourly, 2.0)
        self.assertEqual(result.sites[0].user_level, "Power User")
        self.assertEqual(result.sites[0].torrent_uploads, 12)
        self.assertEqual(result.retirement.sites[0].estimated_bonus_hourly, 2.0)
        self.assertEqual(result.retirement.sites[0].torrent_uploads, 12)

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
