from fastmcp import FastMCP
from fastmcp.server.auth import require_scopes
from src.utils.logger import get_logger
from src.utils.warning_utils import (
    get_xiaolangdi_warning_core, get_sanmenxia_warning_core, get_yellow_river_emergency_response_core
)

logger = get_logger(__name__)


def register_warning_tools(mcp: FastMCP):

    # ============ 小浪底预警等级判断工具 ============
    @mcp.tool(auth=require_scopes("warning"))
    async def get_xiaolangdi_warning_level(
        tongguan_flow: float = None,
        reservoir_level: float = None,
        outflow_flow: float = None
    ) -> dict:
        """
        根据潼关流量、水库蓄水位、出库流量判断小浪底预警等级。

        Args:
            tongguan_flow: 潼关水文站预测或实测流量（m³/s）
            reservoir_level: 预测小浪底水库蓄水位（米）
            outflow_flow: 预测小浪底出库流量（m³/s）

        Returns:
            预警等级及应急保障措施
        """
        logger.info(f"调用 get_xiaolangdi_warning_level，收到参数: tongguan_flow={tongguan_flow}, reservoir_level={reservoir_level}, outflow_flow={outflow_flow}")

        try:
            result = get_xiaolangdi_warning_core(tongguan_flow, reservoir_level, outflow_flow)
            result["tongguan_flow"] = tongguan_flow
            result["reservoir_level"] = reservoir_level
            result["outflow_flow"] = outflow_flow
            logger.debug(f"get_xiaolangdi_warning_level 返回结果: {result}")
            return result

        except Exception as e:
            error_msg = f"判断预警等级时出错: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}

    # ============ 三门峡预警等级判断工具 ============
    @mcp.tool(auth=require_scopes("warning"))
    async def get_sanmenxia_warning_level(
        longmen_flow: float = None,
        tongguan_flow: float = None,
        huaxian_flow: float = None
    ) -> dict:
        """
        根据龙门、潼关、华县流量判断三门峡预警等级及处置措施。

        Args:
            longmen_flow: 龙门流量（m³/s）
            tongguan_flow: 潼关流量（m³/s）
            huaxian_flow: 华县流量（m³/s）

        Returns:
            预警等级及处置措施
        """
        logger.info(f"调用 get_sanmenxia_warning_level，收到参数: longmen_flow={longmen_flow}, tongguan_flow={tongguan_flow}, huaxian_flow={huaxian_flow}")

        try:
            result = get_sanmenxia_warning_core(longmen_flow, tongguan_flow, huaxian_flow)
            result["longmen_flow"] = longmen_flow
            result["tongguan_flow"] = tongguan_flow
            result["huaxian_flow"] = huaxian_flow
            logger.debug(f"get_sanmenxia_warning_level 返回结果: {result}")
            return result

        except Exception as e:
            error_msg = f"判断三门峡预警等级时出错: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}


    # ============ 黄河总体应急响应判断工具 ============
    @mcp.tool(auth=require_scopes("warning"))
    async def get_yellow_river_emergency_response(
        luhun_level: float = None,
        hekoucun_level: float = None,
        dongpinghu_level: float = None,
        guxian_level: float = None,
        xiaolangdi_level: float = None,
        sanmenxia_level: float = None,
        tangnaihai_flow: float = None,
        lanzhou_flow: float = None,
        xiaheyan_flow: float = None,
        shizuishan_flow: float = None,
        wubao_flow: float = None,
        longmen_flow: float = None,
        tongguan_flow: float = None,
        huayuankou_flow: float = None,
        gaocun_flow: float = None,
        huaxian_flow: float = None,
        baimasi_flow: float = None,
        longmenzhen_flow: float = None,
        wuzhi_flow: float = None
    ) -> dict:
        """
        根据黄河流域各水库水位和水文站流量判断总体应急响应等级。

        Args:
            luhun_level: 陆浑水库水位（米）
            hekoucun_level: 河口村水库水位（米）
            dongpinghu_level: 东平湖水位（米）
            guxian_level: 故县水库水位（米）
            xiaolangdi_level: 小浪底水库水位（米）
            sanmenxia_level: 三门峡水库水位（米）
            tangnaihai_flow: 唐乃亥流量（m³/s）
            lanzhou_flow: 兰州流量（m³/s）
            xiaheyan_flow: 下河沿流量（m³/s）
            shizuishan_flow: 石嘴山流量（m³/s）
            wubao_flow: 吴堡流量（m³/s）
            longmen_flow: 龙门流量（m³/s）
            tongguan_flow: 潼关流量（m³/s）
            huayuankou_flow: 花园口流量（m³/s）
            gaocun_flow: 高村流量（m³/s）
            huaxian_flow: 华县流量（m³/s）
            baimasi_flow: 白马寺流量（m³/s）
            longmenzhen_flow: 龙门镇流量（m³/s）
            wuzhi_flow: 武陟流量（m³/s）

        Returns:
            应急响应等级及启动条件
        """
        logger.info(f"调用 get_yellow_river_emergency_response")

        try:
            result = get_yellow_river_emergency_response_core(
                luhun_level=luhun_level,
                hekoucun_level=hekoucun_level,
                dongpinghu_level=dongpinghu_level,
                guxian_level=guxian_level,
                xiaolangdi_level=xiaolangdi_level,
                sanmenxia_level=sanmenxia_level,
                tangnaihai_flow=tangnaihai_flow,
                lanzhou_flow=lanzhou_flow,
                xiaheyan_flow=xiaheyan_flow,
                shizuishan_flow=shizuishan_flow,
                wubao_flow=wubao_flow,
                longmen_flow=longmen_flow,
                tongguan_flow=tongguan_flow,
                huayuankou_flow=huayuankou_flow,
                gaocun_flow=gaocun_flow,
                huaxian_flow=huaxian_flow,
                baimasi_flow=baimasi_flow,
                longmenzhen_flow=longmenzhen_flow,
                wuzhi_flow=wuzhi_flow
            )
            logger.debug(f"get_yellow_river_emergency_response 返回结果: {result}")
            return result

        except Exception as e:
            error_msg = f"判断应急响应等级时出错: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}