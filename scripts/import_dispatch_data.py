#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调度方案时间序列数据导入脚本
从 dispatch_scheme_data_base.json 到数据库
"""

import json
import sys
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.services.database.connection import get_db
from src.utils.logger import get_logger

logger = get_logger(__name__)

# 水库名称到编码的映射
STATION_CODE_MAP = {
    "三门峡": "BDA00000111",
    "小浪底": "BDA00000121",
    "陆浑": "BDA80200721",
    "故县": "BDA80000661",
    "河口村": "BDA00000761",
    "龙门镇": "40103800",
    "白马寺": "40103000",
    "黑石关": "40104950",
    "花园口": "40105150",
}

# 指标类型映射
METRIC_MAP = {
    "水位": "level",
    "蓄量": "storage",
    "入库": "inflow",
    "出库": "outflow",
    "流量": "flow",
}

# 单位映射
UNIT_MAP = {
    "level": "m",
    "storage": "亿m³",
    "inflow": "m³/s",
    "outflow": "m³/s",
    "flow": "m³/s",
}


def load_json_data():
    """加载 JSON 数据"""
    json_path = project_root / "data" / "dispatch_scheme_data_base.json"
    if not json_path.exists():
        logger.error(f"JSON 文件不存在: {json_path}")
        return None

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    logger.info(f"成功加载 JSON 数据: {data.get('row_count')} 行, {data.get('column_count')} 列")
    return data


def import_dispatch_data():
    """导入调度方案数据"""
    data = load_json_data()
    if not data:
        return

    db = get_db()

    # 插入调度方案基础信息
    scheme_date = None
    if data.get("data") and len(data["data"]) > 2:
        first_data_row = data["data"][2]
        time_str = first_data_row.get("时间", "")
        if time_str:
            try:
                scheme_date = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S").date()
            except:
                scheme_date = None

    sql_scheme = """
        INSERT INTO dispatch_schemes (scheme_name, scheme_date, data_source, row_count, column_count)
        VALUES (?, ?, ?, ?, ?)
    """
    cursor = db.execute_insert(
        sql_scheme,
        (
            "调度方案时间序列数据",
            scheme_date,
            "dispatch_scheme_data_base.json",
            data.get("row_count"),
            data.get("column_count"),
        ),
    )
    scheme_id = cursor
    logger.info(f"创建调度方案记录, ID: {scheme_id}")

    # 处理数据列
    columns = data.get("columns", [])
    data_rows = data.get("data", [])

    # 跳过前两行（表头和单位行）
    data_rows = data_rows[2:]

    # 建立列索引映射
    column_mapping = {}
    for col in columns:
        station_name = col
        metric_suffix = ""

        if "." in col:
            parts = col.rsplit(".", 1)
            station_name = parts[0]
            metric_suffix = parts[1]
        else:
            if col != "时间":
                metric_suffix = "1"  # 第一列通常是水位

        column_mapping[col] = {
            "station_name": station_name,
            "metric_suffix": metric_suffix,
        }

    # 插入时间序列数据
    count = 0
    batch_size = 500
    batch_data = []

    for row in data_rows:
        timestamp_str = row.get("时间", "")
        if not timestamp_str:
            continue

        try:
            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        except:
            continue

        for col_name, value in row.items():
            if col_name == "时间":
                continue

            if value is None:
                continue

            mapping = column_mapping.get(col_name, {})
            station_name = mapping.get("station_name", col_name)
            metric_suffix = mapping.get("metric_suffix", "")

            # 获取水库编码
            station_code = STATION_CODE_MAP.get(station_name)

            # 确定指标类型
            if col_name.endswith(".1"):
                metric_type = "storage"
                unit = "亿m³"
            elif col_name.endswith(".2"):
                metric_type = "inflow"
                unit = "m³/s"
            elif col_name.endswith(".3"):
                metric_type = "outflow"
                unit = "m³/s"
            else:
                # 非水库列（如龙门镇、白马寺等水文站）
                if station_name in ["龙门镇", "白马寺", "黑石关", "花园口"]:
                    metric_type = "flow"
                    unit = "m³/s"
                else:
                    metric_type = "level"
                    unit = "m"

            batch_data.append(
                (
                    scheme_id,
                    timestamp,
                    station_code,
                    station_name,
                    metric_type,
                    float(value) if value else None,
                    unit,
                )
            )

            count += 1

            # 批量插入
            if len(batch_data) >= batch_size:
                sql_timeseries = """
                    INSERT INTO dispatch_timeseries
                    (scheme_id, timestamp, station_code, station_name, metric_type, metric_value, unit)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """
                for record in batch_data:
                    db.execute_update(sql_timeseries, record)
                batch_data = []

    # 插入剩余数据
    if batch_data:
        sql_timeseries = """
            INSERT INTO dispatch_timeseries
            (scheme_id, timestamp, station_code, station_name, metric_type, metric_value, unit)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        for record in batch_data:
            db.execute_update(sql_timeseries, record)

    logger.info(f"成功导入 {count} 条时间序列数据")


if __name__ == "__main__":
    import_dispatch_data()
