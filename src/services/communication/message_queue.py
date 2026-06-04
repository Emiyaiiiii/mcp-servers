import asyncio
import uuid
from typing import Optional, Dict, Any
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MessageQueue:
    """消息队列，用于在 MCP 工具和 WebSocket 服务之间传递消息"""
    
    def __init__(self):
        # 存储响应 Future 的字典
        self.response_futures: Dict[str, asyncio.Future] = {}
        # 优化：使用字典存储回调，connection_id → callback
        self._callbacks: Dict[str, Any] = {}  # connection_id → callback
        self._callbacks_for_session: Dict[str, str] = {}  # session_id → connection_id
        # 用于线程安全的锁
        self._lock = asyncio.Lock()
    
    async def send_command(self, command: Dict[str, Any], timeout: int = 10, target_session: Optional[str] = None) -> Dict[str, Any]:
        """
        发送命令到 WebSocket 客户端并等待响应
        
        Args:
            command: 要发送的命令
            timeout: 等待响应的超时时间（秒）
            target_session: 目标 session_id，如果为 None 则广播到所有连接
        
        Returns:
            客户端返回的响应，或者在出错时返回错误信息
        """
        # 生成唯一的 command_id
        command_id = str(uuid.uuid4())
        
        # 确保命令包含 command_id
        command_with_id = {
            **command,
            "command_id": command_id
        }
        
        # 创建 Future 来等待响应
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        
        # 存储 Future
        async with self._lock:
            self.response_futures[command_id] = future
        
        try:
            # 优化：根据 target_session 发送
            await self._notify_callbacks(command_with_id, target_session)
            
            # 等待响应（带超时）
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
            
        except asyncio.TimeoutError:
            logger.error(f"等待响应超时，command_id: {command_id}")
            async with self._lock:
                if command_id in self.response_futures:
                    del self.response_futures[command_id]
            return {
                "success": False,
                "error": "等待响应超时",
                "command_id": command_id
            }
        except Exception as e:
            logger.error(f"发送命令失败: {e}", exc_info=True)
            async with self._lock:
                if command_id in self.response_futures:
                    del self.response_futures[command_id]
            return {
                "success": False,
                "error": str(e),
                "command_id": command_id
            }
    
    async def notify_only(self, command: Dict[str, Any], target_session: Optional[str] = None) -> None:
        """
        仅通知回调（不创建 Future、不等待响应）

        用于 fire-and-forget 场景，避免无谓的 1 秒等待

        Args:
            command: 要发送的命令
            target_session: 目标 session_id，如果为 None 则广播到所有连接
        """
        await self._notify_callbacks(command, target_session)

    async def receive_response(self, response: Dict[str, Any]) -> None:
        """
        接收来自 WebSocket 客户端的响应
        
        Args:
            response: 客户端返回的响应
        """
        command_id = response.get("command_id")
        if not command_id:
            logger.warning(f"响应中缺少 command_id: {response}")
            return
        
        async with self._lock:
            if command_id in self.response_futures:
                future = self.response_futures[command_id]
                if not future.done():
                    future.set_result(response)
                del self.response_futures[command_id]
            else:
                logger.warning(f"收到未知命令的响应，command_id: {command_id}")
    
    def register_ws_callback(self, callback, connection_id: str, session_id: Optional[str] = None) -> None:
        """
        注册 WebSocket 消息回调
        
        Args:
            callback: 当有新消息时调用的回调函数，必须是异步的
            connection_id: 连接 ID
            session_id: 会话 ID（可选）
        """
        self._callbacks[connection_id] = callback
        if session_id:
            self._callbacks_for_session[session_id] = connection_id
        logger.info(f"📝 回调已注册: {connection_id} (session: {session_id or 'broadcast'}), 回调数: {len(self._callbacks)}")
    
    def unregister_ws_callback(self, connection_id: str) -> None:
        """
        注销 WebSocket 消息回调
        
        Args:
            connection_id: 要注销的连接 ID
        """
        if connection_id in self._callbacks:
            del self._callbacks[connection_id]
            
            # 清理 session 映射
            for sess_id, conn_id in list(self._callbacks_for_session.items()):
                if conn_id == connection_id:
                    del self._callbacks_for_session[sess_id]
            
            logger.info(f"🧹 回调已注销: {connection_id}, 回调数: {len(self._callbacks)}")
    
    async def _notify_callbacks(self, command: Dict[str, Any], target_session: Optional[str] = None) -> None:
        """
        通知已注册的 WebSocket 回调
        
        Args:
            command: 要发送的命令
            target_session: 目标 session_id，如果为 None 则广播到所有连接
        """
        if not self._callbacks:
            logger.warning("没有注册的 WebSocket 回调，命令无法发送到客户端")
            return
        
        # 根据 target_session 决定发送方式
        if target_session:
            # 一对一：只发送给特定 session
            connection_id = self._callbacks_for_session.get(target_session)
            if connection_id and connection_id in self._callbacks:
                callback = self._callbacks[connection_id]
                try:
                    await callback(command)
                    logger.info(f"📤 已发送 (→{connection_id}, session: {target_session}): {command.get('function')}")
                except Exception as e:
                    logger.error(f"发送失败: {e}")
            else:
                logger.warning(f"⚠️ 未找到 session: {target_session} 对应的连接")
        else:
            # 广播：发送给所有连接（向后兼容）
            for callback in self._callbacks.values():
                try:
                    await callback(command)
                except Exception as e:
                    logger.error(f"发送失败: {e}")
            logger.info(f"📤 已广播: {command.get('function')}, 接收方: {len(self._callbacks)}")


# 全局消息队列实例
message_queue = MessageQueue()
