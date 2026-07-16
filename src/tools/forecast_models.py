import asyncio
import json
import os
import pyodbc
import requests
import platform
from datetime import datetime, timedelta
from typing import Dict, Any
from fastmcp import FastMCP
from fastmcp.server.auth import require_scopes
from src.utils.logger import get_logger


from src.utils.model.xinanjiang_utils import (
    query_weighted_rainfall_from_db, build_rainfall_array,
    build_control_params, build_rainfall_data, build_etp_data
)


from src.services.external_api.xinanjiang_service import xinanjiang_auth_service, xinanjiang_model_service
from src.services.external_api.water_forecast_service import water_forecast_service
from src.services.external_api.hydrology_forecast_service import hydrology_forecast_service
from src.utils.station_codes import get_reservoir_code, get_hydrology_code
from src.utils.forecast.rainfall_similarity import _step1_query_rainfall, _step2_calculate_similarity, _step3_integrate_hydrology
from src.config.settings import settings

logger = get_logger(__name__)

_query_weighted_rainfall_from_db = query_weighted_rainfall_from_db
_build_rainfall_array = build_rainfall_array
_build_control_params = build_control_params
_build_rainfall_data = build_rainfall_data
_build_etp_data = build_etp_data


def register_forecast_models(mcp: FastMCP):

    @mcp.tool(auth=require_scopes("forecast"))
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
        
        # 限制时间范围不超过30天
        start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
        if (end_dt - start_dt).days > 30:
            return_value = {"success": False, "error": "时间范围不能超过30天，请缩短查询范围"}
            logger.debug(f"run_water_forecast_model 返回结果: {return_value}")
            return return_value
        
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
            else:
                scheme_list = []
            
            if len(scheme_list) == 0:
                return_value = {"success": False, "error": "预报方案清单为空，请检查时间范围或联系管理员"}
                logger.debug(f"run_water_forecast_model 返回结果: {return_value}")
                return return_value
            
            def parse_datetime(dt_str):
                if not dt_str:
                    return None
                for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]:
                    try:
                        return datetime.strptime(dt_str, fmt)
                    except ValueError:
                        continue
                return None
            
            target_start = parse_datetime(start_time)
            target_end = parse_datetime(end_time)
            
            # 收集时间范围内所有方案，按接近 start_time 排序
            candidates = []
            for scheme in scheme_list:
                scheme_time = parse_datetime(scheme.get("schTime", ""))
                if scheme_time and target_start and target_end:
                    if target_start <= scheme_time <= target_end:
                        diff = abs(scheme_time - target_start)
                        candidates.append((diff, scheme))
            
            if not candidates:
                return_value = {"success": False, "error": f"未找到与时间范围 {start_time} - {end_time} 匹配的预报方案"}
                logger.debug(f"run_water_forecast_model 返回结果: {return_value}")
                return return_value
            
            candidates.sort(key=lambda x: x[0])  # 按接近程度排序
            
            # 按顺序尝试每个方案，直到获取到有效数据
            result = None
            last_error = None
            for _, scheme in candidates:
                sch_id = scheme.get("schId") or scheme.get("id")
                if not sch_id:
                    continue
                
                result = water_forecast_service.get_scheme_data_by_station_name(sch_id, station_name)
                
                if result.get("success") is False or result.get("code") not in [200, "200", None]:
                    last_error = result.get("message", result.get("error", "获取预报数据失败"))
                    logger.warning(f"方案 {sch_id} 获取数据失败: {last_error}，尝试下一个方案")
                    continue
                
                # 获取成功，跳出循环
                break
            else:
                # 所有方案均失败
                error_msg = last_error or "所有可用预报方案均获取数据失败"
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

    @mcp.tool(auth=require_scopes("forecast"))
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
                await asyncio.sleep(poll_interval)
                
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
                logger.error(f"新安江模型轮询结束但未获取到径流结果，discharge={discharge}, start_time={start_time_result}, end_time={end_time_result}")
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

    @mcp.tool(auth=require_scopes("forecast"))
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
        - step="1"：查询各流域降雨情况（支持时间范围过滤），返回各流域+降雨事件列表，供用户选择。
        - step="2"：根据用户选择的流域和降雨编号，依次链式执行
                    ①查询降雨详情 ②计算相似雨 ③查询相似雨图斑图片 ④图斑相似度计算
                    （顺序固定，不可调整），返回最相似的3场降雨时间段。
        - step="3"：根据用户选择的某场相似雨时间段，查询对应水文信息，
                    并与图斑图片URL整合返回。

        Args:
            step: 流程阶段，可选值: "1"、"2" 或 "3"
            basin: 流域名称（如：黄河、伊洛河、洛河），在 step="2" 和 step="3" 时必填
            rainfall_id: 降雨编号（由 step="1" 返回），仅在 step="2" 时必填
            start_time: 查询起始时间，step="1" 时可选（用于时间范围过滤），step="3" 时必填
            end_time: 查询结束时间，step="1" 时可选（用于时间范围过滤），step="3" 时必填
            raster_image_url: 对应时段的图斑图片URL，仅在 step="3" 时必填

        Returns:
            step="1" 返回各流域降雨列表；
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

        if step == "1":
            return _step1_query_rainfall(basin, start_time, end_time)

        if step == "2":
            if not basin or not rainfall_id:
                return {
                    "success": False,
                    "command": "FUNC_RAINFALL_SIMILARITY_ANALYSIS_STEP2",
                    "message": "step=2 时 basin 和 rainfall_id 均为必填参数"
                }
            return _step2_calculate_similarity(basin, rainfall_id, start_time, end_time, raster_image_url)

        if step == "3":
            if not all([basin, start_time, end_time, raster_image_url]):
                return {
                    "success": False,
                    "command": "FUNC_RAINFALL_SIMILARITY_ANALYSIS_STEP3",
                    "step": "3",
                    "message": "step=3 需要 basin、start_time、end_time、raster_image_url 参数"
                }
            return _step3_integrate_hydrology(basin, start_time, end_time, raster_image_url)

    # ================================================================
    # 水文局动态预报数据工具（Task 2-3）
    # ================================================================

    @mcp.tool(auth=require_scopes("forecast"))
    async def get_hydrology_forecast_plans(date_time: str) -> dict:
        """
        根据时间获取水文局预报方案列表。

        调用水文局 API（GET /pre/getSwPreWaterDataList），获取指定日期的所有可用预报方案。
        用户选择方案后，使用 get_hydrology_forecast_data 获取具体数据。

        Args:
            date_time: 日期，格式 YYYY-MM-DD，如 "2025-06-16"

        Returns:
            {
                "success": true,
                "date_time": "2025-06-16",
                "plan_count": 3,
                "plan_list": [
                    {"plcd": "7.20暴雨移植-预报", "time": "2025-07-18 08:00:00", "description": "..."},
                    ...
                ],
                "message": "共 3 个预报方案，请选择"
            }
        """
        logger.info(f"调用 get_hydrology_forecast_plans, date_time={date_time}")
        return hydrology_forecast_service.get_forecast_plans(date_time)

    @mcp.tool(auth=require_scopes("forecast"))
    async def get_hydrology_forecast_data(plcd: str, time: str) -> dict:
        """
        根据 plcd 和时间获取水文局预报方案数据，并写入 Access 数据库。

        调用水文局 API（GET /pre/getSwPreWaterDataByPlcd），获取方案详细数据，
        清空 Q_Inputsd 和 Q_Inputxd 表后写入新数据。
        写入完成后，可直接调用 generate_dispatch_scheme 进行调度计算。

        Args:
            plcd: 方案代码，如 "7.20暴雨移植-预报"
            time: 方案时间，如 "2025-07-18 08:00:00"

        Returns:
            {
                "success": true,
                "plcd": "7.20暴雨移植-预报",
                "time": "2025-07-18 08:00:00",
                "write_result": {
                    "upstream_count": 1780,
                    "downstream_count": 8346,
                    "total": 10126
                },
                "message": "预报数据已写入数据库，可调用 generate_dispatch_scheme 进行调度计算"
            }
        """
        logger.info(f"调用 get_hydrology_forecast_data, plcd={plcd}, time={time}")

        if not plcd or not time:
            return {
                "success": False,
                "command": "FUNC_GET_HYDROLOGY_FORECAST_DATA",
                "error": "plcd 和 time 均为必填参数"
            }

        # 1. 调用 API 获取数据
        api_result = hydrology_forecast_service.get_forecast_data(plcd, time)
        if not api_result.get("success"):
            return api_result

        api_data = api_result.get("data", [])
        if not api_data:
            return {
                "success": False,
                "command": "FUNC_GET_HYDROLOGY_FORECAST_DATA",
                "error": "API 返回数据为空",
                "plcd": plcd,
                "time": time
            }

        # 2. 写入 Access 数据库
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        dispatch_dir = os.path.join(project_root, 'src', 'services', 'external_api', 'RegualDispacth')
        mdb_path = os.path.join(dispatch_dir, '6', 'data.mdb')

        if not os.path.exists(mdb_path):
            return {
                "success": False,
                "command": "FUNC_GET_HYDROLOGY_FORECAST_DATA",
                "error": f"数据库文件不存在: {mdb_path}"
            }

        conn = None
        try:
            if platform.system() == "Windows":
                driver_name = "Microsoft Access Driver (*.mdb, *.accdb)"
                conn_str = f'DRIVER={{{driver_name}}};DBQ={mdb_path};'
                conn = pyodbc.connect(conn_str)
                cursor = conn.cursor()
                write_result = hydrology_forecast_service.write_to_access_db(api_data, conn, cursor)
            else:
                write_result = hydrology_forecast_service.write_to_access_db(api_data, None, None, mdb_path)

            if write_result.get("success"):
                if conn:
                    conn.close()
                return {
                    "success": True,
                    "command": "FUNC_GET_HYDROLOGY_FORECAST_DATA",
                    "plcd": plcd,
                    "time": time,
                    "write_result": {
                        "upstream_count": write_result["upstream_count"],
                        "downstream_count": write_result["downstream_count"],
                        "total": write_result["total"],
                        "errors": write_result.get("errors", [])
                    },
                    "message": f"预报数据已写入数据库（上游 {write_result['upstream_count']} 条，下游 {write_result['downstream_count']} 条），可调用 generate_dispatch_scheme 进行调度计算"
                }
            else:
                if conn:
                    conn.close()
                return {
                    "success": False,
                    "command": "FUNC_GET_HYDROLOGY_FORECAST_DATA",
                    "error": f"写入数据库失败: {write_result.get('error', '')}",
                    "write_result": write_result
                }
        except pyodbc.Error as e:
            logger.error(f"get_hydrology_forecast_data 数据库错误: {e}")
            return {
                "success": False,
                "command": "FUNC_GET_HYDROLOGY_FORECAST_DATA",
                "error": f"数据库操作失败: {str(e)}"
            }
        except Exception as e:
            logger.error(f"get_hydrology_forecast_data 出错: {e}")
            return {
                "success": False,
                "command": "FUNC_GET_HYDROLOGY_FORECAST_DATA",
                "error": f"获取预报数据失败: {str(e)}"
            }
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass


