from typing import Dict, Any
from mcp.server.fastmcp import FastMCP
from src.services.scene_connector import scene_connector
from src.services.scheme_storage import get_scheme, get_all_schemes
from src.utils.station_codes import (
    get_reservoir_code, get_station_code,
    search_reservoir, search_station,
    get_all_reservoirs, get_all_stations,
    get_reservoir_station_code
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

    @mcp.tool()
    async def navigate_to_reservoir_overview(session_id: str = None) -> dict:
        """控制前端跳转到水库总览页面

        Args:
            session_id: 目标 session_id（可选），如果不指定，则广播到所有连接

        Returns:
            发送跳转指令的确认信息
        """
        logger.info(f"调用 navigate_to_reservoir_overview，收到参数: session_id={repr(session_id)}")

        result = await send_ui_command_async("FUNC_UI_OPEN_RESERVOIR_OVERVIEW", {}, session_id=session_id)
        return_value = {
            "success": True,
            "is_overview": True,
            "command": "FUNC_UI_OPEN_RESERVOIR_OVERVIEW",
            "response": result
        }
        logger.debug(f"navigate_to_reservoir_overview 返回结果: {return_value}")
        return return_value

    @mcp.tool()
    async def navigate_to_reservoir_detail(
        reservoir_name: str,
        start_time: str,
        end_time: str,
        session_id: str = None
    ) -> dict:
        """控制前端跳转到指定水库的实时数据详情页面

        Args:
            reservoir_name: 水库名称（必须是中文），例如: "小浪底"、"三门峡"、"陆浑"、"故县"、"河口村"
            start_time: 开始时间（必传，默认三天前）。格式: yyyy-MM-dd HH:mm:ss，例如: "2026-04-15 00:00:00"
            end_time: 结束时间（必传，默认现在）。格式: yyyy-MM-dd HH:mm:ss，例如: "2026-04-18 00:00:00"
            session_id: 目标 session_id（可选），如果不指定，则广播到所有连接

        Returns:
            发送跳转指令的确认信息
        """
        logger.info(f"调用 navigate_to_reservoir_detail，收到参数: reservoir_name={repr(reservoir_name)}, start_time={repr(start_time)}, end_time={repr(end_time)}, session_id={repr(session_id)}")

        code = get_reservoir_code(reservoir_name)
        if not code:
            reservoirs = search_reservoir(reservoir_name)
            if reservoirs:
                return_value = {"success": False, "error": f"未找到水库: {reservoir_name}，类似名称: {[r['name'] for r in reservoirs[:3]]}"}
                logger.debug(f"navigate_to_reservoir_detail 返回结果: {return_value}")
                return return_value
            return_value = {"success": False, "error": f"未找到水库: {reservoir_name}"}
            logger.debug(f"navigate_to_reservoir_detail 返回结果: {return_value}")
            return return_value

        reservoir_name_cn = _get_reservoir_name_by_code(code)
        station_code = get_reservoir_station_code(code)
        data = {
            "reservoir": station_code or code,
            "reservoir_name": reservoir_name_cn or reservoir_name,
            "start_time": start_time,
            "end_time": end_time
        }

        result = await send_ui_command_async("FUNC_UI_OPEN_RESERVOIR_DETAIL", data, session_id=session_id)
        return_value = {
            "success": True,
            "reservoir_code": code,
            "station_code": station_code,
            "reservoir_name": reservoir_name_cn,
            "is_overview": False,
            "start_time": start_time,
            "end_time": end_time,
            "command": "FUNC_UI_OPEN_RESERVOIR_DETAIL",
            "response": result
        }
        logger.debug(f"navigate_to_reservoir_detail 返回结果: {return_value}")
        return return_value

    @mcp.tool()
    async def navigate_to_station_overview(session_id: str = None) -> dict:
        """控制前端跳转到水文站总览页面

        Args:
            session_id: 目标 session_id（可选），如果不指定，则广播到所有连接

        Returns:
            发送跳转指令的确认信息
        """
        logger.info(f"调用 navigate_to_station_overview，收到参数: session_id={repr(session_id)}")

        result = await send_ui_command_async("FUNC_UI_OPEN_STATION_OVERVIEW", {}, session_id=session_id)
        return_value = {
            "success": True,
            "is_overview": True,
            "command": "FUNC_UI_OPEN_STATION_OVERVIEW",
            "response": result
        }
        logger.debug(f"navigate_to_station_overview 返回结果: {return_value}")
        return return_value

    @mcp.tool()
    async def navigate_to_station_detail(
        station_name: str,
        start_time: str,
        end_time: str,
        session_id: str = None
    ) -> dict:
        """控制前端跳转到指定水文站的实时数据详情页面

        Args:
            station_name: 水文站名称（必须是中文），例如: "花园口"、"高村"、"孙口"、"艾山"、"泺口"、"利津"
            start_time: 开始时间（必传，默认三天前）。格式: yyyy-MM-dd HH:mm:ss，例如: "2026-04-15 00:00:00"
            end_time: 结束时间（必传，默认现在）。格式: yyyy-MM-dd HH:mm:ss，例如: "2026-04-18 00:00:00"
            session_id: 目标 session_id（可选），如果不指定，则广播到所有连接

        Returns:
            发送跳转指令的确认信息
        """
        logger.info(f"调用 navigate_to_station_detail，收到参数: station_name={repr(station_name)}, start_time={repr(start_time)}, end_time={repr(end_time)}, session_id={repr(session_id)}")

        code = get_station_code(station_name)
        if not code:
            stations = search_station(station_name)
            if stations:
                return_value = {"success": False, "error": f"未找到水文站: {station_name}，类似名称: {[s['name'] for s in stations[:3]]}"}
                logger.debug(f"navigate_to_station_detail 返回结果: {return_value}")
                return return_value
            return_value = {"success": False, "error": f"未找到水文站: {station_name}"}
            logger.debug(f"navigate_to_station_detail 返回结果: {return_value}")
            return return_value

        station_name_cn = _get_station_name_by_code(code)
        data = {
            "station": code,
            "station_name": station_name_cn or station_name,
            "start_time": start_time,
            "end_time": end_time
        }

        result = await send_ui_command_async("FUNC_UI_OPEN_STATION_DETAIL", data, session_id=session_id)
        return_value = {
            "success": True,
            "station_code": code,
            "station_name": station_name_cn,
            "is_overview": False,
            "start_time": start_time,
            "end_time": end_time,
            "command": "FUNC_UI_OPEN_STATION_DETAIL",
            "response": result
        }
        logger.debug(f"navigate_to_station_detail 返回结果: {return_value}")
        return return_value

    @mcp.tool()
    async def navigate_to_rainfall_overview(session_id: str = None) -> dict:
        """控制前端跳转到降雨信息总览页面

        Args:
            session_id: 目标 session_id（可选），如果不指定，则广播到所有连接

        Returns:
            发送跳转指令的确认信息
        """
        logger.info(f"调用 navigate_to_rainfall_overview，收到参数: session_id={repr(session_id)}")

        result = await send_ui_command_async("FUNC_UI_NAVIGATE_RAINFALL", {}, session_id=session_id)
        return_value = {
            "success": True,
            "command": "FUNC_UI_NAVIGATE_RAINFALL",
            "response": result
        }
        logger.debug(f"navigate_to_rainfall_overview 返回结果: {return_value}")
        return return_value

    @mcp.tool()
    async def navigate_to_rainfall_basin(
        basin: str,
        start_time: str,
        end_time: str,
        session_id: str = None
    ) -> dict:
        """控制前端跳转到指定流域的降雨信息页面

        Args:
            basin: 流域名称，例如: "黄河"、"洛河"、"伊洛河"
            start_time: 开始时间（必传，默认三天前）。格式: yyyy-MM-dd HH:mm:ss，例如: "2026-04-15 00:00:00"
            end_time: 结束时间（必传，默认现在）。格式: yyyy-MM-dd HH:mm:ss，例如: "2026-04-18 00:00:00"
            session_id: 目标 session_id（可选），如果不指定，则广播到所有连接

        Returns:
            发送跳转指令的确认信息
        """
        logger.info(f"调用 navigate_to_rainfall_basin，收到参数: basin={repr(basin)}, start_time={repr(start_time)}, end_time={repr(end_time)}, session_id={repr(session_id)}")

        data = {
            "basin": basin,
            "start_time": start_time,
            "end_time": end_time
        }

        result = await send_ui_command_async("FUNC_UI_NAVIGATE_RAINFALL", data, session_id=session_id)
        return_value = {
            "success": True,
            "basin": basin,
            "start_time": start_time,
            "end_time": end_time,
            "command": "FUNC_UI_NAVIGATE_RAINFALL",
            "response": result
        }
        logger.debug(f"navigate_to_rainfall_basin 返回结果: {return_value}")
        return return_value

    @mcp.tool()
    async def navigate_to_similar_rainfall_page(
        start_time: str,
        end_time: str,
        session_id: str = None
    ) -> dict:
        """控制前端跳转到相似雨分析页面

        Args:
            start_time: 开始时间（必传）。格式: yyyy-MM-dd HH:mm:ss，例如: "2026-04-15 00:00:00"
            end_time: 结束时间（必传）。格式: yyyy-MM-dd HH:mm:ss，例如: "2026-04-18 00:00:00"
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
        logger.debug(f"navigate_to_similar_rainfall_page 返回结果: {return_value}")
        return return_value

    @mcp.tool()
    async def navigate_to_reservoir_forecast_page(
        reservoir_name: str,
        start_time: str,
        end_time: str,
        session_id: str = None
    ) -> dict:
        """控制前端跳转到水库预报页面

        Args:
            reservoir_name: 水库名称（必须是中文），例如: "小浪底"、"三门峡"、"陆浑"、"故县"、"河口村"
            start_time: 开始时间（必传，默认三天前）。格式: yyyy-MM-dd HH:mm:ss，例如: "2026-04-15 00:00:00"
            end_time: 结束时间（必传，默认现在）。格式: yyyy-MM-dd HH:mm:ss，例如: "2026-04-18 00:00:00"
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
                logger.debug(f"navigate_to_reservoir_forecast_page 返回结果: {return_value}")
                return return_value
            return_value = {"success": False, "error": f"未找到水库: {reservoir_name}"}
            logger.debug(f"navigate_to_reservoir_forecast_page 返回结果: {return_value}")
            return return_value

        reservoir_name_cn = _get_reservoir_name_by_code(code)
        station_code = get_reservoir_station_code(code)

        data = {
            "reservoir": station_code or code,
            "reservoir_name": reservoir_name_cn or reservoir_name,
            "start_time": start_time,
            "end_time": end_time
        }

        result = await send_ui_command_async("FUNC_UI_NAVIGATE_RESERVOIR_FORECAST", data, session_id=session_id)
        return_value = {
            "success": True,
            "reservoir_code": code,
            "station_code": station_code,
            "reservoir_name": reservoir_name_cn or reservoir_name,
            "start_time": start_time,
            "end_time": end_time,
            "command": "FUNC_UI_NAVIGATE_RESERVOIR_FORECAST",
            "response": result
        }
        logger.debug(f"navigate_to_reservoir_forecast_page 返回结果: {return_value}")
        return return_value

    @mcp.tool()
    async def navigate_to_control_guidance_overview(session_id: str = None) -> dict:
        """控制前端跳转到控导信息总览页面

        Args:
            session_id: 目标 session_id（可选），如果不指定，则广播到所有连接

        Returns:
            发送跳转指令的确认信息
        """
        logger.info(f"调用 navigate_to_control_guidance_overview，收到参数: session_id={repr(session_id)}")

        result = await send_ui_command_async("FUNC_UI_OPEN_CONTROL_GUIDANCE", {}, session_id=session_id)
        return_value = {
            "success": True,
            "is_overview": True,
            "command": "FUNC_UI_OPEN_CONTROL_GUIDANCE",
            "response": result
        }
        logger.debug(f"navigate_to_control_guidance_overview 返回结果: {return_value}")
        return return_value

    @mcp.tool()
    async def navigate_to_control_guidance_section(
        section_name: str,
        session_id: str = None
    ) -> dict:
        """控制前端跳转到指定河段/断面的控导信息页面

        Args:
            section_name: 河段/断面名称
            session_id: 目标 session_id（可选），如果不指定，则广播到所有连接

        Returns:
            发送跳转指令的确认信息
        """
        logger.info(f"调用 navigate_to_control_guidance_section，收到参数: section_name={repr(section_name)}, session_id={repr(session_id)}")

        data = {"section": section_name}
        result = await send_ui_command_async("FUNC_UI_OPEN_CONTROL_GUIDANCE", data, session_id=session_id)
        return_value = {
            "success": True,
            "section": section_name,
            "is_overview": False,
            "command": "FUNC_UI_OPEN_CONTROL_GUIDANCE",
            "response": result
        }
        logger.debug(f"navigate_to_control_guidance_section 返回结果: {return_value}")
        return return_value

    @mcp.tool()
    async def navigate_to_station_forecast_page(
        station_name: str,
        start_time: str,
        end_time: str,
        session_id: str = None
    ) -> dict:
        """控制前端跳转到水文站预报页面

        Args:
            station_name: 水文站名称（必须是中文），例如: "花园口"、"高村"、"孙口"、"艾山"、"泺口"、"利津"
            start_time: 开始时间（必传，默认三天前）。格式: yyyy-MM-dd HH:mm:ss，例如: "2026-04-15 00:00:00"
            end_time: 结束时间（必传，默认现在）。格式: yyyy-MM-dd HH:mm:ss，例如: "2026-04-18 00:00:00"
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
                logger.debug(f"navigate_to_station_forecast_page 返回结果: {return_value}")
                return return_value
            return_value = {"success": False, "error": f"未找到水文站: {station_name}"}
            logger.debug(f"navigate_to_station_forecast_page 返回结果: {return_value}")
            return return_value

        station_name_cn = _get_station_name_by_code(code)

        data = {
            "station": code,
            "station_name": station_name_cn or station_name,
            "start_time": start_time,
            "end_time": end_time
        }

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
        logger.debug(f"navigate_to_station_forecast_page 返回结果: {return_value}")
        return return_value

    @mcp.tool()
    async def generate_dispatch_scheme(
        constraints: str,
        target_flow: str = None,
        target_water_level: str = None,
        session_id: str = None
    ) -> dict:
        """生成五库联调调度方案单（模拟接口，后续会提供真实接口）。

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

        logger.debug(f"generate_dispatch_scheme 返回结果: {scheme}")
        return scheme

    @mcp.tool()
    async def send_simulation_command(
        scheme_id: str,
        session_id: str = None
    ) -> dict:
        """向前端发送预演指令，前端收到后执行具体的预演任务。

        Args:
            scheme_id: 调度方案ID（如 DS-0001），不传则由前端选择当前方案或使用默认方案
            session_id: 目标 session_id（自动从上下文获取，无需用户输入）

        Returns:
            发送预演指令的确认信息
        """
        logger.info(f"调用 send_simulation_command，收到参数: scheme_id={repr(scheme_id)}, session_id={repr(session_id)}")
        import uuid
        from datetime import datetime

        task_id = f"sim_{uuid.uuid4().hex[:8]}"

        if scheme_id:
            scheme = get_scheme(scheme_id)
            if not scheme:
                return_value = {
                    "success": False,
                    "error": f"未找到调度方案: {scheme_id}",
                    "task_id": task_id
                }
                logger.debug(f"send_simulation_command 返回结果: {return_value}")
                return return_value
        else:
            schemes = get_all_schemes()
            scheme = schemes[0] if schemes else None

        data = {
            "task_id": task_id,
            "scheme_id": scheme_id,
            "scheme": scheme,
            "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        await send_ui_command_async("FUNC_UI_START_SIMULATION", data, target="page", session_id=session_id)

        return_value = {
            "success": True,
            "task_id": task_id,
            "scheme_id": scheme_id,
            "message": "预演指令已发送",
            "command": "FUNC_UI_START_SIMULATION"
        }
        logger.debug(f"send_simulation_command 返回结果: {return_value}")
        return return_value

    @mcp.tool()
    async def trigger_simulation_execution(
        task_id: str,
        session_id: str = None
    ) -> dict:
        """向前端发送触发预演执行的指令，启动预演任务。

        Args:
            task_id: 预演任务ID（由 send_simulation_command 返回的 task_id）
            session_id: 目标 session_id（自动从上下文获取，无需用户输入）

        Returns:
            触发执行指令的确认信息
        """
        logger.info(f"调用 trigger_simulation_execution，收到参数: task_id={repr(task_id)}, session_id={repr(session_id)}")
        from datetime import datetime

        data = {
            "task_id": task_id,
            "execute_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": "execute"
        }

        await send_ui_command_async("FUNC_UI_TRIGGER_SIMULATION", data, target="page", session_id=session_id)

        return_value = {
            "success": True,
            "task_id": task_id,
            "message": "预演执行指令已发送",
            "command": "FUNC_UI_TRIGGER_SIMULATION"
        }
        logger.debug(f"trigger_simulation_execution 返回结果: {return_value}")
        return return_value
