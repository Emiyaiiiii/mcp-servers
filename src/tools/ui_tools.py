from typing import Dict, Any
from mcp.server.fastmcp import FastMCP
from src.services.communication.command_sender import command_sender
from src.services.storage.scheme_storage import get_scheme, get_all_schemes
from src.utils.station_codes import (
    get_reservoir_code, get_station_code,
    search_reservoir, search_station,
    get_all_reservoirs, get_all_stations,
    get_reservoir_station_code
)
from src.utils.response_helper import success_response, error_response
from src.utils.logger import get_logger

logger = get_logger(__name__)


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
    async def navigate_to_reservoir_overview() -> dict:
        """控制前端跳转到水库总览页面

        Returns:
            发送跳转指令的确认信息
        """
        logger.info(f"调用 navigate_to_reservoir_overview")

        result = await command_sender.send_ui_command("FUNC_UI_OPEN_RESERVOIR_OVERVIEW", {})
        return_value = success_response(
            command="FUNC_UI_OPEN_RESERVOIR_OVERVIEW",
            response=result,
            is_overview=True
        )
        logger.debug(f"navigate_to_reservoir_overview 返回结果: {return_value}")
        return return_value

    @mcp.tool()
    async def navigate_to_reservoir_detail(
        reservoir_name: str,
        start_time: str,
        end_time: str
    ) -> dict:
        """控制前端跳转到指定水库的实时数据详情页面

        Args:
            reservoir_name: 水库名称（必须是中文），例如: "小浪底"、"三门峡"、"陆浑"、"故县"、"河口村"
            start_time: 开始时间（必传，默认三天前）。格式: yyyy-MM-dd HH:mm:ss，例如: "2026-04-15 00:00:00"
            end_time: 结束时间（必传，默认现在）。格式: yyyy-MM-dd HH:mm:ss，例如: "2026-04-18 00:00:00"

        Returns:
            发送跳转指令的确认信息
        """
        logger.info(f"调用 navigate_to_reservoir_detail，收到参数: reservoir_name={repr(reservoir_name)}, start_time={repr(start_time)}, end_time={repr(end_time)}")

        code = get_reservoir_code(reservoir_name)
        if not code:
            reservoirs = search_reservoir(reservoir_name)
            if reservoirs:
                return_value = error_response(error=f"未找到水库: {reservoir_name}，类似名称: {[r['name'] for r in reservoirs[:3]]}")
            else:
                return_value = error_response(error=f"未找到水库: {reservoir_name}")
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

        result = await command_sender.send_ui_command("FUNC_UI_OPEN_RESERVOIR_DETAIL", data)
        return_value = success_response(
            command="FUNC_UI_OPEN_RESERVOIR_DETAIL",
            response=result,
            reservoir_code=code,
            station_code=station_code,
            reservoir_name=reservoir_name_cn,
            is_overview=False,
            start_time=start_time,
            end_time=end_time
        )
        logger.debug(f"navigate_to_reservoir_detail 返回结果: {return_value}")
        return return_value

    @mcp.tool()
    async def navigate_to_station_overview() -> dict:
        """控制前端跳转到水文站总览页面

        Returns:
            发送跳转指令的确认信息
        """
        logger.info(f"调用 navigate_to_station_overview")

        result = await command_sender.send_ui_command("FUNC_UI_OPEN_STATION_OVERVIEW", {})
        return_value = success_response(
            command="FUNC_UI_OPEN_STATION_OVERVIEW",
            response=result,
            is_overview=True
        )
        logger.debug(f"navigate_to_station_overview 返回结果: {return_value}")
        return return_value

    @mcp.tool()
    async def navigate_to_station_detail(
        station_name: str,
        start_time: str,
        end_time: str
    ) -> dict:
        """控制前端跳转到指定水文站的实时数据详情页面

        Args:
            station_name: 水文站名称（必须是中文），例如: "花园口"、"高村"、"孙口"、"艾山"、"泺口"、"利津"
            start_time: 开始时间（必传，默认三天前）。格式: yyyy-MM-dd HH:mm:ss，例如: "2026-04-15 00:00:00"
            end_time: 结束时间（必传，默认现在）。格式: yyyy-MM-dd HH:mm:ss，例如: "2026-04-18 00:00:00"

        Returns:
            发送跳转指令的确认信息
        """
        logger.info(f"调用 navigate_to_station_detail，收到参数: station_name={repr(station_name)}, start_time={repr(start_time)}, end_time={repr(end_time)}")

        code = get_station_code(station_name)
        if not code:
            stations = search_station(station_name)
            if stations:
                return_value = error_response(error=f"未找到水文站: {station_name}，类似名称: {[s['name'] for s in stations[:3]]}")
            else:
                return_value = error_response(error=f"未找到水文站: {station_name}")
            logger.debug(f"navigate_to_station_detail 返回结果: {return_value}")
            return return_value

        station_name_cn = _get_station_name_by_code(code)
        data = {
            "station": code,
            "station_name": station_name_cn or station_name,
            "start_time": start_time,
            "end_time": end_time
        }

        result = await command_sender.send_ui_command("FUNC_UI_OPEN_STATION_DETAIL", data)
        return_value = success_response(
            command="FUNC_UI_OPEN_STATION_DETAIL",
            response=result,
            station_code=code,
            station_name=station_name_cn,
            is_overview=False,
            start_time=start_time,
            end_time=end_time
        )
        logger.debug(f"navigate_to_station_detail 返回结果: {return_value}")
        return return_value

    @mcp.tool()
    async def navigate_to_rainfall_overview() -> dict:
        """控制前端跳转到降雨信息总览页面

        Returns:
            发送跳转指令的确认信息
        """
        logger.info(f"调用 navigate_to_rainfall_overview")

        result = await command_sender.send_ui_command("FUNC_UI_NAVIGATE_RAINFALL", {})
        return_value = success_response(
            command="FUNC_UI_NAVIGATE_RAINFALL",
            response=result
        )
        logger.debug(f"navigate_to_rainfall_overview 返回结果: {return_value}")
        return return_value

    @mcp.tool()
    async def navigate_to_rainfall_basin(
        basin: str,
        start_time: str,
        end_time: str
    ) -> dict:
        """控制前端跳转到指定流域的降雨信息页面

        Args:
            basin: 流域名称，例如: "黄河"、"洛河"、"伊洛河"
            start_time: 开始时间（必传，默认三天前）。格式: yyyy-MM-dd HH:mm:ss，例如: "2026-04-15 00:00:00"
            end_time: 结束时间（必传，默认现在）。格式: yyyy-MM-dd HH:mm:ss，例如: "2026-04-18 00:00:00"

        Returns:
            发送跳转指令的确认信息
        """
        logger.info(f"调用 navigate_to_rainfall_basin，收到参数: basin={repr(basin)}, start_time={repr(start_time)}, end_time={repr(end_time)}")

        data = {
            "basin": basin,
            "start_time": start_time,
            "end_time": end_time
        }

        result = await command_sender.send_ui_command("FUNC_UI_NAVIGATE_RAINFALL", data)
        return_value = success_response(
            command="FUNC_UI_NAVIGATE_RAINFALL",
            response=result,
            basin=basin,
            start_time=start_time,
            end_time=end_time
        )
        logger.debug(f"navigate_to_rainfall_basin 返回结果: {return_value}")
        return return_value

    @mcp.tool()
    async def navigate_to_similar_rainfall_page(
        start_time: str,
        end_time: str
    ) -> dict:
        """控制前端跳转到相似雨分析页面

        Args:
            start_time: 开始时间（必传）。格式: yyyy-MM-dd HH:mm:ss，例如: "2026-04-15 00:00:00"
            end_time: 结束时间（必传）。格式: yyyy-MM-dd HH:mm:ss，例如: "2026-04-18 00:00:00"

        Returns:
            发送跳转指令的确认信息
        """
        logger.info(f"调用 navigate_to_similar_rainfall_page，收到参数: start_time={repr(start_time)}, end_time={repr(end_time)}")
        data = {
            "start_time": start_time,
            "end_time": end_time
        }

        result = await command_sender.send_ui_command("FUNC_UI_NAVIGATE_SIMILAR_RAINFALL", data)
        return_value = success_response(
            command="FUNC_UI_NAVIGATE_SIMILAR_RAINFALL",
            response=result,
            start_time=start_time,
            end_time=end_time
        )
        logger.debug(f"navigate_to_similar_rainfall_page 返回结果: {return_value}")
        return return_value

    @mcp.tool()
    async def navigate_to_reservoir_forecast_page(
        reservoir_name: str,
        start_time: str,
        end_time: str
    ) -> dict:
        """控制前端跳转到水库预报页面

        Args:
            reservoir_name: 水库名称（必须是中文），例如: "小浪底"、"三门峡"、"陆浑"、"故县"、"河口村"
            start_time: 开始时间（必传，默认三天前）。格式: yyyy-MM-dd HH:mm:ss，例如: "2026-04-15 00:00:00"
            end_time: 结束时间（必传，默认现在）。格式: yyyy-MM-dd HH:mm:ss，例如: "2026-04-18 00:00:00"

        Returns:
            发送跳转指令的确认信息
        """
        logger.info(f"调用 navigate_to_reservoir_forecast_page，收到参数: reservoir_name={repr(reservoir_name)}, start_time={repr(start_time)}, end_time={repr(end_time)}")
        code = get_reservoir_code(reservoir_name)
        if not code:
            reservoirs = search_reservoir(reservoir_name)
            if reservoirs:
                return_value = error_response(error=f"未找到水库: {reservoir_name}，类似名称: {[r['name'] for r in reservoirs[:3]]}")
            else:
                return_value = error_response(error=f"未找到水库: {reservoir_name}")
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

        result = await command_sender.send_ui_command("FUNC_UI_NAVIGATE_RESERVOIR_FORECAST", data)
        return_value = success_response(
            command="FUNC_UI_NAVIGATE_RESERVOIR_FORECAST",
            response=result,
            reservoir_code=code,
            station_code=station_code,
            reservoir_name=reservoir_name_cn or reservoir_name,
            start_time=start_time,
            end_time=end_time
        )
        logger.debug(f"navigate_to_reservoir_forecast_page 返回结果: {return_value}")
        return return_value

    @mcp.tool()
    async def navigate_to_control_guidance_overview() -> dict:
        """控制前端跳转到控导信息总览页面

        Returns:
            发送跳转指令的确认信息
        """
        logger.info(f"调用 navigate_to_control_guidance_overview")

        result = await command_sender.send_ui_command("FUNC_UI_OPEN_CONTROL_GUIDANCE", {})
        return_value = success_response(
            command="FUNC_UI_OPEN_CONTROL_GUIDANCE",
            response=result,
            is_overview=True
        )
        logger.debug(f"navigate_to_control_guidance_overview 返回结果: {return_value}")
        return return_value

    @mcp.tool()
    async def navigate_to_control_guidance_section(
        section_name: str
    ) -> dict:
        """控制前端跳转到指定河段/断面的控导信息页面

        Args:
            section_name: 河段/断面名称

        Returns:
            发送跳转指令的确认信息
        """
        logger.info(f"调用 navigate_to_control_guidance_section，收到参数: section_name={repr(section_name)}")

        data = {"section": section_name}
        result = await command_sender.send_ui_command("FUNC_UI_OPEN_CONTROL_GUIDANCE", data)
        return_value = success_response(
            command="FUNC_UI_OPEN_CONTROL_GUIDANCE",
            response=result,
            section=section_name,
            is_overview=False
        )
        logger.debug(f"navigate_to_control_guidance_section 返回结果: {return_value}")
        return return_value

    @mcp.tool()
    async def navigate_to_station_forecast_page(
        station_name: str,
        start_time: str,
        end_time: str
    ) -> dict:
        """控制前端跳转到水文站预报页面

        Args:
            station_name: 水文站名称（必须是中文），例如: "花园口"、"高村"、"孙口"、"艾山"、"泺口"、"利津"
            start_time: 开始时间（必传，默认三天前）。格式: yyyy-MM-dd HH:mm:ss，例如: "2026-04-15 00:00:00"
            end_time: 结束时间（必传，默认现在）。格式: yyyy-MM-dd HH:mm:ss，例如: "2026-04-18 00:00:00"

        Returns:
            发送跳转指令的确认信息
        """
        logger.info(f"调用 navigate_to_station_forecast_page，收到参数: station_name={repr(station_name)}, start_time={repr(start_time)}, end_time={repr(end_time)}")
        code = get_station_code(station_name)
        if not code:
            stations = search_station(station_name)
            if stations:
                return_value = error_response(error=f"未找到水文站: {station_name}，类似名称: {[s['name'] for s in stations[:3]]}")
            else:
                return_value = error_response(error=f"未找到水文站: {station_name}")
            logger.debug(f"navigate_to_station_forecast_page 返回结果: {return_value}")
            return return_value

        station_name_cn = _get_station_name_by_code(code)

        data = {
            "station": code,
            "station_name": station_name_cn or station_name,
            "start_time": start_time,
            "end_time": end_time
        }

        result = await command_sender.send_ui_command("FUNC_UI_NAVIGATE_STATION_FORECAST", data)
        return_value = success_response(
            command="FUNC_UI_NAVIGATE_STATION_FORECAST",
            response=result,
            station_code=code,
            station_name=station_name_cn or station_name,
            start_time=start_time,
            end_time=end_time
        )
        logger.debug(f"navigate_to_station_forecast_page 返回结果: {return_value}")
        return return_value

    @mcp.tool()
    async def send_simulation_command(
        scheme_id: str
    ) -> dict:
        """向前端发送预演指令，前端收到后执行具体的预演任务。

        Args:
            scheme_id: 调度方案ID（如 DS-0001）

        Returns:
            发送预演指令的确认信息
        """
        logger.info(f"调用 send_simulation_command，收到参数: scheme_id={repr(scheme_id)}")
        import uuid
        from datetime import datetime

        task_id = f"sim_{uuid.uuid4().hex[:8]}"

        scheme = None
        if scheme_id:
            scheme = get_scheme(scheme_id)
            if not scheme:
                return_value = error_response(
                    error=f"未找到调度方案: {scheme_id}",
                    task_id=task_id
                )
                logger.debug(f"send_simulation_command 返回结果: {return_value}")
                return return_value
        else:
            schemes = get_all_schemes()
            scheme = schemes[0] if schemes else None

        if not scheme:
            return_value = error_response(
                error="未找到可用的调度方案",
                task_id=task_id
            )
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

        data = {
            "task_id": task_id,
            "scheme": scheme,
            "reservoir_schemes": reservoir_schemes,
            "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        result = await command_sender.send_ui_command("FUNC_UI_START_SIMULATION", data)

        return_value = success_response(
            command="FUNC_UI_START_SIMULATION",
            response=result,
            message="预演指令已发送",
            task_id=task_id,
            scheme_id=scheme_id,
            scheme_name=scheme.get("scheme_name", ""),
            scheme=scheme,
            reservoir_schemes=reservoir_schemes
        )
        logger.debug(f"send_simulation_command 返回结果: {return_value}")
        return return_value

    @mcp.tool()
    async def trigger_simulation_execution(
        task_id: str
    ) -> dict:
        """向前端发送触发预演执行的指令，启动预演任务。

        Args:
            task_id: 预演任务ID（由 send_simulation_command 返回的 task_id）

        Returns:
            触发执行指令的确认信息
        """
        logger.info(f"调用 trigger_simulation_execution，收到参数: task_id={repr(task_id)}")
        from datetime import datetime

        data = {
            "task_id": task_id,
            "execute_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": "execute"
        }

        result = await command_sender.send_ui_command("FUNC_UI_TRIGGER_SIMULATION", data)

        return_value = success_response(
            command="FUNC_UI_TRIGGER_SIMULATION",
            response=result,
            message="预演执行指令已发送",
            task_id=task_id
        )
        logger.debug(f"trigger_simulation_execution 返回结果: {return_value}")
        return return_value

    @mcp.tool()
    async def send_plan_document_url(
        document_url: str,
        document_name: str
    ) -> dict:
        """将预案文档URL发送给前端展示或下载。

        Args:
            document_url: 预案文档的访问URL，例如: "/mnt/user-data/outputs/五库联调调度预案-DS-0001-20260526.md"
            document_name: 预案文档名称，用于前端显示，例如: "五库联调调度方案-20260512.md"

        Returns:
            发送文档URL的确认信息
        """
        logger.info(f"调用 send_plan_document_url，收到参数: document_url={repr(document_url)}, document_name={repr(document_name)}")
        from datetime import datetime

        data = {
            "document_url": document_url,
            "document_name": document_name,
            "send_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        result = await command_sender.send_ui_command("FUNC_UI_SHOW_PLAN_DOCUMENT", data)

        return_value = success_response(
            command="FUNC_UI_SHOW_PLAN_DOCUMENT",
            response=result,
            message="预案文档URL已发送",
            document_url=document_url,
            document_name=document_name
        )
        logger.debug(f"send_plan_document_url 返回结果: {return_value}")
        return return_value

    @mcp.tool()
    async def show_evacuation_routes(
        village_ids: list
    ) -> dict:
        """在页面中显示撤离转移路线标注。

        根据村庄ID列表，从数据库查询转移路线数据后发送到页面标注。

        Args:
            village_ids: 村庄ID列表，如 [123, 456, 789]。
                由 query_evacuation 返回结果中的 village_id 字段获取。
                传入空列表 [] 可清除全部标注。

        Returns:
            发送标注指令的确认信息
        """
        logger.info(f"调用 show_evacuation_routes，收到 village_ids: {village_ids}")

        if not village_ids:
            data = {
                "action": "clear",
                "route_ids": None
            }
            result = await command_sender.send_ui_command("FUNC_EVACUATION_ROUTE_SHOW", data)
            return_value = success_response(
                command="FUNC_EVACUATION_ROUTE_SHOW",
                response=result,
                message="已清除全部转移路线标注",
                route_count=0
            )
            logger.debug(f"show_evacuation_routes 返回结果: {return_value}")
            return return_value

        placeholders = ','.join('?' * len(village_ids))
        from src.services.storage.database.connection import get_db
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

        data = {
            "routes": routes,
            "action": "show"
        }
        result = await command_sender.send_ui_command("FUNC_EVACUATION_ROUTE_SHOW", data)
        return_value = success_response(
            command="FUNC_EVACUATION_ROUTE_SHOW",
            response=result,
            message=f"已发送 {len(routes)} 条转移路线标注到页面",
            route_count=len(routes)
        )
        logger.debug(f"show_evacuation_routes 返回结果: {return_value}")
        return return_value

    @mcp.tool()
    async def clear_evacuation_routes(
        route_ids: list = None
    ) -> dict:
        """清除页面中的转移路线标注。

        Args:
            route_ids: 要清除的路线ID列表，如 ["village_1", "village_2"]，
                为空或 None 时清除全部转移路线标注

        Returns:
            发送清除指令的确认信息
        """
        logger.info(f"调用 clear_evacuation_routes，收到参数: route_ids={repr(route_ids)}")
        data = {
            "action": "clear",
            "route_ids": route_ids
        }
        result = await command_sender.send_ui_command("FUNC_EVACUATION_ROUTE_SHOW", data)
        return_value = success_response(
            command="FUNC_EVACUATION_ROUTE_SHOW",
            response=result,
            message=f"已清除转移路线标注（{'全部' if not route_ids else f'{len(route_ids)}条'}）",
            cleared_ids=route_ids
        )
        logger.debug(f"clear_evacuation_routes 返回结果: {return_value}")
        return return_value
