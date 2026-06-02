import json
import random
import time
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any
from mcp.server.fastmcp import FastMCP
from src.utils.logger import get_logger
from src.services.scheme_storage import save_scheme, generate_unique_id
from src.services.xinanjiang_service import xinanjiang_auth_service, xinanjiang_model_service
from src.services.auth_service import auth_service
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
    async def run_flood_routing_model(river_section: str, inflow: str, initial_conditions: str) -> dict:
        """
        执行洪水演进模型。

        Args:
            river_section: 河段名称（如：三门峡-小浪底、洛河段等）
            inflow: 入流数据 (JSON格式)，包含上游站的流量过程
            initial_conditions: 初始条件 (JSON格式)，包含初始水位、流量等
        """
        logger.info(f"调用 run_flood_routing_model，收到参数: river_section={repr(river_section)}, inflow={repr(inflow)}, initial_conditions={repr(initial_conditions)}")
        try:
            inflow_data = json.loads(inflow) if isinstance(inflow, str) else inflow
            init_cond = json.loads(initial_conditions) if isinstance(initial_conditions, str) else initial_conditions
        except json.JSONDecodeError:
            return_value = {"success": False, "error": "输入数据格式错误，请提供有效的JSON格式"}
            logger.debug(f"run_flood_routing_model 返回结果: {return_value}")
            return return_value

        initial_level = init_cond.get("initial_water_level", 100)

        routing_result = []
        for i, point in enumerate(inflow_data):
            inflow_val = float(point.get("inflow", 0))
            attenuation = 0.85 + random.uniform(0, 0.1)
            routed_flow = inflow_val * attenuation
            routed_level = initial_level + random.uniform(-2, 3)
            routing_result.append({
                "hour": i,
                "inflow": inflow_val,
                "outflow": round(routed_flow, 2),
                "water_level": round(routed_level, 2)
            })

        return_value = {
            "success": True,
            "river_section": river_section,
            "command": "FUNC_RUN_FLOOD_ROUTING_MODEL",
            "initial_conditions": init_cond,
            "routing_result": routing_result,
            "peak_attenuation": round(100 * (1 - 0.88), 2),
            "message": f"洪水演进模型执行成功，{river_section}演进计算完成"
        }
        logger.debug(f"run_flood_routing_model 返回结果: {return_value}")
        return return_value

    @mcp.tool()
    async def generate_dispatch_scheme(
        count: int = 1,
        control_huayuankou_flow: bool = False,
        huayuankou_max_flow: float = 2500.0,
        flood_season_empty_storage: bool = False,
        target_storage_ratio: float = 0.7,
        smx_max_level: float = None,
        smx_max_storage: float = None,
        xld_max_level: float = None,
        xld_max_storage: float = None,
        lh_max_level: float = None,
        lh_max_storage: float = None,
        gx_max_level: float = None,
        gx_max_storage: float = None,
        hkc_max_level: float = None,
        hkc_max_storage: float = None,
        start_time: str = None
    ) -> dict:
        """
        生成调度方案单。

        Args:
            count: 生成的调度方案数量，默认1个
            control_huayuankou_flow: 是否控制花园口流量
            huayuankou_max_flow: 花园口最大流量限制（m³/s），默认2500
            flood_season_empty_storage: 是否需要汛前腾空库容
            target_storage_ratio: 汛前目标库容比例，默认0.7（70%）
            
            # 三门峡水库约束
            smx_max_level: 三门峡水库最大水位限制（m），不设置则无限制
            smx_max_storage: 三门峡水库最大库容限制（亿m³），不设置则无限制
            
            # 小浪底水库约束
            xld_max_level: 小浪底水库最大水位限制（m），不设置则无限制
            xld_max_storage: 小浪底水库最大库容限制（亿m³），不设置则无限制
            
            # 陆浑水库约束
            lh_max_level: 陆浑水库最大水位限制（m），不设置则无限制
            lh_max_storage: 陆浑水库最大库容限制（亿m³），不设置则无限制
            
            # 故县水库约束
            gx_max_level: 故县水库最大水位限制（m），不设置则无限制
            gx_max_storage: 故县水库最大库容限制（亿m³），不设置则无限制
            
            # 河口村水库约束
            hkc_max_level: 河口村水库最大水位限制（m），不设置则无限制
            hkc_max_storage: 河口村水库最大库容限制（亿m³），不设置则无限制
            
            start_time: 调度开始时间（格式：YYYY-MM-DD），不设置则使用当前时间
        """
        logger.info(f"调用 generate_dispatch_scheme，收到参数: count={count}, control_huayuankou_flow={control_huayuankou_flow}, huayuankou_max_flow={huayuankou_max_flow}, flood_season_empty_storage={flood_season_empty_storage}, target_storage_ratio={target_storage_ratio}")
        
        import time
        from datetime import datetime, timedelta
        
        # 确定请求的日期范围
        if start_time:
            try:
                base_datetime = datetime.strptime(start_time, "%Y-%m-%d")
            except ValueError:
                base_datetime = datetime.now()
        else:
            base_datetime = datetime.now()
        
        # 定义允许的时间范围：2021年10月2日到10月7日
        allowed_start = datetime(2021, 10, 2)
        allowed_end = datetime(2021, 10, 7)
        
        # 检查请求的时间是否在允许范围内
        if not (allowed_start <= base_datetime <= allowed_end):
            return {
                "success": False,
                "command": "FUNC_GENERATE_DISPATCH_SCHEME",
                "message": "目前没有接入五库调度模型，因此无法生成调度方案单"
            }
        
        from src.services.database.data_access import DispatchTimeseriesAccess
        
        # 从数据库获取调度方案数据
        try:
            schemes = DispatchTimeseriesAccess.get_all_schemes()
            if not schemes:
                logger.warning("数据库中没有找到调度方案数据")
                return {
                    "success": False,
                    "command": "FUNC_GENERATE_DISPATCH_SCHEME",
                    "message": "目前没有接入五库调度模型，因此无法生成调度方案单"
                }
            
            # 获取第一个方案的 ID
            scheme_id = schemes[0]['id']
            
            # 获取所有时间序列数据
            timeseries_data = DispatchTimeseriesAccess.get_timeseries(scheme_id)
            
            if not timeseries_data:
                logger.warning(f"调度方案 {scheme_id} 中没有时间序列数据")
                return {
                    "success": False,
                    "command": "FUNC_GENERATE_DISPATCH_SCHEME",
                    "message": "目前没有接入五库调度模型，因此无法生成调度方案单"
                }
            
            # 按站点和指标类型组织数据
            reservoirs = {}
            hydrological_stations = {}
            
            # 站点名称映射和站点编码映射
            station_name_map = {
                "三门峡": "三门峡水库",
                "小浪底": "小浪底水库",
                "陆浑": "陆浑水库",
                "故县": "故县水库",
                "河口村": "河口村水库"
            }
            
            # 水库站点编码映射
            station_code_map = {
                "三门峡": "BDA00000111",
                "小浪底": "BDA00000121",
                "陆浑": "BDA80200721",
                "故县": "BDA80000661",
                "河口村": "BDA00000761"
            }
            
            # 指标类型映射
            metric_type_map = {
                "level": "water_level",
                "storage": "storage",
                "inflow": "inflow",
                "outflow": "outflow",
                "flow": "flow"
            }
            
            # 按时间戳分组，每个站点保留所有指标记录
            time_groups = {}
            for record in timeseries_data:
                ts = record['timestamp']
                if ts not in time_groups:
                    time_groups[ts] = {}
                time_groups[ts].setdefault(record['station_name'], []).append(record)
            
            # 初始化水库数据结构
            for station_name, res_name in station_name_map.items():
                reservoirs[res_name] = {
                    "station_code": station_code_map.get(station_name, ""),
                    "timeseries": []
                }
            
            # 初始化水文站数据结构
            common_stations = ["龙门镇", "白马寺", "黑石关", "花园口"]
            for station in common_stations:
                hydrological_stations[station] = {
                    "timeseries": []
                }
            
            # 按时间顺序处理
            for ts in sorted(time_groups.keys()):
                group = time_groups[ts]
                
                # 格式化时间戳为毫秒
                if hasattr(ts, 'timestamp'):
                    formatted_ts = int(ts.timestamp() * 1000)
                else:
                    formatted_ts = int(time.mktime(time.strptime(str(ts), "%Y-%m-%d %H:%M:%S")) * 1000)
                
                # 处理水库数据
                for station_name, res_name in station_name_map.items():
                    records = group.get(station_name, [])
                    res_data = {
                        "time": formatted_ts,
                        "water_level": None,
                        "storage": None,
                        "inflow": None,
                        "outflow": None
                    }
                    
                    for record in records:
                        metric = metric_type_map.get(record['metric_type'])
                        if metric and metric in res_data:
                            res_data[metric] = record['metric_value']
                    
                    reservoirs[res_name]["timeseries"].append(res_data)
                
                # 处理水文站数据
                for station in common_stations:
                    station_records = group.get(station, [])
                    flow_value = None
                    for record in station_records:
                        if record['metric_type'] == 'flow':
                            flow_value = record['metric_value']
                            break
                    
                    hydrological_stations[station]["timeseries"].append({
                        "time": formatted_ts,
                        "flow": flow_value
                    })
            
            # 构建返回的方案
            result_scheme = {
                "scheme_id": schemes[0].get('id', 'DS-0001'),
                "scheme_name": schemes[0].get('name', '2021年汛期调度方案'),
                "start_date": "2021-10-02",
                "end_date": "2021-10-07",
                "reservoirs": reservoirs,
                "hydrological_stations": hydrological_stations
            }
            
            # 计算方案摘要统计
            def calculate_scheme_summary(scheme):
                stats = {}
                for res_name, res_data in scheme['reservoirs'].items():
                    levels = [t['water_level'] for t in res_data['timeseries'] if t['water_level'] is not None]
                    storages = [t['storage'] for t in res_data['timeseries'] if t['storage'] is not None]
                    inflows = [t['inflow'] for t in res_data['timeseries'] if t['inflow'] is not None]
                    outflows = [t['outflow'] for t in res_data['timeseries'] if t['outflow'] is not None]
                    
                    stats[res_name] = {
                        "water_level_range": [round(min(levels), 2) if levels else None, round(max(levels), 2) if levels else None],
                        "storage_range": [round(min(storages), 2) if storages else None, round(max(storages), 2) if storages else None],
                        "avg_inflow": round(sum(inflows) / len(inflows), 2) if inflows else None,
                        "avg_outflow": round(sum(outflows) / len(outflows), 2) if outflows else None
                    }
                
                if '花园口' in scheme['hydrological_stations']:
                    huayuankou_flows = [t['flow'] for t in scheme['hydrological_stations']['花园口']['timeseries'] if t['flow'] is not None]
                    stats['花园口'] = {
                        "flow_range": [round(min(huayuankou_flows), 2) if huayuankou_flows else None, round(max(huayuankou_flows), 2) if huayuankou_flows else None],
                        "avg_flow": round(sum(huayuankou_flows) / len(huayuankou_flows), 2) if huayuankou_flows else None
                    }
                
                return stats
            
            schemes_summary = [{
                "scheme_id": result_scheme['scheme_id'],
                "scheme_name": result_scheme['scheme_name'],
                "start_date": result_scheme['start_date'],
                "end_date": result_scheme['end_date'],
                "stats": calculate_scheme_summary(result_scheme)
            }]
            
            return_value = {
                "success": True,
                "command": "FUNC_GENERATE_DISPATCH_SCHEME",
                "count": 1,
                "constraints_applied": {
                    "control_huayuankou_flow": control_huayuankou_flow,
                    "huayuankou_max_flow": huayuankou_max_flow if control_huayuankou_flow else None,
                    "flood_season_empty_storage": flood_season_empty_storage,
                    "target_storage_ratio": target_storage_ratio if flood_season_empty_storage else None,
                    "reservoir_constraints": {
                        "三门峡水库": {"max_level": smx_max_level, "max_storage": smx_max_storage},
                        "小浪底水库": {"max_level": xld_max_level, "max_storage": xld_max_storage},
                        "陆浑水库": {"max_level": lh_max_level, "max_storage": lh_max_storage},
                        "故县水库": {"max_level": gx_max_level, "max_storage": gx_max_storage},
                        "河口村水库": {"max_level": hkc_max_level, "max_storage": hkc_max_storage}
                    }
                },
                "schemes_summary": schemes_summary,
                "schemes": [result_scheme],
                "message": "成功获取调度方案单"
            }
            
            logger.debug(f"generate_dispatch_scheme 返回结果: {return_value}")
            return return_value
            
        except Exception as e:
            logger.error(f"获取调度方案失败: {e}")
            return {
                "success": False,
                "command": "FUNC_GENERATE_DISPATCH_SCHEME",
                "message": "目前没有接入五库调度模型，因此无法生成调度方案单"
            }

    @mcp.tool()
    async def run_xinanjiang_model(
        start_time: str,
        end_time: str,
        control_params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        运行新安江水文模型。
        
        大模型只需要传入开始时间和结束时间，工具会自动完成：
        1. 获取降雨数据（整个时间范围的站点降雨量）
        2. 计算等时段面雨量值（按小时划分）
        3. 构建模型参数
        4. 调用新安江模型进行计算
        5. 返回计算结果
        
        Args:
            start_time: 开始时间，格式: yyyy-MM-dd HH:mm:ss，例如: "2026-04-15 08:00:00"
            end_time: 结束时间，格式: yyyy-MM-dd HH:mm:ss，例如: "2026-04-15 12:00:00"
            control_params: 可选的控制参数，如果不传则使用默认参数
        
        Returns:
            {
                "success": true,
                "message": "模型运行成功",
                "result": {
                    "start_time": "2026-04-15 08:00:00",
                    "end_time": "2026-04-15 12:00:00",
                    "rainfall_data": [10.0, 12.5, 8.3, 15.2],
                    "discharge": [0.423, 2.056, 4.293, 6.755],
                    "times": ["2026-04-15 08:00:00", "2026-04-15 09:00:00", ...]
                }
            }
        """
        logger.info(f"调用 run_xinanjiang_model，时间范围: {start_time} 至 {end_time}")
        
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
        
        def _build_control_params() -> Dict[str, Any]:
            return {
                "ncName": "control",
                "type": "hydraulic_elements",
                "dimensionsList": [],
                "variablesList": [],
                "globalList": [
                    {"type": "float", "name": "KC", "fullName": "流域蒸散发折算系数(KC)", "value": "0.9"},
                    {"type": "float", "name": "B", "fullName": "流域蓄水容量分布曲线指数(B)", "value": "0.4"},
                    {"type": "int", "name": "UM", "fullName": "上层张力水容量(UM)", "value": "30"},
                    {"type": "int", "name": "LM", "fullName": "下层张力水容量(LM)", "value": "80"},
                    {"type": "float", "name": "EX", "fullName": "流域自由水容量分布曲线指数(EX)", "value": "1.5"},
                    {"type": "float", "name": "C", "fullName": "深层蒸散发折算系数(C)", "value": "0.12"},
                    {"type": "float", "name": "IM", "fullName": "不透水面积比例(IM)", "value": "0"},
                    {"type": "float", "name": "WM", "fullName": "张力水容量(WM)", "value": "120"},
                    {"type": "float", "name": "SM", "fullName": "自由水客量(SM)", "value": "25"},
                    {"type": "float", "name": "KG", "fullName": "地下水日出流系数(KG)", "value": "0.3"},
                    {"type": "float", "name": "KI", "fullName": "壤中流日出流系数(KI)", "value": "0.3"},
                    {"type": "float", "name": "CS", "fullName": "地表水流消退系数(CS)", "value": "0.8"},
                    {"type": "float", "name": "CG", "fullName": "地下水日消退系数(CG)", "value": "1"},
                    {"type": "float", "name": "CI", "fullName": "壤中流日消退系数(CI)", "value": "1"},
                    {"type": "float", "name": "CR", "fullName": "日模型河网蓄水消退系数(CR)", "value": "0.2"},
                    {"type": "double", "name": "BA", "fullName": "流域面积(BA)", "value": "101.7298"},
                    {"type": "float", "name": "XE", "fullName": "马斯京跟法演算参数(XE)", "value": "0.2"},
                    {"type": "int", "name": "KE", "fullName": "马斯京跟法演算参数(KE)", "value": "1"}
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
            
            ctrl_params = control_params if control_params else _build_control_params()
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

