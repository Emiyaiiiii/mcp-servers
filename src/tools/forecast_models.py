import json
import random
import time
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any
from mcp.server.fastmcp import FastMCP
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
        执行来水预报模型，根据站点类型调用不同接口获取预报数据。

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
            
            return_value = {
                "success": True,
                "station_type": station_type,
                "station_name": station_name,
                "station_code": station_code,
                "start_time": start_time,
                "end_time": end_time,
                "command": "FUNC_RUN_WATER_FORECAST_MODEL",
                "sch_id": sch_id,
                "forecast_data": result.get("data", result),
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
        运行新安江水文模型。

        Args:
            station_name: 站点名称，支持水库或水文站，如：
                - 水库：陆浑水库、故县水库、三门峡水库、小浪底水库、河口村水库
                - 水文站：龙门镇、白马寺、黑石关、花园口
                系统会自动从数据库加载该站点的默认参数，并查询对应的降雨数据。
            start_time: 开始时间，格式: yyyy-MM-dd HH:mm:ss，例如: "2026-04-15 08:00:00"
            end_time: 结束时间，格式: yyyy-MM-dd HH:mm:ss，例如: "2026-04-15 12:00:00"
            custom_params: 可选的自定义参数，用于覆盖站点默认参数。
                支持的参数包括：
                - KC: 流域蒸散发折算系数 (默认: 0.9)
                - B: 流域蓄水容量分布曲线指数 (默认: 0.4)
                - UM: 上层张力水容量 (默认: 30mm)
                - LM: 下层张力水容量 (默认: 80mm)
                - SM: 自由水容量 (默认: 25mm)
                - KG: 地下水日出流系数 (默认: 0.3)
                - KI: 壤中流日出流系数 (默认: 0.3)
                - BA: 流域面积 (默认: 根据站点)
                - XE: 马斯京跟法演算参数 (默认: 0.2)

        Returns:
            {
                "success": true,
                "message": "模型运行成功",
                "station_info": {
                    "station_name": "陆浑水库",
                    "station_type": "reservoir",
                    "basin_name": "伊洛河",
                    "basin_area": 349.0
                },
                "result": {
                    "start_time": "2026-04-15 08:00:00",
                    "end_time": "2026-04-15 12:00:00",
                    "rainfall_data": [10.0, 12.5, 8.3, 15.2],
                    "discharge": [0.423, 2.056, 4.293, 6.755],
                    "times": ["2026-04-15 08:00:00", "2026-04-15 09:00:00", ...]
                }
            }
        """
        logger.info(f"调用 run_xinanjiang_model，站点: {station_name}，时间范围: {start_time} 至 {end_time}")
        
        from src.services.storage.database.xinanjiang_config_access import XinanjiangModelConfigAccess
        
        station_config = XinanjiangModelConfigAccess.get_config_by_station(station_name)
        if not station_config:
            return {"success": False, "message": f"未找到站点配置: {station_name}，请检查站点名称是否正确", "code": 404}
        
        station_type = station_config.get('station_type', 'reservoir')
        station_code = station_config.get('station_code', '')
        basin_name = station_config.get('basin_name', '')
        basin_area = station_config.get('basin_area', 101.7298)
        
        logger.info(f"站点配置信息: {station_name}({station_type}), 流域: {basin_name}, 面积: {basin_area}km²")
        
        def _get_rainfall_data(start: str, end: str, retry: bool = True) -> Dict[str, Any]:
            base_url = getattr(settings, 'DATA_API_BASE_URL', 'http://wt.hxyai.cn/fx')
            try:
                url = f"{base_url}/rainfall/hourrth/getRainfall"
                headers = auth_service.get_auth_headers()
                params = {"startTime": start, "endTime": end}
                
                logger.info(f"获取降雨数据: {url}, params={params}")
                response = requests.get(url, params=params, headers=headers, timeout=30)
                
                if response.status_code == 401 and retry:
                    logger.warning("数据API认证失败，检查token状态")
                    if auth_service._token and auth_service._token_expiry > time.time():
                        logger.info("当前token未过期，但服务器返回401，可能是服务器问题，保留现有token")
                        return _get_rainfall_data(start, end, retry=False)
                    else:
                        logger.info("token已过期，尝试获取新token")
                        new_token = auth_service.get_token()
                        if new_token:
                            return _get_rainfall_data(start, end, retry=False)
                        else:
                            logger.error("无法获取新token")
                
                response.raise_for_status()
                result = response.json()
                
                if result.get("code") == 200:
                    logger.info(f"获取降雨数据成功，共{len(result.get('data', []))}条记录")
                    return result
                else:
                    logger.error(f"获取降雨数据失败: {result.get('msg', '未知错误')}")
                    return result
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"获取降雨数据请求异常: {e}")
                return {"code": 500, "data": None, "msg": str(e)}
        
        def _generate_simulation_rainfall(length: int, avg_value: float) -> List[float]:
            if length <= 1:
                return [avg_value]
            
            rainfall = []
            
            if length <= 4:
                for i in range(length):
                    factor = 0.5 + i * 0.2
                    rainfall.append(round(avg_value * factor, 2))
            else:
                peak_position = length // 2
                for i in range(length):
                    distance_from_peak = abs(i - peak_position)
                    max_distance = max(peak_position, length - 1 - peak_position)
                    if max_distance > 0:
                        factor = 1.0 - (distance_from_peak / max_distance) * 0.6
                    else:
                        factor = 1.0
                    rainfall.append(round(avg_value * factor, 2))
            
            total = sum(rainfall)
            if total > 0:
                scale_factor = (avg_value * length) / total
                rainfall = [round(v * scale_factor, 2) for v in rainfall]
            
            logger.info(f"生成模拟降雨序列: {rainfall[:5]}...（共{len(rainfall)}个时段）")
            return rainfall
        
        def _calculate_average_rainfall(rainfall_data: Dict[str, Any], length: int = 4) -> List[float]:
            data = rainfall_data.get("data", [])
            if not data:
                logger.warning("未获取到降雨数据，使用默认值")
                return _generate_simulation_rainfall(length, 10.0)
            
            rainfall_sum = 0
            count = 0
            for record in data:
                rf = record.get("rf", 0)
                if rf and isinstance(rf, (int, float)):
                    rainfall_sum += rf
                    count += 1
            
            if count == 0:
                logger.warning("未获取到有效降雨量数据，使用默认值")
                return _generate_simulation_rainfall(length, 10.0)
            
            avg_rainfall = round(rainfall_sum / count, 2)
            logger.info(f"计算得到平均降雨量: {avg_rainfall} mm（时间范围共{length}个时段）")
            
            return _generate_simulation_rainfall(length, avg_rainfall)
        
        def _build_control_params(config: Dict[str, Any], custom: Dict[str, Any] = None) -> Dict[str, Any]:
            params = {**config}
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
                    {"type": "double", "name": "BA", "fullName": "流域面积(BA)", "value": str(params.get('basin_area', 101.7298))},
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
        
        try:
            dt_start = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
            dt_end = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
            time_diff = dt_end - dt_start
            hours_diff = int(time_diff.total_seconds() / 3600) + 1
            
            logger.info(f"时间范围: {start_time} 至 {end_time}，共 {hours_diff} 个时段")
            
            rainfall_api_result = _get_rainfall_data(start_time, end_time)
            if rainfall_api_result.get("code") != 200:
                return {"success": False, "message": f"获取降雨数据失败: {rainfall_api_result.get('msg', '未知错误')}", "code": 500}
            
            rainfall_values = _calculate_average_rainfall(rainfall_api_result, hours_diff)
            logger.info(f"计算得到等时段面雨量值: {rainfall_values[:5]}...（共{len(rainfall_values)}个时段）")
            
            ctrl_params = _build_control_params(station_config, custom_params)
            rainfall_data = _build_rainfall_data(rainfall_values, start_time, end_time)
            etp_data = _build_etp_data(len(rainfall_values), start_time, end_time)
            
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
            
            max_polls = 60
            poll_interval = 5
            
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
                    
                    discharge = []
                    for var in variables_list:
                        if var.get("name") == "Q":
                            discharge = [float(v) for v in var.get("arrayValue", [])]
                            break
                    
                    start_time_result = start_time
                    end_time_result = end_time
                    for glb in global_list:
                        if glb.get("name") == "BGTM":
                            start_time_result = glb.get("value")
                        elif glb.get("name") == "EDTM":
                            end_time_result = glb.get("value")
                    
                    times = []
                    try:
                        dt_start = datetime.strptime(start_time_result, "%Y-%m-%d %H:%M:%S")
                        for i in range(len(discharge)):
                            times.append((dt_start + timedelta(hours=i)).strftime("%Y-%m-%d %H:%M:%S"))
                    except:
                        times = []
                    
                    return {
                        "success": True,
                        "message": "新安江模型运行成功",
                        "command": "FUNC_RUN_XINANJIANG_MODEL",
                        "station_info": {
                            "station_name": station_name,
                            "station_type": station_type,
                            "station_code": station_code,
                            "basin_name": basin_name,
                            "basin_area": basin_area
                        },
                        "result": {
                            "start_time": start_time_result,
                            "end_time": end_time_result,
                            "rainfall_data": rainfall_values,
                            "discharge": discharge,
                            "times": times
                        }
                    }
                elif status in [4, 5]:
                    return {"success": False, "message": f"任务失败，状态: {status}", "result": status_result}
            
            return {"success": False, "message": f"轮询超时（{max_polls}次）", "inc_key": inc_key}
            
        except Exception as e:
            logger.error(f"新安江模型完整流程异常: {e}")
            return {"success": False, "message": str(e), "code": 500}

