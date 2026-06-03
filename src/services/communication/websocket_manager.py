import json
from typing import Optional, Dict, Any
from starlette.websockets import WebSocket, WebSocketDisconnect
from src.utils.logger import get_logger
from src.services.communication.message_queue import message_queue

logger = get_logger(__name__)


class WebSocketConnectionManager:
    """WebSocket 连接管理器"""
    
    def __init__(self):
        # 存储所有活跃的连接
        self.active_connections: Dict[str, WebSocket] = {}
        # 连接计数器
        self._connection_counter = 0
        
        # 新增：session 映射
        self.session_to_connection: Dict[str, str] = {}  # session_id → connection_id
        self.connection_to_session: Dict[str, str] = {}  # connection_id → session_id
    
    async def connect(self, websocket: WebSocket, client_type: str = "browser", session_id: Optional[str] = None) -> str:
        """
        接受并建立 WebSocket 连接
        
        Args:
            websocket: WebSocket 连接对象
            client_type: 客户端类型
            session_id: 会话 ID（可选）
        
        Returns:
            唯一的连接 ID
        """
        await websocket.accept()
        
        # 生成连接 ID
        connection_id = f"{client_type}_{self._connection_counter}"
        self._connection_counter += 1
        
        # 存储连接
        self.active_connections[connection_id] = websocket
        
        # 新增：建立 session 映射
        if session_id:
            self.session_to_connection[session_id] = connection_id
            self.connection_to_session[connection_id] = session_id
        
        logger.info(f"✅ 连接已建立: {connection_id} (session: {session_id or 'broadcast'}), 当前连接数: {len(self.active_connections)}")
        
        return connection_id
    
    def disconnect(self, connection_id: str) -> None:
        """
        断开 WebSocket 连接
        
        Args:
            connection_id: 连接 ID
        """
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
            
            # 新增：清理 session 映射
            session_id = self.connection_to_session.get(connection_id)
            if session_id:
                del self.connection_to_session[connection_id]
                if session_id in self.session_to_connection:
                    del self.session_to_connection[session_id]
            
            logger.info(f"❌ 连接已断开: {connection_id} (session: {session_id or 'unknown'}), 当前连接数: {len(self.active_connections)}")
    
    def get_connection_by_session(self, session_id: str) -> Optional[str]:
        """根据 session_id 获取 connection_id"""
        return self.session_to_connection.get(session_id)
    
    async def send_message(self, message: Dict[str, Any], connection_id: Optional[str] = None) -> None:
        """
        发送消息到 WebSocket 客户端
        
        Args:
            message: 要发送的消息（字典格式）
            connection_id: 要发送到的特定连接 ID，如果为 None 则发送到所有连接
        """
        # 将消息转换为 JSON 字符串
        message_str = json.dumps(message, ensure_ascii=False)
        
        # 确定要发送到哪些连接
        if connection_id:
            # 发送到特定连接
            websocket = self.active_connections.get(connection_id)
            if websocket:
                try:
                    await websocket.send_text(message_str)
                except Exception as e:
                    logger.error(f"❌ 向 connection_id: {connection_id} 发送消息失败: {e}", exc_info=True)
            else:
                logger.warning(f"⚠️ 找不到连接，connection_id: {connection_id}")
        else:
            # 发送到所有连接
            for conn_id, websocket in list(self.active_connections.items()):
                try:
                    await websocket.send_text(message_str)
                except Exception as e:
                    logger.error(f"❌ 向 connection_id: {conn_id} 发送消息失败: {e}", exc_info=True)
    
    def get_connection_count(self) -> int:
        """
        获取当前活跃的连接数
        
        Returns:
            当前连接数
        """
        return len(self.active_connections)
    
    def has_connections(self) -> bool:
        """
        检查是否有活跃的连接
        
        Returns:
            如果有活跃连接则返回 True，否则返回 False
        """
        return len(self.active_connections) > 0


# 全局连接管理器实例
websocket_manager = WebSocketConnectionManager()


async def websocket_handler(websocket: WebSocket):
    """
    WebSocket 连接处理函数
    
    处理 WebSocket 连接的生命周期，包括连接建立、消息接收和连接断开。
    
    Args:
        websocket: WebSocket 连接对象
    """
    connection_id: Optional[str] = None
    session_id: Optional[str] = None
    
    # 新增：解析 session_id（从 URL 查询参数）
    try:
        import urllib.parse
        scope = websocket.scope
        if 'query_string' in scope:
            query_str = scope['query_string'].decode('utf-8')
            if query_str:
                params = urllib.parse.parse_qs(query_str)
                if 'session_id' in params:
                    session_id = params['session_id'][0]
    except (AttributeError, KeyError, Exception) as e:
        # 如果无法解析 session_id，也能正常工作（广播模式）
        pass
    
    # 为这个连接创建消息发送回调
    async def send_message_to_ws(message: Dict[str, Any]):
        """向这个 WebSocket 连接发送消息"""
        if connection_id:
            await websocket_manager.send_message(message, connection_id=connection_id)
    
    try:
        # 建立连接（传递 session_id）
        connection_id = await websocket_manager.connect(websocket, session_id=session_id)
        
        # 注册消息回调到消息队列（传递 connection_id 和 session_id）
        message_queue.register_ws_callback(send_message_to_ws, connection_id, session_id)
        
        # 持续接收来自客户端的消息
        while True:
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                # 尝试从响应中提取有用的信息
                func_name = message.get('function') or message.get('command') or message.get('message', 'unknown')
                logger.info(f"📥 收到响应: {func_name}")
                
                # 将消息传递给消息队列处理（通常是响应）
                await message_queue.receive_response(message)
                
            except json.JSONDecodeError as e:
                logger.error(f"❌ 消息格式错误: {e}")
                # 发送错误响应到客户端
                error_response = {
                    "success": False,
                    "error": "消息格式错误，必须是有效的 JSON"
                }
                await websocket.send_text(json.dumps(error_response, ensure_ascii=False))
    
    except WebSocketDisconnect:
        logger.info(f"⬅️ 客户端断开连接: {connection_id}")
    
    except Exception as e:
        logger.error(f"❌ WebSocket 连接异常: {e}", exc_info=True)
    
    finally:
        # 清理资源
        if connection_id:
            # 断开连接
            websocket_manager.disconnect(connection_id)
            # 注销回调（按 connection_id）
            message_queue.unregister_ws_callback(connection_id)
