from collections import defaultdict
from typing import Dict, Any, List, Tuple
from src.utils.logger import get_logger

logger = get_logger(__name__)

RESERVOIR_NAMES = ["三门峡", "小浪底", "陆浑", "故县", "河口村"]

# 下大洪水的水文站列表
STATION_NAMES_UPPER = ["花园口", "夹河滩", "高村", "孙口", "艾山", "泺口", "利津"]
STATION_NAMES_LOWER = ["白马寺", "龙门镇", "黑石关", "山路平", "武陟",
                       "花园口", "夹河滩", "高村", "孙口", "艾山", "泺口", "利津"]

EXCESS_FLOW_STATIONS = {"花园口", "孙口"}
EXCESS_FLOW_THRESHOLD = 10000.0
DURATION_THRESHOLD = 4500.0


def build_reservoir_data(cursor) -> Tuple[Dict[str, Any], List[Dict], List[Dict]]:
    """从 Z_Output 表查询并构建水库时序数据 + 统计指标 + 特征值表。

    一次查询完成所有水库的数据提取，避免重复查询。

    Args:
        cursor: Access 数据库 cursor

    Returns:
        (reservoirs, reservoir_stats, reservoir_table)
        - reservoirs: {"小浪底": {"max_inflow": ..., "max_outflow": ...,
                       "max_water_level": ..., "timeseries": [...]}}
        - reservoir_stats: [{"reservoir": "小浪底", "max_inflow": ..., ...}, ...]
        - reservoir_table: [{"name": "小浪底水库", "project": "最大入库(m3/s)", "value": ...}, ...]
    """
    cursor.execute("SELECT stcd, stnm, tm, Qin, Qout, z, v FROM Z_Output")
    rows = cursor.fetchall()
    rows.sort(key=lambda r: (str(r.stcd), str(r.tm)))

    # 按水库名分组
    groups = defaultdict(list)
    for r in rows:
        name = r.stnm.strip() if r.stnm else ''
        groups[name].append(r)

    reservoirs = {}
    reservoir_stats = []
    reservoir_table = []

    for rname in RESERVOIR_NAMES:
        rows = groups.get(rname, [])
        if not rows:
            continue

        # 构建时序数据
        timeseries = []
        for r in rows:
            entry = {"time": str(r.tm)}
            if r.Qin is not None:
                entry["inflow"] = round(float(r.Qin), 2)
            if r.Qout is not None:
                entry["outflow"] = round(float(r.Qout), 2)
            if r.z is not None:
                entry["water_level"] = round(float(r.z), 2)
            if r.v is not None:
                entry["storage"] = round(float(r.v), 2)
            timeseries.append(entry)

        # 计算统计指标
        qin_vals = [r.Qin for r in rows if r.Qin is not None]
        qout_vals = [r.Qout for r in rows if r.Qout is not None]
        z_vals = [r.z for r in rows if r.z is not None]
        v_vals = [r.v for r in rows if r.v is not None]

        max_inflow = round(max(qin_vals), 2) if qin_vals else None
        max_outflow = round(max(qout_vals), 2) if qout_vals else None
        max_water_level = round(max(z_vals), 2) if z_vals else None
        max_storage = round(max(v_vals), 2) if v_vals else None
        min_storage = round(min(v_vals), 2) if v_vals else None
        flood_retention = round(max_storage - min_storage, 2) if max_storage is not None and min_storage is not None else None
        corresponding_storage = None
        if z_vals and v_vals:
            max_z_idx = z_vals.index(max(z_vals))
            corresponding_storage = round(v_vals[max_z_idx], 2) if max_z_idx < len(v_vals) else None

        # 保存数据
        reservoirs[rname] = {
            "max_inflow": max_inflow,
            "max_outflow": max_outflow,
            "max_water_level": max_water_level,
            "timeseries": timeseries,
        }

        reservoir_stats.append({
            "reservoir": rname,
            "max_inflow": max_inflow,
            "max_outflow": max_outflow,
            "flood_retention": flood_retention,
            "max_water_level": max_water_level,
            "corresponding_storage": corresponding_storage,
        })

        # 特征值表
        for project, value in [
            ('最大入库(m3/s)', max_inflow),
            ('最大出库(m3/s)', max_outflow),
            ('滞蓄洪量(亿m3)', flood_retention),
            ('最高水位(m)', max_water_level),
            ('相应蓄量(亿m3)', corresponding_storage),
        ]:
            reservoir_table.append({
                "name": f"{rname}水库",
                "project": project,
                "value": value,
            })

    return reservoirs, reservoir_stats, reservoir_table


def build_hydrological_data(cursor, flood_type: str = "下大洪水") -> Tuple[Dict[str, Any], List[Dict], List[Dict]]:
    """从 Q_Output 表查询并构建水文站时序数据 + 洪峰统计 + 特征值表。

    一次查询完成所有水文站的数据提取，包含超万洪量（花园口/孙口）和超4500历时（花园口）计算。

    Args:
        cursor: Access 数据库 cursor
        flood_type: 洪水类型，"上大洪水" 或 "下大洪水"

    Returns:
        (stations, hydrologic_stats, hydrologic_table)
        - stations: {"花园口": {"max_flow": ..., "timeseries": [...]}}
        - hydrologic_stats: [{"station": "花园口", "peak_flow": ..., ...}, ...]
        - hydrologic_table: [{"name": "花园口站", "project": "洪峰流量(m³/s)", "value": ...}, ...]
    """
    station_names = STATION_NAMES_UPPER if flood_type == "上大洪水" else STATION_NAMES_LOWER

    cursor.execute("SELECT stcd, stnm, tm, q FROM Q_Output")
    rows = cursor.fetchall()
    rows.sort(key=lambda r: (str(r.stnm), str(r.tm)))

    # 按站名分组
    groups = defaultdict(list)
    for r in rows:
        name = r.stnm.strip() if r.stnm else ''
        groups[name].append(r)

    stations = {}
    hydrologic_stats = []
    hydrologic_table = []

    for st_name in station_names:
        rows = groups.get(st_name, [])
        if not rows:
            continue

        # 构建时序数据
        timeseries = []
        for r in rows:
            if r.q is not None:
                timeseries.append({
                    "time": str(r.tm),
                    "flow": round(float(r.q), 2),
                })

        flows = [r.q for r in rows if r.q is not None]
        peak_flow = round(max(flows), 2) if flows else None

        stat = {"station": st_name, "peak_flow": peak_flow}

        # 超万洪量计算（花园口、孙口）
        if st_name in EXCESS_FLOW_STATIONS and peak_flow:
            excess_volume = 0.0
            for i in range(1, len(rows)):
                prev_q, curr_q = rows[i - 1].q, rows[i].q
                if prev_q is None or curr_q is None:
                    continue
                if prev_q > EXCESS_FLOW_THRESHOLD or curr_q > EXCESS_FLOW_THRESHOLD:
                    avg_q = (prev_q + curr_q) / 2
                    if avg_q > EXCESS_FLOW_THRESHOLD:
                        delta_hours = (rows[i].tm - rows[i - 1].tm).total_seconds() / 3600
                        if delta_hours <= 0:
                            delta_hours = 1
                        excess_volume += (avg_q - EXCESS_FLOW_THRESHOLD) * delta_hours
            stat["excess_volume_10000"] = round(excess_volume / 1e8, 4)

        # 超4500历时（花园口）
        if st_name == "花园口" and peak_flow:
            duration_count = sum(1 for q in flows if q > DURATION_THRESHOLD)
            stat["excess_duration_4500"] = duration_count

        stations[st_name] = {
            "max_flow": peak_flow,
            "timeseries": timeseries,
        }

        hydrologic_stats.append(stat)

        hydrologic_table.append({"name": f"{st_name}站", "project": "洪峰流量(m³/s)", "value": peak_flow})
        if "excess_volume_10000" in stat:
            hydrologic_table.append({"name": "", "project": "超万洪量(亿m³)", "value": stat["excess_volume_10000"]})
        if "excess_duration_4500" in stat:
            hydrologic_table.append({"name": "", "project": "超4500历时(h)", "value": stat["excess_duration_4500"]})

    return stations, hydrologic_stats, hydrologic_table
