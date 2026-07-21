"""统一时钟：业务时间一律按中国时区（Asia/Shanghai）切日与落盘。"""

from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

CHINA_TZ = ZoneInfo("Asia/Shanghai")
TZ_META_KEY = "timestamps_tz"
TZ_META_VALUE = "Asia/Shanghai"


def china_now() -> datetime:
    return datetime.now(CHINA_TZ)


def china_today() -> date:
    return china_now().date()


def china_now_iso() -> str:
    """带 +08:00 的 ISO 字符串（会话、日志、元数据）。"""
    return china_now().isoformat()


def china_now_sql() -> str:
    """SQLite DATETIME 墙钟：YYYY-MM-DD HH:MM:SS（已是中国时间，无时区后缀）。"""
    return china_now().strftime("%Y-%m-%d %H:%M:%S")


def calendar_day(dt_str: str | None) -> str:
    """从已存时间戳取日历日（前 10 位）。存库须已是中国墙钟或带 +08:00 的 ISO。"""
    if not dt_str:
        return ""
    return str(dt_str)[:10]


def to_china_iso(dt_str: str) -> str:
    """将旧 UTC/naive/带偏移时间转为中国时区 ISO。"""
    raw = str(dt_str).strip()
    if not raw:
        return raw
    normalized = raw.replace("Z", "+00:00")
    try:
        if "T" in normalized:
            dt = datetime.fromisoformat(normalized)
        else:
            dt = datetime.strptime(normalized[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return raw
    if dt.tzinfo is None:
        # 历史 CURRENT_TIMESTAMP：SQLite 存的是 UTC naive
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(CHINA_TZ).isoformat()
