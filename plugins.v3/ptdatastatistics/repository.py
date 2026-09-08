"""PT 数据统计插件专属数据库访问层。"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta
from typing import Any

from sqlalchemy import delete, func, or_, select, tuple_, update

from .core import as_text, compute_daily_delta
from .models import PTSiteHourlySnapshot, PTSiteSnapshot


class SnapshotRepository:
    """通过 MoviePilot 提供的插件数据库句柄读写每日站点快照。"""

    def __init__(self, database_handle) -> None:
        self._database = database_handle

    def count(self) -> int:
        """返回当前插件数据库中的快照数量。"""

        with self._database.session() as session:
            return int(session.scalar(select(func.count()).select_from(PTSiteSnapshot)) or 0)

    def upsert(self, snapshots: Iterable[dict[str, Any]]) -> int:
        """按站点域名和服务器日期新增或更新 MP 快照。"""

        items = [item for item in snapshots if item.get("domain") and item.get("updated_day")]
        if not items:
            return 0
        domains = {str(item["domain"]) for item in items}
        days = {str(item["updated_day"]) for item in items}
        with self._database.session() as session:
            try:
                existing_rows = session.execute(
                    select(PTSiteSnapshot).where(
                        PTSiteSnapshot.domain.in_(domains),
                        PTSiteSnapshot.updated_day.in_(days),
                    )
                ).scalars().all()
                existing = {(row.domain, row.updated_day): row for row in existing_rows}
                for item in items:
                    key = (str(item["domain"]), str(item["updated_day"]))
                    row = existing.get(key)
                    if row is None:
                        row = PTSiteSnapshot(domain=key[0], updated_day=key[1])
                        session.add(row)
                        existing[key] = row
                    for field in (
                        "site_id",
                        "site_name",
                        "is_active",
                        "username",
                        "userid",
                        "join_at",
                        "user_level",
                        "upload",
                        "download",
                        "ratio",
                        "bonus",
                        "seeding",
                        "seeding_size",
                        "leeching",
                        "leeching_size",
                        "updated_time",
                        "err_msg",
                        "source_updated_at",
                    ):
                        if field in item:
                            setattr(row, field, item[field])
                session.commit()
                return len(items)
            except Exception:
                session.rollback()
                raise

    def capture_hourly(
        self,
        snapshots: Iterable[dict[str, Any]],
        *,
        captured_at: str | None = None,
    ) -> int:
        """按站点和插件收到刷新结果的时间保存累计值，重复时点不会重复写入。"""

        items = []
        for item in snapshots:
            domain = as_text(item.get("domain"))
            day = as_text(item.get("updated_day"))[:10]
            capture_time = as_text(captured_at or item.get("source_updated_at")).strip()
            if not domain or not day or not capture_time or as_text(item.get("err_msg")).strip():
                continue
            items.append({**item, "domain": domain, "updated_day": day, "captured_at": capture_time})
        if not items:
            return 0

        keys = {(item["domain"], item["captured_at"]) for item in items}
        with self._database.session() as session:
            try:
                existing = set(
                    session.execute(
                        select(PTSiteHourlySnapshot.domain, PTSiteHourlySnapshot.captured_at).where(
                            tuple_(PTSiteHourlySnapshot.domain, PTSiteHourlySnapshot.captured_at).in_(keys)
                        )
                    ).all()
                )
                inserted = 0
                for item in items:
                    key = (item["domain"], item["captured_at"])
                    if key in existing:
                        continue
                    session.add(
                        PTSiteHourlySnapshot(
                            site_id=item.get("site_id"),
                            domain=item["domain"],
                            site_name=as_text(item.get("site_name")),
                            upload=max(int(item.get("upload") or 0), 0),
                            download=max(int(item.get("download") or 0), 0),
                            updated_day=item["updated_day"],
                            updated_time=as_text(item.get("updated_time"))[:16],
                            captured_at=item["captured_at"],
                        )
                    )
                    existing.add(key)
                    inserted += 1
                session.commit()
                return inserted
            except Exception:
                session.rollback()
                raise

    def hourly_for_day(self, day: str, site_id: int | None = None) -> list[dict[str, Any]]:
        """返回指定服务器日期的插件小时快照。"""

        conditions = [PTSiteHourlySnapshot.updated_day == day]
        if site_id is not None:
            conditions.append(PTSiteHourlySnapshot.site_id == site_id)
        statement = (
            select(PTSiteHourlySnapshot)
            .where(*conditions)
            .order_by(PTSiteHourlySnapshot.captured_at, PTSiteHourlySnapshot.domain)
        )
        with self._database.session() as session:
            return [row.to_dict() for row in session.execute(statement).scalars().all()]

    def mark_active_domains(self, active_domains: Iterable[str]) -> None:
        """把站点当前启用状态投影到所有已保存历史行。"""

        domains = {domain for domain in active_domains if domain}
        with self._database.session() as session:
            try:
                session.execute(update(PTSiteSnapshot).values(is_active=False))
                if domains:
                    session.execute(
                        update(PTSiteSnapshot)
                        .where(PTSiteSnapshot.domain.in_(domains))
                        .values(is_active=True)
                    )
                session.commit()
            except Exception:
                session.rollback()
                raise

    @staticmethod
    def _valid_condition():
        """返回成功站点快照的统一过滤条件。"""

        return or_(PTSiteSnapshot.err_msg.is_(None), PTSiteSnapshot.err_msg == "")

    def latest(
        self,
        *,
        active_only: bool = True,
        valid_only: bool = True,
    ) -> list[dict[str, Any]]:
        """返回每个站点最近一条快照，可选择是否排除失败记录。"""

        conditions = [self._valid_condition()] if valid_only else []
        if active_only:
            conditions.append(PTSiteSnapshot.is_active.is_(True))
        latest_subquery = (
            select(
                PTSiteSnapshot.domain,
                func.max(PTSiteSnapshot.updated_day).label("latest_day"),
            )
            .where(*conditions)
            .group_by(PTSiteSnapshot.domain)
            .subquery()
        )
        statement = (
            select(PTSiteSnapshot)
            .join(
                latest_subquery,
                (PTSiteSnapshot.domain == latest_subquery.c.domain)
                & (PTSiteSnapshot.updated_day == latest_subquery.c.latest_day),
            )
            .order_by(PTSiteSnapshot.upload.desc(), PTSiteSnapshot.site_name)
        )
        with self._database.session() as session:
            return [row.to_dict() for row in session.execute(statement).scalars().all()]

    def records_for_days(
        self,
        days: Iterable[str],
        *,
        active_only: bool = False,
    ) -> list[dict[str, Any]]:
        """返回指定服务器日期内的成功快照。"""

        day_values = {day for day in days if day}
        if not day_values:
            return []
        conditions = [PTSiteSnapshot.updated_day.in_(day_values), self._valid_condition()]
        if active_only:
            conditions.append(PTSiteSnapshot.is_active.is_(True))
        with self._database.session() as session:
            rows = session.execute(
                select(PTSiteSnapshot)
                .where(*conditions)
                .order_by(PTSiteSnapshot.updated_day, PTSiteSnapshot.site_name)
            ).scalars().all()
            return [row.to_dict() for row in rows]

    def previous_successful(
        self,
        latest_rows: Iterable[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """返回每个最新快照之前最近的一条成功每日快照。"""

        latest_days = {
            str(row.get("domain") or ""): str(row.get("updated_day") or "")
            for row in latest_rows
            if row.get("domain") and row.get("updated_day")
        }
        if not latest_days:
            return {}
        earlier_conditions = [
            (PTSiteSnapshot.domain == domain)
            & (PTSiteSnapshot.updated_day < latest_day)
            for domain, latest_day in latest_days.items()
        ]
        previous_days = (
            select(
                PTSiteSnapshot.domain,
                func.max(PTSiteSnapshot.updated_day).label("previous_day"),
            )
            .where(self._valid_condition(), or_(*earlier_conditions))
            .group_by(PTSiteSnapshot.domain)
            .subquery()
        )
        statement = select(PTSiteSnapshot).join(
            previous_days,
            (PTSiteSnapshot.domain == previous_days.c.domain)
            & (PTSiteSnapshot.updated_day == previous_days.c.previous_day),
        )
        with self._database.session() as session:
            rows = session.execute(statement).scalars().all()
            return {row.domain: row.to_dict() for row in rows}

    def history(
        self,
        *,
        start_day: str,
        end_day: str,
        site_ids: Iterable[int] | None = None,
        include_archived: bool = True,
        limit: int | None = 10000,
    ) -> list[dict[str, Any]]:
        """查询历史，并为每行附加严格相邻日增量。"""

        conditions = [
            PTSiteSnapshot.updated_day >= start_day,
            PTSiteSnapshot.updated_day <= end_day,
            self._valid_condition(),
        ]
        site_id_values = {int(value) for value in (site_ids or ()) if value}
        if site_id_values:
            conditions.append(PTSiteSnapshot.site_id.in_(site_id_values))
        if not include_archived:
            conditions.append(PTSiteSnapshot.is_active.is_(True))

        statement = (
            select(PTSiteSnapshot)
            .where(*conditions)
            .order_by(PTSiteSnapshot.updated_day.desc(), PTSiteSnapshot.domain)
        )
        if limit is not None:
            statement = statement.limit(max(1, min(limit, 50000)))
        with self._database.session() as session:
            rows = session.execute(statement).scalars().all()
            values = [row.to_dict() for row in rows]

            # 查询命中行各自的严格前一自然日，既保证分页返回最新记录，
            # 又不会因为全局 limit 截断而误报“基线不足”。
            selected_keys = {(row["domain"], row["updated_day"]) for row in values}
            baseline_keys: set[tuple[str, str]] = set()
            for row in values:
                try:
                    previous = (
                        date.fromisoformat(row["updated_day"]) - timedelta(days=1)
                    ).isoformat()
                except ValueError:
                    continue
                key = (row["domain"], previous)
                if key not in selected_keys:
                    baseline_keys.add(key)
            baseline_values = []
            if baseline_keys:
                baseline_rows = session.execute(
                    select(PTSiteSnapshot).where(
                        tuple_(PTSiteSnapshot.domain, PTSiteSnapshot.updated_day).in_(baseline_keys),
                        self._valid_condition(),
                    )
                ).scalars().all()
                baseline_values = [row.to_dict() for row in baseline_rows]

        by_key = {
            (row["domain"], row["updated_day"]): row
            for row in [*values, *baseline_values]
        }
        results: list[dict[str, Any]] = []
        for row in values:
            if row["updated_day"] < start_day:
                continue
            try:
                previous = (date.fromisoformat(row["updated_day"]) - timedelta(days=1)).isoformat()
            except ValueError:
                previous = ""
            delta = compute_daily_delta(row, by_key.get((row["domain"], previous)))
            results.append({**row, **delta})
        results.sort(key=lambda item: (item["updated_day"], item["site_name"]), reverse=True)
        return results

    def cleanup(self, *, retention_days: int, server_day: str) -> int:
        """删除超过保留期的插件副本；零天表示永久保留。"""

        if retention_days <= 0:
            return 0
        try:
            cutoff = (date.fromisoformat(server_day) - timedelta(days=retention_days - 1)).isoformat()
        except ValueError:
            return 0
        with self._database.session() as session:
            try:
                daily_result = session.execute(
                    delete(PTSiteSnapshot).where(PTSiteSnapshot.updated_day < cutoff)
                )
                hourly_result = session.execute(
                    delete(PTSiteHourlySnapshot).where(PTSiteHourlySnapshot.updated_day < cutoff)
                )
                session.commit()
                return (
                    int(getattr(daily_result, "rowcount", 0) or 0)
                    + int(getattr(hourly_result, "rowcount", 0) or 0)
                )
            except Exception:
                session.rollback()
                raise

    def date_bounds(self) -> tuple[str, str]:
        """返回插件历史库的最早和最晚日期。"""

        with self._database.session() as session:
            first, last = session.execute(
                select(func.min(PTSiteSnapshot.updated_day), func.max(PTSiteSnapshot.updated_day))
            ).one()
            return as_text(first), as_text(last)
