from typing import Dict, Any, List
from datetime import datetime, timedelta
from collections import defaultdict
from src.utils.logger import get_logger
from src.services.storage.database.data_access import get_db

logger = get_logger(__name__)


def build_model_parameters(
    rainfall_data: Dict[str, Any],
    evapotranspiration_data: Dict[str, Any] = None,
    initial_conditions: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    构建新安江模型参数。

    Args:
        rainfall_data: 降雨数据
        evapotranspiration_data: 蒸发数据（可选）
        initial_conditions: 初始条件（可选）

    Returns:
        模型参数字典
    """
    try:
        params = {}
        
        if rainfall_data:
            params["rainfall"] = rainfall_data
        
        if evapotranspiration_data:
            params["evapotranspiration"] = evapotranspiration_data
        
        if initial_conditions:
            params["initial_conditions"] = initial_conditions
        else:
            params["initial_conditions"] = {
                "soil_moisture": 0.3,
                "groundwater_level": 1.0,
                "surface_storage": 0.0
            }

        params["model_config"] = {
            "version": "Xinanjiang-I",
            "time_step": 1,
            "area": 1000.0
        }

        return params

    except Exception as e:
        logger.error(f"构建模型参数时出错: {str(e)}")
        return {"error": str(e)}


def extract_rainfall_data(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    从记录中提取降雨数据。

    Args:
        records: 原始数据记录

    Returns:
        格式化的降雨数据列表
    """
    try:
        rainfall_list = []
        
        for record in records:
            rainfall = {
                "time": record.get("time", ""),
                "rainfall": record.get("rainfall", 0),
                "station": record.get("station", "")
            }
            rainfall_list.append(rainfall)

        return rainfall_list

    except Exception as e:
        logger.error(f"提取降雨数据时出错: {str(e)}")
        return []


def calculate_rainfall_statistics(rainfall_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    计算降雨统计数据。

    Args:
        rainfall_data: 降雨数据列表

    Returns:
        统计结果，包含总降雨量、最大降雨强度、平均降雨强度等
    """
    try:
        if not rainfall_data:
            return {"message": "无降雨数据"}

        values = [r.get("rainfall", 0) for r in rainfall_data]
        total_rainfall = sum(values)
        max_intensity = max(values) if values else 0
        avg_intensity = round(total_rainfall / len(values), 2) if values else 0
        
        peak_time = None
        if max_intensity > 0:
            for r in rainfall_data:
                if r.get("rainfall") == max_intensity:
                    peak_time = r.get("time")
                    break

        return {
            "total_rainfall": total_rainfall,
            "max_intensity": max_intensity,
            "avg_intensity": avg_intensity,
            "peak_time": peak_time,
            "data_points": len(values)
        }

    except Exception as e:
        logger.error(f"计算降雨统计时出错: {str(e)}")
        return {"error": str(e)}


def validate_model_input(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    验证模型输入数据。

    Args:
        data: 输入数据

    Returns:
        验证结果，包含是否有效和错误信息
    """
    try:
        errors = []
        
        if "rainfall" not in data:
            errors.append("缺少降雨数据")
        elif not data["rainfall"]:
            errors.append("降雨数据为空")
        
        if "initial_conditions" in data and not isinstance(data["initial_conditions"], dict):
            errors.append("初始条件格式错误")

        return {
            "valid": len(errors) == 0,
            "errors": errors
        }

    except Exception as e:
        logger.error(f"验证模型输入时出错: {str(e)}")
        return {"valid": False, "errors": [str(e)]}


def parse_model_output(output: Dict[str, Any]) -> Dict[str, Any]:
    """
    解析模型输出结果。

    Args:
        output: 模型原始输出

    Returns:
        解析后的结果，包含流量、水位等预测数据
    """
    try:
        result = {}
        
        if output.get("status") == "success":
            result["status"] = "success"
            result["message"] = output.get("message", "计算成功")
            
            if "results" in output:
                results = output["results"]
                result["flow_forecast"] = results.get("flow", [])
                result["level_forecast"] = results.get("level", [])
                result["runoff"] = results.get("runoff", 0)
                result["evapotranspiration"] = results.get("evapotranspiration", 0)
            
            if "statistics" in output:
                result["statistics"] = output["statistics"]
        else:
            result["status"] = "error"
            result["message"] = output.get("message", "计算失败")

        return result

    except Exception as e:
        logger.error(f"解析模型输出时出错: {str(e)}")
        return {"status": "error", "message": str(e)}


def query_weighted_rainfall_from_db(start: str, end: str) -> Dict[str, Any]:
    """
    从本地数据库 rainfall_hourly 表查询逐小时降雨数据，
    结合 rainfall_stations 表的 weight_area 计算加权平均面雨量。

    Returns: {"code": 200, "data": {timestamp: weighted_rainfall}, "station_count": N}
    """
    db = get_db()
    
    hourly_sql = """
        SELECT rh.station_code, rh.station_name, rh.timestamp, rh.rainfall,
               rs.weight_area
        FROM rainfall_hourly rh
        LEFT JOIN rainfall_stations rs ON rh.station_code = rs.code
        WHERE rh.timestamp >= ? AND rh.timestamp < ?
        ORDER BY rh.timestamp, rh.station_code
    """
    raw_records = db.execute_query(hourly_sql, (start, end))
    
    if not raw_records:
        logger.warning(f"数据库查询到 {start}~{end} 无降雨数据")
        return {"code": 200, "data": {}, "station_count": 0}
    
    time_groups = defaultdict(list)
    station_weights = {}
    
    for rec in raw_records:
        ts = rec['timestamp']
        station_code = rec['station_code']
        rainfall = rec['rainfall'] if rec['rainfall'] is not None else 0.0
        weight_area = rec['weight_area'] if rec['weight_area'] is not None else 0.0
        
        time_groups[ts].append({
            'station_code': station_code,
            'rainfall': rainfall,
            'weight_area': weight_area
        })
        if station_code not in station_weights:
            station_weights[station_code] = weight_area
    
    weighted_rainfall = {}
    for ts, records in sorted(time_groups.items()):
        total_weighted = 0.0
        total_weight = 0.0
        for r in records:
            w = r['weight_area']
            total_weighted += r['rainfall'] * w
            total_weight += w
        
        if total_weight > 0:
            weighted_rainfall[str(ts)] = round(total_weighted / total_weight, 2)
        else:
            weighted_rainfall[str(ts)] = round(
                sum(r['rainfall'] for r in records) / len(records), 2
            )
    
    logger.info(
        f"从数据库获取降雨数据成功，涉及 {len(station_weights)} 个雨量站，"
        f"{len(weighted_rainfall)} 个时段"
    )
    
    return {
        "code": 200,
        "data": weighted_rainfall,
        "station_count": len(station_weights),
        "stations": list(station_weights.keys())
    }


def build_rainfall_array(
    weighted_data: Dict[str, Any],
    start: str,
    end: str,
    hours: int
) -> List[float]:
    """
    将加权面雨量字典按时间顺序转为等时段数组。
    缺少数据的时段用 0 填充。
    """
    rainfall_values = []
    dt_start = datetime.strptime(start, "%Y-%m-%d %H:%M:%S")
    
    rainfall_map = weighted_data.get("data", {})
    
    for i in range(hours):
        current_ts = (dt_start + timedelta(hours=i)).strftime("%Y-%m-%d %H:%M:%S")
        val = rainfall_map.get(current_ts, 0.0)
        rainfall_values.append(val)
    
    if all(v == 0.0 for v in rainfall_values):
        logger.warning("所有时段降雨量均为0，使用默认值0.1mm")
        rainfall_values = [0.1] * hours
    
    logger.info(
        f"构建等时段面雨量数组: 共{len(rainfall_values)}个时段, "
        f"最大值={max(rainfall_values)}mm, 平均值={round(sum(rainfall_values)/len(rainfall_values), 2)}mm"
    )
    return rainfall_values


def build_control_params(config: Dict[str, Any], custom: Dict[str, Any] = None, basin_area: float = 1000.0) -> Dict[str, Any]:
    """
    构建新安江模型控制参数。
    """
    skip_keys = {'id', 'station_name', 'station_type', 'station_code', 'basin_name', 'basin_area', 'description', 'created_at', 'updated_at'}
    params = {k: v for k, v in config.items() if k not in skip_keys}
    if custom:
        params.update(custom)
        logger.info(f"使用自定义参数覆盖默认值: {custom}")
    
    return {
        "ncName": "control",
        "type": "hydraulic_elements",
        "dimensionsList": [],
        "variablesList": [],
        "globalList": [
            {"type": "float", "name": "KC", "fullName": "流域蒸散发折算系数(KC)", "value": str(params.get('KC', 0.9))},
            {"type": "float", "name": "B", "fullName": "流域蓄水容量分布曲线指数(B)", "value": str(params.get('B', 0.4))},
            {"type": "int", "name": "UM", "fullName": "上层张力水容量(UM)", "value": str(params.get('UM', 30))},
            {"type": "int", "name": "LM", "fullName": "下层张力水容量(LM)", "value": str(params.get('LM', 80))},
            {"type": "float", "name": "EX", "fullName": "流域自由水容量分布曲线指数(EX)", "value": str(params.get('EX', 1.5))},
            {"type": "float", "name": "C", "fullName": "深层蒸散发折算系数(C)", "value": str(params.get('C', 0.12))},
            {"type": "float", "name": "IM", "fullName": "不透水面积比例(IM)", "value": str(params.get('IM', 0))},
            {"type": "float", "name": "WM", "fullName": "张力水容量(WM)", "value": str(params.get('WM', 120))},
            {"type": "float", "name": "SM", "fullName": "自由水客量(SM)", "value": str(params.get('SM', 25))},
            {"type": "float", "name": "KG", "fullName": "地下水日出流系数(KG)", "value": str(params.get('KG', 0.3))},
            {"type": "float", "name": "KI", "fullName": "壤中流日出流系数(KI)", "value": str(params.get('KI', 0.3))},
            {"type": "float", "name": "CS", "fullName": "地表水流消退系数(CS)", "value": str(params.get('CS', 0.8))},
            {"type": "float", "name": "CG", "fullName": "地下水日消退系数(CG)", "value": str(params.get('CG', 1))},
            {"type": "float", "name": "CI", "fullName": "壤中流日消退系数(CI)", "value": str(params.get('CI', 1))},
            {"type": "float", "name": "CR", "fullName": "日模型河网蓄水消退系数(CR)", "value": str(params.get('CR', 0.2))},
            {"type": "double", "name": "BA", "fullName": "流域面积(BA)", "value": str(params.get('basin_area', basin_area))},
            {"type": "float", "name": "XE", "fullName": "马斯京跟法演算参数(XE)", "value": str(params.get('XE', 0.2))},
            {"type": "int", "name": "KE", "fullName": "马斯京跟法演算参数(KE)", "value": str(params.get('KE', 1))}
        ]
    }


def build_rainfall_data(rainfall_values: List[float], start: str, end: str) -> Dict[str, Any]:
    """
    构建降雨数据NC文件参数。
    """
    return {
        "ncName": "p",
        "type": "hydraulic_elements",
        "dimensionsList": [{"name": "TM", "fullName": "时间维度", "value": len(rainfall_values)}],
        "variablesList": [{
            "valueType": "float",
            "ArrayType": "array1d",
            "name": "PA",
            "fullName": "降雨量",
            "arrayValue": [str(v) for v in rainfall_values],
            "dimensionsSort": ["TM"],
            "arrayType": "array1d"
        }],
        "globalList": [
            {"type": "string", "name": "BGTM", "fullName": "开始时间", "value": start},
            {"type": "string", "name": "EDTM", "fullName": "结束时间", "value": end},
            {"type": "string", "name": "DT_UNIT", "fullName": "时间间隔单位", "value": "H"},
            {"type": "float", "name": "DT", "fullName": "时间间隔", "value": "1"}
        ]
    }


def build_etp_data(length: int, start: str, end: str) -> Dict[str, Any]:
    """
    构建蒸散发数据NC文件参数。
    """
    return {
        "ncName": "em",
        "type": "hydraulic_elements",
        "dimensionsList": [{"name": "TM", "fullName": "时间维度", "value": length}],
        "variablesList": [{
            "valueType": "float",
            "ArrayType": "array1d",
            "name": "ETP",
            "fullName": "蒸散发值",
            "arrayValue": ["0" for _ in range(length)],
            "dimensionsSort": ["TM"],
            "arrayType": "array1d"
        }],
        "globalList": [
            {"type": "string", "name": "BGTM", "fullName": "开始时间", "value": start},
            {"type": "string", "name": "EDTM", "fullName": "结束时间", "value": end},
            {"type": "string", "name": "DT_UNIT", "fullName": "时间间隔单位", "value": "H"},
            {"type": "float", "name": "DT", "fullName": "时间间隔", "value": "1"}
        ]
    }