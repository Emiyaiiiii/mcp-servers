from typing import List
from mcp.server.fastmcp import FastMCP
from src.config.config import config
from src.services.scene_connector import scene_connector
from src.utils.logger import get_logger

logger = get_logger(__name__)

RESERVOIR_DATA = {res['id']: res for res in config.reservoirs}
RESERVOIR_NAMES = list(RESERVOIR_DATA.keys())
GATE_TYPES_MAP = {res_id: list(res.get('gates', {}).keys()) for res_id, res in RESERVOIR_DATA.items() if 'gates' in res}


def _get_reservoir_choices() -> str:
    return ", ".join([f"{r['id']}({r['name']})" for r in config.reservoirs])


RESERVOIR_CHOICES = _get_reservoir_choices()
GATE_RESERVOIR_CHOICES = ", ".join(GATE_TYPES_MAP.keys())


async def fly_to_location(location_name: str, session_id: str = None) -> dict:
    logger.info(f"调用 fly_to_location，收到参数: location_name={repr(location_name)}, session_id={repr(session_id)}")
    if location_name not in RESERVOIR_DATA:
        result = {"success": False, "error": f"未知位置: {location_name}"}
        logger.info(f"fly_to_location 返回结果: {result}")
        return result
    res = RESERVOIR_DATA[location_name]
    result = await scene_connector.send_camera_flyto_async(
        position=res['camera_position'],
        rotation=res['camera_rotation'],
        duration=3,
        target_session=session_id
    )
    return_value = {
        "success": True,
        "location": location_name,
        "location_name_cn": res.get('name', ''),
        "command": "FUNC_CAMERA_FLYTO",
        "position": res['camera_position'],
        "response": result
    }
    logger.info(f"fly_to_location 返回结果: {return_value}")
    return return_value


async def control_floodgate(reservoir_name: str, gate_type: str, gate_index: int, is_open: bool, session_id: str = None) -> dict:
    logger.info(f"调用 control_floodgate，收到参数: reservoir_name={repr(reservoir_name)}, gate_type={repr(gate_type)}, gate_index={gate_index}, is_open={is_open}, session_id={repr(session_id)}")
    if reservoir_name not in GATE_TYPES_MAP:
        result = {"success": False, "error": f"未知水库或该水库无闸门配置: {reservoir_name}"}
        logger.info(f"control_floodgate 返回结果: {result}")
        return result
    gates = RESERVOIR_DATA[reservoir_name].get('gates', {})
    if gate_type not in gates:
        result = {"success": False, "error": f"未知闸门类型: {gate_type}。可选: {', '.join(gates.keys())}"}
        logger.info(f"control_floodgate 返回结果: {result}")
        return result
    gate_ids = gates[gate_type]
    if gate_index < 1 or gate_index > len(gate_ids):
        result = {"success": False, "error": f"闸门索引无效: {gate_index}。可选范围: 1-{len(gate_ids)}"}
        logger.info(f"control_floodgate 返回结果: {result}")
        return result
    tunnel_id = gate_ids[gate_index - 1]
    result = await scene_connector.send_floodgate_control_async(tunnel_id=tunnel_id, is_open=is_open, is_clear=True, target_session=session_id)
    return_value = {
        "success": True,
        "reservoir": reservoir_name,
        "gate_type": gate_type,
        "tunnel_id": tunnel_id,
        "is_open": is_open,
        "command": "FUNC_SCENE_FLOODGATE",
        "response": result
    }
    logger.info(f"control_floodgate 返回结果: {return_value}")
    return return_value


async def set_reservoir_water_level(reservoir_name: str, water_level: float, session_id: str = None) -> dict:
    logger.info(f"调用 set_reservoir_water_level，收到参数: reservoir_name={repr(reservoir_name)}, water_level={water_level}, session_id={repr(session_id)}")
    if reservoir_name not in RESERVOIR_DATA:
        result = {"success": False, "error": f"未知水库: {reservoir_name}"}
        logger.info(f"set_reservoir_water_level 返回结果: {result}")
        return result
    result = await scene_connector.send_set_water_level_async(reservoir_name=reservoir_name, water_level=water_level, target_session=session_id)
    return_value = {
        "success": True,
        "reservoir": reservoir_name,
        "water_level": water_level,
        "command": "FUNC_SCENE_SETWATERLEVEL",
        "response": result
    }
    logger.info(f"set_reservoir_water_level 返回结果: {return_value}")
    return return_value


async def create_water_level_placemark(placemark_id: str, reservoir_name: str, water_level: float, altitude_offset: float = 0, session_id: str = None) -> dict:
    logger.info(f"调用 create_water_level_placemark，收到参数: placemark_id={repr(placemark_id)}, reservoir_name={repr(reservoir_name)}, water_level={water_level}, altitude_offset={altitude_offset}, session_id={repr(session_id)}")
    if reservoir_name not in RESERVOIR_DATA:
        result = {"success": False, "error": f"未知水库: {reservoir_name}"}
        logger.info(f"create_water_level_placemark 返回结果: {result}")
        return result
    base_pos = RESERVOIR_DATA[reservoir_name]["camera_position"]
    points = [base_pos[0], base_pos[1], water_level + altitude_offset]
    name = f"库水位：{water_level}米"
    result = await scene_connector.send_create_placemark_async(placemark_id=placemark_id, name=name, points=points, target_session=session_id)
    return_value = {
        "success": True,
        "placemark_id": placemark_id,
        "reservoir": reservoir_name,
        "water_level": water_level,
        "position": points,
        "command": "FUNC_PLACEMARK_CREATE_POINT",
        "response": result
    }
    logger.info(f"create_water_level_placemark 返回结果: {return_value}")
    return return_value


async def update_water_level_placemark(placemark_id: str, water_level: float, session_id: str = None) -> dict:
    logger.info(f"调用 update_water_level_placemark，收到参数: placemark_id={repr(placemark_id)}, water_level={water_level}, session_id={repr(session_id)}")
    name = f"库水位：{water_level}米"
    result = await scene_connector.send_update_placemark_async(placemark_id=placemark_id, name=name, target_session=session_id)
    return_value = {
        "success": True,
        "placemark_id": placemark_id,
        "water_level": water_level,
        "name": name,
        "command": "FUNC_PLACEMARK_UPDATE",
        "response": result
    }
    logger.info(f"update_water_level_placemark 返回结果: {return_value}")
    return return_value


async def destroy_placemarks(placemark_ids: List[str], session_id: str = None) -> dict:
    logger.info(f"调用 destroy_placemarks，收到参数: placemark_ids={repr(placemark_ids)}, session_id={repr(session_id)}")
    result = await scene_connector.send_destroy_placemark_async(placemark_ids, target_session=session_id)
    return_value = {
        "success": True,
        "placemark_ids": placemark_ids,
        "command": "FUNC_PLACEMARK_DESTROY",
        "response": result
    }
    logger.info(f"destroy_placemarks 返回结果: {return_value}")
    return return_value


async def get_available_locations() -> dict:
    logger.info(f"调用 get_available_locations，收到参数: (无)")
    locations = []
    for res_id, res in RESERVOIR_DATA.items():
        locations.append({
            "id": res_id,
            "name": res.get('name', ''),
            "camera_position": res['camera_position'],
            "camera_rotation": res['camera_rotation']
        })
    return_value = {"locations": locations}
    logger.info(f"get_available_locations 返回结果: {return_value}")
    return return_value


def register_simulation_tools(mcp: FastMCP):
    fly_to_location.__doc__ = f"""控制相机飞向指定位置。

Args:
    location_name: 位置名称。可选值: {RESERVOIR_CHOICES}
    session_id: 目标 session_id（可选），如果不指定，则广播到所有连接"""


    control_floodgate.__doc__ = f"""控制水库闸门开闭。

Args:
    reservoir_name: 水库名称。可选值: {GATE_RESERVOIR_CHOICES}
    gate_type: 闸门类型。示例: "上孔"、"底孔"、"导流洞"（具体可选值取决于水库）
    gate_index: 闸门索引 (从1开始)。例如: 1表示第1个闸门
    is_open: 是否开启 (true=开启, false=关闭)
    session_id: 目标 session_id（可选），如果不指定，则广播到所有连接
"""

    set_reservoir_water_level.__doc__ = f"""设置水库水位。

Args:
    reservoir_name: 水库名称。可选值: {RESERVOIR_CHOICES}
    water_level: 水位值 (米)。例如: 305.5 表示水位305.5米
    session_id: 目标 session_id（可选），如果不指定，则广播到所有连接
"""

    create_water_level_placemark.__doc__ = f"""创建水库水位标签。

Args:
    placemark_id: 标签ID (唯一标识)。例如: "smx_level_001"
    reservoir_name: 水库名称。可选值: {RESERVOIR_CHOICES}
    water_level: 水位值 (米)
    altitude_offset: 高度偏移量 (默认0)
    session_id: 目标 session_id（可选），如果不指定，则广播到所有连接
"""

    update_water_level_placemark.__doc__ = """更新水位标签名称。

Args:
    placemark_id: 标签ID
    water_level: 新的水位值 (米)
    session_id: 目标 session_id（可选），如果不指定，则广播到所有连接
"""



    destroy_placemarks.__doc__ = """删除标签。

Args:
    placemark_ids: 标签ID列表。例如: ["placemark_1", "placemark_2"]
    session_id: 目标 session_id（可选），如果不指定，则广播到所有连接
"""


    get_available_locations.__doc__ = """获取可用的位置列表。

Returns:
    locations: 水库位置列表，包含所有可用航拍点
    session_id: 目标 session_id（可选），如果不指定，则广播到所有连接
"""

    mcp.add_tool(fly_to_location)
    mcp.add_tool(control_floodgate)
    mcp.add_tool(set_reservoir_water_level)
    mcp.add_tool(create_water_level_placemark)
    mcp.add_tool(update_water_level_placemark)
    mcp.add_tool(destroy_placemarks)
    mcp.add_tool(get_available_locations)
