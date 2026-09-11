from __future__ import annotations

import base64
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

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
ptd_cookiecloud = load_module("ptdatastatistics.ptd_cookiecloud", PLUGIN / "ptd_cookiecloud.py")


class PTDCookieCloudTests(unittest.TestCase):
    def test_extracts_only_latest_seeding_metrics_per_site(self):
        values = ptd_cookiecloud._extract_metrics(
            {
                "audiences": {
                    "2026-09-10": {
                        "site": "audiences",
                        "updateAt": 100,
                        "seedingBonus": 1000,
                        "seedingBonusPerHour": 2.5,
                        "uploaded": 999,
                    },
                    "2026-09-11": {
                        "site": "audiences",
                        "updateAt": 200,
                        "seedingBonus": 1200,
                        "bonusPerHour": 3.5,
                        "uploaded": 1999,
                    },
                }
            }
        )

        self.assertEqual(values[0]["seeding_points"], 1200)
        self.assertEqual(values[0]["estimated_bonus_hourly"], 3.5)
        self.assertEqual(values[0]["seeding_points_hourly"], 2.5)
        self.assertNotIn("uploaded", values[0])

    def test_uses_bonus_rate_instead_of_seeding_points_rate_for_hourly_magic(self):
        values = ptd_cookiecloud._extract_metrics(
            {
                "hhanclub": {
                    "site": "hhanclub",
                    "siteName": "憨憨",
                    "seedingBonus": 439_222,
                    "bonusPerHour": 41.35,
                    "seedingBonusPerHour": 12.45,
                }
            }
        )

        self.assertEqual(values[0]["seeding_points"], 439_222)
        self.assertEqual(values[0]["estimated_bonus_hourly"], 41.35)
        self.assertEqual(values[0]["seeding_points_hourly"], 12.45)

    def test_ptd_bonus_rate_is_used_for_seeding_points_eta_when_dedicated_rate_is_missing(self):
        values = ptd_cookiecloud._extract_metrics(
            {
                "audiences": {
                    "site": "audiences",
                    "seedingBonus": 70_260,
                    "bonusPerHour": 42.85,
                }
            }
        )

        self.assertEqual(values[0]["estimated_bonus_hourly"], 42.85)
        self.assertEqual(values[0]["seeding_points_hourly"], 42.85)

    def test_ptd_bonus_rate_fallback_applies_to_every_site(self):
        values = ptd_cookiecloud._extract_metrics(
            {
                "hhanclub": {
                    "site": "hhanclub",
                    "seedingBonus": 56_000,
                    "bonusPerHour": 10_000,
                }
            }
        )

        self.assertEqual(values[0]["seeding_points_hourly"], 10_000)

    def test_matches_known_alias_metadata_and_manual_mapping(self):
        configured = [
            {"id": 1, "name": "观众", "domain": "audiences.me"},
            {"id": 2, "name": "示例站", "domain": "tracker.example"},
        ]
        values = [
            {"ptd_site": "audiences", "seeding_points": 10},
            {"ptd_site": "custom", "estimated_bonus_hourly": 4},
        ]

        matched = ptd_cookiecloud.match_metrics(
            values,
            {},
            configured,
            "custom=tracker.example",
        )

        self.assertEqual({item["domain"] for item in matched}, {"audiences.me", "tracker.example"})

    def test_decrypts_cookiecloud_legacy_payload(self):
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives.padding import PKCS7

        uuid = "ptd-test"
        password = "secret"
        clear = json.dumps({"ptd_data": {"userInfo": {}}, "manifest": {}}).encode()
        passphrase = __import__("hashlib").md5(f"{uuid}-{password}".encode()).hexdigest()[:16].encode()
        salt = b"12345678"
        key, iv = ptd_cookiecloud._evp_bytes_to_key(passphrase, salt)
        padder = PKCS7(128).padder()
        padded = padder.update(clear) + padder.finalize()
        encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
        encrypted = base64.b64encode(b"Salted__" + salt + encryptor.update(padded) + encryptor.finalize()).decode()

        self.assertEqual(
            ptd_cookiecloud._decrypt(encrypted, uuid=uuid, password=password)["ptd_data"],
            {"userInfo": {}},
        )

    def test_parses_current_ptd_cookiecloud_payload(self):
        payload = {
            "ptd_data": {
                "userInfo": {
                    "audiences": {
                        "site": "audiences",
                        "seedingBonus": 1200,
                        "seedingBonusPerHour": 3.5,
                    }
                },
                "metadata": {"siteNameMap": {"audiences": "观众"}},
            },
            "manifest": {"fileName": "PTD_backup_current"},
        }
        with patch.object(ptd_cookiecloud, "_decrypt", return_value=payload):
            backup = ptd_cookiecloud.parse_backup_response(
                response={"encrypted": "ciphertext"},
                uuid="ptd-only",
                password="secret",
            )

        self.assertEqual(backup.name, "PTD_backup_current")
        self.assertEqual(backup.metrics[0]["seeding_points"], 1200)
        self.assertIsNone(backup.metrics[0]["estimated_bonus_hourly"])
        self.assertEqual(backup.metrics[0]["seeding_points_hourly"], 3.5)

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
        self.assertEqual(result["sample_count"], 2)
        self.assertEqual(result["points"][0]["upload"], 30)
        self.assertEqual(result["points"][0]["download"], 5)
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

    def test_hourly_traffic_does_not_treat_previous_day_as_an_hourly_baseline(self):
        result = core.build_hourly_traffic(
            [
                {
                    "domain": "example.test",
                    "updated_day": "2026-09-06",
                    "updated_time": "09:00:00",
                    "upload": 100,
                    "download": 50,
                },
                {
                    "domain": "example.test",
                    "updated_day": "2026-09-07",
                    "updated_time": "09:00:00",
                    "upload": 200,
                    "download": 80,
                },
            ],
            "2026-09-07",
        )

        self.assertFalse(result["baseline_valid"])
        self.assertEqual(result["sample_count"], 0)
        self.assertEqual(sum(point["upload"] for point in result["points"]), 0)
        self.assertEqual(sum(point["download"] for point in result["points"]), 0)


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

    def test_joined_twelve_sites_use_full_join_timestamp_order(self):
        progress = core.build_twelve_progress(
            [
                {"id": 1, "name": "TTG"},
                {"id": 2, "name": "U2"},
                {"id": 3, "name": "M-Team"},
            ],
            {
                1: {"err_msg": "", "join_at": "2026-09-08 18:30:00"},
                2: {"err_msg": "", "join_at": "2026-09-08 08:15:00"},
                3: {"err_msg": "", "join_at": "2026-09-08 12:00:00"},
            },
        )
        joined = [item for item in progress["items"] if item["state"] == "joined"]
        self.assertEqual([item["key"] for item in joined], ["u2", "mteam", "ttg"])

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
        self.assertEqual(levels["Power User"]["min_upload"], 240 * core.GIB)
        self.assertTrue(levels["Power User"]["min_upload_strict"])
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

    def test_audiences_points_eta_matches_ptd_remaining_hours(self):
        progress = core.build_retirement_progress(
            [{
                "site_id": 1,
                "site_name": "观众",
                "user_level": "User",
                "join_at": "2026-01-01",
                "updated_day": "2026-09-11",
                "download": 200 * core.GIB,
                "upload": 500 * core.GIB,
                "ratio": 3,
                "seeding_points": 70_260,
                "seeding_points_hourly": 42.85,
            }],
        )

        power = next(
            level for level in progress["sites"][0]["route"]
            if level["name"] == "Power User"
        )
        self.assertEqual(power["seeding_points_eta_hours"], 694)
        self.assertEqual(power["seeding_points_eta_days"], 29)
        self.assertEqual(power["seeding_points_eta_date"], "2026-10-10")

    def test_audiences_seeding_points_gap_uses_readable_integer_format(self):
        missing = core._requirement_missing(
            {"min_seeding_points": 1_500_000},
            {"seeding_points": 70_260},
        )

        self.assertIn("做种积分剩余 1,429,740", missing)
        self.assertFalse(any("e+" in item.casefold() for item in missing))

    def test_strict_seeding_points_at_threshold_does_not_report_zero_gap(self):
        missing = core._requirement_missing(
            {
                "min_seeding_points": 80_000,
                "min_seeding_points_strict": True,
            },
            {"seeding_points": 80_000},
        )

        self.assertIn("做种积分需大于 80,000", missing)
        self.assertNotIn("做种积分剩余 0", missing)

    def test_mteam_retirement_rules_match_published_level_route(self):
        progress = core.build_retirement_progress(
            [{
                "site_id": 1,
                "site_name": "馒头",
                "user_level": "小卒 / User",
                "join_at": "2026-01-01",
                "updated_day": "2026-01-29",
                "download": 200 * core.GIB,
                "ratio": 2,
            }],
        )
        site = progress["sites"][0]
        levels = {level["name"]: level for level in site["route"]}

        self.assertEqual(site["status"], "upgrading")
        self.assertEqual(site["retirement_level"], "Extreme User")
        self.assertEqual(site["next_level"], "Power User")
        self.assertEqual(levels["Power User"]["eligible_date"], "2026-01-30")
        self.assertEqual(levels["Power User"]["min_download"], 200 * core.GIB)
        self.assertEqual(levels["Power User"]["min_upload"], 400 * core.GIB)
        self.assertTrue(levels["Power User"]["min_join_days_strict"])
        self.assertTrue(levels["Power User"]["min_upload_strict"])
        self.assertTrue(levels["Power User"]["min_download_strict"])
        self.assertTrue(levels["Power User"]["min_ratio_strict"])
        self.assertIn("账号时间剩余 1 天", levels["Power User"]["missing"])
        self.assertIn("下载需大于 200.0 GB", levels["Power User"]["missing"])
        self.assertIn("上传剩余 400.0 GB", levels["Power User"]["missing"])
        self.assertIn("分享率需大于 2", levels["Power User"]["missing"])
        self.assertTrue(levels["Extreme User"]["is_retirement"])
        self.assertIn("永久保号", levels["Extreme User"]["description"])
        self.assertEqual(levels["mTorrent Master"]["min_join_days"], 224)
        self.assertEqual(levels["mTorrent Master"]["min_download"], 3000 * core.GIB)

    def test_mteam_rule_matches_chinese_official_level_name(self):
        progress = core.build_retirement_progress(
            [{
                "site_id": 1,
                "site_name": "M-Team 馒头",
                "user_level": "府尹",
                "join_at": "2025-01-01",
                "updated_day": "2026-09-08",
            }],
        )

        site = progress["sites"][0]
        self.assertEqual(site["status"], "retired")
        self.assertEqual(site["current_level"], "府尹")
        self.assertTrue(next(level for level in site["route"] if level["name"] == "Extreme User")["is_current"])

    def test_hhan_retirement_rules_keep_seeding_points_distinct_from_bonus(self):
        progress = core.build_retirement_progress(
            [{
                "site_id": 1,
                "site_name": "憨憨",
                "user_level": "憨头憨脑 User",
                "join_at": "2026-01-01",
                "updated_day": "2026-09-11",
                "upload": 100 * core.GIB,
                "download": 60 * core.GIB,
                "ratio": 1.1,
                "bonus": 9_999_999,
                "seeding_points": 79_999,
                "seeding_points_hourly": 10,
            }],
        )
        site = progress["sites"][0]
        levels = {level["name"]: level for level in site["route"]}

        self.assertEqual(site["next_level"], "Power User")
        self.assertEqual(site["retirement_level"], "Ultimate User")
        self.assertEqual(levels["Power User"]["min_seeding_points"], 80_000)
        self.assertTrue(levels["Power User"]["min_seeding_points_strict"])
        self.assertIsNone(levels["Power User"]["min_bonus"])
        self.assertIn("做种积分剩余 1", levels["Power User"]["missing"])
        self.assertFalse(any("魔力" in item for item in levels["Power User"]["missing"]))
        self.assertEqual(levels["Power User"]["min_upload"], 63 * core.GIB)
        self.assertEqual(
            [levels[name]["min_seeding_points"] for name in (
                "Power User", "Elite User", "Crazy User", "Insane User",
                "Veteran User", "Extreme User", "Ultimate User", "Nexus Master",
            )],
            [80_000, 150_000, 300_000, 500_000, 900_000, 1_100_000, 1_300_000, 1_500_000],
        )
        self.assertTrue(all(
            levels[name]["min_bonus"] is None
            for name in (
                "Power User", "Elite User", "Crazy User", "Insane User",
                "Veteran User", "Extreme User", "Ultimate User", "Nexus Master",
            )
        ))
        self.assertTrue(levels["Ultimate User"]["is_retirement"])
        self.assertEqual(levels["Power User"]["seeding_points_eta_days"], 1)
        self.assertEqual(levels["Power User"]["seeding_points_eta_date"], "2026-09-12")
        self.assertEqual(levels["Power User"]["seeding_points_eta_hours"], 0)

    def test_hhan_points_eta_never_uses_magic_rate(self):
        progress = core.build_retirement_progress(
            [{
                "site_id": 1,
                "site_name": "憨憨",
                "user_level": "憨头憨脑 User",
                "join_at": "2026-01-01",
                "updated_day": "2026-09-11",
                "upload": 100 * core.GIB,
                "download": 60 * core.GIB,
                "ratio": 1.1,
                "bonus": 999_999,
                "estimated_bonus_hourly": 10_000,
                "seeding_points": 56_000,
                "seeding_points_hourly": 100,
            }],
        )

        power = next(
            level for level in progress["sites"][0]["route"]
            if level["name"] == "Power User"
        )
        self.assertEqual(power["seeding_points_eta_days"], 11)
        self.assertEqual(power["seeding_points_eta_date"], "2026-09-22")

    def test_home_retirement_rules_match_published_requirements(self):
        progress = core.build_retirement_progress(
            [{
                "site_id": 1,
                "site_name": "家园",
                "user_level": "User",
                "join_at": "2026-01-01",
                "updated_day": "2026-09-11",
                "upload": 0,
                "download": 0,
                "ratio": 0,
                "bonus": 99_999_999,
                "seeding_points": 0,
            }],
        )
        site = progress["sites"][0]
        levels = {level["name"]: level for level in site["route"]}
        ordered = (
            "Power User", "Elite User", "Crazy User", "Insane User",
            "Veteran User", "Extreme User", "Ultimate User", "Nexus Master",
        )

        self.assertEqual(site["next_level"], "Power User")
        self.assertEqual(site["retirement_level"], "Nexus Master")
        self.assertEqual(
            [levels[name]["min_join_days"] for name in ordered],
            [35, 56, 84, 112, 140, 168, 210, 252],
        )
        self.assertEqual(
            [levels[name]["min_download"] for name in ordered],
            [256 * core.GIB, 386 * core.GIB, 512 * core.GIB, 768 * core.GIB,
             1024 * core.GIB, 2048 * core.GIB, 8192 * core.GIB, 10240 * core.GIB],
        )
        self.assertEqual(
            [levels[name]["min_seeding_points"] for name in ordered],
            [40_000, 100_000, 180_000, 280_000,
             400_000, 540_000, 700_000, 1_000_000],
        )
        self.assertTrue(all(levels[name]["min_bonus"] is None for name in ordered))
        self.assertEqual(levels["Power User"]["min_upload"], 512 * core.GIB)
        self.assertEqual(levels["Nexus Master"]["min_upload"], 102400 * core.GIB)
        self.assertTrue(levels["Nexus Master"]["is_retirement"])

    def test_hdfans_retirement_rules_use_seeding_points_not_bonus(self):
        progress = core.build_retirement_progress(
            [{
                "site_id": 1,
                "site_name": "红豆饭 HDFans",
                "user_level": "User",
                "join_at": "2026-01-01",
                "updated_day": "2026-09-11",
                "upload": 0,
                "download": 0,
                "ratio": 0,
                "bonus": 9_999_999,
                "seeding_points": 0,
            }],
        )
        site = progress["sites"][0]
        levels = {level["name"]: level for level in site["route"]}
        ordered = (
            "Power User", "Elite User", "Crazy User", "Insane User",
            "Veteran User", "Extreme User", "Ultimate User", "Nexus Master",
        )

        self.assertEqual(site["next_level"], "Power User")
        self.assertEqual(site["retirement_level"], "Extreme User")
        self.assertEqual(
            [levels[name]["min_join_days"] for name in ordered],
            [28, 56, 105, 210, 280, 350, 420, 700],
        )
        self.assertEqual(
            [levels[name]["min_download"] for name in ordered],
            [50 * core.GIB, 120 * core.GIB, 256 * core.GIB, 512 * core.GIB,
             1024 * core.GIB, 2048 * core.GIB, 4096 * core.GIB, 10240 * core.GIB],
        )
        self.assertEqual(
            [levels[name]["min_seeding_points"] for name in ordered],
            [50_000, 100_000, 250_000, 400_000,
             600_000, 800_000, 1_000_000, 1_688_888],
        )
        self.assertTrue(all(levels[name]["min_bonus"] is None for name in ordered))
        self.assertEqual(levels["Power User"]["min_upload"], 50 * core.GIB)
        self.assertEqual(levels["Extreme User"]["min_upload"], 7168 * core.GIB)
        self.assertTrue(levels["Extreme User"]["is_retirement"])

    def test_kylin_retirement_rules_match_published_requirements(self):
        progress = core.build_retirement_progress(
            [{
                "site_id": 1,
                "site_name": "麒麟",
                "user_level": "草塘结庐/User",
                "join_at": "2026-01-01",
                "updated_day": "2026-09-11",
                "upload": 0,
                "download": 0,
                "ratio": 0,
                "bonus": 9_999_999,
                "seeding_points": 0,
            }],
        )
        site = progress["sites"][0]
        levels = {level["name"]: level for level in site["route"]}
        ordered = (
            "Power User", "Elite User", "Crazy User", "Insane User",
            "Veteran User", "Extreme User", "Ultimate User", "Nexus Master",
        )

        self.assertEqual(site["next_level"], "Power User")
        self.assertEqual(site["retirement_level"], "Veteran User")
        self.assertEqual(
            [levels[name]["min_join_days"] for name in ordered],
            [28, 56, 105, 175, 280, 420, 560, 700],
        )
        self.assertEqual(
            [levels[name]["min_download"] for name in ordered],
            [50 * core.GIB, 120 * core.GIB, 300 * core.GIB, 500 * core.GIB,
             750 * core.GIB, 1024 * core.GIB, 4096 * core.GIB, 10240 * core.GIB],
        )
        self.assertEqual(
            [levels[name]["min_ratio"] for name in ordered],
            [2, 3, 4, 5, 6, 7, 8, 10],
        )
        self.assertEqual(
            [levels[name]["min_seeding_points"] for name in ordered],
            [40_000, 80_000, 150_000, 250_000,
             400_000, 600_000, 800_000, 1_000_000],
        )
        self.assertTrue(all(levels[name]["min_bonus"] is None for name in ordered))
        self.assertEqual(levels["Power User"]["min_upload"], 100 * core.GIB)
        self.assertEqual(levels["Veteran User"]["min_upload"], 4500 * core.GIB)
        self.assertTrue(levels["Veteran User"]["is_retirement"])

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

    def test_uploaded_rule_does_not_match_site_domain_when_display_name_differs(self):
        rule = {
            "_custom_rule": True,
            "retirement_level": "Nexus Master",
            "levels": [
                {"name": "User"},
                {"name": "Power User"},
                {"name": "Nexus Master"},
            ],
        }
        progress = core.build_retirement_progress(
            [{
                "site_id": 1,
                "site_name": "我的猫站",
                "domain": "pterclub.com",
                "user_level": "POWER_USER",
                "updated_day": "2026-09-12",
            }],
            {"pterclub.com": rule},
        )
        site = progress["sites"][0]

        self.assertEqual(site["status"], "rule_missing")
        self.assertEqual(site["next_level"], "")
        self.assertEqual(len(site["route"]), 0)


class PackagingTests(unittest.TestCase):
    def test_v3_manifest_matches_source(self):
        manifest = json.loads((ROOT / "package.v3.json").read_text(encoding="utf-8"))
        meta = manifest["PTDataStatistics"]
        source = (PLUGIN / "__init__.py").read_text(encoding="utf-8")
        self.assertEqual(meta["version"], "1.2.2")
        self.assertEqual(meta["history"]["v1.2.2"], "不值一提。")
        self.assertEqual(meta["history"]["v1.2.1"], "不值一提")
        self.assertEqual(meta["history"]["v1.2.0"], "不值一提")
        self.assertEqual(meta["history"]["v1.1.9"], "不值一提")
        self.assertEqual(meta["history"]["v1.1.8"], "不值一提")
        self.assertEqual(meta["history"]["v1.1.7"], "更新了一些东西")
        self.assertEqual(meta["history"]["v1.1.6"], "更新了一些东西")
        self.assertEqual(meta["history"]["v1.1.5"], "更新了一些东西")
        self.assertEqual(meta["history"]["v1.1.4"], "更新了一些东西")
        self.assertEqual(meta["history"]["v1.1.3"], "更新了一些东西")
        self.assertEqual(meta["history"]["v1.1.1"], "更新了一些内容")
        self.assertEqual(meta["history"]["v1.1.0"], "更新了一些内容")
        self.assertEqual(meta["history"]["v1.0.10"], "更新了一些内容")
        self.assertEqual(meta["history"]["v1.0.9"], "更新了一些内容")
        self.assertEqual(meta["history"]["v1.0.8"], "更新了一些内容")
        self.assertEqual(meta["history"]["v1.0.6"], "更新了一些内容")
        self.assertEqual(meta["history"]["v1.0.5"], "更新了一些内容")
        self.assertEqual(meta["history"]["v1.0.4"], "更新了一些内容")
        self.assertEqual(meta["history"]["v1.0.3"], "更新了一些内容")
        self.assertEqual(meta["history"]["v1.0.2"], "更新了一些东西")
        self.assertEqual(meta["history"]["v1.0.1"], "更新了一些东西")
        self.assertEqual(meta["history"]["v1.0.0"], "更新了一些东西")
        self.assertEqual(list(meta["history"]), ["v1.2.2", "v1.2.1", "v1.2.0", "v1.1.9", "v1.1.8", "v1.1.7", "v1.1.6", "v1.1.5", "v1.1.4", "v1.1.3", "v1.1.2", "v1.1.1", "v1.1.0", "v1.0.10", "v1.0.9", "v1.0.8", "v1.0.7", "v1.0.6", "v1.0.5", "v1.0.4", "v1.0.3", "v1.0.2", "v1.0.1", "v1.0.0"])
        self.assertIn('plugin_version = "1.2.2"', source)
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

    def test_workbench_ui_polish_contract(self):
        source = (PLUGIN / "src" / "components" / "PTStatsWorkbench.vue").read_text(
            encoding="utf-8"
        )
        self.assertIn("item.state === 'joined' && item.site_id", source)
        self.assertIn('v-if="item.state === \'joined\'" class="twelve-node__name"', source)
        self.assertNotIn('class="twelve-node__date"', source)
        self.assertNotIn("item.state === 'joined' ? item.name : '未解锁'", source)
        self.assertNotIn('class="twelve-node__latest"', source)
        self.assertNotIn('>最近加入</span>', source)
        self.assertIn('class="twelve-remaining">剩余', source)
        self.assertNotIn(":hint=\"`服务器日期 ${overview.server_date || '—'}`\"", source)
        self.assertNotIn("查询数据</VBtn>", source)
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
        self.assertIn('class="history-workspace"', source)
        self.assertIn('class="history-site-sidebar"', source)
        self.assertIn('class="history-site-sidebar__items"', source)
        self.assertIn('class="history-workspace__main"', source)
        self.assertIn('@click="selectHistorySite(null)"', source)
        self.assertNotIn('class="history-site-expansion"', source)
        self.assertNotIn('v-model="historyMetric"', source)
        self.assertNotIn('label="站点范围"', source)
        self.assertNotIn('class="history-toolbar"', source)
        self.assertNotIn('class="history-toolbar-secondary"', source)
        self.assertNotIn('class="history-detail-summary__title"', source)
        self.assertIn('class="history-summary-scope"', source)
        self.assertNotIn('class="history-period-scope"', source)
        self.assertLess(source.index('class="history-summary-scope"'), source.index('class="history-detail-metrics"'))
        self.assertLess(source.index('class="history-detail-summary"'), source.index('class="history-site-sidebar"'))
        self.assertIn("if (value === 'history' && !(history.value.records || []).length) loadHistory()", source)
        self.assertIn("选择左侧站点可查看该站点历史数据", source)
        self.assertIn("const selectedHistoryRecords = computed", source)
        self.assertIn('class="history-record-table"', source)
        self.assertIn("<th>日期</th><th>累计上传</th><th>累计下载</th>", source)
        self.assertNotIn("<th>账号质量</th>", source)
        self.assertNotIn("<th>积分 / 魔力</th>", source)
        self.assertNotIn("<th>做种数 / 体积</th>", source)
        self.assertIn("<th>分享率</th><th>魔力</th><th>做种数</th><th>做种体积</th>", source)
        self.assertIn("小时曲线至少需要同一站点在当天产生 2 次数据刷新", source)
        self.assertIn('<span><i class="legend__upload" />上传</span>', source)
        self.assertIn('<span><i class="legend__download" />下载</span>', source)
        self.assertNotIn("history-line-chart--expanded", source)
        self.assertIn('>数据统计</VTab>', source)
        self.assertNotIn(">数据刷新</VBtn>", source)
        self.assertNotIn("syncFromMP", source)
        self.assertIn("暂无历史数据，请等待 MoviePilot 站点刷新", source)
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
        self.assertIn("current: complete ? '达成'", source)
        self.assertIn("currentDays} 天", source)
        self.assertNotIn("注册时间已达成", source)
        self.assertIn('class="retirement-explorer"', source)
        self.assertIn('class="retirement-site-list"', source)
        self.assertIn('@click="selectRetirementSite(site)"', source)
        self.assertIn('class="retirement-detail"', source)
        self.assertIn('class="retirement-route-rail"', source)
        self.assertIn('class="retirement-route-rail__track"', source)
        self.assertIn("--route-count", source)
        self.assertIn(".retirement-detail{min-width:0;min-height:0;overflow:visible", source)
        self.assertNotIn(".retirement-detail{min-width:0;min-height:0;overflow-y:auto", source)
        self.assertNotIn("还差", source)
        self.assertNotIn("MoviePilot 不提供站点等级门槛和保号等级", source)
        self.assertIn('class="requirement-panel"', source)
        self.assertIn('class="retirement-levels"', source)
        self.assertIn("selectedRetirementSite", source)
        self.assertIn("const selectedRetirementView = computed", source)
        self.assertIn('class="requirement-overview__score"', source)
        self.assertIn('class="requirement-table__head"', source)
        self.assertIn('<span>目标要求</span><span>当前进度</span><span>剩余</span><span>时间</span><span>完成进度</span>', source)
        self.assertIn("etaDate: level.seeding_points_eta_date", source)
        self.assertLess(source.index("pushNumeric({ key: 'seeding-points'"), source.index("if (joinRow) rows.push(joinRow)"))
        self.assertIn("eta: complete ? '—' : level.eligible_date || '—'", source)
        self.assertIn("function nextLevelEta(site, requirements)", source)
        self.assertIn(".map(row => row.eta)", source)
        self.assertIn("eta: nextLevelEta(site, requirements)", source)
        self.assertIn("row.detail.replace(/^剩余\\s*/, '')", source)
        self.assertIn('class="retirement-levels__columns"', source)
        self.assertIn('<details v-for="level in selectedRetirementView.levels"', source)
        self.assertIn("const route = retirementRoute(site)", source)
        self.assertIn("const levels = site.route || []", source)
        self.assertNotIn("route.slice(currentIndex)", source)
        self.assertIn("boundedRoute.slice(userIndex)", source)
        self.assertIn("completedRouteSegments + overallProgress / 100", source)
        self.assertIn('class="rules-file-input"', source)
        self.assertIn("async function uploadRuleFile(event)", source)
        self.assertIn("settingsDraft.value.custom_retirement_rules = rules", source)
        self.assertIn("alignRulesToMoviePilotSites(normalizeUploadedRules(payload))", source)
        self.assertIn("return { ...rule, site: matchedName, aliases: [] }", source)
        self.assertIn("await props.api.post(`${pluginBase.value}/settings`, payload)", source)
        self.assertIn("`${pluginBase.value}/rules/template`", source)
        self.assertIn("mteam-level-rules-template.json", source)
        self.assertIn("下载模板", source)
        self.assertLess(source.index('class="rules-upload__actions"'), source.index('class="rules-file-input"'))
        self.assertNotIn("使用内置等级规则", source)
        self.assertNotIn("自定义规则优先于同名内置规则", source)
        self.assertIn(':model-value="selectedRetirementView.routeProgress"', source)
        self.assertNotIn("待同步积分时速", source)
        self.assertIn("nextLevelOverallProgress(site)", source)
        self.assertIn("return averageRequirementProgress(requirementRows(site, nextLevel))", source)
        self.assertNotIn("retirementProgressPercent(site)", source)
        self.assertIn("const overallProgress = averageRequirementProgress(requirements)", source)
        self.assertNotIn("retirement-preview-grid", source)
        self.assertNotIn("retirement-mini-progress", source)
        self.assertLess(source.index('class="retirement-site-list"'), source.index('class="retirement-detail"'))
        self.assertLess(source.index('class="retirement-detail__metrics"'), source.index('class="retirement-route-rail"'))
        self.assertLess(source.index('class="retirement-route-rail"'), source.index('class="requirement-panel"'))
        self.assertIn('v-if="level.description"', source)
        self.assertIn(".retirement-level-row__detail strong{max-width:100%;margin-left:auto", source)
        self.assertIn("overflow-wrap:anywhere;text-align:right", source)
        self.assertIn("<h2>养老进度</h2>", source)
        self.assertNotIn("全部站点养老进度", source)
        self.assertNotIn("同步 MP 数据间隔", source)
        self.assertNotIn("mdi-calendar-arrow-up", source)
        self.assertNotIn("mdi-calendar-arrow-down", source)
        self.assertNotIn("mdi-content-copy", source)
        self.assertNotIn("copyPtdReceiverUrl", source)
        self.assertEqual(source.count('icon="mdi-shuffle-variant"'), 2)
        self.assertNotIn('建议同时勾选“站点与服务器配置”', source)

        dashboard = (PLUGIN / "src" / "components" / "Dashboard.vue").read_text(
            encoding="utf-8"
        )
        self.assertLess(dashboard.index("统计日期"), dashboard.index("上传增量"))

        self.assertNotIn("<h2>数据导出</h2>", source)
        self.assertNotIn("ExportDialog", source)
        self.assertNotIn("export_fields", source)
        self.assertIn("url.hostname = 'localhost'", source)
        self.assertIn("其它局域网设备请替换为 MoviePilot 主机 IP", source)

        utils = (PLUGIN / "src" / "utils.js").read_text(encoding="utf-8")
        self.assertIn("event?.preventDefault?.()", utils)


if __name__ == "__main__":
    unittest.main()
