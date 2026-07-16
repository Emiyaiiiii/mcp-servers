from typing import Dict, Any, Tuple
from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_reservoir_thresholds(reservoir_name: str) -> dict:
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


def judge_water_level_warning(reservoir_name: str, water_level: float, period: str = "后汛期") -> Tuple[str, str]:
    thresholds = get_reservoir_thresholds(reservoir_name)
    if not thresholds or all(v == 0.0 for v in thresholds.values()):
        return ("", "")

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

    if water_level >= DAMEL:
        return (f"超坝顶高程{round(water_level - DAMEL, 2)}m", "alert")
    elif water_level >= DAMEL - 0.5:
        return (f"低于坝顶高程{round(DAMEL - water_level, 2)}m", "alert")

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

    if DSFLZ > 0 and DSFLZ != CKFLZ:
        if water_level >= DSFLZ:
            return (f"超设计洪水位{round(water_level - DSFLZ, 2)}m", "alert")
        elif water_level >= DSFLZ - 0.5:
            return (f"低于设计洪水位{round(DSFLZ - water_level, 2)}m", "alert")

    if FHG > 0 and FHG != CKFLZ:
        if water_level >= FHG:
            return (f"超防洪高水位{round(water_level - FHG, 2)}m", "alert")
        elif water_level >= FHG - 0.5:
            return (f"低于防洪高水位{round(FHG - water_level, 2)}m", "alert")

    if water_level >= HHRZ:
        return (f"超历史最高水位{round(water_level - HHRZ, 2)}m", "alert")
    elif water_level >= HHRZ - (1.0 if reservoir_name == "小浪底" else 0.5):
        return (f"低于历史最高水位{round(HHRZ - water_level, 2)}m", "alert")

    if water_level >= XXS:
        return (f"超汛限水位{round(water_level - XXS, 2)}m", "alert")
    elif water_level >= XXS - 0.5:
        return (f"低于汛限水位{round(XXS - water_level, 2)}m", "")

    if DDZ > 0:
        if water_level >= DDZ:
            return (f"超死水位{round(water_level - DDZ, 2)}m", "")
        else:
            return (f"低于死水位{round(DDZ - water_level, 2)}m", "")

    if water_level < XXS:
        return (f"低于汛限水位{round(XXS - water_level, 2)}m", "")

    return (f"水位正常{round(water_level, 2)}m", "")


def add_water_level_description(data: Dict[str, Any], use_max_level: bool = False) -> Dict[str, Any]:
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
                    description, warning_level = judge_water_level_warning(reservoir_name, max_level)
                    if description:
                        item["level_desc"] = description
                    if warning_level:
                        item["warning_level"] = warning_level
        else:
            for item in data["data"]:
                reservoir_name = item.get("ennm")
                water_level = item.get("level")
                if reservoir_name and water_level is not None:
                    description, warning_level = judge_water_level_warning(reservoir_name, water_level)
                    if description:
                        item["level_desc"] = description
                    if warning_level:
                        item["warning_level"] = warning_level
    
    return data


async def trigger_warning_alert(data: Dict[str, Any]) -> None:
    from src.services.communication.command_sender import command_sender
    
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
                    "level": warning_level,
                    "time": item.get("date")
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
