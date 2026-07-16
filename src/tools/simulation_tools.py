from typing import List
from fastmcp import FastMCP
from fastmcp.server.auth import require_scopes
from src.config.config import config
from src.services.communication.command_sender import command_sender
from src.utils.response_helper import success_response, error_response
from src.utils.logger import get_logger

logger = get_logger(__name__)

RESERVOIR_DATA = {res['id']: res for res in config.reservoirs}
RESERVOIR_NAMES = list(RESERVOIR_DATA.keys())
GATE_TYPES_MAP = {res_id: list(res.get('gates', {}).keys()) for res_id, res in RESERVOIR_DATA.items() if 'gates' in res}
RESERVOIR_CHOICES = ", ".join([f"{r['id']}({r['name']})" for r in config.reservoirs])
GATE_RESERVOIR_CHOICES = ", ".join(GATE_TYPES_MAP.keys())


def register_simulation_tools(mcp: FastMCP):

    @mcp.tool(auth=require_scopes("simulation"))
    async def fly_to_location(location_name: str) -> dict:
        """控制相机飞向指定位置。

        Args:
            location_name: 位置名称。可选值: {RESERVOIR_CHOICES}"""
        logger.info(f"调用 fly_to_location，收到参数: location_name={repr(location_name)}")
        if location_name not in RESERVOIR_DATA:
            return_value = error_response(error=f"未知位置: {location_name}")
            logger.debug(f"fly_to_location 返回结果: {return_value}")
            return return_value
        
        res = RESERVOIR_DATA[location_name]
        result = await command_sender.send_camera_flyto(
            position=res['camera_position'],
            rotation=res['camera_rotation'],
            duration=3
        )
        return_value = success_response(
            command="FUNC_CAMERA_FLYTO",
            response=result,
            location=location_name,
            location_name_cn=res.get('name', ''),
            position=res['camera_position']
        )
        logger.debug(f"fly_to_location 返回结果: {return_value}")
        return return_value

    @mcp.tool(auth=require_scopes("simulation"))
    async def control_floodgate(reservoir_name: str, gate_type: str, gate_index: int, is_open: bool) -> dict:
        """控制水库闸门开闭。

        Args:
            reservoir_name: 水库名称。可选值: {GATE_RESERVOIR_CHOICES}
            gate_type: 闸门类型。示例: "上孔"、"底孔"、"导流洞"（具体可选值取决于水库）
            gate_index: 闸门索引 (从1开始)。例如: 1表示第1个闸门
            is_open: 是否开启 (true=开启, false=关闭)"""
        logger.info(f"调用 control_floodgate，收到参数: reservoir_name={repr(reservoir_name)}, gate_type={repr(gate_type)}, gate_index={gate_index}, is_open={is_open}")
        
        if reservoir_name not in GATE_TYPES_MAP:
            return_value = error_response(error=f"未知水库或该水库无闸门配置: {reservoir_name}")
        else:
            gates = RESERVOIR_DATA[reservoir_name].get('gates', {})
            if gate_type not in gates:
                return_value = error_response(error=f"未知闸门类型: {gate_type}。可选: {', '.join(gates.keys())}")
            else:
                gate_ids = gates[gate_type]
                if gate_index < 1 or gate_index > len(gate_ids):
                    return_value = error_response(error=f"闸门索引无效: {gate_index}。可选范围: 1-{len(gate_ids)}")
                else:
                    tunnel_id = gate_ids[gate_index - 1]
                    result = await command_sender.send_floodgate_control(tunnel_id=tunnel_id, is_open=is_open, is_clear=True)
                    return_value = success_response(
                        command="FUNC_SCENE_FLOODGATE",
                        response=result,
                        reservoir=reservoir_name,
                        gate_type=gate_type,
                        tunnel_id=tunnel_id,
                        is_open=is_open
                    )
        
        logger.debug(f"control_floodgate 返回结果: {return_value}")
        return return_value

    @mcp.tool(auth=require_scopes("simulation"))
    async def set_reservoir_water_level(reservoir_name: str, water_level: float) -> dict:
        """设置水库水位。

        Args:
            reservoir_name: 水库名称。可选值: {RESERVOIR_CHOICES}
            water_level: 水位值 (米)。例如: 305.5 表示水位305.5米"""
        logger.info(f"调用 set_reservoir_water_level，收到参数: reservoir_name={repr(reservoir_name)}, water_level={water_level}")
        
        if reservoir_name not in RESERVOIR_DATA:
            return_value = error_response(error=f"未知水库: {reservoir_name}")
        else:
            result = await command_sender.send_set_water_level(reservoir_name=reservoir_name, water_level=water_level)
            return_value = success_response(
                command="FUNC_SCENE_SETWATERLEVEL",
                response=result,
                reservoir=reservoir_name,
                water_level=water_level
            )
        
        logger.debug(f"set_reservoir_water_level 返回结果: {return_value}")
        return return_value

    @mcp.tool(auth=require_scopes("simulation"))
    async def create_water_level_placemark(placemark_id: str, reservoir_name: str, water_level: float, altitude_offset: float = 0) -> dict:
        """创建水库水位标签。

        Args:
            placemark_id: 标签ID (唯一标识)。例如: "smx_level_001"
            reservoir_name: 水库名称。可选值: {RESERVOIR_CHOICES}
            water_level: 水位值 (米)
            altitude_offset: 高度偏移量 (默认0)"""
        logger.info(f"调用 create_water_level_placemark，收到参数: placemark_id={repr(placemark_id)}, reservoir_name={repr(reservoir_name)}, water_level={water_level}, altitude_offset={altitude_offset}")
        
        if reservoir_name not in RESERVOIR_DATA:
            return_value = error_response(error=f"未知水库: {reservoir_name}")
        else:
            base_pos = RESERVOIR_DATA[reservoir_name]["camera_position"]
            points = [base_pos[0], base_pos[1], water_level + altitude_offset]
            name = f"库水位：{water_level}米"
            result = await command_sender.send_create_placemark(placemark_id=placemark_id, name=name, points=points)
            return_value = success_response(
                command="FUNC_PLACEMARK_CREATE_POINT",
                response=result,
                placemark_id=placemark_id,
                reservoir=reservoir_name,
                water_level=water_level,
                position=points
            )
        
        logger.debug(f"create_water_level_placemark 返回结果: {return_value}")
        return return_value

    @mcp.tool(auth=require_scopes("simulation"))
    async def update_water_level_placemark(placemark_id: str, water_level: float) -> dict:
        """更新水位标签名称。

        Args:
            placemark_id: 标签ID
            water_level: 新的水位值 (米)"""
        logger.info(f"调用 update_water_level_placemark，收到参数: placemark_id={repr(placemark_id)}, water_level={water_level}")
        name = f"库水位：{water_level}米"
        result = await command_sender.send_update_placemark(placemark_id=placemark_id, name=name)
        return_value = success_response(
            command="FUNC_PLACEMARK_UPDATE",
            response=result,
            placemark_id=placemark_id,
            water_level=water_level,
            name=name
        )
        logger.debug(f"update_water_level_placemark 返回结果: {return_value}")
        return return_value

    @mcp.tool(auth=require_scopes("simulation"))
    async def destroy_placemarks(placemark_ids: List[str]) -> dict:
        """删除标签。

        Args:
            placemark_ids: 标签ID列表。例如: ["placemark_1", "placemark_2"]"""
        logger.info(f"调用 destroy_placemarks，收到参数: placemark_ids={repr(placemark_ids)}")
        result = await command_sender.send_destroy_placemark(placemark_ids)
        return_value = success_response(
            command="FUNC_PLACEMARK_DESTROY",
            response=result,
            placemark_ids=placemark_ids
        )
        logger.debug(f"destroy_placemarks 返回结果: {return_value}")
        return return_value

    @mcp.tool(auth=require_scopes("simulation"))
    async def get_available_locations() -> dict:
        """获取可用的位置列表。

        Returns:
            locations: 水库位置列表，包含所有可用航拍点"""
        logger.info("调用 get_available_locations，收到参数: (无)")
        locations = []
        for res_id, res in RESERVOIR_DATA.items():
            locations.append({
                "id": res_id,
                "name": res.get('name', ''),
                "camera_position": res['camera_position'],
                "camera_rotation": res['camera_rotation']
            })
        return_value = success_response(
            command="GET_AVAILABLE_LOCATIONS",
            response={"locations": locations},
            locations=locations
        )
        logger.debug(f"get_available_locations 返回结果: {return_value}")
        return return_value