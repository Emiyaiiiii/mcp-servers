from fastmcp import FastMCP
from src.utils.logger import get_logger

logger = get_logger(__name__)


def register_warning_tools(mcp: FastMCP):

    @mcp.tool
    async def check_water_level_warning(
        reservoir: str,
        forecast_water_level: float,
        warning_level: float,
        flood_limit_level: float | None = None
    ) -> dict:
        """判断预报水位是否超预警。

        Args:
            reservoir: 水库名称或编码
            forecast_water_level: 预报水位 (米)
            warning_level: 预警水位 (米)
            flood_limit_level: 汛限水位 (米，可选)
        """
        logger.info(f"调用 check_water_level_warning，收到参数: reservoir={repr(reservoir)}, forecast_water_level={forecast_water_level}, warning_level={warning_level}, flood_limit_level={flood_limit_level}")
        status = "NORMAL"
        alert_level = None

        if flood_limit_level and forecast_water_level >= flood_limit_level:
            status = "FLOOD_LIMIT"
            alert_level = "yellow"
        if forecast_water_level >= warning_level:
            status = "WARNING"
            alert_level = "orange"
        if forecast_water_level >= warning_level * 1.05:
            status = "FLOOD"
            alert_level = "red"

        messages = {
            "NORMAL": f"水库 {reservoir} 水位正常：预报水位 {forecast_water_level}m",
            "FLOOD_LIMIT": f"水库 {reservoir} 超过汛限水位：预报水位 {forecast_water_level}m >= 汛限 {flood_limit_level}m",
            "WARNING": f"水库 {reservoir} 达到预警水位：预报水位 {forecast_water_level}m >= 预警水位 {warning_level}m",
            "FLOOD": f"水库 {reservoir} 超过预警水位：预报水位 {forecast_water_level}m >= 预警水位 {warning_level}m（可能超标洪水）"
        }

        return_value = {
            "reservoir": reservoir,
            "forecast_water_level": forecast_water_level,
            "warning_level": warning_level,
            "flood_limit_level": flood_limit_level,
            "status": status,
            "alert_level": alert_level,
            "message": messages[status],
            "action_required": status in ("WARNING", "FLOOD")
        }
        logger.info(f"check_water_level_warning 返回结果: {return_value}")
        return return_value

    @mcp.tool
    async def check_flow_warning(
        section: str,
        forecast_flow: float,
        warning_flow: float
    ) -> dict:
        """判断预报流量是否超预警。

        Args:
            section: 断面名称或编码
            forecast_flow: 预报流量 (m³/s)
            warning_flow: 预警流量 (m³/s)
        """
        logger.info(f"调用 check_flow_warning，收到参数: section={repr(section)}, forecast_flow={forecast_flow}, warning_flow={warning_flow}")
        status = "NORMAL"
        alert_level = None

        if forecast_flow >= warning_flow:
            status = "WARNING"
            alert_level = "orange"
        if forecast_flow >= warning_flow * 1.1:
            status = "FLOOD"
            alert_level = "red"

        messages = {
            "NORMAL": f"断面 {section} 流量正常：预报流量 {forecast_flow}m³/s",
            "WARNING": f"断面 {section} 达到预警流量：预报流量 {forecast_flow}m³/s >= 预警流量 {warning_flow}m³/s",
            "FLOOD": f"断面 {section} 超过预警流量：预报流量 {forecast_flow}m³/s >= 预警流量 {warning_flow}m³/s（可能超标洪水）"
        }

        return_value = {
            "section": section,
            "forecast_flow": forecast_flow,
            "warning_flow": warning_flow,
            "status": status,
            "alert_level": alert_level,
            "message": messages[status],
            "action_required": status in ("WARNING", "FLOOD")
        }
        logger.info(f"check_flow_warning 返回结果: {return_value}")
        return return_value

    @mcp.tool
    async def generate_warning_bulletin(
        reservoir: str,
        current_water_level: float,
        forecast_water_level: float,
        warning_level: float
    ) -> dict:
        """生成预警简报。

        Args:
            reservoir: 水库名称或编码
            current_water_level: 当前水位 (米)
            forecast_water_level: 预报水位 (米)
            warning_level: 预警水位 (米)
        """
        logger.info(f"调用 generate_warning_bulletin，收到参数: reservoir={repr(reservoir)}, current_water_level={current_water_level}, forecast_water_level={forecast_water_level}, warning_level={warning_level}")
        check_result = await check_water_level_warning(reservoir, forecast_water_level, warning_level)

        bulletin = f"""# 水库预警简报

## 基本信息
- **水库名称**: {reservoir}
- **当前水位**: {current_water_level}m
- **预报水位**: {forecast_water_level}m
- **预警水位**: {warning_level}m

## 预警状态
- **状态**: {check_result['status']}
- **预警级别**: {check_result.get('alert_level') or 'normal'}
- **预警消息**: {check_result['message']}

## 处置建议
{"1. 加强监测，密切关注水情变化\n2. 做好应急准备工作" if check_result['action_required'] else "1. 继续做好日常监测工作"}

## 预报时间
- 生成时间: 2026-04-11
"""
        return_value = {
            "bulletin": bulletin,
            "reservoir": reservoir,
            "status": check_result['status'],
            "action_required": check_result['action_required']
        }
        logger.info(f"generate_warning_bulletin 返回结果: {return_value}")
        return return_value
