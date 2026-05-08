from typing import Dict, List, Optional
import json
from datetime import datetime
from src.utils.logger import get_logger

logger = get_logger(__name__)

_scheme_storage: Dict[str, dict] = {}
_scheme_list: List[dict] = []
_scheme_counter = 1


def generate_unique_id() -> str:
    """
    生成全局唯一的调度方案ID。
    
    Returns:
        唯一的方案ID，格式为 DS-XXXX（XXXX为4位数字）
    """
    global _scheme_counter
    while True:
        scheme_id = f"DS-{_scheme_counter:04d}"
        if scheme_id not in _scheme_storage:
            _scheme_counter += 1
            return scheme_id
        _scheme_counter += 1


def save_scheme(scheme: dict) -> str:
    """
    保存调度方案到内存存储。
    
    Args:
        scheme: 调度方案字典
        
    Returns:
        保存后的方案ID
    """
    scheme_id = scheme.get("scheme_id")
    
    if not scheme_id or scheme_exists(scheme_id):
        scheme_id = generate_unique_id()
        scheme["scheme_id"] = scheme_id
    
    scheme["saved_at"] = datetime.now().isoformat()
    _scheme_storage[scheme_id] = scheme
    
    existing_index = next((i for i, s in enumerate(_scheme_list) if s.get("scheme_id") == scheme_id), None)
    if existing_index is not None:
        _scheme_list[existing_index] = scheme
    else:
        _scheme_list.append(scheme)
    
    logger.info(f"调度方案 {scheme_id} 已保存")
    return scheme_id


def get_scheme(scheme_id: str) -> Optional[dict]:
    """
    根据方案ID获取调度方案。
    
    Args:
        scheme_id: 调度方案ID
        
    Returns:
        调度方案字典，如果不存在则返回 None
    """
    return _scheme_storage.get(scheme_id)


def get_all_schemes() -> List[dict]:
    """
    获取所有已保存的调度方案列表。
    
    Returns:
        所有调度方案的列表
    """
    return _scheme_list.copy()


def delete_scheme(scheme_id: str) -> bool:
    """
    删除指定的调度方案。
    
    Args:
        scheme_id: 调度方案ID
        
    Returns:
        删除是否成功
    """
    if scheme_id in _scheme_storage:
        scheme = _scheme_storage.pop(scheme_id)
        if scheme in _scheme_list:
            _scheme_list.remove(scheme)
        logger.info(f"调度方案 {scheme_id} 已删除")
        return True
    return False


def clear_all_schemes() -> None:
    """
    清空所有调度方案。
    """
    _scheme_storage.clear()
    _scheme_list.clear()
    logger.info("所有调度方案已清空")


def scheme_exists(scheme_id: str) -> bool:
    """
    检查方案是否存在。
    
    Args:
        scheme_id: 调度方案ID
        
    Returns:
        方案是否存在
    """
    return scheme_id in _scheme_storage