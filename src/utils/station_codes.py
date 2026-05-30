import json
from typing import Optional, List, Dict
from src.services.database.data_access import (
    ReservoirAccess, HydrologyStationAccess, RainfallStationAccess, StationAliasAccess
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

_reservoir_name_to_code: Dict[str, str] = {}
_reservoir_aliases: Dict[str, str] = {}
_hydrology_name_to_code: Dict[str, str] = {}
_rainfall_name_to_code: Dict[str, str] = {}
_initialized = False


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    return text.strip().lower().replace(" ", "").replace("　", "")


def _levenshtein_distance(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def _calculate_similarity(str1: str, str2: str) -> float:
    s1 = _normalize_text(str1)
    s2 = _normalize_text(str2)
    if not s1 or not s2:
        return 0.0
    if s1 == s2:
        return 1.0
    if s1 in s2 or s2 in s1:
        ratio = min(len(s1), len(s2)) / max(len(s1), len(s2))
        return 0.85 + ratio * 0.1
    distance = _levenshtein_distance(s1, s2)
    max_len = max(len(s1), len(s2))
    edit_sim = 1 - distance / max_len if max_len > 0 else 0
    set1, set2 = set(s1), set(s2)
    jaccard = len(set1 & set2) / len(set1 | set2) if set1 or set2 else 0
    final_score = edit_sim * 0.6 + jaccard * 0.4
    return max(final_score, 0.0)


def _load_all_data():
    global _reservoir_name_to_code, _reservoir_aliases, _hydrology_name_to_code, _rainfall_name_to_code, _initialized
    if _initialized:
        return

    try:
        reservoirs = ReservoirAccess.get_all()
        for r in reservoirs:
            name = r.get('name', '').strip()
            code = r.get('code', '').strip()
            station_code = r.get('station_code', '').strip() if r.get('station_code') else ''

            if name and code:
                _reservoir_name_to_code[name] = code
                _reservoir_aliases[_normalize_text(name)] = code

                if name.endswith('水库'):
                    alias = name[:-2]
                    _reservoir_aliases[_normalize_text(alias)] = code

                if station_code and station_code != code:
                    _reservoir_aliases[_normalize_text(station_code)] = code
    except Exception as e:
        logger.warning(f"从数据库加载水库数据失败: {e}")

    try:
        aliases = StationAliasAccess.get_all()
        for a in aliases:
            alias = a.get('alias', '').strip()
            code = a.get('station_code', '').strip()
            if alias and code:
                _reservoir_aliases[_normalize_text(alias)] = code
    except Exception as e:
        logger.warning(f"从数据库加载站点别名失败: {e}")

    try:
        hydrology_stations = HydrologyStationAccess.get_all_name_code()
        _hydrology_name_to_code.update(hydrology_stations)
    except Exception as e:
        logger.warning(f"从数据库加载水文站数据失败: {e}")

    try:
        rainfall_stations = RainfallStationAccess.get_all_name_code()
        _rainfall_name_to_code.update(rainfall_stations)
    except Exception as e:
        logger.warning(f"从数据库加载雨量站数据失败: {e}")

    _initialized = True


def get_reservoir_code(name: str, similarity_threshold: float = 0.6) -> Optional[str]:
    _load_all_data()
    if not name:
        return None
    
    name = name.strip()
    normalized = _normalize_text(name)
    
    if name in _reservoir_name_to_code:
        return _reservoir_name_to_code[name]
    
    if normalized in _reservoir_aliases:
        return _reservoir_aliases[normalized]
    
    best_match = None
    best_score = 0.0
    for n, code in _reservoir_name_to_code.items():
        score = _calculate_similarity(name, n)
        if score > best_score:
            best_score = score
            best_match = code
    
    for alias, code in _reservoir_aliases.items():
        score = _calculate_similarity(name, alias)
        if score > best_score:
            best_score = score
            best_match = code
    
    if best_match and best_score >= similarity_threshold:
        return best_match
    
    try:
        r = ReservoirAccess.get_by_code(name)
        if r:
            return r['code']
    except Exception:
        pass
    
    return None


def get_hydrology_code(name: str, similarity_threshold: float = 0.6) -> Optional[str]:
    _load_all_data()
    if not name:
        return None
    
    name = name.strip()
    
    if name in _hydrology_name_to_code:
        return _hydrology_name_to_code[name]
    
    best_match = None
    best_score = 0.0
    for n, code in _hydrology_name_to_code.items():
        score = _calculate_similarity(name, n)
        if score > best_score:
            best_score = score
            best_match = code
    
    if best_match and best_score >= similarity_threshold:
        return best_match
    
    try:
        s = HydrologyStationAccess.get_by_code(name)
        if s:
            return s['code']
    except Exception:
        pass
    
    return None


def get_rainfall_code(name: str, similarity_threshold: float = 0.6) -> Optional[str]:
    _load_all_data()
    if not name:
        return None
    
    name = name.strip()
    
    if name in _rainfall_name_to_code:
        return _rainfall_name_to_code[name]
    
    best_match = None
    best_score = 0.0
    for n, code in _rainfall_name_to_code.items():
        score = _calculate_similarity(name, n)
        if score > best_score:
            best_score = score
            best_match = code
    
    if best_match and best_score >= similarity_threshold:
        return best_match
    
    try:
        s = RainfallStationAccess.get_by_code(name)
        if s:
            return s['code']
    except Exception:
        pass
    
    return None


def get_station_code(name: str, similarity_threshold: float = 0.6) -> Optional[str]:
    if not name:
        return None
    
    name = name.strip()
    normalized = _normalize_text(name)
    
    if normalized in _reservoir_aliases:
        code = _reservoir_aliases[normalized]
        if code and not code.startswith('BDA'):
            return None
        return code
    
    if name.startswith('BDA'):
        r = get_reservoir_code(name, similarity_threshold)
        return r if r else None
    
    if normalized.isdigit():
        r = get_hydrology_code(name, similarity_threshold)
        if r:
            return r
        r = get_rainfall_code(name, similarity_threshold)
        return r if r else None
    
    r = get_reservoir_code(name, similarity_threshold)
    if r:
        return r
    r = get_hydrology_code(name, similarity_threshold)
    if r:
        return r
    r = get_rainfall_code(name, similarity_threshold)
    return r


def get_reservoir_station_code(reservoir_code: str) -> Optional[str]:
    return reservoir_code


def search_reservoir(keyword: str, limit: int = 20, similarity_threshold: float = 0.3) -> List[Dict[str, str]]:
    _load_all_data()
    if not keyword:
        return [{"code": code, "name": name} for name, code in list(_reservoir_name_to_code.items())[:limit]]
    
    results = []
    for name, code in _reservoir_name_to_code.items():
        similarity = _calculate_similarity(keyword, name)
        if similarity >= similarity_threshold:
            results.append({"code": code, "name": name, "similarity": similarity})
    
    for alias, code in _reservoir_aliases.items():
        similarity = _calculate_similarity(keyword, alias)
        if similarity >= similarity_threshold:
            reservoir_name = next((n for n, c in _reservoir_name_to_code.items() if c == code), "")
            if not any(r["code"] == code for r in results):
                results.append({"code": code, "name": reservoir_name, "similarity": similarity})
    
    results.sort(key=lambda x: x["similarity"], reverse=True)
    return [{"code": r["code"], "name": r["name"]} for r in results[:limit]]


def search_station(keyword: str, limit: int = 20, similarity_threshold: float = 0.3) -> List[Dict[str, str]]:
    _load_all_data()
    all_stations = {**_hydrology_name_to_code, **_rainfall_name_to_code}
    if not keyword:
        return [{"code": code, "name": name} for name, code in list(all_stations.items())[:limit]]
    
    results = []
    for name, code in all_stations.items():
        similarity = _calculate_similarity(keyword, name)
        if similarity >= similarity_threshold:
            results.append({"code": code, "name": name, "similarity": similarity})
    
    results.sort(key=lambda x: x["similarity"], reverse=True)
    return [{"code": r["code"], "name": r["name"]} for r in results[:limit]]


def get_all_reservoirs() -> List[Dict[str, str]]:
    _load_all_data()
    return [{"code": code, "name": name} for name, code in _reservoir_name_to_code.items()]


def get_all_stations() -> List[Dict[str, str]]:
    _load_all_data()
    all_stations = {**_hydrology_name_to_code, **_rainfall_name_to_code}
    return [{"code": code, "name": name} for name, code in all_stations.items()]


def reset_cache():
    global _initialized
    _initialized = False
