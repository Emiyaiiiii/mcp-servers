from typing import Dict, Any, List, Tuple
from datetime import datetime, timedelta
from src.utils.logger import get_logger

logger = get_logger(__name__)


def extract_q_statistics(data: Dict[str, Any], station_name: str) -> Dict[str, Any]:
    """
    从Q_Output数据中提取统计指标。

    Args:
        data: Q_Output返回数据
        station_name: 水文站名称

    Returns:
        统计结果，包含最大/最小/平均流量、峰值时间、趋势等
    """
    try:
        records = data.get("data", {}).get("records", [])
        if not records:
            return {
                "station": station_name,
                "message": "无数据",
                "max_q": None,
                "min_q": None,
                "avg_q": None,
                "peak_time": None,
                "peak_q": None,
                "current_q": None,
                "trend": "稳定",
                "data": []
            }

        flow_list = []
        time_list = []
        
        for record in records:
            flow = record.get("flow")
            time_str = record.get("time")
            if flow is not None:
                flow_list.append(float(flow))
                if time_str:
                    time_list.append(time_str)

        if not flow_list:
            return {
                "station": station_name,
                "message": "无有效流量数据",
                "max_q": None,
                "min_q": None,
                "avg_q": None,
                "peak_time": None,
                "peak_q": None,
                "current_q": None,
                "trend": "稳定",
                "data": []
            }

        max_q = max(flow_list)
        min_q = min(flow_list)
        avg_q = round(sum(flow_list) / len(flow_list), 2)
        
        peak_index = flow_list.index(max_q)
        peak_time = time_list[peak_index] if peak_index < len(time_list) else None

        current_q = flow_list[-1]
        if len(flow_list) >= 2:
            prev_q = flow_list[-2]
            if current_q > prev_q * 1.1:
                trend = "上涨"
            elif current_q < prev_q * 0.9:
                trend = "下降"
            else:
                trend = "稳定"
        else:
            trend = "稳定"

        return {
            "station": station_name,
            "max_q": max_q,
            "min_q": min_q,
            "avg_q": avg_q,
            "peak_time": peak_time,
            "peak_q": max_q,
            "current_q": current_q,
            "trend": trend,
            "data": [{"time": t, "flow": f} for t, f in zip(time_list, flow_list)]
        }

    except Exception as e:
        logger.error(f"提取Q统计数据时出错: {str(e)}")
        return {"error": str(e)}


def extract_z_statistics(data: Dict[str, Any], station_name: str) -> Dict[str, Any]:
    """
    从Z_Output数据中提取统计指标。

    Args:
        data: Z_Output返回数据
        station_name: 水文站名称

    Returns:
        统计结果，包含最大/最小/平均水位、峰值时间、趋势等
    """
    try:
        records = data.get("data", {}).get("records", [])
        if not records:
            return {
                "station": station_name,
                "message": "无数据",
                "max_z": None,
                "min_z": None,
                "avg_z": None,
                "peak_time": None,
                "peak_z": None,
                "current_z": None,
                "trend": "稳定",
                "data": []
            }

        level_list = []
        time_list = []
        
        for record in records:
            level = record.get("level")
            time_str = record.get("time")
            if level is not None:
                level_list.append(float(level))
                if time_str:
                    time_list.append(time_str)

        if not level_list:
            return {
                "station": station_name,
                "message": "无有效水位数据",
                "max_z": None,
                "min_z": None,
                "avg_z": None,
                "peak_time": None,
                "peak_z": None,
                "current_z": None,
                "trend": "稳定",
                "data": []
            }

        max_z = max(level_list)
        min_z = min(level_list)
        avg_z = round(sum(level_list) / len(level_list), 2)
        
        peak_index = level_list.index(max_z)
        peak_time = time_list[peak_index] if peak_index < len(time_list) else None

        current_z = level_list[-1]
        if len(level_list) >= 2:
            prev_z = level_list[-2]
            if current_z > prev_z * 1.01:
                trend = "上涨"
            elif current_z < prev_z * 0.99:
                trend = "下降"
            else:
                trend = "稳定"
        else:
            trend = "稳定"

        return {
            "station": station_name,
            "max_z": max_z,
            "min_z": min_z,
            "avg_z": avg_z,
            "peak_time": peak_time,
            "peak_z": max_z,
            "current_z": current_z,
            "trend": trend,
            "data": [{"time": t, "level": l} for t, l in zip(time_list, level_list)]
        }

    except Exception as e:
        logger.error(f"提取Z统计数据时出错: {str(e)}")
        return {"error": str(e)}


def calculate_forecast_statistics(q_data: Dict[str, Any], z_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    综合计算预报统计数据。

    Args:
        q_data: 流量数据
        z_data: 水位数据

    Returns:
        综合统计结果
    """
    try:
        result = {}
        
        if q_data:
            q_stats = extract_q_statistics(q_data, "")
            result.update({
                "max_flow": q_stats.get("max_q"),
                "min_flow": q_stats.get("min_q"),
                "avg_flow": q_stats.get("avg_q"),
                "peak_flow": q_stats.get("peak_q"),
                "peak_flow_time": q_stats.get("peak_time"),
                "current_flow": q_stats.get("current_q"),
                "flow_trend": q_stats.get("trend"),
                "flow_data": q_stats.get("data", [])
            })
        
        if z_data:
            z_stats = extract_z_statistics(z_data, "")
            result.update({
                "max_level": z_stats.get("max_z"),
                "min_level": z_stats.get("min_z"),
                "avg_level": z_stats.get("avg_z"),
                "peak_level": z_stats.get("peak_z"),
                "peak_level_time": z_stats.get("peak_time"),
                "current_level": z_stats.get("current_z"),
                "level_trend": z_stats.get("trend"),
                "level_data": z_stats.get("data", [])
            })

        return result

    except Exception as e:
        logger.error(f"计算综合统计数据时出错: {str(e)}")
        return {"error": str(e)}


def aggregate_reservoir_data(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    聚合水库数据，提取关键指标。

    Args:
        records: 水库记录列表

    Returns:
        聚合后的统计数据
    """
    try:
        if not records:
            return {"message": "无数据"}

        result = {}
        for record in records:
            reservoir_name = record.get("reservoirName", "未知")
            result[reservoir_name] = {
                "reservoirName": reservoir_name,
                "currentLevel": record.get("currentLevel"),
                "warningLevel": record.get("warningLevel"),
                "limitLevel": record.get("limitLevel"),
                "deadLevel": record.get("deadLevel"),
                "damLevel": record.get("damLevel"),
                "currentStorage": record.get("currentStorage"),
                "totalStorage": record.get("totalStorage"),
                "inflow": record.get("inflow"),
                "outflow": record.get("outflow"),
                "levelStatus": record.get("levelStatus"),
                "storagePercent": round(record.get("currentStorage", 0) / record.get("totalStorage", 1) * 100, 2) if record.get("totalStorage") else 0
            }

        return result

    except Exception as e:
        logger.error(f"聚合水库数据时出错: {str(e)}")
        return {"error": str(e)}


def calculate_reservoir_stats(conn) -> Tuple[List, List]:
    """从 Z_Output 表中提取各水库的关键统计指标（exe 运行后生成）

    Z_Output 表结构: stcd, stnm, tm, Qin(入库), Qout(出库), z(水位), v(蓄量)

    Returns:
        (reservoir_stats, reservoir_table)
        reservoir_stats: [{"reservoir": "三门峡", "max_inflow": ..., ...}, ...]
        reservoir_table: 特征值格式，每行 {"name": "三门峡水库", "project": "最大入库(m3/s)", "value": 1420.0}
    """
    from typing import Tuple
    stats = []
    RESERVOIR_NAMES = ["三门峡", "小浪底", "陆浑", "故县", "河口村"]

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT stcd, stnm, tm, Qin, Qout, z, v FROM Z_Output")
        rows = cursor.fetchall()
        rows.sort(key=lambda r: (str(r.stcd), str(r.tm)))

        if not rows:
            logger.warning("Z_Output 表为空，无法提取水库统计指标")
            return [], []

        for rname in RESERVOIR_NAMES:
            reservoir_rows = [r for r in rows if (r.stnm.strip() if r.stnm else '') == rname]
            if not reservoir_rows:
                continue

            qin_values = [r.Qin for r in reservoir_rows]
            qout_values = [r.Qout for r in reservoir_rows]
            z_values = [r.z for r in reservoir_rows]
            v_values = [r.v for r in reservoir_rows]

            max_inflow = max(qin_values)
            max_outflow = max(qout_values)
            max_water_level = max(z_values)
            max_storage = max(v_values)
            min_storage = min(v_values)
            flood_retention = max_storage - min_storage

            max_z_idx = z_values.index(max_water_level)
            corresponding_storage = v_values[max_z_idx]

            stats.append({
                "reservoir": rname,
                "max_inflow": round(float(max_inflow), 2),
                "max_outflow": round(float(max_outflow), 2),
                "flood_retention": round(float(flood_retention), 2),
                "max_water_level": round(float(max_water_level), 2),
                "corresponding_storage": round(float(corresponding_storage), 2)
            })

        reservoir_table = []
        for s in stats:
            rname = s['reservoir'] + '水库'
            rows_data = [
                (rname, '最大入库(m3/s)', s['max_inflow']),
                ('', '最大出库(m3/s)', s['max_outflow']),
                ('', '滞蓄洪量(亿m3)', s['flood_retention']),
                ('', '最高水位(m)', s['max_water_level']),
                ('', '相应蓄量(亿m3)', s['corresponding_storage']),
            ]
            for name, project, value in rows_data:
                reservoir_table.append({
                    "name": name,
                    "project": project,
                    "value": value
                })

        return stats, reservoir_table

    except Exception as e:
        logger.warning(f"从 Z_Output 提取水库统计指标失败: {e}")
        return [], []


def calculate_hydrologic_stats(conn, flood_type: str = "下大洪水") -> Tuple[List, List]:
    """从 Q_Output 表计算各水文站洪峰流量、超万洪量、花园口超4500历时
    
    Returns:
        (hydrologic_stats, hydrologic_table)
    """
    from typing import Tuple
    if flood_type == "上大洪水":
        STATIONS = ["花园口", "夹河滩", "高村", "孙口", "艾山", "泺口", "利津"]
    else:
        STATIONS = ["白马寺", "龙门镇", "黑石关", "山路平", "武陟", "花园口", "夹河滩", "高村", "孙口", "艾山", "泺口", "利津"]
    
    EXCESS_FLOW_STATIONS = ["花园口", "孙口"]
    EXCESS_FLOW_THRESHOLD = 10000.0
    DURATION_THRESHOLD = 4500.0
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT stcd, stnm, tm, q FROM Q_Output")
        rows = cursor.fetchall()
        rows.sort(key=lambda r: (str(r.stnm), str(r.tm)))
        
        if not rows:
            return [], []
        
        stats = []
        for st_name in STATIONS:
            station_rows = [(r.tm, r.q) for r in rows if (r.stnm.strip() if r.stnm else '') == st_name]
            if not station_rows:
                continue
            
            flows = [q for _, q in station_rows]
            peak_flow = round(max(flows), 2)
            
            stat = {"station": st_name, "peak_flow": peak_flow}
            
            if st_name in EXCESS_FLOW_STATIONS:
                excess_volume = 0.0
                for i in range(1, len(station_rows)):
                    prev_tm, prev_q = station_rows[i-1]
                    curr_tm, curr_q = station_rows[i]
                    if prev_q > EXCESS_FLOW_THRESHOLD or curr_q > EXCESS_FLOW_THRESHOLD:
                        avg_q = (prev_q + curr_q) / 2
                        if avg_q > EXCESS_FLOW_THRESHOLD:
                            delta_hours = (curr_tm - prev_tm).total_seconds() / 3600
                            if delta_hours <= 0:
                                delta_hours = 1
                            excess_volume += (avg_q - EXCESS_FLOW_THRESHOLD) * delta_hours
                stat["excess_volume_10000"] = round(excess_volume / 1e8, 4)
            
            if st_name == "花园口":
                duration_count = sum(1 for _, q in station_rows if q > DURATION_THRESHOLD)
                stat["excess_duration_4500"] = duration_count
            
            stats.append(stat)
        
        hydrologic_table = []
        for s in stats:
            st_label = s["station"] + "站"
            hydrologic_table.append({"name": st_label, "project": "洪峰流量(m³/s)", "value": s["peak_flow"]})
            if "excess_volume_10000" in s:
                hydrologic_table.append({"name": "", "project": "超万洪量(亿m³)", "value": s["excess_volume_10000"]})
            if "excess_duration_4500" in s:
                hydrologic_table.append({"name": "", "project": "超4500历时(h)", "value": s["excess_duration_4500"]})
        
        return stats, hydrologic_table
    
    except Exception as e:
        logger.warning(f"从 Q_Output 提取水文统计指标失败: {e}")
        return [], []