"""服务模块

提供各类服务：
- communication: 通信服务（WebSocket、消息队列、命令发送）
- external_api: 外部 API 服务（数据 API、来水预报、增强搜索、新安江模型）
- storage: 存储服务（数据库、方案存储）
"""

# 通信服务
from src.services.communication import (
    websocket_manager,
    message_queue,
    command_sender,
)

# 外部 API 服务
from src.services.external_api import (
    data_api_auth_service,
    water_forecast_auth_service,
    water_forecast_service,
    enhanced_search_auth_service,
    enhanced_search_service,
    xinanjiang_auth_service,
    xinanjiang_model_service,
)

# 存储服务
from src.services.storage import (
    generate_unique_id,
    save_scheme,
    get_scheme,
    get_all_schemes,
    delete_scheme,
    clear_all_schemes,
    scheme_exists,
)

__all__ = [
    # 通信服务
    'websocket_manager',
    'message_queue',
    'command_sender',
    # 外部 API 服务
    'data_api_auth_service',
    'water_forecast_auth_service',
    'water_forecast_service',
    'enhanced_search_auth_service',
    'enhanced_search_service',
    'xinanjiang_auth_service',
    'xinanjiang_model_service',
    # 存储服务
    'generate_unique_id',
    'save_scheme',
    'get_scheme',
    'get_all_schemes',
    'delete_scheme',
    'clear_all_schemes',
    'scheme_exists',
]
