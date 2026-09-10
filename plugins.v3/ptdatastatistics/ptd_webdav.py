"""Read the newest unencrypted PT-Depiler user-info backup from WebDAV."""

from __future__ import annotations

import base64
import io
import json
import re
import ssl
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urljoin, urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile


_BACKUP_RE = re.compile(r"^PTD_backup_(\d{8}T\d{4,6})\.zip$", re.IGNORECASE)
_MAX_BACKUP_BYTES = 64 * 1024 * 1024
_MAX_JSON_BYTES = 32 * 1024 * 1024
_METRIC_KEYS = {
    "seedingBonus",
    "seedingBonusPerHour",
    "bonusPerHour",
}
_KNOWN_ALIASES = {
    "mteam": ("馒头", "mteam", "m-team"),
    "audiences": ("观众", "audiences", "audience"),
    "rainbow": ("彩虹岛", "rainbow", "chdbits"),
    "hhan": ("憨憨", "hhan", "hhanclub"),
    "spring": ("春天", "spring", "spring-sunday"),
    "hdsky": ("天空", "hdsky", "skyey"),
    "pter": ("猫站", "pter", "pterclub"),
    "hdhome": ("家园", "hdhome"),
    "ourbits": ("我堡", "ourbits"),
}


class PTDWebDAVError(RuntimeError):
    """A safe, user-facing PTD WebDAV import failure."""


@dataclass(frozen=True)
class PTDBackup:
    """The newest PTD backup and the parsed values needed by this plugin."""

    name: str
    url: str
    metrics: list[dict[str, Any]]
    metadata: dict[str, Any]


def _request(
    url: str,
    *,
    method: str,
    username: str,
    password: str,
    verify_ssl: bool,
    body: bytes | None = None,
) -> bytes:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise PTDWebDAVError("WebDAV 地址必须是完整的 HTTP 或 HTTPS 地址")
    headers = {"User-Agent": "MoviePilot-PTDataStatistics/1"}
    if username or password:
        token = base64.b64encode(f"{username}:{password}".encode()).decode()
        headers["Authorization"] = f"Basic {token}"
    if method == "PROPFIND":
        headers.update({"Depth": "1", "Content-Type": "application/xml; charset=utf-8"})
    request = Request(url, data=body, headers=headers, method=method)
    context = None
    if parsed.scheme == "https" and not verify_ssl:
        context = ssl._create_unverified_context()  # noqa: SLF001 - explicit user setting
    try:
        with urlopen(request, timeout=30, context=context) as response:
            length = int(response.headers.get("Content-Length") or 0)
            if length > _MAX_BACKUP_BYTES:
                raise PTDWebDAVError("PTD 备份超过 64 MB，已拒绝读取")
            data = response.read(_MAX_BACKUP_BYTES + 1)
            if len(data) > _MAX_BACKUP_BYTES:
                raise PTDWebDAVError("PTD 备份超过 64 MB，已拒绝读取")
            return data
    except PTDWebDAVError:
        raise
    except Exception as error:  # noqa: BLE001
        raise PTDWebDAVError(f"连接 PTD WebDAV 失败：{error}") from error


def _latest_backup_url(xml_data: bytes, base_url: str) -> tuple[str, str]:
    try:
        root = ElementTree.fromstring(xml_data)
    except ElementTree.ParseError as error:
        raise PTDWebDAVError("WebDAV 返回的目录列表无法解析") from error
    candidates: list[tuple[str, str]] = []
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1].lower() != "href" or not element.text:
            continue
        href = unquote(element.text.strip())
        name = href.rstrip("/").rsplit("/", 1)[-1]
        match = _BACKUP_RE.match(name)
        if match:
            candidates.append((match.group(1), urljoin(base_url, href)))
    if not candidates:
        raise PTDWebDAVError("WebDAV 目录中没有找到 PTD_backup_*.zip")
    _, url = max(candidates, key=lambda item: item[0])
    return unquote(urlparse(url).path).rsplit("/", 1)[-1], url


def _json_member(archive: ZipFile, filename: str, *, required: bool) -> Any:
    member = next((name for name in archive.namelist() if name.rsplit("/", 1)[-1] == filename), None)
    if not member:
        if required:
            raise PTDWebDAVError(
                f"PTD 备份中缺少 {filename}；请在 PTD 备份字段中勾选用户信息并关闭备份加密"
            )
        return {}
    info = archive.getinfo(member)
    if info.file_size > _MAX_JSON_BYTES:
        raise PTDWebDAVError(f"{filename} 超过 32 MB，已拒绝读取")
    try:
        return json.loads(archive.read(member).decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PTDWebDAVError(f"{filename} 不是有效 JSON；加密备份暂不支持") from error


def _record_score(record: dict[str, Any], day_key: str = "") -> tuple[float, str]:
    try:
        updated = float(record.get("updateAt") or 0)
    except (TypeError, ValueError):
        updated = 0
    return updated, day_key


def _extract_metrics(user_info: Any) -> list[dict[str, Any]]:
    if isinstance(user_info, dict) and isinstance(user_info.get("userInfo"), dict):
        user_info = user_info["userInfo"]
    if not isinstance(user_info, dict):
        raise PTDWebDAVError("userInfo.json 的数据结构不受支持")

    output: list[dict[str, Any]] = []
    for site_key, history in user_info.items():
        records: list[tuple[str, dict[str, Any]]] = []
        if isinstance(history, dict) and (_METRIC_KEYS & set(history)):
            records.append(("", history))
        elif isinstance(history, dict):
            records.extend(
                (str(day), value)
                for day, value in history.items()
                if isinstance(value, dict)
            )
        if not records:
            continue
        day_key, record = max(records, key=lambda item: _record_score(item[1], item[0]))
        seeding_points = _number(record.get("seedingBonus"))
        bonus_hourly = _number(record.get("seedingBonusPerHour"))
        if bonus_hourly is None:
            bonus_hourly = _number(record.get("bonusPerHour"))
        if seeding_points is None and bonus_hourly is None:
            continue
        output.append(
            {
                "ptd_site": str(record.get("site") or site_key),
                "site_name": str(record.get("siteName") or record.get("name") or ""),
                "seeding_points": seeding_points,
                "estimated_bonus_hourly": bonus_hourly,
                "source_updated_at": str(record.get("updateAt") or day_key or ""),
            }
        )
    if not output:
        raise PTDWebDAVError("最新 PTD 备份中没有时魔或做种积分数据")
    return output


def _number(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _identity(value: Any) -> str:
    return "".join(character for character in str(value or "").casefold() if character.isalnum())


def _hostname(value: Any) -> str:
    text = str(value or "").strip().casefold()
    parsed = urlparse(text if "://" in text else f"//{text}")
    return (parsed.hostname or text.split("/", 1)[0]).removeprefix("www.")


def _find_mapping(value: Any, key_name: str) -> dict[str, Any]:
    if not isinstance(value, (dict, list)):
        return {}
    if isinstance(value, dict):
        direct = value.get(key_name)
        if isinstance(direct, dict):
            return direct
        for nested in value.values():
            found = _find_mapping(nested, key_name)
            if found:
                return found
    else:
        for nested in value:
            found = _find_mapping(nested, key_name)
            if found:
                return found
    return {}


def _mapping_values(mapping: dict[str, Any], site_key: str) -> list[str]:
    values: list[str] = []
    direct = mapping.get(site_key)
    if isinstance(direct, list):
        values.extend(str(item) for item in direct)
    elif direct not in (None, ""):
        values.append(str(direct))
    wanted = _identity(site_key)
    for key, value in mapping.items():
        candidates = value if isinstance(value, list) else [value]
        if any(_identity(candidate) == wanted for candidate in candidates):
            values.append(str(key))
    return values


def _manual_mappings(raw: str) -> dict[str, str]:
    output: dict[str, str] = {}
    for line in str(raw or "").replace(",", "\n").splitlines():
        if "=" not in line:
            continue
        source, target = line.split("=", 1)
        if _identity(source) and target.strip():
            output[_identity(source)] = target.strip()
    return output


def match_metrics(
    metrics: list[dict[str, Any]],
    metadata: dict[str, Any],
    configured_sites: list[dict[str, Any]],
    manual_mappings: str = "",
) -> list[dict[str, Any]]:
    """Match PTD site identifiers to MP sites without importing other fields."""

    host_map = _find_mapping(metadata, "siteHostMap")
    name_map = _find_mapping(metadata, "siteNameMap")
    manual = _manual_mappings(manual_mappings)
    matched: dict[str, dict[str, Any]] = {}
    for metric in metrics:
        ptd_site = str(metric.get("ptd_site") or "")
        ptd_identity = _identity(ptd_site)
        candidates = [ptd_site, metric.get("site_name") or ""]
        candidates.extend(_mapping_values(host_map, ptd_site))
        candidates.extend(_mapping_values(name_map, ptd_site))
        candidates.extend(_KNOWN_ALIASES.get(ptd_identity, ()))
        if ptd_identity in manual:
            candidates.insert(0, manual[ptd_identity])
        identities = {_identity(value) for value in candidates if value}
        hostnames = {_hostname(value) for value in candidates if value}
        selected = None
        for site in configured_sites:
            domain = _hostname(site.get("domain"))
            name = _identity(site.get("name"))
            domain_identity = _identity(domain)
            if (
                domain in hostnames
                or name in identities
                or domain_identity in identities
                or any(identity and identity in domain_identity for identity in identities)
            ):
                selected = site
                break
        if not selected:
            continue
        domain = str(selected.get("domain") or "").casefold()
        matched[domain] = {
            **metric,
            "site_id": selected.get("id"),
            "domain": domain,
            "site_name": selected.get("name") or metric.get("site_name") or ptd_site,
        }
    return list(matched.values())


def fetch_latest_backup(
    *,
    url: str,
    username: str = "",
    password: str = "",
    verify_ssl: bool = True,
) -> PTDBackup:
    """List WebDAV, download its newest PTD ZIP and parse only two metrics."""

    base_url = url.rstrip("/") + "/"
    propfind = b'''<?xml version="1.0" encoding="utf-8"?><d:propfind xmlns:d="DAV:"><d:prop><d:getlastmodified/><d:getcontentlength/></d:prop></d:propfind>'''
    listing = _request(
        base_url,
        method="PROPFIND",
        username=username,
        password=password,
        verify_ssl=verify_ssl,
        body=propfind,
    )
    name, backup_url = _latest_backup_url(listing, base_url)
    content = _request(
        backup_url,
        method="GET",
        username=username,
        password=password,
        verify_ssl=verify_ssl,
    )
    try:
        with ZipFile(io.BytesIO(content)) as archive:
            user_info = _json_member(archive, "userInfo.json", required=True)
            metadata = _json_member(archive, "metadata.json", required=False)
    except BadZipFile as error:
        raise PTDWebDAVError("最新 PTD 备份不是有效 ZIP 文件") from error
    return PTDBackup(
        name=name,
        url=backup_url,
        metrics=_extract_metrics(user_info),
        metadata=metadata if isinstance(metadata, dict) else {},
    )
