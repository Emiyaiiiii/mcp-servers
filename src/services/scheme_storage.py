from typing import Dict, List, Optional
from src.services.database.data_access import SchemeAccess
from src.services.database.init_database import init_database
from src.utils.logger import get_logger

logger = get_logger(__name__)

init_database()


def generate_unique_id() -> str:
    """
    生成唯一的调度方案ID。
    
    Returns:
        格式为 DS-XXXX 的唯一ID
    """
    from src.services.database.connection import get_db
    
    sql = """
        SELECT MAX(CAST(SUBSTR(scheme_id, 4) AS INTEGER)) as max_id 
        FROM schemes
    """
    result = get_db().execute_one(sql)
    max_id = result['max_id'] or 0
    return f"DS-{max_id + 1:04d}"


def save_scheme(scheme: dict) -> str:
    """
    保存调度方案到数据库持久化存储。
    
    Args:
        scheme: 调度方案字典
        
    Returns:
        保存后的方案ID
    """
    return SchemeAccess.save(scheme)


def get_scheme(scheme_id: str) -> Optional[dict]:
    """
    根据方案ID从数据库获取调度方案。
    
    Args:
        scheme_id: 调度方案ID
        
    Returns:
        调度方案字典，如果不存在则返回 None
    """
    return SchemeAccess.get_by_id(scheme_id)


def get_all_schemes() -> List[dict]:
    """
    从数据库获取所有已保存的调度方案列表。
    
    Returns:
        所有调度方案的列表
    """
    return SchemeAccess.get_all()


def delete_scheme(scheme_id: str) -> bool:
    """
    从数据库删除指定的调度方案。
    
    Args:
        scheme_id: 调度方案ID
        
    Returns:
        删除是否成功
    """
    return SchemeAccess.delete(scheme_id)


def clear_all_schemes() -> None:
    """
    清空数据库中所有调度方案。
    """
    SchemeAccess.clear_all()


def scheme_exists(scheme_id: str) -> bool:
    """
    检查方案在数据库中是否存在。
    
    Args:
        scheme_id: 调度方案ID
        
    Returns:
        方案是否存在
    """
    return get_scheme(scheme_id) is not None
