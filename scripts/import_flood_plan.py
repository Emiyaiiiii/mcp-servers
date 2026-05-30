#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
防汛计划与物资清单数据导入脚本
从 Flood_Control_Plan.json 到数据库
"""

import json
import sqlite3
import sys
import os
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.services.database.connection import get_db
from src.utils.logger import get_logger

logger = get_logger(__name__)

# 水库名称到编码映射
RESERVOIR_NAME_MAP = {
    "渤海湾水利枢纽": None,  # 暂时没有编码
    "故县水库": "BDA80000661",
    "河口村水库": "BDA00000761"
}

def load_json_data():
    """加载 JSON 数据"""
    json_path = project_root / "data" / "Flood_Control_Plan.json"
    if not json_path.exists():
        logger.error(f"JSON 文件不存在: {json_path}")
        return None
    
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    logger.info(f"成功加载 JSON 数据，包含 {len(data)} 个水库")
    return data

def import_materials():
    """导入防汛物资"""
    data = load_json_data()
    if not data:
        return
    
    db = get_db()
    count = 0
    for reservoir_name, plan_data in data.items():
        reservoir_code = RESERVOIR_NAME_MAP.get(reservoir_name)
        
        for category, items in plan_data.items():
            if "储备物资表" in category or "储备表" in category:
                for item in items:
                    # 兼容不同的字段名
                    name = item.get("品名", item.get("物资名称"))
                    unit = item.get("单位")
                    quantity = item.get("数量")
                    keeper = item.get("保管人")
                    keeper_phone = item.get("联系电话")
                    remark = item.get("备注")
                    if not name:
                        continue
                    
                    sql = """
                        INSERT INTO flood_control_materials
                        (reservoir_code, plan_category, material_name, unit, quantity, keeper, keeper_phone, remark)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """
                    db.execute_update(
                        sql,
                        (reservoir_code, category, name, unit, quantity, keeper, keeper_phone, remark)
                    )
                    count += 1
    
    logger.info(f"成功导入 {count} 条物资数据")


def import_contacts():
    """导入联系人"""
    data = load_json_data()
    if not data:
        return
    
    db = get_db()
    count = 0
    for reservoir_name, plan_data in data.items():
        reservoir_code = RESERVOIR_NAME_MAP.get(reservoir_name)
        
        for category, items in plan_data.items():
            if "指挥部" in category or "人员名单" in category or "技术队" in category:
                sort_order = 0
                for item in items:
                    sort_order += 1
                    name = item.get("姓名")
                    if not name:
                        continue
                    title = item.get("职务", item.get("职务单位"))
                    unit = item.get("单位")
                    phone = item.get("电话", item.get("联系方式"))
                    remark = item.get("备注")
                    
                    sql = """
                        INSERT INTO flood_control_contacts
                        (reservoir_code, plan_category, name, title, unit, phone, remark, sort_order)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """
                    db.execute_update(
                        sql,
                        (reservoir_code, category, name, title, unit, phone, remark, sort_order)
                    )
                    count += 1
    
    logger.info(f"成功导入 {count} 条联系人数据")


def import_evacuation_plans():
    """导入人员转移安置计划"""
    data = load_json_data()
    if not data:
        return
    
    db = get_db()
    count = 0
    for reservoir_name, plan_data in data.items():
        reservoir_code = RESERVOIR_NAME_MAP.get(reservoir_name)
        
        for category, items in plan_data.items():
            if "人员转移" in category or "下泄" in category:
                for item in items:
                    region = item.get("区域")
                    discharge = item.get("需转移")
                    transfer_person = item.get("转移责任人")
                    transfer_phone = item.get("转移电话")
                    resettle_person = item.get("安置责任人")
                    resettle_phone = item.get("安置电话")
                    
                    if not region:
                        continue
                    
                    sql = """
                        INSERT INTO flood_evacuation_plans
                        (reservoir_code, discharge_range, region, evacuate_count, transfer_person, transfer_phone, resettle_person, resettle_phone)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """
                    db.execute_update(
                        sql,
                        (reservoir_code, category, region, discharge, transfer_person, transfer_phone, resettle_person, resettle_phone)
                    )
                    count += 1
    
    logger.info(f"成功导入 {count} 条转移安置计划数据")


def import_reservoir_staff():
    """导入库区滞留人员"""
    data = load_json_data()
    if not data:
        return
    
    db = get_db()
    count = 0
    for reservoir_name, plan_data in data.items():
        reservoir_code = RESERVOIR_NAME_MAP.get(reservoir_name)
        
        for category, items in plan_data.items():
            if "滞留养殖人员" in category:
                for item in items:
                    name = item.get("姓名")
                    if not name:
                        continue
                    phone = item.get("联系方式")
                    stay = item.get("留守人员")
                    staff_type = item.get("人员性质")
                    sheep = item.get("羊数量")
                    residence = item.get("居住地点")
                    transfer_location = item.get("转移地点")
                    transfer_contact = item.get("转移联系人")
                    
                    sql = """
                        INSERT INTO flood_reservoir_staff
                        (reservoir_code, name, phone, stay_count, staff_type, sheep_count, residence, transfer_location, transfer_contact)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """
                    db.execute_update(
                        sql,
                        (reservoir_code, name, phone, stay, staff_type, sheep, residence, transfer_location, transfer_contact)
                    )
                    count += 1
    
    logger.info(f"成功导入 {count} 条库区滞留人员数据")


def import_inundation_stats():
    """导入淹没损失统计"""
    data = load_json_data()
    if not data:
        return
    
    db = get_db()
    count = 0
    for reservoir_name, plan_data in data.items():
        reservoir_code = RESERVOIR_NAME_MAP.get(reservoir_name)
        
        for category, items in plan_data.items():
            if "淹没损失统计" in category:
                for item in items:
                    leader = item.get("乡镇领导")
                    village = item.get("村庄")
                    name = item.get("姓名")
                    title = item.get("职务")
                    phone = item.get("联系电话")
                    evac_location = item.get("撤离地点")
                    evac_route = item.get("撤离路线")
                    household = item.get("户数")
                    permanent = item.get("常住人口")
                    temporary = item.get("临时生产人员")
                    house = item.get("房屋")
                    cave = item.get("窑洞")
                    farmland = item.get("耕地")
                    forest = item.get("林地")
                    orchard = item.get("果园")
                    well = item.get("机井")
                    pump = item.get("提灌站")
                    
                    sql = """
                        INSERT INTO flood_inundation_stats
                        (reservoir_code, level_range, township_leader, village, contact_name, contact_title, contact_phone, evacuation_location, evacuation_route, household_count, permanent_residents, temporary_staff, house_count, cave_count, farmland_area, forest_area, orchard_area, well_count, pump_count)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """
                    db.execute_update(
                        sql,
                        (reservoir_code, category, leader, village, name, title, phone, evac_location, evac_route, household, permanent, temporary, house, cave, farmland, forest, orchard, well, pump)
                    )
                    count += 1
    
    logger.info(f"成功导入 {count} 条淹没损失统计数据")


def import_contact_phones():
    """导入常用联系电话"""
    data = load_json_data()
    if not data:
        return
    
    db = get_db()
    count = 0
    for reservoir_name, plan_data in data.items():
        reservoir_code = RESERVOIR_NAME_MAP.get(reservoir_name)
        
        for category, items in plan_data.items():
            if "常用电话" in category:
                sort_order = 0
                for item in items:
                    sort_order += 1
                    unit = item.get("单位名称")
                    if not unit:
                        continue
                    phone = item.get("电话")
                    fax = item.get("传真")
                    remark = item.get("备注")
                    
                    sql = """
                        INSERT INTO flood_contact_phones
                        (reservoir_code, unit_name, phone, fax, remark, sort_order)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """
                    db.execute_update(
                        sql,
                        (reservoir_code, unit, phone, fax, remark, sort_order)
                    )
                    count += 1
    
    logger.info(f"成功导入 {count} 条常用联系电话数据")


def import_all():
    """导入所有数据"""
    logger.info("开始导入防汛计划数据...")
    import_materials()
    import_contacts()
    import_evacuation_plans()
    import_reservoir_staff()
    import_inundation_stats()
    import_contact_phones()
    logger.info("所有数据导入完成！")


if __name__ == "__main__":
    import_all()
