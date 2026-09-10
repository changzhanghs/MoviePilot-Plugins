"""PT 数据统计插件 API 的显式响应模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class SiteSnapshotData(BaseModel):
    """单个站点的累计值与当日增量。"""

    id: int | None = None
    site_id: int | None = None
    site_name: str = ""
    is_active: bool = False
    username: str = ""
    userid: str = ""
    join_at: str = ""
    user_level: str = ""
    upload: int = 0
    download: int = 0
    daily_upload: int = 0
    daily_download: int = 0
    baseline_valid: bool = False
    counter_reset: bool = False
    ratio: float | None = None
    bonus: float | None = None
    estimated_bonus_hourly: float | None = None
    seeding_points: float | None = None
    seeding: int = 0
    seeding_size: int = 0
    updated_day: str = ""
    contribution: float = 0


class SummaryData(BaseModel):
    """侧栏总览和 PT 生涯共用的聚合指标。"""

    valid_sites: int = 0
    total_upload: int = 0
    total_download: int = 0
    overall_ratio: float | None = None
    total_seeding: int = 0
    total_seeding_size: int = 0
    today_upload: int = 0
    today_download: int = 0
    today_sites: int = 0
    earliest_join_at: str = ""
    career_days: int | None = None
    average_upload: int = 0
    average_download: int = 0
    top_upload_site: str = ""
    top_download_site: str = ""


class TwelveSiteData(BaseModel):
    """十二大中的单个站点状态。"""

    key: str
    name: str
    state: str
    site_id: int | None = None
    join_at: str = ""


class TwelveProgressData(BaseModel):
    """十二大完成进度。"""

    joined: int = 0
    total: int = 12
    percent: int = 0
    items: list[TwelveSiteData] = Field(default_factory=list)


class TrafficDistributionItem(BaseModel):
    """某个时间范围内单站的上传下载增量。"""

    site_id: int | None = None
    site_name: str = ""
    upload: int = 0
    download: int = 0


class TrafficDistributionResponse(BaseModel):
    """数据总览使用的月度与日度站点流量分布。"""

    month: str
    day: str
    monthly: list[TrafficDistributionItem] = Field(default_factory=list)
    daily: list[TrafficDistributionItem] = Field(default_factory=list)


class LevelRequirementData(BaseModel):
    """养老进度中的一个等级及其门槛。"""

    name: str
    description: str = ""
    min_join_days: int = 0
    min_join_days_strict: bool = False
    min_upload: int = 0
    min_upload_strict: bool = False
    min_download: int = 0
    min_download_strict: bool = False
    min_ratio: float | None = None
    min_ratio_strict: bool = False
    min_bonus: float | None = None
    min_seeding_points: float | None = None
    min_seeding: int = 0
    eligible_date: str = ""
    reached: bool = False
    is_current: bool = False
    is_retirement: bool = False
    missing: list[str] = Field(default_factory=list)


class RetirementSiteData(BaseModel):
    """单站升级路线与达到保号等级的进度。"""

    site_id: int | None = None
    site_name: str = ""
    current_level: str = ""
    next_level: str = ""
    retirement_level: str = ""
    status: str = "rule_missing"
    join_at: str = ""
    upload: int = 0
    download: int = 0
    ratio: float | None = None
    bonus: float | None = None
    seeding_points: float | None = None
    estimated_bonus_hourly: float | None = None
    seeding: int = 0
    updated_day: str = ""
    levels_remaining: int | None = None
    route: list[LevelRequirementData] = Field(default_factory=list)


class RetirementProgressData(BaseModel):
    """全部站点养老进度汇总。"""

    total: int = 0
    retired: int = 0
    upgrading: int = 0
    rule_missing: int = 0
    sites: list[RetirementSiteData] = Field(default_factory=list)


class OverviewResponse(BaseModel):
    """侧栏与仪表盘读取的完整统计响应。"""

    server_date: str
    generated_at: str
    last_mp_update: str = ""
    first_history_day: str = ""
    last_history_day: str = ""
    summary: SummaryData
    sites: list[SiteSnapshotData] = Field(default_factory=list)
    today_sites: list[SiteSnapshotData] = Field(default_factory=list)
    history_sites: list[SiteSnapshotData] = Field(default_factory=list)
    twelve: TwelveProgressData
    retirement: RetirementProgressData


class HistoryResponse(BaseModel):
    """历史查询响应。"""

    start_day: str
    end_day: str
    count: int
    records: list[SiteSnapshotData] = Field(default_factory=list)


class HourlyTrafficPoint(BaseModel):
    """一个自然小时内由 MP 相邻采样计算出的真实流量增量。"""

    hour: str
    upload: int = 0
    download: int = 0
    samples: int = 0


class HourlyTrafficResponse(BaseModel):
    """指定日期及站点范围的小时流量曲线。"""

    day: str
    site_id: int | None = None
    site_name: str = "全部站点"
    baseline_valid: bool = False
    sample_count: int = 0
    points: list[HourlyTrafficPoint] = Field(default_factory=list)


class ExportFieldData(BaseModel):
    """可导出字段定义。"""

    key: str
    label: str


class SettingsData(BaseModel):
    """插件可编辑设置。"""

    enabled: bool = False
    show_sidebar: bool = True
    retention_days: int = 365
    notification_enabled: bool = False
    notification_cron: str = "0 9 * * *"
    notification_modes: list[str] = Field(default_factory=lambda: ["today"])
    ptd_cookiecloud_enabled: bool = False
    ptd_cookiecloud_uuid: str = ""
    ptd_cookiecloud_password: str = ""
    ptd_cookiecloud_headers: str = ""
    ptd_site_mappings: str = ""

    @field_validator("retention_days")
    @classmethod
    def validate_retention_days(cls, value: int) -> int:
        """保留期允许永久（0）或不超过一百年的正整数。"""

        return max(0, min(int(value), 36500))

    @field_validator("notification_cron")
    @classmethod
    def validate_notification_cron(cls, value: str) -> str:
        """使用 APScheduler 校验标准五段式 Cron。"""

        from apscheduler.triggers.cron import CronTrigger

        normalized = " ".join(str(value or "0 9 * * *").split())
        if len(normalized.split(" ")) != 5:
            raise ValueError("通知 Cron 必须为标准五段式表达式")
        try:
            CronTrigger.from_crontab(normalized)
        except ValueError as error:
            raise ValueError(f"通知 Cron 无效：{error}") from error
        return normalized

    @field_validator("notification_modes")
    @classmethod
    def validate_notification_modes(cls, value: list[str]) -> list[str]:
        """仅保留今日和所有数据两种通知内容。"""

        allowed = {"today", "all"}
        modes = [item for item in value if item in allowed]
        return list(dict.fromkeys(modes))

    @field_validator(
        "ptd_cookiecloud_uuid",
        "ptd_cookiecloud_headers",
        "ptd_site_mappings",
    )
    @classmethod
    def strip_ptd_text(cls, value: str) -> str:
        return str(value or "").strip()


class SettingsResponse(BaseModel):
    """设置读取或保存响应。"""

    settings: SettingsData
    export_fields: list[ExportFieldData] = Field(default_factory=list)


class SyncResponse(BaseModel):
    """从 MP 同步数据的执行结果。"""

    imported: int = 0
    deleted: int = 0
    completed_at: str = ""
    ptd_imported: int = 0
    ptd_backup: str = ""
    ptd_error: str = ""


class MessageResponse(BaseModel):
    """通用动作结果。"""

    success: bool
    message: str = ""
    data: dict[str, Any] | None = None


class CookieCloudUpdateData(BaseModel):
    """PTD CookieCloud 兼容上传请求。"""

    uuid: str = Field(min_length=5, max_length=256)
    encrypted: str = Field(min_length=1, max_length=64 * 1024 * 1024)


class CookieCloudEncryptedData(BaseModel):
    """PTD CookieCloud 兼容下载响应。"""

    encrypted: str


class CookieCloudActionResponse(BaseModel):
    """PTD CookieCloud 兼容写入结果。"""

    action: str
