"""PT 数据统计 CSV 导出器。"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Sequence
from typing import Any

from .core import EXPORT_FIELD_LABELS


def export_rows(records: Iterable[dict[str, Any]], fields: Sequence[str]) -> list[list[Any]]:
    """按用户选择的字段顺序生成二维导出数据。"""

    rows: list[list[Any]] = [[EXPORT_FIELD_LABELS[field] for field in fields]]
    for record in records:
        rows.append(["" if record.get(field) is None else record.get(field) for field in fields])
    return rows


def build_csv(records: Iterable[dict[str, Any]], fields: Sequence[str]) -> bytes:
    """生成带 UTF-8 BOM 的 CSV，确保常见表格软件直接识别中文。"""

    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerows(export_rows(records, fields))
    return buffer.getvalue().encode("utf-8-sig")
