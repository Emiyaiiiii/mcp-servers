"""统一的消息发送服务

提供统一的消息发送接口，支持：
- page: 发送给前端页面
- scene: 发送给 UE 场景

返回格式统一为：
{
    "success": True/False,
    "command": "FUNC_XXX",
    "message": "操作描述（可选）",
    "response": {...},  # 原始响应
    # ... 其他业务字段
}
"""

from typing import Dict, Any, Optional, List
from src.services.communication.websocket_manager import websocket_manager
from src.services.communication.message_queue import message_queue
from src.services.communication.session_context import get_current_session_id
from src.utils.logger import get_logger

logger = get_logger(__name__)

# 默认超时时间（秒）
DEFAULT_TIMEOUT = 60


class CommandSender:
    """统一的消息发送服务"""

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout

    async def send_command(
        self,
        function: str,
        data: Dict[str, Any],
        target: str = "scene",
        session_id: Optional[str] = None,
        wait_response: bool = False
    ) -> Dict[str, Any]:
        """发送指令

        Args:
            function: 指令函数名，如 "FUNC_CAMERA_FLYTO"
            data: 指令数据
            target: 目标类型，"page" 或 "scene"
            session_id: 目标 session_id，如果为 None 则尝试从当前工具调用
                        上下文获取，如果仍然为 None 则广播到所有连接
            wait_response: 是否等待响应

        Returns:
            统一格式的响应
        """
        # 如果未指定 session_id，尝试从当前工具调用上下文获取
        if session_id is None:
            session_id = get_current_session_id()
        # 检查是否有活跃的 WebSocket 连接
        if not websocket_manager.has_connections():
            logger.warning("没有活跃的 WebSocket 连接！请先连接前端/UE 到 ws://localhost:8082/browser")
            return {
                "success": False,
                "error": "没有活跃的 WebSocket 连接！请先连接前端/UE 到 ws://localhost:8082/browser"
            }

        # 构建命令
        command = {
            "cmd": "lshh",
            "function": function,
            "target": target,
            "data": data
        }

        if wait_response:
            response = await message_queue.send_command(command, self.timeout, session_id)
        else:
            # 不需要等待响应的情况：直接通知回调，不进入 Future 等待
            await message_queue.notify_only(command, target_session=session_id)
            response = {"success": True, "message": "指令已发送"}

        return response

    async def send_camera_flyto(
        self,
        position: List[float],
        rotation: List[float],
        duration: float = 3,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """发送相机飞向指令

        Args:
            position: 相机位置 [x, y, z]
            rotation: 相机旋转 [pitch, yaw, roll]
            duration: 飞行时间（秒）
            session_id: 目标 session_id

        Returns:
            统一格式的响应
        """
        data = {
            "position": position,
            "rotation": rotation,
            "duration": duration
        }
        return await self.send_command("FUNC_CAMERA_FLYTO", data, target="scene", session_id=session_id)

    async def send_floodgate_control(
        self,
        tunnel_id: str,
        is_open: bool,
        is_clear: bool = True,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """发送闸门控制指令

        Args:
            tunnel_id: 隧道 ID
            is_open: 是否打开
            is_clear: 是否清除
            session_id: 目标 session_id

        Returns:
            统一格式的响应
        """
        data = {
            "tunnelID": tunnel_id,
            "isOpen": is_open,
            "isClear": is_clear
        }
        return await self.send_command("FUNC_SCENE_FLOODGATE", data, target="scene", session_id=session_id)

    async def send_set_water_level(
        self,
        reservoir_name: str,
        water_level: float,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """发送设置水位指令

        Args:
            reservoir_name: 水库名称
            water_level: 水位值
            session_id: 目标 session_id

        Returns:
            统一格式的响应
        """
        data = {
            "name": reservoir_name,
            "waterLevel": water_level
        }
        return await self.send_command("FUNC_SCENE_SETWATERLEVEL", data, target="scene", session_id=session_id)

    async def send_create_placemark(
        self,
        placemark_id: str,
        name: str,
        points: List[float],
        icon_path: str = "E:/zhxshare/YhEngine/YhEarth/YhEarthCloudDemo1222/Source/Res/texture/水位标签.png",
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """发送创建标签指令

        Args:
            placemark_id: 标签 ID
            name: 标签名称
            points: 标签点 [x, y, z]
            icon_path: 图标路径
            session_id: 目标 session_id

        Returns:
            统一格式的响应
        """
        data = {
            "id": placemark_id,
            "name": name,
            "isPick": True,
            "points": points,
            "normalStyle": {
                "icon": icon_path,
                "iconScale": 0.5,
                "iconColor": [1, 1, 1, 1],
                "fontSize": 12,
                "fontPivot": [0.5, 3.0],
                "fontColor": [1, 1, 1, 1],
                "outlineColor": [0, 0, 0, 1],
                "outlineSize": 0.5
            }
        }
        return await self.send_command("FUNC_PLACEMARK_CREATE_POINT", data, target="scene", session_id=session_id)

    async def send_update_placemark(
        self,
        placemark_id: str,
        name: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """发送更新标签指令

        Args:
            placemark_id: 标签 ID
            name: 标签名称（可选）
            session_id: 目标 session_id

        Returns:
            统一格式的响应
        """
        data = {"id": placemark_id}
        if name:
            data["name"] = name
        return await self.send_command("FUNC_PLACEMARK_UPDATE", data, target="scene", session_id=session_id)

    async def send_destroy_placemark(
        self,
        placemark_ids: List[str],
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """发送删除标签指令

        Args:
            placemark_ids: 标签 ID 列表
            session_id: 目标 session_id

        Returns:
            统一格式的响应
        """
        return await self.send_command("FUNC_PLACEMARK_DESTROY", placemark_ids, target="scene", session_id=session_id)

    async def send_ui_command(
        self,
        function: str,
        data: Dict[str, Any],
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """发送 UI 指令（发送给前端页面）

        Args:
            function: 指令函数名
            data: 指令数据
            session_id: 目标 session_id

        Returns:
            统一格式的响应
        """
        return await self.send_command(function, data, target="page", session_id=session_id)


# 全局实例
command_sender = CommandSender()
