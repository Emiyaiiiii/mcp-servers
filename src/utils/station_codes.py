import csv
import os
import re
from pathlib import Path
from typing import Optional, List, Dict

# 尝试导入拼音库，如果不可用则跳过
try:
    from pypinyin import lazy_pinyin
    PYPINYIN_AVAILABLE = True
except ImportError:
    PYPINYIN_AVAILABLE = False

DATA_DIR = Path(__file__).parent.parent.parent / "data"

_reservoir_cache: Dict[str, str] = {}
_reservoir_name_to_code: Dict[str, str] = {}
_reservoir_aliases: Dict[str, str] = {}  # 别名映射
_station_cache: Dict[str, str] = {}
_station_name_to_code: Dict[str, str] = {}

_initialized = False


def _normalize_text(text: str) -> str:
    """标准化文本：去除空格、统一大小写"""
    if not text:
        return ""
    return text.strip().lower().replace(" ", "").replace("　", "")


def _levenshtein_distance(s1: str, s2: str) -> int:
    """计算编辑距离（Levenshtein Distance）"""
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
    """计算两个字符串的综合相似度（0-1之间）

    综合考虑：
    1. 完全匹配
    2. 包含关系
    3. 编辑距离
    4. 字符集合相似度
    5. 拼音相似度（如果可用）
    """
    s1 = _normalize_text(str1)
    s2 = _normalize_text(str2)

    if not s1 or not s2:
        return 0.0

    # 1. 完全匹配
    if s1 == s2:
        return 1.0

    # 2. 包含关系（高相似度）
    if s1 in s2 or s2 in s1:
        # 长度越接近，相似度越高
        ratio = min(len(s1), len(s2)) / max(len(s1), len(s2))
        return 0.85 + ratio * 0.1  # 0.85 - 0.95

    # 3. 编辑距离相似度
    distance = _levenshtein_distance(s1, s2)
    max_len = max(len(s1), len(s2))
    edit_sim = 1 - distance / max_len if max_len > 0 else 0

    # 4. 字符集合相似度（Jaccard）
    set1, set2 = set(s1), set(s2)
    jaccard = len(set1 & set2) / len(set1 | set2) if set1 or set2 else 0

    # 5. 拼音相似度
    pinyin_sim = 0.0
    if PYPINYIN_AVAILABLE:
        try:
            py1 = ''.join(lazy_pinyin(s1))
            py2 = ''.join(lazy_pinyin(s2))
            if py1 == py2:
                pinyin_sim = 0.9  # 拼音完全相同
            else:
                py_distance = _levenshtein_distance(py1, py2)
                py_max_len = max(len(py1), len(py2))
                pinyin_sim = 1 - py_distance / py_max_len if py_max_len > 0 else 0
        except Exception:
            pass

    # 综合评分（加权平均）
    if PYPINYIN_AVAILABLE:
        # 有拼音支持时，拼音权重较高（中文容错）
        final_score = edit_sim * 0.25 + jaccard * 0.15 + pinyin_sim * 0.6
    else:
        # 无拼音支持时，依赖编辑距离和字符集合
        final_score = edit_sim * 0.6 + jaccard * 0.4

    return max(final_score, 0.0)


def _load_reservoir_codes():
    global _reservoir_cache, _reservoir_name_to_code, _reservoir_aliases, _initialized
    if _initialized:
        return

    reservoir_file = DATA_DIR / "水库.csv"
    if reservoir_file.exists():
        try:
            with open(reservoir_file, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = row.get("rsnm", "").strip()
                    code = row.get("rscd", "").strip()
                    station_name = row.get("stnm", "").strip()  # 测站名称

                    if name and code:
                        _reservoir_cache[code] = name
                        _reservoir_name_to_code[name] = code

                        # 添加标准化名称映射
                        normalized_name = _normalize_text(name)
                        _reservoir_aliases[normalized_name] = code

                        # 处理常见别名：去除"水库"后缀
                        if name.endswith("水库"):
                            alias = name[:-2]
                            _reservoir_aliases[_normalize_text(alias)] = code

                    # 同时添加测站名称映射
                    if station_name and station_name != "null":
                        _reservoir_aliases[_normalize_text(station_name)] = code

        except Exception as e:
            print(f"加载水库编码表失败: {e}")

    _initialized = True


def _load_station_codes():
    global _station_cache, _station_name_to_code, _initialized

    # 加载雨量站数据
    station_file = DATA_DIR / "雨量站.csv"
    if station_file.exists():
        encodings = ["utf-8-sig", "gbk", "gb2312", "latin1"]
        for enc in encodings:
            try:
                with open(station_file, "r", encoding=enc) as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        name = row.get("st_name", "").strip()
                        code = row.get("stcd", "").strip()
                        if name and code:
                            _station_cache[code] = name
                            _station_name_to_code[name] = code
                break
            except UnicodeDecodeError:
                continue

    # 加载水文站数据
    hydrology_file = DATA_DIR / "水文站.csv"
    if hydrology_file.exists():
        encodings = ["utf-8-sig", "gbk", "gb2312", "latin1"]
        for enc in encodings:
            try:
                with open(hydrology_file, "r", encoding=enc) as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        name = row.get("hy_name", "").strip()
                        code = row.get("hysta", "").strip()
                        if name and code:
                            _station_cache[code] = name
                            _station_name_to_code[name] = code
                break
            except UnicodeDecodeError:
                continue


def get_reservoir_code(name_or_code: str, similarity_threshold: float = 0.6) -> Optional[str]:
    """获取水库编码，支持模糊匹配

    Args:
        name_or_code: 水库名称或编码
        similarity_threshold: 相似度阈值，低于此值视为不匹配（默认0.6）

    Returns:
        水库编码，未找到返回 None

    匹配优先级：
    1. 精确匹配编码
    2. 精确匹配名称（包括标准化后的名称）
    3. 别名匹配
    4. 相似度匹配（返回最相似的，需超过阈值）
    """
    _load_reservoir_codes()

    if not name_or_code:
        return None

    name_or_code = name_or_code.strip()
    normalized_input = _normalize_text(name_or_code)

    # 1. 精确匹配编码
    if name_or_code in _reservoir_cache:
        return name_or_code

    # 2. 精确匹配名称
    if name_or_code in _reservoir_name_to_code:
        return _reservoir_name_to_code[name_or_code]

    # 3. 标准化名称匹配（别名）
    if normalized_input in _reservoir_aliases:
        return _reservoir_aliases[normalized_input]

    # 4. 相似度匹配
    best_match = None
    best_score = 0.0

    for name, code in _reservoir_name_to_code.items():
        score = _calculate_similarity(name_or_code, name)
        if score > best_score:
            best_score = score
            best_match = code

    # 也检查别名
    for alias, code in _reservoir_aliases.items():
        score = _calculate_similarity(name_or_code, alias)
        if score > best_score:
            best_score = score
            best_match = code

    # 只有超过阈值才返回
    if best_match and best_score >= similarity_threshold:
        return best_match

    return None


def get_station_code(name_or_code: str, similarity_threshold: float = 0.6) -> Optional[str]:
    """获取站点编码，支持模糊匹配"""
    _load_station_codes()

    if not name_or_code:
        return None

    name_or_code = name_or_code.strip()

    # 精确匹配
    if name_or_code in _station_cache:
        return name_or_code

    if name_or_code in _station_name_to_code:
        return _station_name_to_code[name_or_code]

    # 相似度匹配
    best_match = None
    best_score = 0.0

    for name, code in _station_name_to_code.items():
        score = _calculate_similarity(name_or_code, name)
        if score > best_score:
            best_score = score
            best_match = code

    if best_match and best_score >= similarity_threshold:
        return best_match

    return None


def search_reservoir(keyword: str, limit: int = 20, similarity_threshold: float = 0.3) -> List[Dict[str, str]]:
    """搜索水库，支持模糊匹配，按相似度排序

    Args:
        keyword: 搜索关键词
        limit: 返回结果数量限制
        similarity_threshold: 相似度阈值

    Returns:
        匹配的水库列表，按相似度降序排列
    """
    _load_reservoir_codes()

    if not keyword:
        return [{"code": code, "name": name} for code, name in list(_reservoir_cache.items())[:limit]]

    results = []

    # 检查所有水库名称
    for name, code in _reservoir_name_to_code.items():
        similarity = _calculate_similarity(keyword, name)
        if similarity >= similarity_threshold:
            results.append({"code": code, "name": name, "similarity": similarity})

    # 也检查别名
    for alias, code in _reservoir_aliases.items():
        similarity = _calculate_similarity(keyword, alias)
        if similarity >= similarity_threshold:
            reservoir_name = _reservoir_cache.get(code, "")
            # 避免重复
            if not any(r["code"] == code for r in results):
                results.append({"code": code, "name": reservoir_name, "similarity": similarity})

    # 按相似度排序
    results.sort(key=lambda x: x["similarity"], reverse=True)

    # 移除相似度字段，只返回 code 和 name
    return [{"code": r["code"], "name": r["name"]} for r in results[:limit]]


def search_station(keyword: str, limit: int = 20, similarity_threshold: float = 0.3) -> List[Dict[str, str]]:
    """搜索站点，支持模糊匹配"""
    _load_station_codes()

    if not keyword:
        return [{"code": code, "name": name} for code, name in list(_station_cache.items())[:limit]]

    results = []

    for name, code in _station_name_to_code.items():
        similarity = _calculate_similarity(keyword, name)
        if similarity >= similarity_threshold:
            results.append({"code": code, "name": name, "similarity": similarity})

    # 按相似度排序
    results.sort(key=lambda x: x["similarity"], reverse=True)

    return [{"code": r["code"], "name": r["name"]} for r in results[:limit]]


def get_all_reservoirs() -> List[Dict[str, str]]:
    _load_reservoir_codes()
    return [{"code": code, "name": name} for code, name in _reservoir_cache.items()]


def get_all_stations() -> List[Dict[str, str]]:
    _load_station_codes()
    return [{"code": code, "name": name} for code, name in _station_cache.items()]
