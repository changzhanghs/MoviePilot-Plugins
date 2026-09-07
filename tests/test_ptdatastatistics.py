from __future__ import annotations

import csv
import importlib.util
import io
import json
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins.v3" / "ptdatastatistics"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


package = types.ModuleType("ptdatastatistics")
package.__path__ = [str(PLUGIN)]
sys.modules.setdefault("ptdatastatistics", package)
core = load_module("ptdatastatistics.core", PLUGIN / "core.py")
exporters = load_module("ptdatastatistics.exporters", PLUGIN / "exporters.py")


class DeltaTests(unittest.TestCase):
    def test_requires_exact_previous_server_day(self):
        current = {"updated_day": "2026-09-05", "upload": 500, "download": 200}
        result = core.compute_daily_delta(
            current,
            {"updated_day": "2026-09-03", "upload": 100, "download": 50},
        )
        self.assertFalse(result["baseline_valid"])
        self.assertEqual(result["daily_upload"], 0)

    def test_calculates_strict_daily_deltas(self):
        result = core.compute_daily_delta(
            {"updated_day": "2026-09-05", "upload": 500, "download": 220},
            {"updated_day": "2026-09-04", "upload": 110, "download": 20, "err_msg": ""},
        )
        self.assertEqual(result["daily_upload"], 390)
        self.assertEqual(result["daily_download"], 200)
        self.assertTrue(result["baseline_valid"])

    def test_counter_reset_is_clamped_and_flagged(self):
        result = core.compute_daily_delta(
            {"updated_day": "2026-09-05", "upload": 10, "download": 2},
            {"updated_day": "2026-09-04", "upload": 100, "download": 1, "err_msg": ""},
        )
        self.assertEqual(result["daily_upload"], 0)
        self.assertEqual(result["daily_download"], 1)
        self.assertTrue(result["counter_reset"])

    def test_failed_previous_day_is_not_a_baseline(self):
        result = core.compute_daily_delta(
            {"updated_day": "2026-09-05", "upload": 200, "download": 100},
            {"updated_day": "2026-09-04", "upload": 100, "download": 50, "err_msg": "超时"},
        )
        self.assertFalse(result["baseline_valid"])

    def test_estimates_hourly_bonus_from_successive_snapshots(self):
        result = core.estimate_bonus_hourly(
            {"bonus": 148, "source_updated_at": "2026-09-05 08:00:00"},
            {"bonus": 100, "source_updated_at": "2026-09-04 08:00:00"},
        )
        self.assertEqual(result, 2.0)

    def test_hourly_bonus_does_not_guess_after_points_are_spent(self):
        result = core.estimate_bonus_hourly(
            {"bonus": 80, "source_updated_at": "2026-09-05 08:00:00"},
            {"bonus": 100, "source_updated_at": "2026-09-04 08:00:00"},
        )
        self.assertIsNone(result)

    def test_builds_hourly_traffic_from_real_mp_samples(self):
        result = core.build_hourly_traffic(
            [
                {
                    "domain": "example.test",
                    "updated_day": "2026-09-06",
                    "updated_time": "23:30:00",
                    "upload": 100,
                    "download": 50,
                },
                {
                    "domain": "example.test",
                    "updated_day": "2026-09-07",
                    "updated_time": "00:10:00",
                    "upload": 150,
                    "download": 70,
                },
                {
                    "domain": "example.test",
                    "updated_day": "2026-09-07",
                    "updated_time": "00:50:00",
                    "upload": 180,
                    "download": 75,
                },
                {
                    "domain": "example.test",
                    "updated_day": "2026-09-07",
                    "updated_time": "02:00:00",
                    "upload": 200,
                    "download": 90,
                },
            ],
            "2026-09-07",
        )

        self.assertTrue(result["baseline_valid"])
        self.assertEqual(result["sample_count"], 3)
        self.assertEqual(result["points"][0]["upload"], 80)
        self.assertEqual(result["points"][0]["download"], 25)
        self.assertEqual(result["points"][1]["samples"], 0)
        self.assertEqual(result["points"][2]["upload"], 20)
        self.assertEqual(result["points"][2]["download"], 15)

    def test_hourly_traffic_does_not_invent_first_sample_delta(self):
        result = core.build_hourly_traffic(
            [{
                "domain": "example.test",
                "updated_day": "2026-09-07",
                "updated_time": "08:00:00",
                "upload": 999,
                "download": 500,
            }],
            "2026-09-07",
        )

        self.assertFalse(result["baseline_valid"])
        self.assertEqual(sum(point["upload"] for point in result["points"]), 0)


class TwelveAndExportTests(unittest.TestCase):
    def test_ourbits_is_named_our_castle(self):
        configured = [{"id": 12, "name": "OurBits"}]
        progress = core.build_twelve_progress(
            configured,
            {12: {"err_msg": "", "join_at": "2025-01-02"}},
        )
        target = next(item for item in progress["items"] if item["key"] == "ourbits")
        self.assertEqual(target["name"], "我堡")
        self.assertEqual(target["state"], "joined")

    def test_waiting_and_missing_states_are_distinct(self):
        progress = core.build_twelve_progress(
            [{"id": 1, "name": "U2"}],
            {},
        )
        states = {item["key"]: item["state"] for item in progress["items"]}
        self.assertEqual(states["u2"], "waiting")
        self.assertEqual(states["ttg"], "missing")

    def test_joined_twelve_sites_are_sorted_by_join_date(self):
        progress = core.build_twelve_progress(
            [
                {"id": 1, "name": "TTG"},
                {"id": 2, "name": "U2"},
                {"id": 3, "name": "M-Team"},
            ],
            {
                1: {"err_msg": "", "join_at": "2024-08-01"},
                2: {"err_msg": "", "join_at": "2023-06-02"},
                3: {"err_msg": "", "join_at": ""},
            },
        )
        joined = [item for item in progress["items"] if item["state"] == "joined"]
        self.assertEqual([item["key"] for item in joined], ["u2", "ttg", "mteam"])

    def test_export_field_filter_preserves_selection_order(self):
        self.assertEqual(
            core.selected_export_fields("download,unknown,site_name"),
            ["download", "site_name"],
        )

    def test_csv_has_utf8_bom_and_chinese_headers(self):
        content = exporters.build_csv(
            [{"site_name": "馒头", "upload": 123}],
            ["site_name", "upload"],
        )
        self.assertTrue(content.startswith(b"\xef\xbb\xbf"))
        rows = list(csv.reader(io.StringIO(content.decode("utf-8-sig"))))
        self.assertEqual(rows[0], ["站点", "累计上传(B)"])
        self.assertEqual(rows[1], ["馒头", "123"])

    def test_export_fields_never_include_removed_fields(self):
        labels = dict(core.EXPORT_FIELDS)
        keys = list(labels)
        self.assertNotIn("domain", keys)
        self.assertNotIn("leeching", keys)
        self.assertNotIn("err_msg", keys)
        self.assertEqual(labels["bonus"], "魔力")

    def test_retirement_progress_does_not_guess_missing_rules(self):
        progress = core.build_retirement_progress(
            [{"site_id": 1, "site_name": "示例", "user_level": "User"}],
        )
        self.assertEqual(progress["rule_missing"], 1)
        self.assertEqual(progress["sites"][0]["status"], "rule_missing")

    def test_retirement_progress_marks_target_level(self):
        progress = core.build_retirement_progress(
            [{
                "site_id": 1,
                "site_name": "示例",
                "user_level": "Power User",
                "join_at": "2026-01-01",
                "updated_day": "2026-09-05",
                "upload": 500,
            }],
            {"示例": {
                "retirement_level": "Power User",
                "levels": [
                    {"name": "User"},
                    {"name": "Power User", "min_join_days": 30, "min_upload": 200},
                ],
            }},
        )
        self.assertEqual(progress["retired"], 1)
        self.assertEqual(progress["sites"][0]["status"], "retired")

    def test_audiences_retirement_rules_match_published_level_route(self):
        progress = core.build_retirement_progress(
            [{
                "site_id": 1,
                "site_name": "观众",
                "user_level": "User",
                "join_at": "2026-07-03 18:19:19",
                "updated_day": "2026-09-06",
                "download": 50 * core.GIB,
                "ratio": 1.5,
                "bonus": 50_000,
            }],
        )
        site = progress["sites"][0]
        levels = {level["name"]: level for level in site["route"]}

        self.assertEqual(site["status"], "upgrading")
        self.assertEqual(site["retirement_level"], "Extreme User")
        self.assertEqual(levels["Power User"]["eligible_date"], "2026-08-07")
        self.assertEqual(levels["Power User"]["min_download"], 120 * core.GIB)
        self.assertEqual(levels["Power User"]["min_upload"], 0)
        self.assertEqual(levels["Power User"]["min_ratio"], 2.0)
        self.assertTrue(levels["Power User"]["min_ratio_strict"])
        self.assertEqual(levels["Power User"]["min_seeding_points"], 100_000.0)
        self.assertIsNone(levels["Power User"]["min_bonus"])
        self.assertIn("做种积分数据未提供", levels["Power User"]["missing"])
        self.assertFalse(
            any("门槛" in item for item in levels["Power User"]["missing"])
        )
        self.assertIn("NFO", levels["Power User"]["description"])
        self.assertEqual(levels["Crazy User"]["eligible_date"], "2026-12-18")
        self.assertIn("可以查看排行榜", levels["Crazy User"]["description"])
        self.assertEqual(levels["Insane User"]["min_ratio"], 3.4)
        self.assertEqual(levels["Extreme User"]["min_ratio"], 4.4)
        self.assertEqual(levels["Extreme User"]["eligible_date"], "2028-01-14")
        self.assertTrue(levels["Extreme User"]["is_retirement"])
        self.assertIn("永久保留账号", levels["Extreme User"]["description"])
        self.assertEqual(levels["Rainbow"]["eligible_date"], "2028-12-15")
        self.assertIn("彩虹 ID", levels["Rainbow"]["description"])

    def test_audiences_ratio_threshold_is_strict(self):
        progress = core.build_retirement_progress(
            [{
                "site_id": 1,
                "site_name": "观众",
                "user_level": "User",
                "join_at": "2026-01-01",
                "updated_day": "2026-12-31",
                "download": 120 * core.GIB,
                "ratio": 2.0,
                "seeding_points": 100_000,
            }],
        )
        power = next(
            level
            for level in progress["sites"][0]["route"]
            if level["name"] == "Power User"
        )
        self.assertIn("分享率需大于 2", power["missing"])

    def test_audiences_rule_matches_decorated_site_and_level_names(self):
        progress = core.build_retirement_progress(
            [{
                "site_id": 1,
                "site_name": "观众 Audiences",
                "user_level": "Power User（同年轻气盛）",
                "join_at": "2026-07-03 18:19:19",
                "updated_day": "2026-09-06",
            }],
        )
        site = progress["sites"][0]

        self.assertEqual(site["status"], "upgrading")
        self.assertEqual(site["next_level"], "Elite User")
        self.assertTrue(next(level for level in site["route"] if level["name"] == "Power User")["is_current"])

    def test_known_site_keeps_route_when_mp_level_is_unknown(self):
        progress = core.build_retirement_progress(
            [{
                "site_id": 1,
                "site_name": "观众",
                "user_level": "站点暂未返回等级",
                "join_at": "2026-07-03 18:19:19",
                "updated_day": "2026-09-06",
            }],
        )
        site = progress["sites"][0]

        self.assertEqual(site["status"], "rule_missing")
        self.assertEqual(site["retirement_level"], "Extreme User")
        self.assertEqual(len(site["route"]), 10)


class PackagingTests(unittest.TestCase):
    def test_v3_manifest_matches_source(self):
        manifest = json.loads((ROOT / "package.v3.json").read_text(encoding="utf-8"))
        meta = manifest["PTDataStatistics"]
        source = (PLUGIN / "__init__.py").read_text(encoding="utf-8")
        self.assertEqual(meta["version"], "1.0.0")
        self.assertEqual(meta["history"]["v1.0.0"], "更新了一些东西")
        self.assertEqual(list(meta["history"]), ["v1.0.0"])
        self.assertIn('plugin_version = "1.0.0"', source)
        self.assertEqual(meta["system_version"], ">=3.0.0")
        self.assertNotIn("release", meta)

    def test_plugin_source_does_not_read_downloaders_or_pt_sites(self):
        source = (PLUGIN / "__init__.py").read_text(encoding="utf-8")
        self.assertNotIn("Downloader", source)
        self.assertNotIn("requests.", source)
        self.assertIn("SiteOper", source)

    def test_federation_exposes_all_v3_components(self):
        source = (PLUGIN / "vite.config.js").read_text(encoding="utf-8")
        for name in ("./Page", "./Config", "./Dashboard", "./AppPage"):
            self.assertIn(name, source)

    def test_federation_components_accept_v3_runtime_instance_props(self):
        for filename in ("Page.vue", "Config.vue", "Dashboard.vue", "AppPage.vue"):
            source = (PLUGIN / "src" / "components" / filename).read_text(encoding="utf-8")
            self.assertIn("pluginId", source, filename)
            self.assertIn("sourcePluginId", source, filename)
            self.assertIn("nativeSubscribe", source, filename)
        config = (PLUGIN / "src" / "components" / "Config.vue").read_text(encoding="utf-8")
        self.assertIn("initialConfig", config)
        self.assertIn("'save'", config)

    def test_career_export_does_not_leak_hidden_site_name_in_avatar(self):
        source = (PLUGIN / "src" / "components" / "CareerExportDialog.vue").read_text(
            encoding="utf-8"
        )
        self.assertIn("const avatarLabel = showSiteNames", source)
        self.assertIn(": String(siteIndex + 1)", source)
        self.assertNotIn("完整档案", source)
        self.assertNotIn("公开分享", source)
        self.assertNotIn("applyPreset", source)

    def test_workbench_ui_polish_contract(self):
        source = (PLUGIN / "src" / "components" / "PTStatsWorkbench.vue").read_text(
            encoding="utf-8"
        )
        self.assertIn("item.state === 'joined' && item.site_id", source)
        self.assertIn("item.state === 'joined' ? item.name : '未解锁'", source)
        self.assertNotIn(":hint=\"`服务器日期 ${overview.server_date || '—'}`\"", source)
        self.assertIn('prepend-icon="mdi-magnify"', source)
        self.assertIn("查询数据</VBtn>", source)
        self.assertIn(":label=\"panel.inputLabel\"", source)
        self.assertIn(":prepend-inner-icon=\"panel.icon\"", source)
        self.assertIn(':model-value="distributionFilters[panel.dateKey]"', source)
        self.assertIn('@click="openNativePicker"', source)
        self.assertIn('@update:model-value="value => updateDistributionFilter(panel.dateKey, value)"', source)
        self.assertIn("distributionRequestSequence", source)
        self.assertIn("const historyGroups = computed", source)
        self.assertIn("const selectedHistoryPeriod = computed", source)
        self.assertIn("selectHistoryPeriod(period)", source)
        self.assertIn("const selectedPeriodSites = computed", source)
        self.assertIn("selectHistorySite(item)", source)
        self.assertIn("Chart from 'chart.js/auto'", source)
        self.assertIn("history/hourly", source)
        self.assertNotIn("站点贡献", source)
        self.assertIn('class="history-console"', source)
        self.assertIn('class="history-period-strip"', source)
        self.assertIn('class="history-site-expansion"', source)
        self.assertIn('v-model="historyMetric"', source)
        self.assertIn("自然日 00:00–23:59", source)
        self.assertIn("在上方查看曲线，并在该行下方展开历史数据", source)
        self.assertIn("const selectedHistoryRecords = computed", source)
        self.assertIn('class="history-record-table"', source)
        self.assertIn("<th>日期</th><th>累计上传</th><th>累计下载</th>", source)
        self.assertNotIn("history-line-chart--expanded", source)
        self.assertIn('>数据统计</VTab>', source)
        self.assertIn(">数据刷新</VBtn>", source)
        self.assertNotIn("重新读取 MP 数据", source)
        self.assertNotIn('<header class="hero">', source)
        self.assertLess(source.index('value="retirement"'), source.index('value="history"'))
        self.assertIn('class="site-data-list"', source)
        self.assertNotIn("服务器日期 {{ overview.server_date", source)
        self.assertIn('class="site-stat-grid"', source)
        self.assertIn("<span>魔力</span>", source)
        self.assertIn("<span>预估时魔</span>", source)
        self.assertNotIn("魔力（预估时魔）", source)
        self.assertIn("const siteSortOptions", source)
        for key in ("upload", "download", "bonus", "seeding", "seeding_size"):
            self.assertIn(f"value: '{key}'", source)
        self.assertIn('v-for="site in sortedCurrentSites"', source)
        self.assertIn("bonusValue(item.bonus)", source)
        self.assertNotIn("<th>站点</th><th>数据日期</th>", source)
        self.assertIn("site.join_at?.slice(0, 10)", source)
        self.assertIn('@click="openNativePicker"', source)
        self.assertIn("注册时间已达成", source)
        self.assertIn('class="retirement-explorer"', source)
        self.assertIn('class="retirement-site-list"', source)
        self.assertIn('@click="selectRetirementSite(site)"', source)
        self.assertIn('class="retirement-detail"', source)
        self.assertIn('class="retirement-route-rail"', source)
        self.assertIn('class="retirement-route-rail__track"', source)
        self.assertIn("--route-count", source)
        self.assertIn("overflow-y:auto;overscroll-behavior:contain", source)
        self.assertNotIn("距离保号还差", source)
        self.assertNotIn("MoviePilot 不提供站点等级门槛和保号等级", source)
        self.assertIn('class="requirement-panel"', source)
        self.assertIn('class="retirement-levels"', source)
        self.assertIn("selectedRetirementSite", source)
        self.assertIn("requirementRows(selectedRetirementSite", source)
        self.assertIn('<details v-for="level in selectedRetirementSite.route"', source)
        self.assertIn("retirementProgressPercent(site)", source)
        self.assertNotIn("retirement-preview-grid", source)
        self.assertNotIn("retirement-mini-progress", source)
        self.assertLess(source.index('class="retirement-site-list"'), source.index('class="retirement-detail"'))
        self.assertLess(source.index('class="retirement-detail__metrics"'), source.index('class="retirement-route-rail"'))
        self.assertLess(source.index('class="retirement-route-rail"'), source.index('class="requirement-panel"'))
        self.assertIn('v-if="level.description"', source)
        self.assertIn("<h2>养老进度</h2>", source)
        self.assertNotIn("全部站点养老进度", source)
        self.assertNotIn("同步 MP 数据间隔", source)
        self.assertNotIn("mdi-calendar-arrow-up", source)
        self.assertNotIn("mdi-calendar-arrow-down", source)

        dashboard = (PLUGIN / "src" / "components" / "Dashboard.vue").read_text(
            encoding="utf-8"
        )
        self.assertLess(dashboard.index("统计日期"), dashboard.index("上传增量"))

        export_dialog = (PLUGIN / "src" / "components" / "ExportDialog.vue").read_text(
            encoding="utf-8"
        )
        self.assertEqual(export_dialog.count('@click="openNativePicker"'), 2)

        utils = (PLUGIN / "src" / "utils.js").read_text(encoding="utf-8")
        self.assertIn("event?.preventDefault?.()", utils)


if __name__ == "__main__":
    unittest.main()
