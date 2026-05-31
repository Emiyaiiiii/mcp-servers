import asyncio
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.services.message_queue import message_queue
from src.services.websocket_manager import websocket_manager
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SceneConnector:
    """场景连接器 - 使用内部消息队列（异步实现）"""

    def __init__(self):
        self.command_timeout: int = 60

    async def send_command_async(self, command: Dict[str, Any], wait_response: bool = True, target_session: Optional[str] = None) -> Dict[str, Any]:
        """发送指令（异步版本）
        
        Args:
            command: 要发送的命令
            wait_response: 是否等待响应
            target_session: 目标 session_id，如果为 None 则广播到所有连接
        """
        # 检查是否有活跃的 WebSocket 连接
        if not websocket_manager.has_connections():
            logger.warning("没有活跃的 WebSocket 连接！请先连接前端/UE 到 ws://localhost:8082/browser")
            return {
                "success": False,
                "error": "没有活跃的 WebSocket 连接！请先连接前端/UE 到 ws://localhost:8082/browser"
            }
        
        if wait_response:
            return await message_queue.send_command(command, self.command_timeout, target_session)
        else:
            # 不需要等待响应的情况
            # 通过消息队列发送（即使没有响应也会传递给 WebSocket 客户端）
            await message_queue.send_command(command, timeout=1, target_session=target_session)
            return {"success": True, "message": "指令已发送"}

    async def send_command_and_wait_async(
        self,
        command: Dict[str, Any],
        timeout: Optional[int] = None,
        target_session: Optional[str] = None
    ) -> Dict[str, Any]:
        """发送指令并等待响应（异步版本）
        
        Args:
            command: 要发送的命令
            timeout: 超时时间（秒）
            target_session: 目标 session_id，如果为 None 则广播到所有连接
        """
        return await message_queue.send_command(command, timeout or self.command_timeout, target_session)

    async def send_batch_commands_async(
        self,
        commands: list[Dict[str, Any]],
        max_workers: int = 5,
        target_session: Optional[str] = None
    ) -> list[Dict[str, Any]]:
        """批量发送命令（并发执行，异步版本）
        
        Args:
            commands: 命令列表
            max_workers: 最大并发数
            target_session: 目标 session_id，如果为 None 则广播到所有连接
        """
        tasks = [self.send_command_async(cmd, target_session=target_session) for cmd in commands]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常
        final_results = []
        for result in results:
            if isinstance(result, Exception):
                final_results.append({"error": str(result), "success": False})
            else:
                final_results.append(result)
        return final_results

    async def send_camera_flyto_async(self, position: list, rotation: list, duration: float = 3, target_session: Optional[str] = None) -> Dict[str, Any]:
        """发送相机飞向指令（异步版本）
        
        Args:
            position: 相机位置
            rotation: 相机旋转
            duration: 飞行时间
            target_session: 目标 session_id，如果为 None 则广播到所有连接
        """
        command = {
            "cmd": "lshh",
            "function": "FUNC_CAMERA_FLYTO",
            "target": "scene",
            "data": {
                "position": position,
                "rotation": rotation,
                "duration": duration
            }
        }
        return await self.send_command_async(command, target_session=target_session)

    async def send_floodgate_control_async(self, tunnel_id: str, is_open: bool, is_clear: bool = True, target_session: Optional[str] = None) -> Dict[str, Any]:
        """发送闸门控制指令（异步版本）
        
        Args:
            tunnel_id: 隧道 ID
            is_open: 是否打开
            is_clear: 是否清除
            target_session: 目标 session_id，如果为 None 则广播到所有连接
        """
        command = {
            "cmd": "lshh",
            "function": "FUNC_SCENE_FLOODGATE",
            "target": "scene",
            "data": {
                "tunnelID": tunnel_id,
                "isOpen": is_open,
                "isClear": is_clear
            }
        }
        return await self.send_command_async(command, target_session=target_session)

    async def send_set_water_level_async(self, reservoir_name: str, water_level: float, target_session: Optional[str] = None) -> Dict[str, Any]:
        """发送设置水位指令（异步版本）
        
        Args:
            reservoir_name: 水库名称
            water_level: 水位
            target_session: 目标 session_id，如果为 None 则广播到所有连接
        """
        command = {
            "cmd": "lshh",
            "function": "FUNC_SCENE_SETWATERLEVEL",
            "target": "scene",
            "data": {
                "name": reservoir_name,
                "waterLevel": water_level
            }
        }
        return await self.send_command_async(command, target_session=target_session)

    async def send_create_placemark_async(
        self,
        placemark_id: str,
        name: str,
        points: list,
        icon_path: str = "E:/zhxshare/YhEngine/YhEarth/YhEarthCloudDemo1222/Source/Res/texture/水位标签.png",
        target_session: Optional[str] = None
    ) -> Dict[str, Any]:
        """发送创建标签指令（异步版本）
        
        Args:
            placemark_id: 标签 ID
            name: 标签名称
            points: 标签点
            icon_path: 图标路径
            target_session: 目标 session_id，如果为 None 则广播到所有连接
        """
        command = {
            "cmd": "lshh",
            "function": "FUNC_PLACEMARK_CREATE_POINT",
            "target": "scene",
            "data": {
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
        }
        return await self.send_command_async(command, target_session=target_session)

    async def send_update_placemark_async(self, placemark_id: str, name: Optional[str] = None, target_session: Optional[str] = None) -> Dict[str, Any]:
        """发送更新标签指令（异步版本）
        
        Args:
            placemark_id: 标签 ID
            name: 标签名称（可选）
            target_session: 目标 session_id，如果为 None 则广播到所有连接
        """
        data = {"id": placemark_id}
        if name:
            data["name"] = name

        command = {
            "cmd": "lshh",
            "function": "FUNC_PLACEMARK_UPDATE",
            "target": "scene",
            "data": data
        }
        return await self.send_command_async(command, target_session=target_session)

    async def send_destroy_placemark_async(self, placemark_ids: list, target_session: Optional[str] = None) -> Dict[str, Any]:
        """发送删除标签指令（异步版本）
        
        Args:
            placemark_ids: 标签 ID 列表
            target_session: 目标 session_id，如果为 None 则广播到所有连接
        """
        command = {
            "cmd": "lshh",
            "function": "FUNC_PLACEMARK_DESTROY",
            "target": "scene",
            "data": placemark_ids
        }
        return await self.send_command_async(command, target_session=target_session)

    async def query_scene_status_async(self, scene_id: str = "lshh") -> Dict[str, Any]:
        """查询场景状态（异步版本）"""
        from src.services.websocket_manager import websocket_manager
        return {
            "connected": websocket_manager.get_connection_count() > 0,
            "active_connections": websocket_manager.get_connection_count(),
            "scene_id": scene_id
        }

    async def close_async(self, scene_id: Optional[str] = None):
        """关闭连接（异步版本，本实现不需要实际关闭连接）"""
        logger.info(f"close_async 被调用，scene_id: {scene_id}")

    async def get_pool_status_async(self) -> Dict[str, Any]:
        """获取连接状态（异步版本）"""
        from src.services.websocket_manager import websocket_manager
        return {
            "total_connections": websocket_manager.get_connection_count(),
            "active_connections": websocket_manager.get_connection_count(),
            "scenes": []
        }

    async def send_warning_highlight_async(
        self,
        markers: list,
        target_session: Optional[str] = None
    ) -> Dict[str, Any]:
        """发送告警高亮指令（异步版本）
        
        Args:
            markers: 告警标记列表，每个元素包含:
                - id: 站点ID（reservoir_code 或 station_code）
                - name: 站点名称
                - type: "reservoir" 或 "station"
                - warning_type: "water_level" 或 "flow"
                - current_value: 当前值
                - threshold: 阈值
                - level: 告警等级 "red" | "orange" | "yellow"
            target_session: 目标 session_id，如果为 None 则广播到所有连接
        """
        command = {
            "cmd": "lshh",
            "function": "FUNC_WARNING_HIGHLIGHT",
            "target": "scene",
            "data": {
                "markers": markers,
                "action": "show"
            }
        }
        return await self.send_command_async(command, target_session=target_session)

    async def clear_warning_highlight_async(
        self,
        marker_ids: list = None,
        target_session: Optional[str] = None
    ) -> Dict[str, Any]:
        """清除告警高亮（异步版本）
        
        Args:
            marker_ids: 要清除的标记ID列表，None表示清除全部
            target_session: 目标 session_id，如果为 None 则广播到所有连接
        """
        command = {
            "cmd": "lshh",
            "function": "FUNC_WARNING_HIGHLIGHT",
            "target": "scene",
            "data": {
                "action": "clear",
                "marker_ids": marker_ids
            }
        }
        return await self.send_command_async(command, target_session=target_session)

    # ========== 兼容同步方法的包装 ==========
    # 为了保持向后兼容，我们保留这些同步方法
    # 但它们内部会调用异步方法（需要在同步环境中谨慎使用）
    
    def send_command(self, command: Dict[str, Any], wait_response: bool = True) -> Dict[str, Any]:
        """发送指令（同步版本，为了向后兼容）"""
        return asyncio.run(self.send_command_async(command, wait_response))

    def send_command_and_wait(
        self,
        command: Dict[str, Any],
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """发送指令并等待响应（同步版本，为了向后兼容）"""
        return asyncio.run(self.send_command_and_wait_async(command, timeout))

    def send_batch_commands(
        self,
        commands: list[Dict[str, Any]],
        max_workers: int = 5
    ) -> list[Dict[str, Any]]:
        """批量发送命令（同步版本，为了向后兼容）"""
        return asyncio.run(self.send_batch_commands_async(commands, max_workers))

    def send_camera_flyto(self, position: list, rotation: list, duration: float = 3) -> Dict[str, Any]:
        """发送相机飞向指令（同步版本，为了向后兼容）"""
        return asyncio.run(self.send_camera_flyto_async(position, rotation, duration))

    def send_floodgate_control(self, tunnel_id: str, is_open: bool, is_clear: bool = True) -> Dict[str, Any]:
        """发送闸门控制指令（同步版本，为了向后兼容）"""
        return asyncio.run(self.send_floodgate_control_async(tunnel_id, is_open, is_clear))

    def send_set_water_level(self, reservoir_name: str, water_level: float) -> Dict[str, Any]:
        """发送设置水位指令（同步版本，为了向后兼容）"""
        return asyncio.run(self.send_set_water_level_async(reservoir_name, water_level))

    def send_create_placemark(
        self,
        placemark_id: str,
        name: str,
        points: list,
        icon_path: str = "E:/zhxshare/YhEngine/YhEarth/YhEarthCloudDemo1222/Source/Res/texture/水位标签.png"
    ) -> Dict[str, Any]:
        """发送创建标签指令（同步版本，为了向后兼容）"""
        return asyncio.run(self.send_create_placemark_async(placemark_id, name, points, icon_path))

    def send_update_placemark(self, placemark_id: str, name: Optional[str] = None) -> Dict[str, Any]:
        """发送更新标签指令（同步版本，为了向后兼容）"""
        return asyncio.run(self.send_update_placemark_async(placemark_id, name))

    def send_destroy_placemark(self, placemark_ids: list) -> Dict[str, Any]:
        """发送删除标签指令（同步版本，为了向后兼容）"""
        return asyncio.run(self.send_destroy_placemark_async(placemark_ids))

    def query_scene_status(self, scene_id: str = "lshh") -> Dict[str, Any]:
        """查询场景状态（同步版本，为了向后兼容）"""
        return asyncio.run(self.query_scene_status_async(scene_id))

    def close(self, scene_id: Optional[str] = None):
        """关闭连接（同步版本，为了向后兼容）"""
        return asyncio.run(self.close_async(scene_id))

    def get_pool_status(self) -> Dict[str, Any]:
        """获取连接状态（同步版本，为了向后兼容）"""
        return asyncio.run(self.get_pool_status_async())


scene_connector = SceneConnector()
