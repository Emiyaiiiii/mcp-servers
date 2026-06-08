import asyncio
from logging import info
import requests
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Tuple
from mcp.server.fastmcp import FastMCP
from src.config.settings import settings
from src.utils.station_codes import get_reservoir_code, get_station_code, get_reservoir_station_code
from src.services.external_api.auth_service import auth_service
from src.services.communication.command_sender import command_sender
from src.utils.response_helper import success_response
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _format_timestamp(value: Any) -> str | None:
    """将时间戳转换为可读日期格式（北京时间 UTC+8）"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # 13位毫秒时间戳
        if 100000000000 <= value <= 9999999999999:
            beijing_tz = timezone(timedelta(hours=8))
            if value >= 1000000000000:
                dt = datetime.fromtimestamp(value / 1000, tz=beijing_tz)
            else:
                # 12位时间戳，假设是毫秒
                dt = datetime.fromtimestamp(value / 1000, tz=beijing_tz)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        # 10位秒时间戳
        elif 1000000000 <= value <= 9999999999:
            beijing_tz = timezone(timedelta(hours=8))
            dt = datetime.fromtimestamp(value, tz=beijing_tz)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
    return None


def _format_date_fields(data: Any) -> Any:
    """递归遍历数据结构，将所有 date 字段的时间戳转换为可读日期"""
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if key in ("date", "dt", "wdate", "tm", "time") and isinstance(value, (int, float)):
                formatted = _format_timestamp(value)
                if formatted:
                    result[key] = formatted
                else:
                    result[key] = value
            else:
                result[key] = _format_date_fields(value)
        return result
    elif isinstance(data, list):
        return [_format_date_fields(item) for item in data]
    else:
        return data

BASE_URL = getattr(settings, 'DATA_API_BASE_URL', 'http://wt.hxyai.cn/fx')

TIMEOUT = 30

_session = None

def _get_session() -> requests.Session:
    """获取或创建请求会话"""
    global _session
    if _session is None:
        _session = requests.Session()
    return _session

def _resolve_reservoir(name_or_code: str) -> str | None:
    """解析水库名称或编码，返回编码"""
    if not name_or_code:
        return None
    code = get_reservoir_code(name_or_code)
    if code:
        return code
    return name_or_code if name_or_code else None

def _resolve_station(name_or_code: str) -> str | None:
    """解析水文站/雨量站名称或编码，返回编码"""
    if not name_or_code:
        return None
    code = get_station_code(name_or_code)
    if code:
        return code
    return name_or_code if name_or_code else None

def _resolve_reservoir_for_api(name_or_code: str) -> str | None:
    """解析水库名称或编码，返回stationCode（BDA开头的编码）
    
    现在 get_reservoir_code 已经直接返回 stationCode，
    此函数保持向后兼容。
    """
    if not name_or_code:
        return None
    
    # get_reservoir_code 现在直接返回 stationCode
    station_code = get_reservoir_code(name_or_code)
    if not station_code:
        # 如果找不到编码，直接返回原始输入
        return name_or_code
    
    return station_code

def _get_reservoir_thresholds(reservoir_name: str) -> dict:
    """从数据库获取水库特征水位阈值"""
    from src.services.storage.database.data_access import ReservoirAccess
    
    reservoir = ReservoirAccess.get_by_name(reservoir_name + "水库")
    if not reservoir:
        reservoir = ReservoirAccess.get_by_name(reservoir_name)
    
    if not reservoir:
        return {}
    
    return {
        "DAMEL": reservoir.get("level_dam_top") or 0.0,
        "CKFLZ": reservoir.get("level_flood_check") or 0.0,
        "DSFLZ": reservoir.get("level_flood_design") or 0.0,
        "FHG": reservoir.get("level_flood_high") or 0.0,
        "HHRZ": reservoir.get("level_flood_max") or 0.0,
        "XXS_Q": reservoir.get("level_flood_limit") or 0.0,
        "XXS_H": reservoir.get("level_flood_limit_back") or 0.0,
        "DDZ": reservoir.get("level_dead") or 0.0,
        "FHYY": reservoir.get("level_flood_operation") or 0.0
    }

def _judge_water_level_warning(reservoir_name: str, water_level: float, period: str = "后汛期") -> Tuple[str, str]:
    """根据水位判断水位描述和告警级别
    
    遵循Excel逻辑：从上到下按水位阈值降序判断，每个阈值T划分三个区间：
    - [T, +∞) → "超XX水位"
    - [T-0.5, T) → "低于XX水位"
    - (-∞, T-0.5) → 继续往下判断
    
    Returns:
        (description, warning_level): 水位描述和告警级别
            warning_level: "alert"(超过任一警戒水位), ""(安全)
    """
    thresholds = _get_reservoir_thresholds(reservoir_name)
    if not thresholds or all(v == 0.0 for v in thresholds.values()):
        return ("", "")

    # ---- 东平湖（只判断防洪运用水位和汛限水位） ----
    if reservoir_name == "东平湖":
        FHYY = thresholds["FHYY"]
        XXS = thresholds["XXS_H"] if period == "后汛期" else thresholds["XXS_Q"]

        if water_level >= FHYY:
            return (f"超防洪运用水位{round(water_level - FHYY, 2)}m", "alert")
        elif water_level >= FHYY - 0.5:
            return (f"低于防洪运用水位{round(FHYY - water_level, 2)}m", "")
        elif water_level >= XXS:
            return (f"超汛限水位{round(water_level - XXS, 2)}m", "alert")
        elif water_level >= XXS - 0.5:
            return (f"低于汛限水位{round(XXS - water_level, 2)}m", "")
        else:
            return (f"低于汛限水位{round(XXS - water_level, 2)}m", "")

    DAMEL = thresholds["DAMEL"]
    CKFLZ = thresholds["CKFLZ"]
    DSFLZ = thresholds["DSFLZ"]
    FHG = thresholds["FHG"]
    HHRZ = thresholds["HHRZ"]
    if period == "后汛期":
        XXS = thresholds["XXS_H"] if thresholds["XXS_H"] > 0 else thresholds["XXS_Q"]
    else:
        XXS = thresholds["XXS_Q"] if thresholds["XXS_Q"] > 0 else thresholds["XXS_H"]
    DDZ = thresholds["DDZ"]

    # ========== 按Excel从上到下顺序判断 ==========

    # --- 坝顶高程 ---
    if water_level >= DAMEL:
        return (f"超坝顶高程{round(water_level - DAMEL, 2)}m", "alert")
    elif water_level >= DAMEL - 0.5:
        return (f"低于坝顶高程{round(DAMEL - water_level, 2)}m", "alert")

    # --- 校核洪水位 ---
    elif water_level >= CKFLZ:
        if CKFLZ == DSFLZ and DSFLZ > 0:
            return (f"超校核洪水位（设计洪水位）{round(water_level - CKFLZ, 2)}m", "alert")
        elif CKFLZ == FHG and FHG > 0:
            return (f"超校核洪水位（防洪高水位）{round(water_level - CKFLZ, 2)}m", "alert")
        else:
            return (f"超校核洪水位{round(water_level - CKFLZ, 2)}m", "alert")
    elif water_level >= CKFLZ - 0.5:
        if CKFLZ == DSFLZ and DSFLZ > 0:
            return (f"低于校核洪水位（设计洪水位）{round(CKFLZ - water_level, 2)}m", "alert")
        elif CKFLZ == FHG and FHG > 0:
            return (f"低于校核洪水位（防洪高水位）{round(CKFLZ - water_level, 2)}m", "alert")
        else:
            return (f"低于校核洪水位{round(CKFLZ - water_level, 2)}m", "alert")

    # --- 设计洪水位 ---
    if DSFLZ > 0 and DSFLZ != CKFLZ:
        if water_level >= DSFLZ:
            return (f"超设计洪水位{round(water_level - DSFLZ, 2)}m", "alert")
        elif water_level >= DSFLZ - 0.5:
            return (f"低于设计洪水位{round(DSFLZ - water_level, 2)}m", "alert")

    # --- 防洪高水位 ---
    if FHG > 0 and FHG != CKFLZ:
        if water_level >= FHG:
            return (f"超防洪高水位{round(water_level - FHG, 2)}m", "alert")
        elif water_level >= FHG - 0.5:
            return (f"低于防洪高水位{round(FHG - water_level, 2)}m", "alert")

    # --- 历史最高水位 ---
    if water_level >= HHRZ:
        return (f"超历史最高水位{round(water_level - HHRZ, 2)}m", "alert")
    elif water_level >= HHRZ - (1.0 if reservoir_name == "小浪底" else 0.5):
        return (f"低于历史最高水位{round(HHRZ - water_level, 2)}m", "alert")

    # --- 汛限水位 ---
    if water_level >= XXS:
        return (f"超汛限水位{round(water_level - XXS, 2)}m", "alert")
    elif water_level >= XXS - 0.5:
        return (f"低于汛限水位{round(XXS - water_level, 2)}m", "")

    # --- 死水位 ---
    if DDZ > 0:
        if water_level >= DDZ:
            return (f"超死水位{round(water_level - DDZ, 2)}m", "")
        else:
            return (f"低于死水位{round(DDZ - water_level, 2)}m", "")

    if water_level < XXS:
        return (f"低于汛限水位{round(XXS - water_level, 2)}m", "")

    return (f"水位正常{round(water_level, 2)}m", "")

def _add_water_level_description(data: Dict[str, Any], use_max_level: bool = False) -> Dict[str, Any]:
    """为水库水情数据添加水位描述和告警级别
    
    Args:
        data: 原始数据
        use_max_level: 是否使用时间段内的最大水位判断（用于时间段查询）
    """
    if data.get("code") != 200:
        return data
    
    if "data" in data and isinstance(data["data"], list):
        if use_max_level and len(data["data"]) > 1:
            reservoir_max_levels = {}
            for item in data["data"]:
                reservoir_name = item.get("ennm")
                water_level = item.get("level")
                if reservoir_name and water_level is not None:
                    if reservoir_name not in reservoir_max_levels or water_level > reservoir_max_levels[reservoir_name]:
                        reservoir_max_levels[reservoir_name] = water_level
            
            for item in data["data"]:
                reservoir_name = item.get("ennm")
                max_level = reservoir_max_levels.get(reservoir_name)
                if reservoir_name and max_level is not None:
                    description, warning_level = _judge_water_level_warning(reservoir_name, max_level)
                    if description:
                        item["level_desc"] = description
                    if warning_level:
                        item["warning_level"] = warning_level
        else:
            for item in data["data"]:
                reservoir_name = item.get("ennm")
                water_level = item.get("level")
                if reservoir_name and water_level is not None:
                    description, warning_level = _judge_water_level_warning(reservoir_name, water_level)
                    if description:
                        item["level_desc"] = description
                    if warning_level:
                        item["warning_level"] = warning_level
    
    return data

async def _trigger_warning_alert(data: Dict[str, Any]) -> None:
    """异步发送水库告警指令到前端，控制GIS站点颜色"""
    if data.get("code") != 200:
        return
    
    markers = []
    if "data" in data and isinstance(data["data"], list):
        for item in data["data"]:
            warning_level = item.get("warning_level")
            if warning_level:
                marker = {
                    "id": item.get("ennmcd"),
                    "name": item.get("ennm"),
                    "type": "reservoir",
                    "warning_type": "water_level",
                    "current_value": item.get("level"),
                    "description": item.get("level_desc"),
                    "level": warning_level
                }
                markers.append(marker)
    
    if markers:
        try:
            result = await command_sender.send_ui_command("FUNC_WARNING_HIGHLIGHT", {
                "markers": markers, "action": "show"
            })
            if not result.get("success"):
                logger.warning(f"告警指令发送失败: {result.get('error', '未知错误')}")
            else:
                logger.info(f"已发送告警指令: {len(markers)} 个站点")
        except Exception as e:
            logger.error(f"发送告警指令异常: {e}", exc_info=True)

def _get(url: str, params: Dict[str, Any] | None = None, retry_with_auth: bool = True) -> Dict[str, Any]:
    """发送GET请求，支持token认证和自动刷新"""
    try:
        session = _get_session()
        headers = auth_service.get_auth_headers()
        
        # 诊断：记录是否有 Authorization 头及其前20位
        auth_val = headers.get("Authorization", "")
        logger.info(f"_get 请求 [url={url}, has_auth={bool(auth_val)}, auth_prefix={auth_val[:20] if auth_val else 'N/A'}]")

        response = session.get(url, params=params, headers=headers, timeout=TIMEOUT)

        # 诊断：记录响应状态码和前200字符
        logger.info(f"_get 响应 [status={response.status_code}, body_prefix={response.text[:200]}]")

        # 处理401未授权错误，尝试刷新token后重试
        if response.status_code == 401 and retry_with_auth:
            logger.warning("Token过期或无效，正在重新登录...")
            auth_service.clear_token()
            headers = auth_service.get_auth_headers()
            if headers:
                logger.info("_get 使用新token重试请求")
                response = session.get(url, params=params, headers=headers, timeout=TIMEOUT)
                logger.info(f"_get 重试响应 [status={response.status_code}, body_prefix={response.text[:200]}]")

        response.raise_for_status()
        result = response.json()

        # 检查业务层面的认证错误
        if result.get("code") == 401 and retry_with_auth:
            logger.warning("API返回认证错误，正在重新登录...")
            auth_service.clear_token()
            headers = auth_service.get_auth_headers()
            if headers:
                logger.info("_get 使用新token重试请求(业务层)")
                response = session.get(url, params=params, headers=headers, timeout=TIMEOUT)
                response.raise_for_status()
                result = response.json()
                logger.info(f"_get 业务重试响应 [body_prefix={response.text[:200]}]")

        return _format_date_fields(result)

    except requests.exceptions.RequestException as e:
        logger.error(f"请求异常: {e}")
        return {"code": 500, "data": None, "msg": str(e)}

def register_data_api_tools(mcp: FastMCP):

    @mcp.tool()
    async def get_rainfall_station_info(station: str) -> Dict[str, Any]:
        """
        获取雨量站基本信息。

        Args:
            station: 雨量站名称（支持模糊匹配，必传）

        Returns:
            {
                "code": 200,              // 状态码
                "msg": "success",         // 消息
                "data": {
                    "admag": "黄河水利委员会",  // 领导机关
                    "esstyr": "2005",           // 设立年份
                    "hncd": "黄河",             // 水系
                    "lgtd": 102.583333,       // 经度
                    "lttd": 32.816667,        // 纬度
                    "rvnm": "白河",             // 河名
                    "stcd": "40221550",       // 站码
                    "stct": "降水",             // 站别
                    "stnm": "卯溪"              // 站名
                }
            }
        """
        logger.info(f"调用 get_rainfall_station_info，收到参数: station={repr(station)}")
        station_code = _resolve_station(station)
        logger.info(f"get_rainfall_station_info 站码解析结果: station_code={repr(station_code)}")
        if not station_code:
            result = {"code": 400, "data": None, "msg": f"未找到雨量站: {station}"}
        else:
            url = f"{BASE_URL}/rainfall/psta/get/{station_code}"
            result = _get(url)
        logger.debug(f"get_rainfall_station_info 返回结果: {result}")
        return result

    # @mcp.tool()
    # async def get_realtime_rainfall(
    #     start_time: str,
    #     end_time: str
    # ) -> Dict[str, Any]:
    #     """
    #     获取实时雨量监测数据。

    #     Args:
    #         start_time: 开始时间（必传，默认三天前）。格式: yyyy-MM-dd HH:mm:ss，例如: "2026-04-15 00:00:00"
    #         end_time: 结束时间（必传，默认现在）。格式: yyyy-MM-dd HH:mm:ss，例如: "2026-04-18 00:00:00"

    #     Returns:
    #         {
    #             "code": 200,      // 状态码
    #             "msg": "success", // 消息
    #             "data": [
    #                 {
    #                     "stcd": "40100150",    // 站码
    #                     "rf": 4.20,            // 降雨量
    #                     "stnm": "吉迈",        // 站名
    #                     "lgtd": 99.650000,     // 经度
    #                     "lttd": 33.766666     // 纬度
    #                 }
    #             ]
    #         }
    #     """
    #     logger.info(f"调用 get_realtime_rainfall，收到参数: start_time={repr(start_time)}, end_time={repr(end_time)}")
    #     url = f"{BASE_URL}/rainfall/hourrt/getRainfall"
    #     params = {
    #         "startTime": start_time,
    #         "endTime": end_time
    #     }
    #     result = _get(url, params)
    #     logger.debug(f"get_realtime_rainfall 返回结果: {result}")
    #     return result

    # @mcp.tool()
    # async def get_daily_rainfall_stats(
    #     station: str,
    #     start_date: str,
    #     end_date: str
    # ) -> Dict[str, Any]:
    #     """
    #     获取时段日降雨量统计数据。

    #     Args:
    #         station: 雨量站名称（支持模糊匹配，必传）
    #         start_date: 开始日期（必传，默认三天前）。格式: yyyy-MM-dd，例如: "2026-04-15"
    #         end_date: 结束日期（必传，默认现在）。格式: yyyy-MM-dd，例如: "2026-04-18"

    #     Returns:
    #         {
    #             "code": 200,      // 状态码
    #             "msg": "",        // 消息
    #             "data": [
    #                 {
    #                     "stcd": "41612117",    // 雨量站码
    #                     "rf": 18.50,           // 降雨量
    #                     "stnm": "焦河",        // 雨量站名
    #                     "lgtd": 111.443000,    // 经度
    #                     "lttd": 34.433500     // 纬度
    #                 }
    #             ]
    #         }
    #     """
    #     logger.info(f"调用 get_daily_rainfall_stats，收到参数: station={repr(station)}, start_date={repr(start_date)}, end_date={repr(end_date)}")
    #     station_code = _resolve_station(station)
    #     if not station_code:
    #         result = {"code": 400, "data": None, "msg": f"未找到雨量站: {station}"}
    #     else:
    #         url = f"{BASE_URL}/rainfall/dayrt/getRainfall"
    #         params = {
    #             "stcd": station_code,
    #             "startDate": start_date,
    #             "endDate": end_date
    #         }
    #         result = _get(url, params)
    #     logger.debug(f"get_daily_rainfall_stats 返回结果: {result}")
    #     return result

    @mcp.tool()
    async def get_rainfall_statistics(
        start_time: str,
        end_time: str,
        stnm: str = ""
    ) -> Dict[str, Any]:
        """
        获取实时雨量站统计结果。

        Args:
            start_time: 开始时间（必传，默认三天前）。格式: yyyy-MM-dd HH:mm:ss，例如: "2026-04-15 00:00:00"
            end_time: 结束时间（必传，默认现在）。格式: yyyy-MM-dd HH:mm:ss，例如: "2026-04-18 00:00:00"
            stnm: 站点名称（可选，支持模糊匹配）。例如: "羊虎山"、"白沙"、"玛曲"、"唐乃亥"

        Returns:
            {
                "code": 200,
                "msg": "",
                "data": [
                    {
                        "avg50": 65.71,           // 50毫米降雨量
                        "area200": 0,             // 200毫米降雨量笼罩面积
                        "area100": 0.00,          // 100毫米降雨量笼罩面积
                        "avg100": 108.61,         // 100毫米降雨量
                        "maxHour24Rf": 115.50,    // 最大24小时降雨量
                        "maxHourRf": 30.75,       // 最大小时降雨量
                        "area50": 0.00,           // 50毫米降雨量笼罩面积
                        "stcd": "40104435",       // 站码
                        "rf": 115.50,             // 降雨量
                        "avg200": 0,              // 200毫米降雨量
                        "stnm": "羊虎山"          // 站名
                    }
                ]
            }
        """
        logger.info(f"调用 get_rainfall_statistics，收到参数: start_time={repr(start_time)}, end_time={repr(end_time)}, stnm={repr(stnm)}")
        url = f"{BASE_URL}/rainfall/hourrth/getRainfall"
        params = {
            "startTime": start_time,
            "endTime": end_time
        }
        result = _get(url, params)
        if stnm and result.get("code") == 200 and isinstance(result.get("data"), list):
            result["data"] = [item for item in result["data"] if stnm in item.get("stnm", "")]
            logger.info(f"get_rainfall_statistics 按 stnm={repr(stnm)} 筛选后，剩余 {len(result['data'])} 条记录")
        logger.debug(f"get_rainfall_statistics 返回结果: {result}")
        return result

    @mcp.tool()
    async def get_river_station_info(station: str) -> Dict[str, Any]:
        """
        获取河道水文站基本信息。

        Args:
            station: 水文站名称（支持模糊匹配，必传）

        Returns:
            {
                "code": 200,
                "msg": "",
                "data": {
                    "stct": "水文",              // 站别
                    "lttd": 35.083000,          // 纬度
                    "section": true,            // 所属区段（上、中、下游）
                    "esstyr": "1956",           // 设立年份
                    "stlc": "",                 // 站址
                    "esstmth": "6",             // 设立月份
                    "drar": 2283.00,            // 集水面积
                    "fdtmnm": "黄海",           // 基准基面名称
                    "stcd": "41402400",         // 站码
                    "rvnm": "天然文岩渠",       // 河名
                    "stnm": "大车集",           // 站名
                    "admag": "河南省水文水资源局", // 领导机关
                    "hncd": "黄河",             // 水系
                    "lgtd": 114.683000          // 经度
                }
            }
        """
        logger.info(f"调用 get_river_station_info，收到参数: station={repr(station)}")
        station_code = _resolve_station(station)
        if not station_code:
            result = {"code": 400, "data": None, "msg": f"未找到水文站: {station}"}
        else:
            url = f"{BASE_URL}/hydrometric/qsta/get"
            params = {"hysta": station_code}
            result = _get(url, params)
        logger.debug(f"get_river_station_info 返回结果: {result}")
        return result

    @mcp.tool()
    async def list_hydrological_stations() -> Dict[str, Any]:
        """
        获取水文站基本信息列表。

        Returns:
            {
                "code": 200,
                "msg": "",
                "data": [
                    {
                        "admag": "黄河水利委员会",    // 领导机关
                        "drar": 17728.00,           // 集水面积
                        "esstmth": "12",            // 设立月份
                        "esstyr": "2005",           // 设立年份
                        "fdtmnm": "假定",           // 基准基面名称
                        "hncd": "黄河",             // 水系
                        "lgtd": 97.367000,          // 经度
                        "lttd": 34.850000,          // 纬度
                        "rvnm": "扎陵湖",           // 河名
                        "section": 1,               // 所属区段（上、中、下游）
                        "stcd": "40100020",         // 站码
                        "stct": "水位",             // 站别
                        "stlc": "",                 // 站址
                        "stnm": "扎陵湖"            // 站名
                    }
                ]
            }
        """
        logger.info(f"调用 list_hydrological_stations，收到参数: (无)")
        url = f"{BASE_URL}/hydrometric/qsta/list"
        result = _get(url)
        logger.debug(f"list_hydrological_stations 返回结果: {result}")
        return result

    @mcp.tool()
    async def list_design_flood_results(station: str) -> Dict[str, Any]:
        """
        获取设计洪水成果信息列表。

        Args:
            station: 水文站名称（支持模糊匹配，必传）

        Returns:
            {
                "code": 200,
                "msg": "",
                "data": [
                    {
                        "period": "三年一遇",      // 洪水规模
                        "oneDayFlood": 3.49,       // 一日洪量
                        "maxFlood": 7430.00,       // 最大流量
                        "stnm": "吴堡",            // 站名
                        "fiveDayFlood": 13.65,     // 五日洪量
                        "tweDayFlood": 29.39       // 二十日洪量
                    },
                    {
                        "period": "五年一遇",
                        "oneDayFlood": 4.28,
                        "maxFlood": 10100.00,
                        "stnm": "吴堡",
                        "fiveDayFlood": 16.29,
                        "tweDayFlood": 34.79,
                        "aftMaxFlood": 11700.00    // 最大流量（后）
                    }
                ]
            }
        """
        logger.info(f"调用 list_design_flood_results，收到参数: station={repr(station)}")
        station_code = _resolve_station(station)
        if not station_code:
            result = {"code": 400, "data": None, "msg": f"未找到水文站: {station}"}
        else:
            url = f"{BASE_URL}/hydrometric/flood/list"
            params = {"hysta": station_code}
            result = _get(url, params)
        logger.debug(f"list_design_flood_results 返回结果: {result}")
        return result

    @mcp.tool()
    async def get_hydrological_features(station: str) -> Dict[str, Any]:
        """
        获取水文站水文特征统计信息。

        Args:
            station: 水文站名称（支持模糊匹配，必传）

        Returns:
            {
                "code": 200,
                "msg": "",
                "data": [
                    {
                        "cyitem": "实测最高水位（米）",    // 测验项目
                        "dt": 18374400000,              // 出现日期
                        "id": "29",                     // 水文特征id
                        "mthd": "水尺观测",             // 测量方法
                        "stcd": "40104000",             // 站码
                        "stnm": "吴堡",                 // 站名
                        "value": 644.35,                // 测量值
                        "wtlvq": 17000.00               // 相应水位/流量
                    },
                    {
                        "cyitem": "实测最大流量（立方米每秒）",
                        "dt": 207763200000,
                        "id": "31",
                        "mthd": "浮标法",
                        "stcd": "40104000",
                        "stnm": "吴堡",
                        "value": 22000.00,
                        "wtlvq": 643.44
                    }
                ]
            }
        """
        logger.info(f"调用 get_hydrological_features，收到参数: station={repr(station)}")
        station_code = _resolve_station(station)
        if not station_code:
            result = {"code": 400, "data": None, "msg": f"未找到水文站: {station}"}
        else:
            url = f"{BASE_URL}/hydrometric/hystatis/get"
            params = {"hysta": station_code}
            result = _get(url, params)
        logger.debug(f"get_hydrological_features 返回结果: {result}")
        return result

    @mcp.tool()
    async def list_water_level_sections(season_code: str, station: str) -> Dict[str, Any]:
        """
        获取监测水位断面列表。

        Args:
            season_code: 场次（必传）
            station: 水文站名称（支持模糊匹配，必传）

        Returns:
            {
                "code": 200,
                "msg": "",
                "data": {
                    "40104360": [
                        {
                            "date": 838835999000,    // 监测信息时间戳
                            "flcd": "96.8",          // 洪水编号
                            "q": 1420.00,            // 洪峰流量
                            "s": 235.00,             // 最大含沙量
                            "stcd": "40104360",      // 站码
                            "stnm": "潼关",          // 站名
                            "z": 326.73              // 洪峰水位
                        }
                    ]
                }
            }
        """
        logger.info(f"调用 list_water_level_sections，收到参数: season_code={repr(season_code)}, station={repr(station)}")
        station_code = _resolve_station(station)
        if not station_code:
            result = {"code": 400, "data": None, "msg": f"未找到水文站: {station}"}
        else:
            url = f"{BASE_URL}/hydrometric/tyflood/floods"
            params = {"flcd": season_code, "stcd": station_code}
            result = _get(url, params)
        logger.debug(f"list_water_level_sections 返回结果: {result}")
        return result

    @mcp.tool()
    async def list_realtime_hydrology(
        station: str,
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        """
        获取水文站实时水情信息列表。

        Args:
            station: 水文站名称（支持模糊匹配，必传）
            start_date: 开始时间（必传，默认三天前）
            end_date: 截止时间（必传，默认现在）

        Returns:
            {
                "code": 200,
                "msg": "",
                "data": [
                    {
                        "date": 1664665200000,   // 时间
                        "flow": 1110.0000,       // 流量
                        "level": 325.9300,       // 水位
                        "qs": 6.0000,            // 含沙量
                        "stcd": "40104360",      // 站码
                        "stnm": "潼关"           // 站名
                    }
                ]
            }
        """
        logger.info(f"调用 list_realtime_hydrology，收到参数: station={repr(station)}, start_date={repr(start_date)}, end_date={repr(end_date)}")
        station_code = _resolve_station(station)
        if not station_code:
            result = {"code": 400, "data": None, "msg": f"未找到水文站: {station}"}
        else:
            url = f"{BASE_URL}/hydrometric/hourrt/list"
            params = {"hysta": station_code, "startDate": start_date, "endDate": end_date}
            result = _get(url, params)
        logger.debug(f"list_realtime_hydrology 返回结果: {result}")
        return result

    @mcp.tool()
    async def list_daily_hydrology(
        station: str,
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        """
        获取水文站日均水情信息列表。

        Args:
            station: 水文站名称（支持模糊匹配，必传）
            start_date: 开始时间（必传，默认三天前）
            end_date: 截止时间（必传，默认现在）
        """
        logger.info(f"调用 list_daily_hydrology，收到参数: station={repr(station)}, start_date={repr(start_date)}, end_date={repr(end_date)}")
        station_code = _resolve_station(station)
        if not station_code:
            result = {"code": 400, "data": None, "msg": f"未找到水文站: {station}"}
        else:
            url = f"{BASE_URL}/hydrometric/dayrt/list"
            params = {"hysta": station_code, "startDate": start_date, "endDate": end_date}
            result = _get(url, params)
        logger.debug(f"list_daily_hydrology 返回结果: {result}")
        return result

    # @mcp.tool()
    # async def list_reservoirs(reservoir_type: int) -> Dict[str, Any]:
    #     """
    #     获取水库关系列表（包括伊洛河流域水库）。

    #     Args:
    #         reservoir_type: 水库类型（1-黄河流域主要水库；2-伊洛河水库，必传）

    #     Returns:
    #         {
    #             "code": 200,
    #             "msg": "",
    #             "data": [
    #                 {
    #                     "ennmcd": "BDA00000011",    // 水库编码
    #                     "swcd": "40100400",         // 水库8位码
    #                     "ennm": "龙羊峡",           // 水库名称
    #                     "inswcd": "40100780",       // 入库取的水库编码
    #                     "outswcd": "40100780",      // 出库取的水库编码
    #                     "upstcd": "401T0350",       // 上游水文站编码
    #                     "downstcd": "40100500",     // 下游水文站编码
    #                     "upstnm": "唐乃亥(羊曲下)", // 上游水文站名称
    #                     "downstnm": "贵德（二）"    // 下游水文站名称
    #                 }
    #             ]
    #         }
    #     """
    #     logger.info(f"调用 list_reservoirs，收到参数: reservoir_type={reservoir_type}")
    #     url = f"{BASE_URL}/project/resv/rqList"
    #     params = {"type": reservoir_type}
    #     result = _get(url, params)
    #     logger.debug(f"list_reservoirs 返回结果: {result}")
    #     return result

    @mcp.tool()
    async def get_reservoir_features(reservoir: str) -> Dict[str, Any]:
        """
        获取水库特性。

        Args:
            reservoir: 水库名称（支持模糊匹配，必传）

        Returns:
            {
                "code": 200,
                "msg": "",
                "data": {
                    "UPSTCD": "40104360",              // 上游站码
                    "ennm": "三门峡",                 // 水库名称
                    "capMaxfldlvl": 58.89,            // 防洪高水位相应库容
                    "FDZSJ": "",                      // 发电站
                    "lttd": 34.830765,                // 纬度
                    "transtionPeriod": "从10月21日起水库水位可以向非汛期水位过渡。", // 过渡期
                    "capCtrfldlvl": 0.7,              // 汛限水位相应库容
                    "XHDSJ": "",                      // 泄洪洞
                    "SWTZSJ": "",                     // 水文特征
                    "ennmcd": "BDA00000111",          // 水库编码
                    "zjrl": 450.00,                   // 装机容量
                    "capAll": 58.1,                   // 总库容
                    "ZBSJ": "",                       // 主坝情况
                    "capFld": 58.0,                   // 防洪库容
                    "function": "防洪、防凌、灌溉、发电、供水", // 功能
                    "lgtd": 111.339344,               // 经度
                    "minElecLevel": "1～5#机组、最低发电水位303m，6#、7#机组最低发电水位313m", // 最低发电水位
                    "upLocation": "上距潼关约120km",  // 距上游多远
                    "W_VALUE": 0.50,                  // 警示阈值
                    "pict": 7,                        // 图片
                    "introduction": "三门峡水库的任务是防洪、防凌、灌溉、供水和发电。", // 简介
                    "SKTZSJ": "",                     // 水库特征
                    "FCYHDSJ": "",                    // 非常溢洪道
                    "basinarea": 688400.0,            // 控制面积(km2)
                    "lvlNormal": 318.0,               // 正常蓄水位
                    "SYSDSJ": "",                     // 输引水道
                    "capNormallvl": 5.59,             // 正常蓄水位相应库容
                    "SWCD": "40104430",               // 水库8位码
                    "aduncd": "",                     // 管理单位代码
                    "lvlIceMax": 326.0,               // 防凌最高运用水位
                    "DOWNSTCD": "40104450",           // 下游站码
                    "ZCYHDSJ": "",                    // 正常溢洪道
                    "FBSJ": "",                       // 副坝情况
                    "task": "以防洪为主，兼顾防凌、灌溉、发电、供水等综合利用", // 任务
                    "BZYSSJ": "",                     // 坝址岩石
                    "downLocation": "下距花园口约260km", // 距下游的距离
                    "LVL_FLD_CTR_DATE": "7.1-10.31",  // 汛限水位持续日期
                    "lvlFldMax": 335.0,               // 防洪高水位
                    "capMaxicelvl": 21.3,             // 防凌最高运用水位相应库容
                    "location": "位于河南省陕县（右岸）和山西省平陆县（左岸）交界处", // 位置
                    "lvlFldCtr": 305.0,               // 汛限水位
                    "singleMachFullFlow": "221.4m3/s" // 单机满发流量
                }
            }
        """
        logger.info(f"调用 get_reservoir_features，收到参数: reservoir={repr(reservoir)}")
        reservoir_code = _resolve_reservoir_for_api(reservoir)
        if not reservoir_code:
            result = {"code": 400, "data": None, "msg": f"未找到水库: {reservoir}"}
        else:
            url = f"{BASE_URL}/project/resv/get"
            params = {"resname": reservoir_code}
            result = _get(url, params)
        logger.debug(f"get_reservoir_features 返回结果: {result}")
        return result

    @mcp.tool()
    async def list_reservoir_level_capacity(reservoir: str) -> Dict[str, Any]:
        """
        获取水库水位库容曲线。

        Args:
            reservoir: 水库名称（支持模糊匹配，必传）

        Returns:
            {
                "code": 200,
                "msg": "",
                "data": [
                    {
                        "area": 0.0,              // 面积
                        "capactiy": 0.15,         // 库容
                        "date": 1589212800000,    // 测量日期
                        "ennm": "三门峡",         // 水库名
                        "ennmcd": "BDA00000111",  // 水库编码
                        "level": 305.0            // 水位
                    }
                ]
            }
        """
        logger.info(f"调用 list_reservoir_level_capacity，收到参数: reservoir={repr(reservoir)}")
        reservoir_code = _resolve_reservoir_for_api(reservoir)
        if not reservoir_code:
            result = {"code": 400, "data": None, "msg": f"未找到水库: {reservoir}"}
        else:
            url = f"{BASE_URL}/project/resvzv/list"
            params = {"resname": reservoir_code}
            result = _get(url, params)
        logger.debug(f"list_reservoir_level_capacity 返回结果: {result}")
        return result

    @mcp.tool()
    async def list_reservoir_features(reservoir: str) -> Dict[str, Any]:
        """
        获取水库特征值信息列表。

        Args:
            reservoir: 水库名称（支持模糊匹配，必传）

        Returns:
            {
                "code": 200,
                "msg": "",
                "data": [
                    {
                        "capImmilvl": "",       // 移民水位相应库容
                        "capNormallvl": 5.59,   // 正常蓄水位相应库容
                        "lvlIceMax": 326.0,     // 防凌最高运用水位
                        "lvlFldDes": "",        // 设计洪水位
                        "capMaxfldlvl": 58.89,  // 防洪高水位相应库容
                        "capCtrfldlvl": 0.7,    // 汛限水位相应库容
                        "capCtrlvlAf": "",      // 后汛期汛限水位相应库容
                        "capLandlvl": "",       // 征地水位相应库容
                        "capChkfldlvl": "",     // 校核洪水位相应库容
                        "ennmcd": "BDA00000111", // 水库编码
                        "lvlImmi": "",          // 移民水位
                        "lvlFldChk": "",        // 校核洪水位
                        "capAll": 58.1,         // 总库容
                        "capFld": 58.0,         // 防洪库容
                        "lvlFldMax": 335.0,     // 防洪高水位
                        "capMaxicelvl": 21.3,   // 防凌最高运用水位相应库容
                        "lvlFldCtrAf": "",      // 后汛期汛限水位
                        "capDesfldlvl": "",     // 设计洪水位相应库容
                        "lvlFldCtrBe": "",      // 前汛期汛限水位
                        "lvlFldCtr": 305.0,     // 汛限水位
                        "capCtrlvlBe": "",      // 前汛期汛限水位相应库容
                        "lvlNormal": 318.0,     // 正常蓄水位
                        "lvlLand": ""           // 征地水位
                    }
                ]
            }
        """
        logger.info(f"调用 list_reservoir_features，收到参数: reservoir={repr(reservoir)}")
        reservoir_code = _resolve_reservoir_for_api(reservoir)
        if not reservoir_code:
            result = {"code": 400, "data": None, "msg": f"未找到水库: {reservoir}"}
        else:
            url = f"{BASE_URL}/project/rprop/list"
            params = {"ennmcd": reservoir_code}
            result = _get(url, params)
        logger.debug(f"list_reservoir_features 返回结果: {result}")
        return result

    @mcp.tool()
    async def get_reservoir_realtime(
        reservoir: str,
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        """
        获取水库实时水情。

        Args:
            reservoir: 水库名称（支持模糊匹配，必传）
            start_date: 开始时间（必传，默认三天前）。格式: yyyy-MM-dd，例如: "2026-04-15"
            end_date: 截止时间（必传，默认现在）。格式: yyyy-MM-dd，例如: "2026-04-18"

        Returns:
            {
                "code": 200,
                "msg": "",
                "data": [
                    {
                        "date": 1664553600000,    // 监测时间
                        "ennm": "小浪底",         // 水库名
                        "ennmcd": "BDA00000121",  // 水库编码
                        "inflow": 854.0000,       // 入库流量
                        "level": 247.2300,        // 水位
                        "outflow": 888.0000,      // 出库流量
                        "wq": 32.5100,            // 蓄量
                        "level_desc": "超汛限水位247.23m",  // 水位描述
                        "warning_level": "yellow"  // 告警级别: red/yellow/orange/空
                    }
                ]
            }
        """
        logger.info(f"调用 get_reservoir_realtime，收到参数: reservoir={repr(reservoir)}, start_date={repr(start_date)}, end_date={repr(end_date)}")
        reservoir_code = _resolve_reservoir_for_api(reservoir)
        if not reservoir_code:
            result = {"code": 400, "data": None, "msg": f"未找到水库: {reservoir}"}
        else:
            url = f"{BASE_URL}/hydrometric/rhourrt/list"
            params = {"resname": reservoir_code, "startDate": start_date, "endDate": end_date}
            result = _get(url, params)
            result = _add_water_level_description(result, use_max_level=True)
            await _trigger_warning_alert(result)
        logger.debug(f"get_reservoir_realtime 返回结果: {result}")
        return result

    # @mcp.tool()
    # async def get_reservoir_realtime_with_yiluo(
    #     reservoir: str,
    #     start_date: str,
    #     end_date: str
    # ) -> Dict[str, Any]:
    #     """
    #     获取水库实时水情（包括伊洛河流域水库）。

    #     Args:
    #         reservoir: 水库名称（支持模糊匹配，必传）
    #         start_date: 开始时间（必传，默认三天前）。格式: yyyy-MM-dd，例如: "2026-04-15"
    #         end_date: 截止时间（必传，默认现在）。格式: yyyy-MM-dd，例如: "2026-04-18"

    #     Returns:
    #         {
    #             "code": 200,
    #             "msg": "",
    #             "data": [
    #                 {
    #                     "date": 1696204800000,    // 时间
    #                     "ennm": "三门峡",         // 水库名称
    #                     "ennmcd": "BDA00000111",  // 水库编码
    #                     "inflow": 442.0000,       // 入库流量
    #                     "level": 312.06,          // 水位
    #                     "outflow": 161.0000,      // 出库流量
    #                     "wq": 2.55                // 蓄水量
    #                 }
    #             ]
    #         }
    #     """
    #     logger.info(f"调用 get_reservoir_realtime_with_yiluo，收到参数: reservoir={repr(reservoir)}, start_date={repr(start_date)}, end_date={repr(end_date)}")
    #     reservoir_code = _resolve_reservoir_for_api(reservoir)
    #     if not reservoir_code:
    #         result = {"code": 400, "data": None, "msg": f"未找到水库: {reservoir}"}
    #         logger.debug(f"get_reservoir_realtime_with_yiluo 返回结果: {result}")
    #         return result
    #     url = f"{BASE_URL}/hydrometric/rdayrt/rqList"
    #     params = {"resname": reservoir_code, "startDate": start_date, "endDate": end_date}
    #     result = _get(url, params)
    #     logger.debug(f"get_reservoir_realtime_with_yiluo 返回结果: {result}")
    #     return result

    # @mcp.tool()
    # async def get_reservoir_daily(
    #     reservoir: str,
    #     start_date: str,
    #     end_date: str
    # ) -> Dict[str, Any]:
    #     """
    #     获取水库日均水情。

    #     Args:
    #         reservoir: 水库名称（支持模糊匹配，必传）
    #         start_date: 开始时间（必传，默认三天前）。格式: yyyy-MM-dd，例如: "2026-04-15"
    #         end_date: 截止时间（必传，默认现在）。格式: yyyy-MM-dd，例如: "2026-04-18"

    #     Returns:
    #         {
    #             "code": 200,
    #             "msg": "",
    #             "data": [
    #                 {
    #                     "date": 1696204800000,    // 时间
    #                     "ennm": "三门峡",         // 水库名称
    #                     "ennmcd": "BDA00000111",  // 水库编码
    #                     "inflow": 442.0000,       // 入库流量
    #                     "level": 312.06,          // 水位
    #                     "outflow": 161.0000,      // 出库流量
    #                     "wq": 2.55                // 蓄水量
    #                 }
    #             ]
    #         }
    #     """
    #     logger.info(f"调用 get_reservoir_daily，收到参数: reservoir={repr(reservoir)}, start_date={repr(start_date)}, end_date={repr(end_date)}")
    #     reservoir_code = _resolve_reservoir_for_api(reservoir)
    #     if not reservoir_code:
    #         result = {"code": 400, "data": None, "msg": f"未找到水库: {reservoir}"}
    #         logger.debug(f"get_reservoir_daily 返回结果: {result}")
    #         return result
    #     url = f"{BASE_URL}/hydrometric/rdayrt/list"
    #     params = {"resname": reservoir_code, "startDate": start_date, "endDate": end_date}
    #     result = _get(url, params)
    #     logger.debug(f"get_reservoir_daily 返回结果: {result}")
    #     return result

    # @mcp.tool()
    # async def get_reservoir_daily_with_yiluo(
    #     reservoir: str,
    #     start_date: str,
    #     end_date: str
    # ) -> Dict[str, Any]:
    #     """
    #     获取水库日均水情（包括伊洛河流域水库）。

    #     Args:
    #         reservoir: 水库名称（支持模糊匹配，必传）
    #         start_date: 开始时间（必传，默认三天前）。格式: yyyy-MM-dd，例如: "2026-04-15"
    #         end_date: 截止时间（必传，默认现在）。格式: yyyy-MM-dd，例如: "2026-04-18"

    #     Returns:
    #         {
    #             "code": 200,
    #             "msg": "",
    #             "data": [
    #                 {
    #                     "date": 1696204800000,    // 时间
    #                     "ennm": "三门峡",         // 水库名称
    #                     "ennmcd": "BDA00000111",  // 水库编码
    #                     "inflow": 442.0000,       // 入库流量
    #                     "level": 312.06,          // 水位
    #                     "outflow": 161.0000,      // 出库流量
    #                     "wq": 2.55                // 蓄水量
    #                 }
    #             ]
    #         }
    #     """
    #     logger.info(f"调用 get_reservoir_daily_with_yiluo，收到参数: reservoir={repr(reservoir)}, start_date={repr(start_date)}, end_date={repr(end_date)}")
    #     reservoir_code = _resolve_reservoir_for_api(reservoir)
    #     if not reservoir_code:
    #         result = {"code": 400, "data": None, "msg": f"未找到水库: {reservoir}"}
    #         logger.debug(f"get_reservoir_daily_with_yiluo 返回结果: {result}")
    #         return result
    #     url = f"{BASE_URL}/hydrometric/rdayrt/rqList"
    #     params = {"resname": reservoir_code, "startDate": start_date, "endDate": end_date}
    #     result = _get(url, params)
    #     logger.debug(f"get_reservoir_daily_with_yiluo 返回结果: {result}")
    #     return result

    @mcp.tool()
    async def get_river_latest_realtime() -> Dict[str, Any]:
        """
        获取河道水文站最新实时水情。

        Returns:
            {
                "code": 200,
                "msg": "",
                "data": [
                    {
                        "date": 40101011,         // 监测时间
                        "stnm": "潼关",           // 站名
                        "stcd": "BDA00000121",    // 站码
                        "flow": 854.0000,         // 流量
                        "level": 247.2300         // 水位
                    }
                ]
            }
        """
        logger.info(f"调用 get_river_latest_realtime，收到参数: (无)")
        url = f"{BASE_URL}/hydrometric/hourrt/listLatest"
        result = _get(url)
        logger.debug(f"get_river_latest_realtime 返回结果: {result}")
        return result

    @mcp.tool()
    async def get_reservoir_latest_realtime() -> Dict[str, Any]:
        """
        获取水库最新实时水情。

        Returns:
            {
                "code": 200,
                "msg": "",
                "data": [
                    {
                        "date": 1664553600000,    // 监测时间
                        "ennm": "小浪底",         // 水库名称
                        "ennmcd": "BDA00000121",  // 水库编码
                        "inflow": 854.0000,       // 入库流量
                        "level": 247.2300,        // 水位
                        "outflow": 888.0000,      // 出库流量
                        "wq": 32.5100,            // 蓄量
                        "level_desc": "超汛限水位247.23m",  // 水位描述
                        "warning_level": "yellow"  // 告警级别: red/yellow/orange/空
                    }
                ]
            }
        """
        logger.info(f"调用 get_reservoir_latest_realtime，收到参数: (无)")
        url = f"{BASE_URL}/hydrometric/rhourrt/listLatest"
        result = _get(url)
        result = _add_water_level_description(result)
        await _trigger_warning_alert(result)
        logger.debug(f"get_reservoir_latest_realtime 返回结果: {result}")
        return result

    @mcp.tool()
    async def get_hydrological_extreme(
        station: str,
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        """
        获取水文站极值信息。

        Args:
            station: 水文站名称（支持模糊匹配，必传）
            start_date: 开始日期（必传，默认三天前）。格式: yyyy-MM-dd HH:mm:ss，例如: "2026-04-15 00:00:00"
            end_date: 截止日期（必传，默认现在）。格式: yyyy-MM-dd HH:mm:ss，例如: "2026-04-18 00:00:00"

        Returns:
            {
                "code": 200,
                "msg": "",
                "data": {
                    "date": 1685966400000,    // 监测时间
                    "flow": 2920.0000,        // 流量
                    "level": 326.8400,        // 水位
                    "qs": 8.9300,             // 含沙量
                    "ss": 5.0000,             // 水势
                    "stcd": "40104360",       // 站码
                    "stnm": "潼关"            // 站名
                }
            }
        """
        logger.info(f"调用 get_hydrological_extreme，收到参数: station={repr(station)}, start_date={repr(start_date)}, end_date={repr(end_date)}")
        station_code = _resolve_station(station)
        if not station_code:
            result = {"code": 400, "data": None, "msg": f"未找到水文站: {station}"}
        else:
            url = f"{BASE_URL}/hydrometric/hourrt/getPeakValue"
            params = {
                "hysta": station_code,
                "staDate": start_date,
                "endDate": end_date
            }
            result = _get(url, params)
        logger.debug(f"get_hydrological_extreme 返回结果: {result}")
        return result

    @mcp.tool()
    async def get_hydrological_same_period(
        station: str,
        date: str
    ) -> Dict[str, Any]:
        """
        获取水文站同期数据。

        Args:
            station: 水文站名称（支持模糊匹配，必传）
            date: 日期（必传）。格式: yyyy-MM-dd，例如: "2026-05-06"

        Returns:
            {
                "code": 200,
                "msg": "",
                "data": [
                    {
                        "date": 1694448000000,    // 监测时间
                        "flow": 980.0000,         // 流量
                        "stcd": "40104360",       // 站码
                        "stnm": "潼关"            // 站名
                    }
                ]
            }
        """
        logger.info(f"调用 get_hydrological_same_period，收到参数: station={repr(station)}, date={repr(date)}")
        station_code = _resolve_station(station)
        if not station_code:
            result = {"code": 400, "data": None, "msg": f"未找到水文站: {station}"}
        else:
            url = f"{BASE_URL}/hydrometric/dayrt/getSameValue"
            params = {"hysta": station_code, "date": date}
            result = _get(url, params)
        logger.debug(f"get_hydrological_same_period 返回结果: {result}")
        return result

    @mcp.tool()
    async def get_hydrological_historical_same_period(
        station: str,
        start_day: str,
        end_day: str
    ) -> Dict[str, Any]:
        """
        获取水文站历史同期数据。

        Args:
            station: 水文站名称（支持模糊匹配，必传）
            start_day: 开始日期（必传）。格式: MM-dd，例如: "04-15"
            end_day: 结束日期（必传）。格式: MM-dd，例如: "05-06"

        Returns:
            {
                "code": 200,
                "msg": "",
                "data": [
                    {
                        "avgLevel": 317.12984277, // 平均水位
                        "stcd": "40104360",       // 站码
                        "year": 2016,             // 年份
                        "avgFlow": 634.98774566,  // 平均流量
                        "stnm": "潼关"            // 站名
                    }
                ]
            }
        """
        logger.info(f"调用 get_hydrological_historical_same_period，收到参数: station={repr(station)}, start_day={repr(start_day)}, end_day={repr(end_day)}")
        station_code = _resolve_station(station)
        if not station_code:
            result = {"code": 400, "data": None, "msg": f"未找到水文站: {station}"}
        else:
            url = f"{BASE_URL}/hydrometric/hourrt/getSameValue"
            params = {"hysta": station_code, "staDay": start_day, "endDay": end_day}
            result = _get(url, params)
        logger.debug(f"get_hydrological_historical_same_period 返回结果: {result}")
        return result

    @mcp.tool()
    async def get_hydrological_yearly_extreme(
        station: str,
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        """
        获取水文站各年份极值数据。

        Args:
            station: 水文站名称（支持模糊匹配，必传）
            start_date: 开始日期（必传，默认三天前）。格式: yyyy-MM-dd HH:mm:ss，例如: "2026-04-15 00:00:00"
            end_date: 结束日期（必传，默认现在）。格式: yyyy-MM-dd HH:mm:ss，例如: "2026-04-18 00:00:00"

        Returns:
            {
                "code": 200,
                "msg": "",
                "data": [
                    {
                        "maxLevel": 327.0570,     // 最大水位
                        "stcd": "40104360",       // 站码
                        "year": 2022,             // 年份
                        "stnm": "潼关",           // 站名
                        "maxFlow": 3430.0000      // 最大流量
                    }
                ]
            }
        """
        logger.info(f"调用 get_hydrological_yearly_extreme，收到参数: station={repr(station)}, start_date={repr(start_date)}, end_date={repr(end_date)}")
        station_code = _resolve_station(station)
        if not station_code:
            result = {"code": 400, "data": None, "msg": f"未找到水文站: {station}"}
        else:
            url = f"{BASE_URL}/hydrometric/hourrt/getYearPeakValue"
            params = {"hysta": station_code, "staDate": start_date, "endDate": end_date}
            result = _get(url, params)
        logger.debug(f"get_hydrological_yearly_extreme 返回结果: {result}")
        return result

    @mcp.tool()
    async def get_rainfall_warning() -> Dict[str, Any]:
        """
        获取雨量站预警信息。

        Returns:
            {
                "code": 200,
                "msg": "",
                "data": [
                    {
                        "hour": 12,               // 预警类型（12小时或24小时内）
                        "id": 31425,              // 预警ID
                        "lgtd": 109.416667,       // 经度
                        "lttd": 37.250000,        // 纬度
                        "rf": 32.20,              // 预警值
                        "rvnm": "清涧河",         // 河流名称
                        "stcd": "40633200",       // 站点编码
                        "stnm": "李家岔",         // 站点名称
                        "wdate": 1718827500000    // 预警时间
                    }
                ]
            }
        """
        logger.info(f"调用 get_rainfall_warning，收到参数: (无)")
        url = f"{BASE_URL}/rainfall/warn/getPWarnInfo"
        result = _get(url)
        logger.debug(f"get_rainfall_warning 返回结果: {result}")
        return result

    @mcp.tool()
    async def get_reservoir_warning() -> Dict[str, Any]:
        """
        获取水库预警信息。

        Returns:
            {
                "code": 200,
                "msg": "",
                "data": [
                    {
                        "date": 1718895600000,    // 监测时间
                        "dvalue": 223.00,         // 水位
                        "level": 1160.00,         // 超汛限值
                        "id": 14287,              // 预警id
                        "lgtd": 102.500000,       // 经度
                        "lttd": 35.833000,        // 纬度
                        "stcd": "BDA00000761",    // 水库编码
                        "stnm": "故县",           // 水库名称
                        "wdate": 1718924401000    // 预警时间
                    }
                ]
            }
        """
        logger.info(f"调用 get_reservoir_warning，收到参数: (无)")
        url = f"{BASE_URL}/hydrometric/warn/getResEWarnInfo"
        result = _get(url)
        logger.debug(f"get_reservoir_warning 返回结果: {result}")
        return result

    @mcp.tool()
    async def get_hydrological_warning() -> Dict[str, Any]:
        """
        获取水文站预警信息。

        Returns:
            {
                "code": 200,
                "msg": "",
                "data": [
                    {
                        "date": 1718895600000,    // 监测时间
                        "dvalue": 223.00,         // 超过值
                        "flow": 1160.00,          // 流量
                        "id": 14287,              // 预警id
                        "lgtd": 102.500000,       // 经度
                        "lttd": 35.833000,        // 纬度
                        "stcd": "40100550",       // 站码
                        "stnm": "循化",           // 站名
                        "type": 1,                // 超限类型
                        "wdate": 1718924401000    // 预警时间
                    }
                ]
            }
        """
        logger.info(f"调用 get_hydrological_warning，收到参数: (无)")
        url = f"{BASE_URL}/hydrometric/warn/getQEWarnInfo"
        result = _get(url)
        logger.debug(f"get_hydrological_warning 返回结果: {result}")
        return result

    @mcp.tool()
    async def get_reservoir_period_comparison(
        reservoir: str,
        before_date: str,
        after_date: str
    ) -> Dict[str, Any]:
        """
        获取水库同期分析信息。

        Args:
            reservoir: 水库名称（支持模糊匹配，必传）
            before_date: 开始日期（必传）
            after_date: 预测日期（必传）

        Returns:
            {
                "code": 200,
                "msg": "",
                "data": {
                    "data": [
                        {
                            "score": 7.7500,          // 得分
                            "similar": 1,             // 相似度
                            "ennmcd": "BDA00000111",  // 水库编码
                            "year": 2022,             // 年份
                            "level": 304.48,          // 水位
                            "inflow": 1031,           // 流量
                            "wq": -0.04               // 蓄量
                        }
                    ],
                    "stnm": "潼关"                // 入库站
                }
            }
        """
        logger.info(f"调用 get_reservoir_period_comparison，收到参数: reservoir={repr(reservoir)}, before_date={repr(before_date)}, after_date={repr(after_date)}")
        reservoir_code = _resolve_reservoir_for_api(reservoir)
        if not reservoir_code:
            result = {"code": 400, "data": None, "msg": f"未找到水库: {reservoir}"}
        else:
            url = f"{BASE_URL}/hydrometric/resv/contrast"
            params = {"resname": reservoir_code, "beforeDate": before_date, "afterDate": after_date}
            result = _get(url, params)
        logger.debug(f"get_reservoir_period_comparison 返回结果: {result}")
        return result

    @mcp.tool()
    async def get_river_period_comparison(
        station: str,
        before_date: str,
        current_date: str,
        after_date: str
    ) -> Dict[str, Any]:
        """
        获取河道同期对比信息。

        Args:
            station: 水文站名称（支持模糊匹配，必传）
            before_date: 向前推N天的日期（必填）
            current_date: 当前日期（必填）
            after_date: 向后推N天的日期（必填）

        Returns:
            {
                "code": 200,
                "msg": "",
                "data": [
                    {
                        "dayFlows": [             // 日流量列表
                            {
                                "date": 1696089600000,   // 日期时间
                                "stcd": "40100350",      // 站码
                                "year": 2023,            // 年份
                                "flow": 2120             // 流量
                            }
                        ],
                        "similar": 0,             // 相似度
                        "stcd": "40100350",       // 站码
                        "year": 2023,             // 年份
                        "avgFlow": 2100.00        // 推前日期的平均流量
                    }
                ]
            }
        """
        logger.info(f"调用 get_river_period_comparison，收到参数: station={repr(station)}, before_date={repr(before_date)}, current_date={repr(current_date)}, after_date={repr(after_date)}")
        station_code = _resolve_station(station)
        if not station_code:
            result = {"code": 400, "data": None, "msg": f"未找到水文站: {station}"}
        else:
            url = f"{BASE_URL}/hydrometric/psta/contrast"
            params = {
                "hysta": station_code,
                "beforeDate": before_date,
                "currentDate": current_date,
                "afterDate": after_date
            }
            result = _get(url, params)
        logger.debug(f"get_river_period_comparison 返回结果: {result}")
        return result

    # @mcp.tool()
    # async def get_rainflood_similarity_times() -> Dict[str, Any]:
    #     """
    #     获取雨洪沙相似性分析时间信息。

    #     Returns:
    #         {
    #             "code": 200,
    #             "msg": "",
    #             "data": [
    #                 {
    #                     "date": 1692545088000,    // 时间日期
    #                     "month": 8,               // 月份
    #                     "year": 2023,             // 年份
    #                     "id": 7                   // 数据id
    #                 }
    #             ]
    #         }
    #     """
    #     logger.info(f"调用 get_rainflood_similarity_times，收到参数: (无)")
    #     url = f"{BASE_URL}/rainfall/sanalysis/getCombo"
    #     result = _get(url)
    #     logger.debug(f"get_rainflood_similarity_times 返回结果: {result}")
    #     return result

    @mcp.tool()
    async def get_rainflood_similarity_content(data_id: int) -> Dict[str, Any]:
        """
        获取雨洪沙相似性分析内容信息。

        Args:
            data_id: 数据id（get_rainflood_similarity_times工具返回内容里的id，必填）

        Returns:
            {
                "code": 200,
                "msg": "",
                "data": {
                    "date": 1596533548000,    // 时间日期
                    "id": 1,                  // 数据id
                    "picture": 3307,          // 图片id
                    "remark": "",             // 备注
                    "result": "2020年7月21日至2020年8月4日..." // 结果描述
                }
            }
        """
        logger.info(f"调用 get_rainflood_similarity_content，收到参数: data_id={data_id}")
        url = f"{BASE_URL}/rainfall/sanalysis/get/{data_id}"
        result = _get(url)
        logger.debug(f"get_rainflood_similarity_content 返回结果: {result}")
        return result

    @mcp.tool()
    async def download_image(image_id: int) -> bytes:
        """
        下载图片。

        Args:
            image_id: 图片id（get_rainflood_similarity_content工具返回的picture字段，必填）

        Returns:
            图片二进制数据
        """
        logger.info(f"调用 download_image，收到参数: image_id={image_id}")
        url = f"{BASE_URL}/filemanage/file/getImage"
        params = {"id": image_id}
        try:
            session = _get_session()
            response = session.get(url, params=params, timeout=TIMEOUT)
            response.raise_for_status()
            result = response.content
            logger.debug(f"download_image 返回结果: (图片数据，长度={len(result)})")
            return result
        except requests.exceptions.RequestException as e:
            result = f"Error: {str(e)}".encode()
            logger.error(f"download_image 错误: {str(e)}")
            return result

    @mcp.tool()
    async def query_flood_plan(
        keyword: str,
        category: str = "all"
    ) -> Dict[str, Any]:
        """
        综合查询防洪预案数据。整合转移计划、物资保障、人员保障、联系电话、联系人等信息。

        Args:
            keyword: 搜索关键词，水库名称、村庄名或任意关键词（支持模糊匹配）
            category: 数据类别，可选值：
                - "all"（默认）：搜索所有类别
                - "evacuation_plan"：洪水转移计划
                - "materials"：防汛物资保障
                - "personnel"：水库人员保障
                - "contact_phones"：防汛联系电话
                - "contacts"：防汛联系人

        Returns:
            {
                "code": 200,
                "msg": "success",
                "data": {
                    "evacuation_plan": [...],   // 存在时返回
                    "materials": [...],         // 存在时返回
                    "personnel": [...],         // 存在时返回
                    "contact_phones": [...],   // 存在时返回
                    "contacts": [...]           // 存在时返回
                }
            }
        """
        logger.info(f"query_flood_plan: keyword={keyword!r}, category={category!r}")
        from src.services.storage.database.data_access import (
            ReservoirAccess,
            FloodEvacuationPlanAccess,
            FloodControlMaterialAccess,
            FloodReservoirStaffAccess,
            FloodContactPhoneAccess,
            FloodControlContactAccess
        )

        reservoir = ReservoirAccess.get_by_name(keyword)
        code = reservoir['code'] if reservoir else keyword

        CATEGORIES = {
            "all": [
                ("evacuation_plan", FloodEvacuationPlanAccess, "search_by_reservoir_or_region"),
                ("materials", FloodControlMaterialAccess, "get_by_reservoir_code" if reservoir else "search"),
                ("personnel", FloodReservoirStaffAccess, "get_by_reservoir_code" if reservoir else "search"),
                ("contact_phones", FloodContactPhoneAccess, "get_by_reservoir_code" if reservoir else "search"),
                ("contacts", FloodControlContactAccess, "get_by_reservoir_code" if reservoir else "search"),
            ],
            "evacuation_plan": [("evacuation_plan", FloodEvacuationPlanAccess, "search_by_reservoir_or_region")],
            "materials": [("materials", FloodControlMaterialAccess, "get_by_reservoir_code" if reservoir else "search")],
            "personnel": [("personnel", FloodReservoirStaffAccess, "get_by_reservoir_code" if reservoir else "search")],
            "contact_phones": [("contact_phones", FloodContactPhoneAccess, "get_by_reservoir_code" if reservoir else "search")],
            "contacts": [("contacts", FloodControlContactAccess, "get_by_reservoir_code" if reservoir else "search")],
        }

        if category not in CATEGORIES:
            return {"code": 400, "msg": f"未知类别: {category}，可选: all/evacuation_plan/materials/personnel/contact_phones/contacts", "data": {}}

        data = {}
        for name, AccessCls, method_name in CATEGORIES[category]:
            accessor = AccessCls()
            method = getattr(accessor, method_name)
            result = method(code) if reservoir else method(keyword)
            if result:
                data[name] = result

        if not data:
            return {"code": 404, "msg": f"未找到与 '{keyword}' 相关的数据", "data": {}}
        logger.debug(f"query_flood_plan 返回: {list(data.keys())}")
        return {"code": 200, "msg": "success", "data": data}

    @mcp.tool()
    async def query_evacuation(
        reservoir_name: str = None,
        village: str = None,
        water_level: float = None,
        township: str = None
    ) -> Dict[str, Any]:
        """
        查询撤离转移信息。通过水库名、村庄名、水位、乡镇多维检索。

        Args:
            reservoir_name: 水库名称，必填其一。如"河口村水库"、"故县水库"、"陆浑水库"
            village: 村庄名称，可选（支持模糊）。如"北窑村"
            water_level: 水位值（米），可选。如 331.8
            township: 乡镇名称，可选。如"陆浑镇"

        Returns:
            {
                "code": 200,
                "msg": "success",
                "data": [
                    {
                        "village_id": 123,
                        "evacuation_id": 456,
                        "reservoir_name": "故县水库",
                        "water_level": 533.64,
                        "township_name": "故县镇",
                        "village_name": "北窑村",
                        "contact_name": "宋洛生",
                        "contact_phone": "18625797490",
                        "evacuation_location": "党群服务中心",
                        "evacuation_route": "通村公路"
                    }
                ]
            }
        """
        logger.info(f"query_evacuation: reservoir={reservoir_name}, village={village}, level={water_level}, township={township}")
        from src.services.storage.database.data_access import EvacuationQueryAccess

        if village:
            data = EvacuationQueryAccess.search_village(village)
        elif reservoir_name:
            data = EvacuationQueryAccess.get_by_reservoir(reservoir_name, township, water_level, village)
        else:
            return {"code": 400, "msg": "reservoir_name 或 village 至少填一个", "data": []}

        code = 200 if data else 404
        msg = "success" if data else f"未找到撤离信息"
        logger.debug(f"返回 {len(data) if data else 0} 条")
        return {"code": code, "msg": msg, "data": data}

    @mcp.tool()
    async def query_reservoir_info(
        reservoir_name: str = None,
        water_level: float = None
    ) -> Dict[str, Any]:
        """
        查询水库的水位阈值及乡镇信息。

        Args:
            reservoir_name: 水库名称，如"陆浑水库"
            water_level: 水位值（米），可选。不指定则返回所有水位阈值

        Returns:
            {
                "code": 200,
                "msg": "success",
                "data": {
                    "reservoir_name": "陆浑水库",
                    "water_levels": [
                        {"water_level": 321.5, "township_count": 2, "village_count": 24, "level_description": "..."},
                        {"water_level": 331.8, "township_count": 3, "village_count": 53, "level_description": "..."}
                    ],
                    "townships": [
                        {"township_name": "陆浑镇", "village_count": 100},
                        {"township_name": "饭坡镇", "village_count": 37}
                    ]
                }
            }
        """
        logger.info(f"query_reservoir_info: {reservoir_name}, level={water_level}")
        from src.services.storage.database.data_access import EvacuationQueryAccess, ReservoirAccess

        if not reservoir_name:
            return {"code": 400, "msg": "reservoir_name 必填", "data": {}}
        reservoir = ReservoirAccess.get_by_name(reservoir_name)
        if not reservoir:
            return {"code": 404, "msg": f"未找到水库: {reservoir_name}", "data": {}}

        water_levels = EvacuationQueryAccess.get_water_levels(reservoir_name, water_level)
        townships = EvacuationQueryAccess.get_townships(reservoir_name, water_level)
        return {
            "code": 200,
            "msg": "success",
            "data": {
                "reservoir_name": reservoir['name'],
                "water_levels": water_levels,
                "townships": townships
            }
        }