"""存储服务模块

提供数据持久化服务：
- 数据库连接和访问 (database/)
- 调度方案存储 (scheme_storage)
"""

from src.services.storage.scheme_storage import (
    generate_unique_id,
    save_scheme,
    get_scheme,
    get_all_schemes,
    delete_scheme,
    clear_all_schemes,
    scheme_exists
)

__all__ = [
    'generate_unique_id',
    'save_scheme',
    'get_scheme',
    'get_all_schemes',
    'delete_scheme',
    'clear_all_schemes',
    'scheme_exists',
]
