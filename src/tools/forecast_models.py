import json
import random
from typing import List, Dict, Any
from fastmcp import FastMCP
from src.utils.logger import get_logger

logger = get_logger(__name__)


def register_forecast_models(mcp: FastMCP):

    @mcp.tool
    async def run_hydrological_model(basin: str, start_time: str, end_time: str, rainfall_data: str) -> dict:
        """
        执行水文预报模型。

        Args:
            basin: 流域名称（如：黄河、洛河、伊洛河等）
            start_time: 开始时间 (格式: YYYY-MM-DD)
            end_time: 结束时间 (格式: YYYY-MM-DD)
            rainfall_data: 降雨数据 (JSON格式)，包含各雨量站的降雨过程
        """
        logger.info(f"调用 run_hydrological_model，收到参数: basin={repr(basin)}, start_time={repr(start_time)}, end_time={repr(end_time)}, rainfall_data={repr(rainfall_data)}")
        try:
            rainfall = json.loads(rainfall_data) if isinstance(rainfall_data, str) else rainfall_data
        except json.JSONDecodeError:
            return_value = {"success": False, "error": "降雨数据格式错误，请提供有效的JSON格式"}
            logger.info(f"run_hydrological_model 返回结果: {return_value}")
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
        logger.info(f"run_hydrological_model 返回结果: {return_value}")
        return return_value

    @mcp.tool
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
            logger.info(f"run_flood_routing_model 返回结果: {return_value}")
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
        logger.info(f"run_flood_routing_model 返回结果: {return_value}")
        return return_value
