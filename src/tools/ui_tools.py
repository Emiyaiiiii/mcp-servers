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

        scheme = None
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

        if not scheme:
            return_value = {
                "success": False,
                "error": "未找到可用的调度方案",
                "task_id": task_id
            }
            logger.debug(f"send_simulation_command 返回结果: {return_value}")
            return return_value

        reservoir_schemes = {}
        try:
            from src.tools.plan_tools import _generate_xiaolangdi_scheme_core, _generate_sanmenxia_scheme_core
            
            reservoirs = scheme.get("reservoirs", {})
            
            xld_data = reservoirs.get("小浪底水库", {})
            if xld_data:
                timeseries = xld_data.get("timeseries", [])
                if timeseries:
                    max_outflow = None
                    max_level = None
                    for ts in timeseries:
                        outflow = ts.get("outflow")
                        level = ts.get("water_level")
                        if outflow is not None and (max_outflow is None or outflow > max_outflow):
                            max_outflow = outflow
                        if level is not None and (max_level is None or level > max_level):
                            max_level = level
                    xld_scheme = _generate_xiaolangdi_scheme_core(
                        date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        liu_liang=max_outflow if max_outflow is not None else 1500,
                        shui_wei=max_level if max_level is not None else 240,
                        han_sha_liang=10.0
                    )
                    reservoir_schemes["小浪底水库"] = xld_scheme
            
            smx_data = reservoirs.get("三门峡水库", {})
            if smx_data:
                timeseries = smx_data.get("timeseries", [])
                if timeseries:
                    max_outflow = None
                    max_level = None
                    for ts in timeseries:
                        outflow = ts.get("outflow")
                        level = ts.get("water_level")
                        if outflow is not None and (max_outflow is None or outflow > max_outflow):
                            max_outflow = outflow
                        if level is not None and (max_level is None or level > max_level):
                            max_level = level
                    smx_scheme = _generate_sanmenxia_scheme_core(
                        date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        liu_liang=max_outflow if max_outflow is not None else 1000,
                        shui_wei=max_level if max_level is not None else 310,
                        han_sha_liang=10.0
                    )
                    reservoir_schemes["三门峡水库"] = smx_scheme
        except Exception as e:
            logger.warning(f"生成孔洞开启方案失败: {e}")

        scheme_details = {
            "scheme_id": scheme.get("scheme_id", scheme_id),
            "scheme_name": scheme.get("scheme_name", ""),
            "description": scheme.get("description", ""),
            "basin": scheme.get("basin", ""),
            "start_date": scheme.get("start_date", ""),
            "end_date": scheme.get("end_date", ""),
            "constraints": scheme.get("constraints", []),
            "details": scheme.get("details", []),
            "constraints_applied": scheme.get("constraints_applied", {}),
            "original_scheme": scheme,
            "reservoir_schemes": reservoir_schemes
        }

        data = {
            "task_id": task_id,
            "scheme_id": scheme_id,
            "scheme": scheme,
            "scheme_details": scheme_details,
            "reservoir_schemes": reservoir_schemes,
            "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        await send_ui_command_async("FUNC_UI_START_SIMULATION", data, target="page", session_id=session_id)

        return_value = {
            "success": True,
            "task_id": task_id,
            "scheme_id": scheme_id,
            "scheme_name": scheme.get("scheme_name", ""),
            "message": "预演指令已发送",
            "command": "FUNC_UI_START_SIMULATION",
            "scheme_details": scheme_details,
            "reservoir_schemes": reservoir_schemes
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

    @mcp.tool()
    async def send_plan_document_url(
        document_url: str,
        document_name: str,
        session_id: str = None
    ) -> dict:
        """将预案文档URL发送给前端展示或下载。

        Args:
            document_url: 预案文档的访问URL，例如: "/mnt/user-data/outputs/五库联调调度预案-DS-0001-20260526.md"
            document_name: 预案文档名称，用于前端显示，例如: "五库联调调度方案-20260512.md"
            session_id: 目标 session_id（自动从上下文获取，无需用户输入）

        Returns:
            发送文档URL的确认信息
        """
        logger.info(f"调用 send_plan_document_url，收到参数: document_url={repr(document_url)}, document_name={repr(document_name)}, session_id={repr(session_id)}")
        from datetime import datetime

        data = {
            "document_url": document_url,
            "document_name": document_name,
            "send_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        await send_ui_command_async("FUNC_UI_SHOW_PLAN_DOCUMENT", data, target="page", session_id=session_id)

        return_value = {
            "success": True,
            "document_url": document_url,
            "document_name": document_name,
            "message": "预案文档URL已发送",
            "command": "FUNC_UI_SHOW_PLAN_DOCUMENT"
        }
        logger.debug(f"send_plan_document_url 返回结果: {return_value}")
        return return_value

    @mcp.tool()
    async def highlight_warnings(
        markers: list,
        session_id: str = None
    ) -> dict:
        """在GIS场景中高亮显示告警站点。

        当水位或流量超警时，调用此工具在GIS场景中以醒目颜色高亮对应水库或水文站站点，
        便于决策者直观判断当前险情分布。

        Args:
            markers: 告警标记列表，每项为一个 dict：
                {
                    "id": "BDA00000761",        // 站点编码（水库编码或水文站码）
                    "name": "河口村水库",        // 站点名称
                    "type": "reservoir",        // 类型：reservoir（水库）或 station（水文站）
                    "warning_type": "water_level", // 告警类型：water_level（水位）或 flow（流量）
                    "current_value": 287.5,     // 当前值（水位：米；流量：m³/s）
                    "threshold": 285.43,        // 阈值（水位：汛限/校核水位；流量：预警流量）
                    "level": "red"              // 告警级别：red（红色/超校核）、orange（橙色/超汛限）、yellow（黄色/超预警）
                }
                如果当前无任何告警，传入空列表 []，场景中将清除所有告警高亮。
            session_id: 目标 session_id（可选），如果不指定，则广播到所有连接

        Returns:
            发送高亮指令的确认信息
        """
        logger.info(f"调用 highlight_warnings，收到参数: markers={len(markers)} 个, session_id={repr(session_id)}")
        result = await scene_connector.send_warning_highlight_async(markers, target_session=session_id)
        warning_count = len(markers)
        red_count = sum(1 for m in markers if m.get("level") == "red")
        orange_count = sum(1 for m in markers if m.get("level") == "orange")
        yellow_count = sum(1 for m in markers if m.get("level") == "yellow")
        return_value = {
            "success": True,
            "marker_count": warning_count,
            "breakdown": {
                "red": red_count,
                "orange": orange_count,
                "yellow": yellow_count
            },
            "message": f"GIS告警高亮已更新：{warning_count} 个站点（红色{red_count}、橙色{orange_count}、黄色{yellow_count}）",
            "command": "FUNC_WARNING_HIGHLIGHT",
            "response": result
        }
        logger.debug(f"highlight_warnings 返回结果: {return_value}")
        return return_value

    @mcp.tool()
    async def clear_warning_highlights(
        marker_ids: list = None,
        session_id: str = None
    ) -> dict:
        """清除GIS场景中的告警高亮。

        Args:
            marker_ids: 要清除的站点编码列表，如 ["BDA00000761", "40104360"]，
                为空或 None 时清除全部告警高亮
            session_id: 目标 session_id（可选），如果不指定，则广播到所有连接

        Returns:
            发送清除指令的确认信息
        """
        logger.info(f"调用 clear_warning_highlights，收到参数: marker_ids={repr(marker_ids)}, session_id={repr(session_id)}")
        result = await scene_connector.clear_warning_highlight_async(marker_ids, target_session=session_id)
        return_value = {
            "success": True,
            "cleared_ids": marker_ids,
            "message": f"已清除告警高亮（{'全部' if not marker_ids else f'{len(marker_ids)}个'}）",
            "command": "FUNC_WARNING_HIGHLIGHT",
            "response": result
        }
        logger.debug(f"clear_warning_highlights 返回结果: {return_value}")
        return return_value

    @mcp.tool()
    async def show_evacuation_routes(
        village_ids: list,
        session_id: str = None
    ) -> dict:
        """在GIS场景中显示撤离转移路线标注。

        根据村庄ID列表，从数据库查询转移路线数据后发送到GIS场景标注。

        Args:
            village_ids: 村庄ID列表，如 [123, 456, 789]。
                由 query_evacuation 返回结果中的 village_id 字段获取。
                传入空列表 [] 可清除全部标注。
            session_id: 目标 session_id（可选），如果不指定，则广播到所有连接

        Returns:
            发送标注指令的确认信息
        """
        logger.info(f"调用 show_evacuation_routes，收到 village_ids: {village_ids}, session_id={repr(session_id)}")

        if not village_ids:
            result = await scene_connector.clear_evacuation_routes_async(target_session=session_id)
            return {"success": True, "route_count": 0, "message": "已清除全部转移路线标注"}

        placeholders = ','.join('?' * len(village_ids))
        from src.services.database.connection import get_db
        db = get_db()
        rows = db.execute_query(
            f"""
            SELECT v.id AS village_id,
                   v.village_name,
                   r.name AS reservoir_name,
                   w.water_level,
                   e.evacuation_location,
                   e.evacuation_route,
                   e.contact_name,
                   e.contact_phone
            FROM villages v
            JOIN townships t ON v.township_id = t.id
            JOIN water_level_thresholds w ON t.water_level_id = w.id
            JOIN reservoirs r ON w.reservoir_code = r.code
            LEFT JOIN evacuation_details e ON v.id = e.village_id
            WHERE v.id IN ({placeholders})
            """,
            village_ids
        )

        routes = []
        for row in rows:
            if row.get('village_id'):
                routes.append({
                    "id": str(row['village_id']),
                    "name": row.get('village_name', ''),
                    "reservoir": row.get('reservoir_name', ''),
                    "water_level": row.get('water_level'),
                    "evacuation_location": row.get('evacuation_location', ''),
                    "evacuation_route": row.get('evacuation_route', ''),
                    "contact_name": row.get('contact_name', ''),
                    "contact_phone": row.get('contact_phone', ''),
                })

        result = await scene_connector.send_evacuation_routes_async(routes, target_session=session_id)
        return_value = {
            "success": True,
            "route_count": len(routes),
            "message": f"已发送 {len(routes)} 条转移路线标注到GIS场景",
            "command": "FUNC_EVACUATION_ROUTE_SHOW",
            "response": result
        }
        logger.debug(f"show_evacuation_routes 返回结果: {return_value}")
        return return_value

    @mcp.tool()
    async def clear_evacuation_routes(
        route_ids: list = None,
        session_id: str = None
    ) -> dict:
        """清除GIS场景中的转移路线标注。

        Args:
            route_ids: 要清除的路线ID列表，如 ["village_1", "village_2"]，
                为空或 None 时清除全部转移路线标注
            session_id: 目标 session_id（可选），如果不指定，则广播到所有连接

        Returns:
            发送清除指令的确认信息
        """
        logger.info(f"调用 clear_evacuation_routes，收到参数: route_ids={repr(route_ids)}, session_id={repr(session_id)}")
        result = await scene_connector.clear_evacuation_routes_async(route_ids, target_session=session_id)
        return_value = {
            "success": True,
            "cleared_ids": route_ids,
            "message": f"已清除转移路线标注（{'全部' if not route_ids else f'{len(route_ids)}条'}）",
            "command": "FUNC_EVACUATION_ROUTE_SHOW",
            "response": result
        }
        logger.debug(f"clear_evacuation_routes 返回结果: {return_value}")
        return return_value
