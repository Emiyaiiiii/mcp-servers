import os
import pandas as pd
from typing import Dict, Any, List
from src.utils.logger import get_logger

logger = get_logger(__name__)


def scan_templates() -> dict:
    """扫描 Parameter_template 目录，返回模板名称→文件路径的映射

    Returns:
        {
            "模板名称": {
                "category": "上大洪水控制",
                "file_path": "D:/.../方案一.xlsx",
                "file_name": "方案一：（小浪底不保滩，控花园口10000）.xlsx"
            },
            ...
        }
    """
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    template_dir = os.path.join(project_root, 'src', 'services', 'external_api', 'RegualDispacth', 'Parameter_template')

    templates = {}
    if not os.path.exists(template_dir):
        return templates

    for category in os.listdir(template_dir):
        category_path = os.path.join(template_dir, category)
        if not os.path.isdir(category_path):
            continue
        for fname in os.listdir(category_path):
            if fname.endswith('.xlsx'):
                file_path = os.path.join(category_path, fname)
                short_name = fname.split('：')[0] if '：' in fname else fname.replace('.xlsx', '')
                unique_key = f"{category}/{short_name}"
                templates[unique_key] = {
                    "category": category,
                    "file_path": file_path,
                    "file_name": fname,
                    "short_name": short_name
                }
    return templates


def find_template_file(template_name: str) -> dict | None:
    """通过关键词模糊匹配模板文件

    匹配规则：
    1. 精确匹配简短名称（如"方案一"）- 若多个类别匹配，返回第一个
    2. 精确匹配唯一键（如"上大洪水控制/方案一"）
    3. 包含匹配完整文件名（如"常规调度"匹配"方案一：演练洪水-常规调度-...xlsx"）
    4. 类别匹配（如"上大"、"下大"）
    """
    templates = scan_templates()
    if not templates:
        return None

    if template_name in templates:
        return templates[template_name]

    for key, info in templates.items():
        if template_name == info.get('short_name', ''):
            return info

    for key, info in templates.items():
        if template_name in info['file_name']:
            return info

    for key, info in templates.items():
        if template_name in info['category']:
            return info

    return None


def get_template_sheets(file_path: str) -> list:
    """获取模板 Excel 文件的所有 sheet 名称"""
    try:
        xl = pd.ExcelFile(file_path)
        return xl.sheet_names
    except Exception:
        return []


def generate_natural_language_summary(
    reservoir_stats: List,
    hydrologic_stats: List,
    flood_submergence: dict,
    dongpinghu_diversion: dict,
    flood_type: str
) -> str:
    """根据所有计算结果生成格式化自然语言总结"""
    lines = []
    
    res_map = {s["reservoir"]: s for s in reservoir_stats}
    
    for rname in ["三门峡", "小浪底", "陆浑", "故县", "河口村"]:
        if rname not in res_map:
            continue
        r = res_map[rname]
        water_level = r["max_water_level"]
        if rname == "三门峡":
            lines.append(f"按照常规方案调算，{rname}水库最高水位{water_level}米。")
        elif rname == "小浪底":
            lines.append(f"{rname}水库最高水位{water_level}米。")
        elif rname == "陆浑":
            lines.append(f"支流{rname}水库最高水位{water_level}米。")
        elif rname == "故县":
            lines.append(f"{rname}水库最高水位{water_level}米，不涉及人口转移。")
        elif rname == "河口村":
            lines.append(f"{rname}水库最高水位{water_level}米。")
    
    lines.append("")
    
    hydro_map = {s["station"]: s for s in hydrologic_stats}
    
    garden_peak = hydro_map.get("花园口", {}).get("peak_flow", 0)
    garden_excess = hydro_map.get("花园口", {}).get("excess_volume_10000", 0)
    sunk_peak = hydro_map.get("孙口", {}).get("peak_flow", 0)
    sunk_excess = hydro_map.get("孙口", {}).get("excess_volume_10000", 0)
    
    lines.append(f"通过几个水库调蓄，花园口洪峰{garden_peak:.0f}立方米每秒，超万洪量{garden_excess:.2f}亿立方米。")
    
    if flood_submergence.get("description") == "不漫滩":
        lines.append("下游滩区不会漫滩。")
    else:
        lines.append(f"预估下游滩区发生漫滩，涉及人口{flood_submergence.get('involved_population', 0):.2f}万人，需转移安置{flood_submergence.get('evacuated_population', 0):.2f}万人。")
    
    lines.append(f"孙口站洪峰流量{sunk_peak:.0f}立方米每秒，超万洪量{sunk_excess:.2f}亿立方米。")
    
    if dongpinghu_diversion.get("enabled"):
        lines.append(f"需要启用东平湖滞洪区分洪，东平湖最大分洪流量{dongpinghu_diversion['max_flow']}立方米每秒，分滞洪量{dongpinghu_diversion['volume']}亿立方米，需要同时启用老湖区和新湖区。")
    
    return "\n".join(lines)