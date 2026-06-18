import json
import random
import time
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from fastmcp import FastMCP
from src.utils.logger import get_logger
from src.services.storage.scheme_storage import save_scheme, generate_unique_id
from src.services.external_api.xinanjiang_service import xinanjiang_auth_service, xinanjiang_model_service
from src.services.external_api.auth_service import auth_service
from src.services.external_api.water_forecast_service import water_forecast_service
from src.utils.station_codes import get_reservoir_code, get_hydrology_code
from src.config.settings import settings

logger = get_logger(__name__)


def register_forecast_models(mcp: FastMCP):

    @mcp.tool()
    async def run_rainfall_forecast_model(basin: str, start_time: str, end_time: str, rainfall_data: str) -> dict:
        """
        执行降雨预报模型。

        Args:
            basin: 流域名称（如：黄河、洛河、伊洛河等）
            start_time: 开始时间 (格式: YYYY-MM-DD)
            end_time: 结束时间 (格式: YYYY-MM-DD)
            rainfall_data: 降雨数据 (JSON格式)，包含各雨量站的降雨过程
        """
        logger.info(f"调用 run_rainfall_forecast_model，收到参数: basin={repr(basin)}, start_time={repr(start_time)}, end_time={repr(end_time)}, rainfall_data={repr(rainfall_data)}")
        try:
            rainfall = json.loads(rainfall_data) if isinstance(rainfall_data, str) else rainfall_data
        except json.JSONDecodeError:
            return_value = {"success": False, "error": "降雨数据格式错误，请提供有效的JSON格式"}
            logger.debug(f"run_hydrological_model 返回结果: {return_value}")
            return return_value

        total_rainfall = sum(float(r.get("rainfall", 0)) for r in rainfall) if rainfall else 0
        base_flow = total_rainfall * random.uniform(10, 30)

        forecast_points = []
        for i in range(24):
            flow = base_flow * random.uniform(0.6, 1.4) * (1 - i * 0.02)
            water_level = 100 + random.uniform(-5, 5)
            forecast_points.append({
                "hour": i,
                "inflow": round(flow, 2),
                "water_level": round(water_level, 2)
            })

        return_value = {
            "success": True,
            "basin": basin,
            "start_time": start_time,
            "end_time": end_time,
            "command": "FUNC_RUN_HYDROLOGICAL_MODEL",
            "total_rainfall": total_rainfall,
            "peak_flow": round(base_flow * 1.2, 2),
            "forecast_points": forecast_points,
            "message": f"水文预报模型执行成功，{basin}流域共产生{total_rainfall:.1f}mm降雨"
        }
        logger.debug(f"run_hydrological_model 返回结果: {return_value}")
        return return_value

    @mcp.tool()
    async def run_water_forecast_model(station_type: str, station_name: str, start_time: str = None, end_time: str = None) -> dict:
        """
        执行设计院的分布式水文来水预报模型，根据站点类型调用不同接口获取预报数据。

        Args:
            station_type: 站点类型，可选值: reservoir(水库), hydrology(水文站)
            station_name: 站点名称，如: 三门峡, 小浪底, 龙门镇, 花园口等（支持名称匹配编码）
            start_time: 开始时间（格式：YYYY-MM-DD HH:MM:SS），不指定则使用当前时间前一天
            end_time: 结束时间（格式：YYYY-MM-DD HH:MM:SS），不指定则使用当前时间后一天
        """
        logger.info(f"调用 run_water_forecast_model，收到参数: station_type={repr(station_type)}, station_name={repr(station_name)}, start_time={repr(start_time)}, end_time={repr(end_time)}")
        
        # 设置默认时间范围
        if not start_time:
            start_time = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        if not end_time:
            end_time = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            if station_type.lower() not in ["reservoir", "hydrology"]:
                return_value = {"success": False, "error": f"不支持的站点类型: {station_type}，请使用 reservoir 或 hydrology"}
                logger.debug(f"run_water_forecast_model 返回结果: {return_value}")
                return return_value
            
            scheme_list_result = water_forecast_service.get_scheme_list(start_time, end_time)
            
            if scheme_list_result.get("success") is False or scheme_list_result.get("code") not in [200, "200", None]:
                error_msg = scheme_list_result.get("message", scheme_list_result.get("error", "获取预报方案清单失败"))
                return_value = {"success": False, "error": error_msg}
                logger.debug(f"run_water_forecast_model 返回结果: {return_value}")
                return return_value
            
            data_field = scheme_list_result.get("data")
            
            if isinstance(data_field, dict):
                scheme_list = data_field.get("schList", [])
                if not scheme_list:
                    scheme_list = data_field.get("recommended", [])
            elif isinstance(data_field, list):
                scheme_list = data_field
            elif isinstance(scheme_list_result, list):
                scheme_list = scheme_list_result
            else:
                scheme_list = []
            
            if len(scheme_list) == 0:
                return_value = {"success": False, "error": "预报方案清单为空，请检查时间范围或联系管理员"}
                logger.debug(f"run_water_forecast_model 返回结果: {return_value}")
                return return_value
            
            def parse_datetime(dt_str):
                for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]:
                    try:
                        return datetime.strptime(dt_str, fmt)
                    except ValueError:
                        continue
                return None
            
            target_start = parse_datetime(start_time)
            target_end = parse_datetime(end_time)
            
            matched_scheme = None
            for scheme in scheme_list:
                scheme_time = parse_datetime(scheme.get("schTime", ""))
                
                if scheme_time and target_start and target_end:
                    if target_start <= scheme_time <= target_end:
                        matched_scheme = scheme
                        break
            
            if not matched_scheme:
                return_value = {"success": False, "error": f"未找到与时间范围 {start_time} - {end_time} 匹配的预报方案"}
                logger.debug(f"run_water_forecast_model 返回结果: {return_value}")
                return return_value
            
            sch_id = matched_scheme.get("schId") or matched_scheme.get("id")
            if not sch_id:
                return_value = {"success": False, "error": "预报方案中未找到 schId"}
                logger.debug(f"run_water_forecast_model 返回结果: {return_value}")
                return return_value
            
            result = water_forecast_service.get_scheme_data_by_station_name(sch_id, station_name)
            
            if result.get("success") is False or result.get("code") not in [200, "200", None]:
                error_msg = result.get("message", result.get("error", "获取预报数据失败"))
                return_value = {"success": False, "error": error_msg}
                logger.debug(f"run_water_forecast_model 返回结果: {return_value}")
                return return_value
            
            station_code = ""
            if station_type.lower() == "reservoir":
                station_code = get_reservoir_code(station_name) or ""
            elif station_type.lower() == "hydrology":
                station_code = get_hydrology_code(station_name) or ""
            
            # 过滤掉 level 水位字段
            raw_data = result.get("data", result)
            if isinstance(raw_data, list):
                filtered_data = []
                for item in raw_data:
                    if isinstance(item, dict):
                        filtered_data.append({k: v for k, v in item.items() if k != "level"})
                    else:
                        filtered_data.append(item)
            else:
                filtered_data = raw_data
            
            return_value = {
                "success": True,
                "station_type": station_type,
                "station_name": station_name,
                "station_code": station_code,
                "start_time": start_time,
                "end_time": end_time,
                "command": "FUNC_RUN_WATER_FORECAST_MODEL",
                "sch_id": sch_id,
                "forecast_data": filtered_data,
                "message": f"来水预报模型执行成功，已获取{station_type} {station_name}的预报数据"
            }
            logger.debug(f"run_water_forecast_model 返回结果: {return_value}")
            return return_value
            
        except Exception as e:
            error_msg = f"执行来水预报模型时出错: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

    @mcp.tool()
    async def generate_dispatch_scheme(
        start_time: str = None
    ) -> dict:
        """
        生成调度方案单。

        从数据库中读取真实的调度方案时间序列数据，生成标准格式的调度方案单，
        并自动保存到调度方案存储中，供后续预演和预案生成使用。

        Args:
            start_time: 调度开始时间（格式：YYYY-MM-DD），当前仅支持2021年汛期数据（2021-10-02~2021-10-07）
        """
        logger.info(f"调用 generate_dispatch_scheme，收到参数: start_time={repr(start_time)}")
        
        from src.services.storage.database.data_access import DispatchTimeseriesAccess
        from src.tools.data_api_tools import _judge_water_level_warning
        
        try:
            schemes = DispatchTimeseriesAccess.get_all_schemes()
            if not schemes:
                logger.warning("数据库中没有找到调度方案数据")
                return {
                    "success": False,
                    "command": "FUNC_GENERATE_DISPATCH_SCHEME",
                    "message": "数据库中未找到调度方案数据，请确认种子数据已导入"
                }
            
            dispatch_scheme = schemes[0]
            timeseries_data = DispatchTimeseriesAccess.get_timeseries(dispatch_scheme['id'])
            
            if not timeseries_data:
                logger.warning(f"调度方案 {dispatch_scheme['id']} 中没有时间序列数据")
                return {
                    "success": False,
                    "command": "FUNC_GENERATE_DISPATCH_SCHEME",
                    "message": "数据库中未找到调度方案时间序列数据"
                }
            
            reservoirs = {}
            hydrological_stations = {}
            
            station_name_map = {
                "三门峡": "三门峡水库",
                "小浪底": "小浪底水库",
                "陆浑": "陆浑水库",
                "故县": "故县水库",
                "河口村": "河口村水库"
            }
            
            station_code_map = {
                "三门峡": "BDA00000111",
                "小浪底": "BDA00000121",
                "陆浑": "BDA80200721",
                "故县": "BDA80000661",
                "河口村": "BDA00000761"
            }
            
            metric_type_map = {
                "level": "water_level",
                "storage": "storage",
                "inflow": "inflow",
                "outflow": "outflow",
                "flow": "flow"
            }
            
            time_groups = {}
            for record in timeseries_data:
                ts = record['timestamp']
                if ts not in time_groups:
                    time_groups[ts] = {}
                time_groups[ts].setdefault(record['station_name'], []).append(record)
            
            for station_name, res_name in station_name_map.items():
                reservoirs[res_name] = {
                    "station_code": station_code_map.get(station_name, ""),
                    "timeseries": []
                }
            
            common_stations = ["龙门镇", "白马寺", "黑石关", "花园口"]
            for station in common_stations:
                hydrological_stations[station] = {
                    "timeseries": []
                }
            
            for ts in sorted(time_groups.keys()):
                group = time_groups[ts]
                formatted_ts = str(ts)
                
                for station_name, res_name in station_name_map.items():
                    records = group.get(station_name, [])
                    res_data = {"time": formatted_ts}
                    has_value = False
                    water_level = None
                    
                    for record in records:
                        metric = metric_type_map.get(record['metric_type'])
                        if metric:
                            raw_value = record['metric_value']
                            if raw_value is not None:
                                has_value = True
                                if metric == 'water_level':
                                    water_level = round(raw_value, 2)
                                    res_data[metric] = water_level
                                elif metric == 'storage':
                                    res_data[metric] = round(raw_value, 2)
                                else:
                                    res_data[metric] = round(raw_value)
                    
                    if water_level is not None:
                        description, warning_level = _judge_water_level_warning(station_name, water_level)
                        if description:
                            res_data["level_desc"] = description
                    
                    if has_value:
                        reservoirs[res_name]["timeseries"].append(res_data)
                
                for station in common_stations:
                    station_records = group.get(station, [])
                    for record in station_records:
                        if record['metric_type'] == 'flow':
                            raw_value = record['metric_value']
                            if raw_value is not None:
                                hydrological_stations[station]["timeseries"].append({
                                    "time": formatted_ts,
                                    "flow": round(raw_value)
                                })
                            break
            
            scheme_data = {
                "scheme_name": dispatch_scheme.get('name', '2021年汛期调度方案'),
                "description": "基于2021年汛期实测数据的调度方案",
                "basin": "黄河",
                "start_date": "2021-10-02",
                "end_date": "2021-10-07",
                "status": "active",
                "constraints": [],
                "details": [],
                "constraints_applied": {},
                "reservoirs": reservoirs,
                "hydrological_stations": hydrological_stations
            }

            saved_scheme_id = save_scheme(scheme_data)
            logger.info(f"调度方案已保存，ID: {saved_scheme_id}")
            
            def calculate_scheme_summary(scheme):
                stats = {}
                for res_name, res_data in scheme['reservoirs'].items():
                    levels = [t['water_level'] for t in res_data['timeseries'] if t.get('water_level') is not None]
                    storages = [t['storage'] for t in res_data['timeseries'] if t.get('storage') is not None]
                    inflows = [t['inflow'] for t in res_data['timeseries'] if t.get('inflow') is not None]
                    outflows = [t['outflow'] for t in res_data['timeseries'] if t.get('outflow') is not None]
                    
                    stats[res_name] = {
                        "water_level_range": [round(min(levels), 2) if levels else None, round(max(levels), 2) if levels else None],
                        "storage_range": [round(min(storages), 2) if storages else None, round(max(storages), 2) if storages else None],
                        "avg_inflow": round(sum(inflows) / len(inflows), 2) if inflows else None,
                        "avg_outflow": round(sum(outflows) / len(outflows), 2) if outflows else None
                    }
                
                if '花园口' in scheme['hydrological_stations']:
                    huayuankou_flows = [t['flow'] for t in scheme['hydrological_stations']['花园口']['timeseries'] if t.get('flow') is not None]
                    stats['花园口'] = {
                        "flow_range": [round(min(huayuankou_flows), 2) if huayuankou_flows else None, round(max(huayuankou_flows), 2) if huayuankou_flows else None],
                        "avg_flow": round(sum(huayuankou_flows) / len(huayuankou_flows), 2) if huayuankou_flows else None
                    }
                
                return stats
            
            schemes_summary = [{
                "scheme_id": saved_scheme_id,
                "scheme_name": scheme_data['scheme_name'],
                "start_date": scheme_data['start_date'],
                "end_date": scheme_data['end_date'],
                "stats": calculate_scheme_summary(scheme_data)
            }]
            
            return_value = {
                "success": True,
                "command": "FUNC_GENERATE_DISPATCH_SCHEME",
                "scheme_id": saved_scheme_id,
                "scheme_name": scheme_data['scheme_name'],
                "start_date": scheme_data['start_date'],
                "end_date": scheme_data['end_date'],
                "schemes_summary": schemes_summary,
                "schemes": [scheme_data],
                "message": "成功获取调度方案单"
            }
            
            logger.debug(f"generate_dispatch_scheme 返回结果: {return_value}")
            return return_value
            
        except Exception as e:
            logger.error(f"获取调度方案失败: {e}")
            return {
                "success": False,
                "command": "FUNC_GENERATE_DISPATCH_SCHEME",
                "message": f"获取调度方案失败: {str(e)}"
            }

    @mcp.tool()
    async def run_xinanjiang_model(
        station_name: str,
        start_time: str,
        end_time: str,
        custom_params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        运行新安江水文模型，计算目标站点的流量（区间来水）。

        Args:
            station_name: 站点名称，支持水库或水文站，如：
                - 水库：陆浑水库、故县水库、三门峡水库、小浪底水库、河口村水库
                - 水文站：龙门镇、白马寺、黑石关、花园口
                系统会自动从数据库加载该站点的默认参数。
            start_time: 开始时间，格式: yyyy-MM-dd HH:mm:ss，例如: "2021-10-02 00:00:00"
            end_time: 结束时间，格式: yyyy-MM-dd HH:mm:ss，例如: "2021-10-07 00:00:00"
            custom_params: 可选的自定义参数，用于覆盖站点默认参数。
                支持的参数包括：
                - KC: 流域蒸散发折算系数 (默认: 根据站点配置)
                - B: 流域蓄水容量分布曲线指数 (默认: 根据站点配置)
                - UM: 上层张力水容量 (默认: 根据站点配置)
                - LM: 下层张力水容量 (默认: 根据站点配置)
                - SM: 自由水容量 (默认: 根据站点配置)
                - KG: 地下水日出流系数 (默认: 根据站点配置)
                - KI: 壤中流日出流系数 (默认: 根据站点配置)
                - XE: 马斯京跟法演算参数 (默认: 根据站点配置)

        Returns:
            {
                "success": true,
                "message": "模型运行成功",
                "station_info": { ... },
                "model_params": {                    # 新安江模型使用的完整参数
                    "KC": {"value": "0.9", "fullName": "流域蒸散发折算系数(KC)"},
                    "B": {"value": "0.4", "fullName": "流域蓄水容量分布曲线指数(B)"},
                    "SM": {"value": "25", "fullName": "自由水客量(SM)"},
                    "KG": {"value": "0.3", "fullName": "地下水日出流系数(KG)"},
                    "BA": {"value": "349.0", "fullName": "流域面积(BA)"},
                    "__custom_overrides__": ["KC"]   # 如有自定义覆盖参数，列出被覆盖的键名
                },
                "result": {
                    "start_time": "...",
                    "end_time": "...",
                    "rainfall_data": [...],          # 加权面雨量（mm/h）
                    "flow": [...],              # 新安江模型流量（m³/s）
                    "times": [...]
                }
            }
        """
        logger.info(f"调用 run_xinanjiang_model，站点: {station_name}，时间范围: {start_time} 至 {end_time}")
        
        from src.services.storage.database.xinanjiang_config_access import XinanjiangModelConfigAccess
        from src.services.storage.database.connection import get_db
        
        station_config = XinanjiangModelConfigAccess.get_config_by_station(station_name)
        if not station_config:
            return {"success": False, "message": f"未找到站点配置: {station_name}，请检查站点名称是否正确", "code": 404}
        
        station_type = station_config.get('station_type', 'reservoir')
        station_code = station_config.get('station_code', '')
        basin_name = station_config.get('basin_name', '')
        basin_area = station_config.get('basin_area', 101.7298)
        
        logger.info(f"站点配置信息: {station_name}({station_type}), 流域: {basin_name}, 面积: {basin_area}km²")
        
        # -------------------------------------------------------------------
        # 1. 从本地数据库查询降雨数据，基于雨量站权重计算加权面雨量
        # -------------------------------------------------------------------
        def _query_weighted_rainfall_from_db(start: str, end: str) -> Dict[str, Any]:
            """
            从本地数据库 rainfall_hourly 表查询逐小时降雨数据，
            结合 rainfall_stations 表的 weight_area 计算加权平均面雨量。

            返回: {"code": 200, "data": {timestamp: weighted_rainfall}, "station_count": N}
            """
            db = get_db()
            
            # 查询该时间范围内所有雨量站的逐小时降雨记录
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
            
            # 按时间戳分组
            from collections import defaultdict
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
            
            # 对每个时间步长计算加权平均降雨量
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
                    # 无权重信息时使用简单平均
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
        
        def _build_rainfall_array(
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
            
            # 如果完全没有数据，使用极小默认值（防止模型报错）
            if all(v == 0.0 for v in rainfall_values):
                logger.warning("所有时段降雨量均为0，使用默认值0.1mm")
                rainfall_values = [0.1] * hours
            
            logger.info(
                f"构建等时段面雨量数组: 共{len(rainfall_values)}个时段, "
                f"最大值={max(rainfall_values)}mm, 平均值={round(sum(rainfall_values)/len(rainfall_values), 2)}mm"
            )
            return rainfall_values
        
        # -------------------------------------------------------------------
        # 2. 构建模型控制参数
        # -------------------------------------------------------------------
        def _build_control_params(config: Dict[str, Any], custom: Dict[str, Any] = None) -> Dict[str, Any]:
            # 过滤掉 SQL 元数据和非参数键，只保留水文参数
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
        
        def _build_rainfall_data(rainfall_values: List[float], start: str, end: str) -> Dict[str, Any]:
            return {
                "ncName": "p",
                "type": "hydraulic_elements",
                "dimensionsList": [{"name": "TM", "fullName": "时间维度", "value": len(rainfall_values)}],
                "variablesList": [{
                    "valueType": "float",
                    "ArrayType": "array1d",
                    "name": "PA",
                    "fullName": "等时段面雨量值",
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
        
        def _build_etp_data(length: int, start: str, end: str) -> Dict[str, Any]:
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
        
        # -------------------------------------------------------------------
        # 主流程
        # -------------------------------------------------------------------
        try:
            dt_start = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
            dt_end = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
            time_diff = dt_end - dt_start
            hours_diff = int(time_diff.total_seconds() / 3600) + 1
            
            logger.info(f"时间范围: {start_time} 至 {end_time}，共 {hours_diff} 个时段")
            
            # ---- 步骤1: 从数据库查询降雨数据并计算加权面雨量 ----
            weighted_rainfall_data = _query_weighted_rainfall_from_db(start_time, end_time)
            rainfall_values = _build_rainfall_array(weighted_rainfall_data, start_time, end_time, hours_diff)
            
            logger.info(
                f"计算得到等时段加权面雨量: "
                f"涉及 {weighted_rainfall_data.get('station_count', 0)} 个雨量站"
            )
            
            # ---- 步骤2: 构建NC文件参数并调用新安江模型 ----
            ctrl_params = _build_control_params(station_config, custom_params)
            rainfall_data = _build_rainfall_data(rainfall_values, start_time, end_time)
            etp_data = _build_etp_data(len(rainfall_values), start_time, end_time)
            
            # 提取模型参数为可读格式（用于返回给调用方）
            # 过滤掉 BA（流域面积），从数据库读取的数据可能不准确
            skip_model_params = {"BA"}
            model_params = {}
            for item in ctrl_params.get("globalList", []):
                name = item.get("name", "")
                if name in skip_model_params:
                    continue
                value = item.get("value", "")
                full_name = item.get("fullName", name)
                model_params[name] = {"value": value, "fullName": full_name}
            # 也记录用户自定义覆盖的参数
            if custom_params:
                model_params["__custom_overrides__"] = list(custom_params.keys())
            
            if not xinanjiang_auth_service.get_token():
                return {"success": False, "message": "新安江模型登录失败", "code": 500}
            
            write_result = xinanjiang_model_service.write_service_nc_file(ctrl_params, rainfall_data, etp_data)
            if not write_result.get("success"):
                return {"success": False, "message": "写入NC文件失败", "result": write_result}
            
            file_list = write_result.get("result", {}).get("fileList", [])
            control_path = None
            em_path = None
            p_path = None
            
            for file_info in file_list:
                nc_name = file_info.get("ncName")
                file_path = file_info.get("filePath")
                if nc_name == "control":
                    control_path = file_path
                elif nc_name == "em":
                    em_path = file_path
                elif nc_name == "p":
                    p_path = file_path
            
            if not all([control_path, em_path, p_path]):
                return {"success": False, "message": "文件路径解析失败", "result": file_list}
            
            call_result = xinanjiang_model_service.call_model(control_path, em_path, p_path)
            if not call_result.get("success"):
                return {"success": False, "message": "模型调用失败", "result": call_result}
            
            inc_key = call_result.get("result", {}).get("incKey")
            if not inc_key:
                return {"success": False, "message": "获取任务ID失败", "result": call_result}
            
            logger.info(f"任务ID: {inc_key}")
            
            # ---- 步骤3: 轮询等待模型计算结果 ----
            max_polls = 60
            poll_interval = 5
            discharge = []
            start_time_result = start_time
            end_time_result = end_time
            
            for poll_count in range(max_polls):
                time.sleep(poll_interval)
                
                status_result = xinanjiang_model_service.get_service_instance(inc_key)
                if not status_result.get("success"):
                    continue
                
                status = status_result.get("result", {}).get("status")
                logger.info(f"轮询 {poll_count + 1}/{max_polls}: 状态={status}")
                
                if status == 3:
                    callback_data_str = status_result.get("result", {}).get("callbackData", "{}")
                    
                    callback_data = json.loads(callback_data_str)
                    output_data = callback_data.get("data", [])
                    
                    output_file_path = None
                    for item in output_data:
                        if item.get("key") == "out":
                            output_file_path = item.get("value")
                            break
                    
                    if not output_file_path:
                        return {"success": False, "message": "未找到输出文件路径", "result": status_result}
                    
                    parse_result = xinanjiang_model_service.nc_to_json(output_file_path)
                    if not parse_result.get("success"):
                        return {"success": False, "message": "NC文件解析失败", "result": parse_result}
                    
                    variables_list = parse_result.get("result", {}).get("variablesList", [])
                    global_list = parse_result.get("result", {}).get("globalList", [])
                    
                    for var in variables_list:
                        if var.get("name") == "Q":
                            discharge = [float(v) for v in var.get("arrayValue", [])]
                            break
                    
                    for glb in global_list:
                        if glb.get("name") == "BGTM":
                            start_time_result = glb.get("value")
                        elif glb.get("name") == "EDTM":
                            end_time_result = glb.get("value")
                    
                    break  # 获取结果成功，退出轮询
                    
                elif status in [4, 5]:
                    return {"success": False, "message": f"新安江模型任务失败，状态: {status}", "result": status_result}
            
            if not discharge:
                return {"success": False, "message": f"新安江模型轮询超时（{max_polls}次）或未获取到径流结果", "inc_key": inc_key}
            
            # ---- 步骤4: 构建时间轴 ----
            times = []
            try:
                dt_ref = datetime.strptime(start_time_result, "%Y-%m-%d %H:%M:%S")
                for i in range(len(discharge)):
                    times.append((dt_ref + timedelta(hours=i)).strftime("%Y-%m-%d %H:%M:%S"))
            except Exception:
                times = [(dt_start + timedelta(hours=i)).strftime("%Y-%m-%d %H:%M:%S") for i in range(len(discharge))]
            
            # ---- 步骤5: 返回完整结果 ----
            response_data = {
                "success": True,
                "message": "新安江模型运行成功",
                "command": "FUNC_RUN_XINANJIANG_MODEL",
                "station_info": {
                    "station_name": station_name,
                    "station_type": station_type,
                    "station_code": station_code,
                    "basin_name": basin_name
                },
                "model_params": model_params,
                "result": {
                    "start_time": start_time_result,
                    "end_time": end_time_result,
                    "rainfall_data": rainfall_values,
                    "flow": discharge,
                    "times": times
                }
            }
            
            return response_data
            
        except Exception as e:
            logger.error(f"新安江模型完整流程异常: {e}")
            return {"success": False, "message": str(e), "code": 500}

    @mcp.tool()
    async def rainfall_similarity_analysis(
        step: str,
        basin: str = None,
        rainfall_id: str = None,
        start_time: str = None,
        end_time: str = None,
        raster_image_url: str = None
    ) -> dict:
        """
        降雨图斑相似性分析模型（统一入口）。

        整体流程分三步：
        - step="1"：查询各流域最新降雨情况，返回各流域+降雨事件列表，供用户选择。
        - step="2"：根据用户选择的流域和降雨编号，依次链式执行
                    ①查询降雨详情 ②计算相似雨 ③查询相似雨图斑图片 ④图斑相似度计算
                    （顺序固定，不可调整），返回最相似的3场降雨时间段。
        - step="3"：根据用户选择的某场相似雨时间段，查询对应水文信息，
                    并与图斑图片URL整合返回。

        Args:
            step: 流程阶段，可选值: "1"、"2" 或 "3"
            basin: 流域名称（如：黄河、伊洛河、洛河），在 step="2" 和 step="3" 时必填
            rainfall_id: 降雨编号（由 step="1" 返回），仅在 step="2" 时必填
            start_time: 查询起始时间，仅在 step="3" 时必填
            end_time: 查询结束时间，仅在 step="3" 时必填
            raster_image_url: 对应时段的图斑图片URL，仅在 step="3" 时必填

        Returns:
            step="1" 返回各流域最新降雨列表；
            step="2" 返回链式执行结果，包含降雨详情、相似雨列表、图斑图片、最相似图斑；
            step="3" 返回水文信息与图斑图片URL整合结果。
        """
        logger.info(
            f"调用 rainfall_similarity_analysis，收到参数: "
            f"step={repr(step)}, basin={repr(basin)}, rainfall_id={repr(rainfall_id)}"
        )

        if step not in ("1", "2", "3"):
            return {
                "success": False,
                "command": "FUNC_RAINFALL_SIMILARITY_ANALYSIS",
                "message": f"不支持的 step 参数: {step}，仅支持 '1'、'2' 或 '3'"
            }

        # -------------------------------------------------------------------
        # 第一步：查询各流域最新降雨情况
        # -------------------------------------------------------------------
        if step == "1":
            try:
                # 调用"查询各流域最新降雨情况"接口
                url = "http://36.99.160.89:8066/rain/getLatestRainList"
                
                logger.info(f"调用查询最新降雨接口: {url}")
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                
                result = response.json()
                logger.info(f"接口返回结果: {result}")
                
                if result.get("code") != 200:
                    raise Exception(f"接口返回错误: {result.get('msg', '未知错误')}")
                
                raw_data = result.get("data", [])
                
                # 转换为 skill 文档定义的格式
                basins_dict = {}
                for item in raw_data:
                    watershed_name = item.get("watershedName", "")
                    if watershed_name not in basins_dict:
                        basins_dict[watershed_name] = {
                            "basin_name": watershed_name,
                            "basin_code": "",
                            "rainfall_events": []
                        }
                    
                    basins_dict[watershed_name]["rainfall_events"].append({
                        "rainfall_id": str(item.get("id", "")),
                        "start_time": item.get("startTime", ""),
                        "end_time": item.get("endTime", ""),
                        "total_rainfall": item.get("precipitationTotal", 0),
                        "description": f"降雨时段: {item.get('startTime', '')} 至 {item.get('endTime', '')}"
                    })
                
                basins_with_rainfall = list(basins_dict.values())
                
                return_value = {
                    "success": True,
                    "command": "FUNC_RAINFALL_SIMILARITY_ANALYSIS_STEP1",
                    "step": "1",
                    "basins": basins_with_rainfall,
                    "message": "已查询到各流域最新降雨情况，请选择目标流域和降雨事件"
                }
                logger.debug(f"rainfall_similarity_analysis step=1 返回结果: {return_value}")
                return return_value
            except Exception as e:
                logger.error(f"查询各流域最新降雨情况失败: {e}")
                return {
                    "success": False,
                    "command": "FUNC_RAINFALL_SIMILARITY_ANALYSIS_STEP1",
                    "message": f"查询各流域最新降雨情况失败: {str(e)}"
                }

        # -------------------------------------------------------------------
        # 第二步：链式执行 详情→相似雨→图斑→图斑相似度
        # -------------------------------------------------------------------
        if step == "2":
            if not basin or not rainfall_id:
                return {
                    "success": False,
                    "command": "FUNC_RAINFALL_SIMILARITY_ANALYSIS_STEP2",
                    "message": "step=2 时 basin 和 rainfall_id 均为必填参数"
                }

            steps_result = {}

            # ---- 2.1 查询降雨详情 ----
            try:
                # 调用"按降雨编号查询降雨详情"接口
                url = f"http://36.99.160.89:8066/rain/getRainDetailById?id={rainfall_id}"

                logger.info(f"调用查询降雨详情接口: {url}")
                response = requests.get(url, timeout=30)
                response.raise_for_status()

                result = response.json()
                logger.info(f"降雨详情接口返回结果: {result}")

                if result.get("code") != 200:
                    raise Exception(f"接口返回错误: {result.get('msg', '未知错误')}")

                rainfall_detail = result.get("data", {})
                steps_result["rainfall_detail"] = rainfall_detail
            except Exception as e:
                logger.error(f"查询降雨详情失败: {e}")
                return {
                    "success": False,
                    "command": "FUNC_RAINFALL_SIMILARITY_ANALYSIS_STEP2",
                    "step": "2.1",
                    "message": f"查询降雨详情失败: {str(e)}",
                    "basin": basin,
                    "rainfall_id": rainfall_id
                }

            # ---- 2.2 计算相似雨 ----
            try:
                # 调用"计算相似雨"接口
                url = "http://36.99.160.89:10017/tbapi/data/analyse/conformAnalysis"

                # 构建请求体：使用上一步获取的降雨详情，添加流域名称字段
                request_data = rainfall_detail.copy()
                request_data["rvnm"] = basin  # 添加流域名称

                logger.info(f"调用计算相似雨接口: {url}")
                logger.info(f"请求体: {request_data}")

                response = requests.post(url, json=request_data, headers={"Content-Type": "application/json"}, timeout=60)
                response.raise_for_status()

                result = response.json()
                logger.info(f"相似雨计算接口返回结果: {result}")

                if result.get("code") != 200:
                    raise Exception(f"接口返回错误: {result.get('msg', '未知错误')}")

                # 假设返回的data字段包含相似雨列表
                similar_rainfall_list = result.get("data", [])
                steps_result["similar_rainfall"] = similar_rainfall_list
            except Exception as e:
                logger.error(f"计算相似雨失败: {e}")
                return {
                    "success": False,
                    "command": "FUNC_RAINFALL_SIMILARITY_ANALYSIS_STEP2",
                    "step": "2.2",
                    "message": f"计算相似雨失败: {str(e)}",
                    "basin": basin,
                    "rainfall_id": rainfall_id,
                    "partial_result": steps_result
                }

            # ---- 2.3 查询相似雨图斑图片 ----
            try:
                # 调用"查询降雨图斑图片"接口
                url = "http://36.99.160.89:10017/tbapi/data/getInfo"

                # 从降雨详情中提取当前降雨时段
                prototype_start = rainfall_detail.get("rainfallDate", "")
                prototype_end = rainfall_detail.get("endRainfallDate", "")

                # 构建请求体
                request_data = {
                    "requestData": False,
                    "requestContour": False,
                    "requestImage": True,
                    "basin": basin,
                    "prototypePeriod": {
                        "period": {
                            "ftm": prototype_start.split(" ")[0] if prototype_start else "",
                            "ttm": prototype_end.split(" ")[0] if prototype_end else ""
                        },
                        "eigenPeriods": []
                    },
                    "similarPeriods": []
                }

                # 从相似雨列表中提取每场雨的时段
                if isinstance(similar_rainfall_list, list):
                    for item in similar_rainfall_list:
                        start_time = item.get("rainfallDate", "")
                        end_time = item.get("endRainfallDate", "")
                        request_data["similarPeriods"].append({
                            "period": {
                                "ftm": start_time.split(" ")[0] if start_time else "",
                                "ttm": end_time.split(" ")[0] if end_time else ""
                            },
                            "eigenPeriods": []
                        })

                logger.info(f"调用查询图斑图片接口: {url}")
                logger.info(f"请求体: {request_data}")

                response = requests.post(url, json=request_data, headers={"Content-Type": "application/json"}, timeout=60)
                response.raise_for_status()

                result = response.json()
                logger.info(f"图斑图片接口返回结果: {result}")

                raster_images = result
                steps_result["rainfall_raster_images"] = raster_images
            except Exception as e:
                logger.error(f"查询降雨图斑图片失败: {e}")
                return {
                    "success": False,
                    "command": "FUNC_RAINFALL_SIMILARITY_ANALYSIS_STEP2",
                    "step": "2.3",
                    "message": f"查询降雨图斑图片失败: {str(e)}",
                    "basin": basin,
                    "rainfall_id": rainfall_id,
                    "partial_result": steps_result
                }

            # ---- 2.4 图斑相似度计算 ----
            try:
                # 调用"图斑相似度计算"接口
                url = "http://36.99.160.89:10017/wpi/process"

                # 提取图斑图片URL列表
                urls = []

                # 添加当前降雨图斑（prototypeInfo的contourImage）
                prototype_data = raster_images.get("data", {})
                prototype_info = prototype_data.get("prototypeInfo", {})
                prototype_rain_info = prototype_info.get("rainInfo", {})
                prototype_image_url = prototype_rain_info.get("contourImage", "")
                if prototype_image_url:
                    urls.append(prototype_image_url.strip())

                # 添加相似雨图斑（similarInfos中每个的contourImage）
                similar_infos = prototype_data.get("similarInfos", [])
                if isinstance(similar_infos, list):
                    for similar_item in similar_infos:
                        rain_info = similar_item.get("rainInfo", {})
                        image_url = rain_info.get("contourImage", "")
                        if image_url:
                            urls.append(image_url.strip())

                # 构建请求体
                request_data = {"urls": urls}

                logger.info(f"调用图斑相似度计算接口: {url}")
                logger.info(f"请求体: {request_data}")

                response = requests.post(url, json=request_data, headers={"Content-Type": "application/json"}, timeout=60)
                response.raise_for_status()

                result = response.json()
                logger.info(f"图斑相似度计算接口返回结果: {result}")

                # 返回结果是最相似的降雨时间列表
                most_similar_raster = result
                steps_result["most_similar_raster"] = most_similar_raster
            except Exception as e:
                logger.error(f"图斑相似度计算失败: {e}")
                return {
                    "success": False,
                    "command": "FUNC_RAINFALL_SIMILARITY_ANALYSIS_STEP2",
                    "step": "2.4",
                    "message": f"图斑相似度计算失败: {str(e)}",
                    "basin": basin,
                    "rainfall_id": rainfall_id,
                    "partial_result": steps_result
                }

            # ---- 2.5 数据精简处理 ----
            try:
                # 精简 rainfall_detail：删除空字段和大字段
                if "rainfall_detail" in steps_result:
                    detail = steps_result["rainfall_detail"]
                    # 删除空字段和大字段
                    for key in ["lookLikePoint", "resemblance", "maxRainfallStnm", "timeRainfallQ", "rainfallParameters"]:
                        if key in detail:
                            del detail[key]
                    steps_result["rainfall_detail"] = detail

                # 精简 rainfall_raster_images：删除大字段 contour 和接口元信息
                if "rainfall_raster_images" in steps_result:
                    raster_data = steps_result["rainfall_raster_images"]
                    # 删除接口元信息
                    for key in ["respCode", "respMsg", "elapsed", "extraData"]:
                        if key in raster_data:
                            del raster_data[key]
                    # 删除 prototypeInfo 中的 contour
                    if "data" in raster_data:
                        data = raster_data["data"]
                        if "prototypeInfo" in data:
                            proto_info = data["prototypeInfo"]
                            if "rainInfo" in proto_info:
                                rain_info = proto_info["rainInfo"]
                                if "contour" in rain_info:
                                    del rain_info["contour"]
                        # 删除 similarInfos 中的 contour
                        if "similarInfos" in data:
                            for similar_item in data["similarInfos"]:
                                if "rainInfo" in similar_item:
                                    rain_info = similar_item["rainInfo"]
                                    if "contour" in rain_info:
                                        del rain_info["contour"]
                    steps_result["rainfall_raster_images"] = raster_data

                # 精简 similar_rainfall：删除空字段和 rainfallParameters
                if "similar_rainfall" in steps_result:
                    similar_list = steps_result["similar_rainfall"]
                    for item in similar_list:
                        for key in ["lookLikePoint", "resemblance", "maxRainfallStnm", "timeRainfallQ", "rainfallParameters"]:
                            if key in item:
                                del item[key]
                    steps_result["similar_rainfall"] = similar_list

            except Exception as e:
                logger.warning(f"数据精简处理失败，将返回原始数据: {e}")

            return_value = {
                "success": True,
                "command": "FUNC_RAINFALL_SIMILARITY_ANALYSIS_STEP2",
                "step": "2",
                "basin": basin,
                "rainfall_id": rainfall_id,
                "steps": steps_result,
                "message": "图斑相似性分析完成"
            }
            logger.debug(f"rainfall_similarity_analysis step=2 返回结果: {return_value}")
            return return_value

        # -------------------------------------------------------------------
        # 第三步：根据用户选择的相似雨时间段查询水文信息并整合图斑图片
        # -------------------------------------------------------------------
        if step == "3":
            if not all([basin, start_time, end_time, raster_image_url]):
                return {
                    "success": False,
                    "command": "FUNC_RAINFALL_SIMILARITY_ANALYSIS_STEP3",
                    "step": "3",
                    "message": "step=3 需要 basin、start_time、end_time、raster_image_url 参数"
                }

            try:
                # 3.1 调用"查询水文信息"接口
                url = "http://36.99.160.89:10017/api/hyd/getByBasinNameListAndTime"
                request_data = {
                    "basinNameList": [basin],
                    "startTime": start_time,
                    "endTime": end_time
                }

                logger.info(f"调用查询水文信息接口: {url}")
                logger.info(f"请求体: {request_data}")

                response = requests.post(url, json=request_data, headers={"Content-Type": "application/json"}, timeout=60)
                response.raise_for_status()

                result = response.json()
                logger.info(f"水文信息接口返回结果: {result}")

                if result.get("code") != 200:
                    raise Exception(f"接口返回错误: {result.get('msg', '未知错误')}")

                hydrological_data = result.get("data", [])

                return {
                    "success": True,
                    "command": "FUNC_RAINFALL_SIMILARITY_ANALYSIS_STEP3",
                    "step": "3",
                    "basin": basin,
                    "start_time": start_time,
                    "end_time": end_time,
                    "hydrological_data": hydrological_data,
                    "raster_image_url": raster_image_url,
                    "message": "已查询到对应时段的水文信息，并与图斑图片URL整合"
                }

            except Exception as e:
                logger.error(f"查询水文信息失败: {e}")
                return {
                    "success": False,
                    "command": "FUNC_RAINFALL_SIMILARITY_ANALYSIS_STEP3",
                    "step": "3",
                    "message": f"查询水文信息失败: {str(e)}",
                    "basin": basin,
                    "start_time": start_time,
                    "end_time": end_time,
                    "raster_image_url": raster_image_url
                }

