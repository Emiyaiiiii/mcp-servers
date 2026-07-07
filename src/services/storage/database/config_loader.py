#!/usr/bin/env python3
"""
配置加载器 - 从数据库动态加载所有配置
避免硬编码，提高可维护性
"""

from typing import Dict, Optional, List
from .data_access import (
    StationAliasAccess,
    ReservoirAccess,
    HydrologyStationAccess,
    RainfallStationAccess
)

# 缓存配置，避免频繁查询数据库
_alias_cache = None
_reservoir_cache = None
_hydrology_cache = None
_rainfall_cache = None


def load_alias_map() -> Dict[str, str]:
    """
    从数据库加载别名映射
    返回: {别名: 编码} 的字典
    """
    global _alias_cache
    
    if _alias_cache is None:
        aliases = StationAliasAccess.get_all()
        _alias_cache = {alias['alias']: alias['station_code'] for alias in aliases}
    
    return _alias_cache


def resolve_station_code(alias_or_code: str) -> str:
    """
    解析站点编码，支持别名
    如果找不到别名，返回原编码
    """
    alias_map = load_alias_map()
    return alias_map.get(alias_or_code, alias_or_code)


def load_reservoir_config() -> Dict[str, dict]:
    """
    从数据库加载水库配置
    返回: {水库名称: {配置}} 的字典
    """
    global _reservoir_cache
    
    if _reservoir_cache is None:
        reservoirs = ReservoirAccess.get_all()
        _reservoir_cache = {}
        
        for res in reservoirs:
            _reservoir_cache[res['name']] = {
                'code': res['code'],
                'station_code': res['station_code'],
                'base_level': res.get('level_normal'),
                'base_storage': res.get('capacity_total'),
                'max_level': res.get('level_flood_max'),
                'max_storage': res.get('capacity_total'),
                'level_flood_check': res.get('level_flood_check'),
                'river': res.get('river'),
                'location': res.get('location')
            }
    
    return _reservoir_cache


def get_reservoir_config_by_code(code: str) -> Optional[dict]:
    """
    根据编码获取水库配置
    """
    config = load_reservoir_config()
    code = resolve_station_code(code)
    
    for name, res_config in config.items():
        if res_config['code'] == code or res_config['station_code'] == code:
            return res_config
    
    return None


def load_hydrology_stations() -> Dict[str, dict]:
    """
    从数据库加载水文站配置
    返回: {站点名称: {配置}} 的字典
    """
    global _hydrology_cache
    
    if _hydrology_cache is None:
        stations = HydrologyStationAccess.get_all()
        _hydrology_cache = {station['name']: station for station in stations}
    
    return _hydrology_cache


def load_rainfall_stations() -> Dict[str, dict]:
    """
    从数据库加载雨量站配置
    返回: {站点名称: {配置}} 的字典
    """
    global _rainfall_cache
    
    if _rainfall_cache is None:
        stations = RainfallStationAccess.get_all()
        _rainfall_cache = {station['name']: station for station in stations}
    
    return _rainfall_cache


def get_all_reservoir_codes() -> List[str]:
    """获取所有水库编码"""
    config = load_reservoir_config()
    return [res['code'] for res in config.values()]


def get_all_reservoir_names() -> List[str]:
    """获取所有水库名称"""
    config = load_reservoir_config()
    return list(config.keys())


def clear_cache():
    """清除缓存，强制重新加载"""
    global _alias_cache, _reservoir_cache, _hydrology_cache, _rainfall_cache
    _alias_cache = None
    _reservoir_cache = None
    _hydrology_cache = None
    _rainfall_cache = None


def reload_config():
    """重新加载所有配置"""
    clear_cache()
    load_alias_map()
    load_reservoir_config()
    load_hydrology_stations()
    load_rainfall_stations()
