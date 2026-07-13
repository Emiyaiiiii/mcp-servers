from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List


def format_timestamp(value: Any) -> str | None:
    """将时间戳转换为可读日期格式（北京时间 UTC+8）"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if 100000000000 <= value <= 9999999999999:
            beijing_tz = timezone(timedelta(hours=8))
            if value >= 1000000000000:
                dt = datetime.fromtimestamp(value / 1000, tz=beijing_tz)
            else:
                dt = datetime.fromtimestamp(value / 1000, tz=beijing_tz)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        elif 1000000000 <= value <= 9999999999:
            beijing_tz = timezone(timedelta(hours=8))
            dt = datetime.fromtimestamp(value, tz=beijing_tz)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
    return None


def format_date_fields(data: Any) -> Any:
    """递归遍历数据结构，将所有 date 字段的时间戳转换为可读日期"""
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if key in ("date", "dt", "wdate", "tm", "time") and isinstance(value, (int, float)):
                formatted = format_timestamp(value)
                if formatted:
                    result[key] = formatted
                else:
                    result[key] = value
            else:
                result[key] = format_date_fields(value)
        return result
    elif isinstance(data, list):
        return [format_date_fields(item) for item in data]
    else:
        return data
