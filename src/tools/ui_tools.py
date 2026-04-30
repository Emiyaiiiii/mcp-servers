from typing import Dict, Any
from fastmcp import FastMCP
from src.services.scene_connector import scene_connector
from src.utils.station_codes import (
    get_reservoir_code, get_station_code,
    search_reservoir, search_station,
    get_all_reservoirs, get_all_stations
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def send_ui_command_async(function: str, data: Dict[str, Any], target: str = "page", session_id: str = None) -> Dict[str, Any]:
    """发送UI指令
    
    Args:
        function: 指令函数名
        data: 指令数据
        target: 目标类型（page或scene）
        session_id: 目标 session_id（可选），如果不指定，则广播到所有连接
    """
    command = {
        "cmd": "lshh",
        "function": function,
        "data": data,
        "target": target
    }
    return await scene_connector.send_command_async(command, target_session=session_id)


def _get_reservoir_name_by_code(code: str) -> str | None:
    """根据水库编码获取标准名称"""
    if not code:
        return None
    reservoirs = get_all_reservoirs()
    for reservoir in reservoirs:
        if reservoir["code"] == code:
            return reservoir["name"]
    return None


def _get_station_name_by_code(code: str) -> str | None:
    """根据站点编码获取标准名称"""
    if not code:
        return None
    stations = get_all_stations()
    for station in stations:
        if station["code"] == code:
            return station["name"]
    return None


def register_ui_tools(mcp: FastMCP):

    @mcp.tool
    async def navigate_to_reservoir_page(
        reservoir_name: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        session_id: str | None = None
    ) -> dict:
        """控制前端跳转到水库实时数据页面
        
        Args:
            reservoir_name: 水库名称（必须是中文），例如: "小浪底"、"三门峡"、"陆浑"、"故县"、"河口村" 
                            不指定则跳转到水库总览页面
            start_time: 开始时间 (可选)。格式: YYYY-MM-DD 或 YYYY-MM-DD HH:mm
            end_time: 结束时间 (可选)。格式: YYYY-MM-DD 或 YYYY-MM-DD HH:mm
            session_id: 目标 session_id（可选），如果不指定，则广播到所有连接
        
        Returns:
            发送跳转指令的确认信息
        """
        logger.info(f"调用 navigate_to_reservoir_page，收到参数: reservoir_name={repr(reservoir_name)}, start_time={repr(start_time)}, end_time={repr(end_time)}, session_id={repr(session_id)}")
        data = {}
        reservoir_name_cn = None

        if reservoir_name:
            code = get_reservoir_code(reservoir_name)
            if not code:
                reservoirs = search_reservoir(reservoir_name)
                if reservoirs:
                    return_value = {"success": False, "error": f"未找到水库: {reservoir_name}，类似名称: {[r['name'] for r in reservoirs[:3]]}"}
                    logger.info(f"navigate_to_reservoir_page 返回结果: {return_value}")
                    return return_value
                return_value = {"success": False, "error": f"未找到水库: {reservoir_name}"}
                logger.info(f"navigate_to_reservoir_page 返回结果: {return_value}")
                return return_value

            # 获取标准名称
            reservoir_name_cn = _get_reservoir_name_by_code(code)
            data["reservoir"] = code
            data["reservoir_name"] = reservoir_name_cn or reservoir_name
            command = "FUNC_UI_OPEN_RESERVOIR_DETAIL"
        else:
            command = "FUNC_UI_OPEN_RESERVOIR_OVERVIEW"

        if start_time:
            data["start_time"] = start_time
        if end_time:
            data["end_time"] = end_time

        result = await send_ui_command_async(command, data, session_id=session_id)
        return_value = {
            "success": True,
            "reservoir_code": data.get("reservoir"),
            "reservoir_name": reservoir_name_cn,
            "is_overview": not bool(reservoir_name),
            "start_time": start_time,
            "end_time": end_time,
            "command": command,
            "response": result
        }
        logger.info(f"navigate_to_reservoir_page 返回结果: {return_value}")
        return return_value

    @mcp.tool
    async def navigate_to_station_page(
        station_name: str = None,
        start_time: str = None,
        end_time: str = None,
        session_id: str = None
    ) -> dict:
        """控制前端跳转到水文站实时数据页面
        
        Args:
            station_name: 水文站名称（必须是中文），例如: "花园口"、"高村"、"孙口"、"艾山"、"泺口"、"利津"
                            不指定则跳转到水文站总览页面
            start_time: 开始时间 (可选)。格式: YYYY-MM-DD 或 YYYY-MM-DD HH:mm
            end_time: 结束时间 (可选)。格式: YYYY-MM-DD 或 YYYY-MM-DD HH:mm
            session_id: 目标 session_id（可选），如果不指定，则广播到所有连接
        
        Returns:
            发送跳转指令的确认信息
        """
        logger.info(f"调用 navigate_to_station_page，收到参数: station_name={repr(station_name)}, start_time={repr(start_time)}, end_time={repr(end_time)}, session_id={repr(session_id)}")
        data = {}
        station_name_cn = None

        if station_name:
            code = get_station_code(station_name)
            if not code:
                stations = search_station(station_name)
                if stations:
                    return_value = {"success": False, "error": f"未找到水文站: {station_name}，类似名称: {[s['name'] for s in stations[:3]]}"}
                    logger.info(f"navigate_to_station_page 返回结果: {return_value}")
                    return return_value
                return_value = {"success": False, "error": f"未找到水文站: {station_name}"}
                logger.info(f"navigate_to_station_page 返回结果: {return_value}")
                return return_value

            # 获取标准名称
            station_name_cn = _get_station_name_by_code(code)
            data["station"] = code
            data["station_name"] = station_name_cn or station_name
            command = "FUNC_UI_OPEN_STATION_DETAIL"
        else:
            command = "FUNC_UI_OPEN_STATION_OVERVIEW"

        if start_time:
            data["start_time"] = start_time
        if end_time:
            data["end_time"] = end_time

        result = await send_ui_command_async(command, data, session_id=session_id)
        return_value = {
            "success": True,
            "station_code": data.get("station"),
            "station_name": station_name_cn,
            "is_overview": not bool(station_name),
            "start_time": start_time,
            "end_time": end_time,
            "command": command,
            "response": result
        }
        logger.info(f"navigate_to_station_page 返回结果: {return_value}")
        return return_value

    @mcp.tool
    async def navigate_to_rainfall_page(
        basin: str = None,
        start_time: str = None,
        end_time: str = None,
        session_id: str = None
    ) -> dict:
        """控制前端跳转到降雨信息页面
        
        Args:
            basin: 流域名称 (可选)。例如: 黄河, 洛河, 伊洛河
            start_time: 开始时间 (可选)。格式: YYYY-MM-DD 或 YYYY-MM-DD HH:mm
            end_time: 结束时间 (可选)。格式: YYYY-MM-DD 或 YYYY-MM-DD HH:mm
            session_id: 目标 session_id（可选），如果不指定，则广播到所有连接
        
        Returns:
            发送跳转指令的确认信息
        """
        logger.info(f"调用 navigate_to_rainfall_page，收到参数: basin={repr(basin)}, start_time={repr(start_time)}, end_time={repr(end_time)}, session_id={repr(session_id)}")
        data = {}
        if basin:
            data["basin"] = basin
        if start_time:
            data["start_time"] = start_time
        if end_time:
            data["end_time"] = end_time

        result = await send_ui_command_async("FUNC_UI_NAVIGATE_RAINFALL", data, session_id=session_id)
        return_value = {
            "success": True,
            "basin": basin,
            "start_time": start_time,
            "end_time": end_time,
            "command": "FUNC_UI_NAVIGATE_RAINFALL",
            "response": result
        }
        logger.info(f"navigate_to_rainfall_page 返回结果: {return_value}")
        return return_value

    @mcp.tool
    async def navigate_to_similar_rainfall_page(
        start_time: str,
        end_time: str,
        session_id: str = None
    ) -> dict:
        """控制前端跳转到相似雨分析页面
        
        Args:
            start_time: 开始时间。格式: YYYY-MM-DD 或 YYYY-MM-DD HH:mm
            end_time: 结束时间。格式: YYYY-MM-DD 或 YYYY-MM-DD HH:mm
            session_id: 目标 session_id（可选），如果不指定，则广播到所有连接
        
        Returns:
            发送跳转指令的确认信息
        """
        logger.info(f"调用 navigate_to_similar_rainfall_page，收到参数: start_time={repr(start_time)}, end_time={repr(end_time)}, session_id={repr(session_id)}")
        data = {
            "start_time": start_time,
            "end_time": end_time
        }

        result = await send_ui_command_async("FUNC_UI_NAVIGATE_SIMILAR_RAINFALL", data, session_id=session_id)
        return_value = {
            "success": True,
            "start_time": start_time,
            "end_time": end_time,
            "command": "FUNC_UI_NAVIGATE_SIMILAR_RAINFALL",
            "response": result
        }
        logger.info(f"navigate_to_similar_rainfall_page 返回结果: {return_value}")
        return return_value

    @mcp.tool
    async def navigate_to_reservoir_forecast_page(
        reservoir_name: str,
        start_time: str = None,
        end_time: str = None,
        session_id: str = None
    ) -> dict:
        """控制前端跳转到水库降雨预报页面
        
        Args:
            reservoir_name: 水库名称（必须是中文），例如: "小浪底"、"三门峡"、"陆浑"、"故县"、"河口村"
            start_time: 开始时间 (可选)。格式: YYYY-MM-DD 或 YYYY-MM-DD HH:mm
            end_time: 结束时间 (可选)。格式: YYYY-MM-DD 或 YYYY-MM-DD HH:mm
            session_id: 目标 session_id（可选），如果不指定，则广播到所有连接
        
        Returns:
            发送跳转指令的确认信息
        """
        logger.info(f"调用 navigate_to_reservoir_forecast_page，收到参数: reservoir_name={repr(reservoir_name)}, start_time={repr(start_time)}, end_time={repr(end_time)}, session_id={repr(session_id)}")
        code = get_reservoir_code(reservoir_name)
        if not code:
            reservoirs = search_reservoir(reservoir_name)
            if reservoirs:
                return_value = {"success": False, "error": f"未找到水库: {reservoir_name}，类似名称: {[r['name'] for r in reservoirs[:3]]}"}
                logger.info(f"navigate_to_reservoir_forecast_page 返回结果: {return_value}")
                return return_value
            return_value = {"success": False, "error": f"未找到水库: {reservoir_name}"}
            logger.info(f"navigate_to_reservoir_forecast_page 返回结果: {return_value}")
            return return_value

        # 获取标准名称
        reservoir_name_cn = _get_reservoir_name_by_code(code)

        data = {
            "reservoir": code,
            "reservoir_name": reservoir_name_cn or reservoir_name
        }
        if start_time:
            data["start_time"] = start_time
        if end_time:
            data["end_time"] = end_time

        result = await send_ui_command_async("FUNC_UI_NAVIGATE_RESERVOIR_FORECAST", data, session_id=session_id)
        return_value = {
            "success": True,
            "reservoir_code": code,
            "reservoir_name": reservoir_name_cn or reservoir_name,
            "start_time": start_time,
            "end_time": end_time,
            "command": "FUNC_UI_NAVIGATE_RESERVOIR_FORECAST",
            "response": result
        }
        logger.info(f"navigate_to_reservoir_forecast_page 返回结果: {return_value}")
        return return_value

    @mcp.tool
    async def navigate_to_control_guidance_page(
        section_name: str = None,
        session_id: str = None
    ) -> dict:
        """控制前端跳转到控导信息页面
        
        Args:
            section_name: 河段/断面名称 (可选)。不指定则跳转到控导总览页面
            session_id: 目标 session_id（可选），如果不指定，则广播到所有连接
        
        Returns:
            发送跳转指令的确认信息
        """
        logger.info(f"调用 navigate_to_control_guidance_page，收到参数: section_name={repr(section_name)}, session_id={repr(session_id)}")
        data = {
            "section": section_name
        }

        result = await send_ui_command_async("FUNC_UI_OPEN_CONTROL_GUIDANCE", data, session_id=session_id)
        return_value = {
            "success": True,
            "section": section_name,
            "command": "FUNC_UI_OPEN_CONTROL_GUIDANCE",
            "response": result
        }
        logger.info(f"navigate_to_control_guidance_page 返回结果: {return_value}")
        return return_value

    @mcp.tool
    async def navigate_to_station_forecast_page(
        station_name: str,
        start_time: str = None,
        end_time: str = None,
        session_id: str = None
    ) -> dict:
        """控制前端跳转到水文站降雨预报页面
        
        Args:
            station_name: 水文站名称（必须是中文），例如: "花园口"、"高村"、"孙口"、"艾山"、"泺口"、"利津"
            start_time: 开始时间 (可选)。格式: YYYY-MM-DD 或 YYYY-MM-DD HH:mm
            end_time: 结束时间 (可选)。格式: YYYY-MM-DD 或 YYYY-MM-DD HH:mm
            session_id: 目标 session_id（可选），如果不指定，则广播到所有连接
        
        Returns:
            发送跳转指令的确认信息
        """
        logger.info(f"调用 navigate_to_station_forecast_page，收到参数: station_name={repr(station_name)}, start_time={repr(start_time)}, end_time={repr(end_time)}, session_id={repr(session_id)}")
        code = get_station_code(station_name)
        if not code:
            stations = search_station(station_name)
            if stations:
                return_value = {"success": False, "error": f"未找到水文站: {station_name}，类似名称: {[s['name'] for s in stations[:3]]}"}
                logger.info(f"navigate_to_station_forecast_page 返回结果: {return_value}")
                return return_value
            return_value = {"success": False, "error": f"未找到水文站: {station_name}"}
            logger.info(f"navigate_to_station_forecast_page 返回结果: {return_value}")
            return return_value

        # 获取标准名称
        station_name_cn = _get_station_name_by_code(code)

        data = {
            "station": code,
            "station_name": station_name_cn or station_name
        }
        if start_time:
            data["start_time"] = start_time
        if end_time:
            data["end_time"] = end_time

        result = await send_ui_command_async("FUNC_UI_NAVIGATE_STATION_FORECAST", data, session_id=session_id)
        return_value = {
            "success": True,
            "station_code": code,
            "station_name": station_name_cn or station_name,
            "start_time": start_time,
            "end_time": end_time,
            "command": "FUNC_UI_NAVIGATE_STATION_FORECAST",
            "response": result
        }
        logger.info(f"navigate_to_station_forecast_page 返回结果: {return_value}")
        return return_value

    @mcp.tool
    async def generate_dispatch_scheme(
        constraints: str,
        target_flow: str = None,
        target_water_level: str = None,
        session_id: str = None
    ) -> dict:
        """
        生成五库联调调度方案单（模拟接口，后续会提供真实接口）。

        Args:
            constraints: 用户约束条件描述，如"控制花园口流量不超过4500m³/s，调整小浪底水位不超248m"
            target_flow: 目标流量约束（可选），如"4500m³/s"
            target_water_level: 目标水位约束（可选），如"248m"
            session_id: 目标 session_id（可选），如果不指定，则广播到所有连接

        Returns:
            调度方案单，包含五库调度指令
        """
        logger.info(f"调用 generate_dispatch_scheme，收到参数: constraints={repr(constraints)}, target_flow={repr(target_flow)}, target_water_level={repr(target_water_level)}, session_id={repr(session_id)}")
        import random
        from datetime import datetime

        reservoirs = ["陆浑", "故县", "三门峡", "小浪底", "河口村"]
        reservoir_codes = ["LuHun", "GuXian", "SanMenXia", "XiaoLangDi", "HeKouCun"]

        dispatch_instructions = []
        for name, code in zip(reservoirs, reservoir_codes):
            current_level = round(random.uniform(270, 315), 1)
            target_level = round(current_level + random.uniform(-5, 5), 1)
            outflow = round(random.uniform(300, 2000), 0)

            gate_action = "开启" if random.random() > 0.5 else "关闭"

            dispatch_instructions.append({
                "水库": name,
                "水库编码": code,
                "当前水位": f"{current_level}米",
                "目标水位": f"{target_level}米",
                "闸门操作": gate_action,
                "出库流量": f"{outflow:.0f} m³/s"
            })

        if target_flow:
            actual_flow = round(random.uniform(float(target_flow.replace("m³/s", "")) * 0.9,
                                               float(target_flow.replace("m³/s", "")) * 1.1), 0)
        else:
            actual_flow = round(random.uniform(3000, 5000), 0)

        if target_water_level:
            actual_level = round(random.uniform(float(target_water_level.replace("m", "")) - 2,
                                               float(target_water_level.replace("m", "")) + 1), 1)
        else:
            actual_level = round(random.uniform(245, 252), 1)

        meets_constraint = True
        if target_flow and actual_flow > float(target_flow.replace("m³/s", "")):
            meets_constraint = False
        if target_water_level and actual_level > float(target_water_level.replace("m", "")):
            meets_constraint = False

        scheme = {
            "success": True,
            "scheme_name": "五库联调调度方案",
            "generate_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user_constraints": {
                "约束描述": constraints,
                "目标流量": target_flow,
                "目标水位": target_water_level
            },
            "dispatch_instructions": dispatch_instructions,
            "expected_effects": {
                "花园口流量": f"{actual_flow:.0f} m³/s",
                "小浪底水位": f"{actual_level} m",
                "是否满足约束": "满足" if meets_constraint else "不满足"
            },
            "command": "FUNC_GENERATE_DISPATCH_SCHEME"
        }

        await send_ui_command_async("FUNC_UI_DISPATCH_SCHEME", scheme, target="page", session_id=session_id)

        logger.info(f"generate_dispatch_scheme 返回结果: {scheme}")
        return scheme

    @mcp.tool
    async def send_simulation_command(
        dispatch_scheme: str,
        session_id: str = None
    ) -> dict:
        """
        向前端发送预演指令，前端收到后执行具体的预演任务。
        发送后会一直等待前端返回预演结果（超时时间1小时）。

        Args:
            dispatch_scheme: 调度方案单（JSON格式字符串）
            session_id: 目标 session_id（可选），如果不指定，则广播到所有连接

        Returns:
            前端返回的预演结果
        """
        logger.info(f"调用 send_simulation_command，收到参数: dispatch_scheme={repr(dispatch_scheme)}, session_id={repr(session_id)}")
        import uuid
        from datetime import datetime

        try:
            scheme_data = eval(dispatch_scheme) if isinstance(dispatch_scheme, str) else dispatch_scheme
        except:
            return_value = {"success": False, "error": "调度方案单格式错误"}
            logger.info(f"send_simulation_command 返回结果: {return_value}")
            return return_value

        task_id = f"sim_{uuid.uuid4().hex[:8]}"

        command = {
            "cmd": "lshh",
            "function": "FUNC_UI_START_SIMULATION",
            "target": "page",
            "data": {
                "task_id": task_id,
                "dispatch_scheme": scheme_data,
                "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        }

        result = await scene_connector.send_command_and_wait_async(command, timeout=3600, target_session=session_id)

        return_value = {
            "success": True,
            "task_id": task_id,
            "message": "预演执行完成",
            "command": "FUNC_UI_START_SIMULATION",
            "response": result
        }
        logger.info(f"send_simulation_command 返回结果: {return_value}")
        return return_value
