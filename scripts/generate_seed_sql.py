#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQL 种子数据生成脚本
将 JSON 数据转换为 SQL INSERT 语句
"""

import json
import sys
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def escape_sql_string(s):
    """SQL 字符串转义"""
    if s is None:
        return 'NULL'
    if isinstance(s, (int, float)):
        return str(s)
    if isinstance(s, str):
        s = s.replace("'", "''")
        s = s.replace("\\", "\\\\")
        return "'" + s + "'"
    return "'" + str(s) + "'"


def load_json_data(filename):
    """加载 JSON 数据"""
    json_path = project_root / "data" / filename
    if not json_path.exists():
        print(f"JSON 文件不存在: {json_path}")
        return None
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_flood_plan_sql():
    """生成防汛计划 SQL"""
    print("生成 05_seed_flood_plan.sql ...")
    
    data = load_json_data("Flood_Control_Plan.json")
    if not data:
        return
    
    sql_lines = []
    sql_lines.append("-- 防汛物资与联系人数据")
    sql_lines.append("-- 来源: 从 Flood_Control_Plan.json 迁移")
    sql_lines.append("")
    
    # 水库编码映射
    reservoir_codes = {
        "渤海湾水利枢纽": None,
        "故县水库": "BDA80000661",
        "河口村水库": "BDA00000761"
    }
    
    # 1. 防汛物资
    sql_lines.append("-- ============================================")
    sql_lines.append("-- 1. 防汛物资数据")
    sql_lines.append("-- ============================================")
    sql_lines.append("")
    sql_lines.append("DELETE FROM flood_control_materials;")
    sql_lines.append("")
    
    materials_count = 0
    for reservoir_name, plan_data in data.items():
        reservoir_code = reservoir_codes.get(reservoir_name)
        
        for category, items in plan_data.items():
            if "储备物资表" in category or "储备表" in category:
                for item in items:
                    name = item.get("品名", item.get("物资名称"))
                    if not name:
                        continue
                    
                    unit = escape_sql_string(item.get("单位"))
                    quantity_raw = item.get("数量")
                    keeper = escape_sql_string(item.get("保管人"))
                    keeper_phone = escape_sql_string(item.get("联系电话"))
                    remark_raw = item.get("备注")
                    
                    # 处理非数字的 quantity
                    if quantity_raw is not None:
                        try:
                            quantity_val = float(quantity_raw)
                            quantity_sql = str(int(quantity_val)) if quantity_val == int(quantity_val) else str(quantity_val)
                        except (ValueError, TypeError):
                            quantity_sql = "NULL"
                            remark_raw = f"{quantity_raw} {remark_raw or ''}".strip()
                    else:
                        quantity_sql = "NULL"
                    
                    remark = escape_sql_string(remark_raw)
                    
                    sql = f"INSERT INTO flood_control_materials (reservoir_code, plan_category, material_name, unit, quantity, keeper, keeper_phone, remark) VALUES ({escape_sql_string(reservoir_code)}, {escape_sql_string(category)}, {escape_sql_string(name)}, {unit}, {quantity_sql}, {keeper}, {keeper_phone}, {remark});"
                    sql_lines.append(sql)
                    materials_count += 1
    
    sql_lines.append("")
    sql_lines.append(f"-- 共 {materials_count} 条物资数据")
    sql_lines.append("")
    
    # 2. 防汛联系人
    sql_lines.append("-- ============================================")
    sql_lines.append("-- 2. 防汛联系人数据")
    sql_lines.append("-- ============================================")
    sql_lines.append("")
    sql_lines.append("DELETE FROM flood_control_contacts;")
    sql_lines.append("")
    
    contacts_count = 0
    for reservoir_name, plan_data in data.items():
        reservoir_code = reservoir_codes.get(reservoir_name)
        
        for category, items in plan_data.items():
            if "指挥部" in category or "人员名单" in category or "技术队" in category:
                sort_order = 0
                for item in items:
                    sort_order += 1
                    name = item.get("姓名")
                    if not name:
                        continue
                    
                    title = escape_sql_string(item.get("职务", item.get("职务单位")))
                    unit = escape_sql_string(item.get("单位"))
                    phone = escape_sql_string(item.get("电话", item.get("联系方式")))
                    remark = escape_sql_string(item.get("备注"))
                    
                    sql = f"INSERT INTO flood_control_contacts (reservoir_code, plan_category, name, title, unit, phone, remark, sort_order) VALUES ({escape_sql_string(reservoir_code)}, {escape_sql_string(category)}, {escape_sql_string(name)}, {title}, {unit}, {phone}, {remark}, {sort_order});"
                    sql_lines.append(sql)
                    contacts_count += 1
    
    sql_lines.append("")
    sql_lines.append(f"-- 共 {contacts_count} 条联系人数据")
    sql_lines.append("")
    
    # 3. 人员转移安置计划
    sql_lines.append("-- ============================================")
    sql_lines.append("-- 3. 人员转移安置计划数据")
    sql_lines.append("-- ============================================")
    sql_lines.append("")
    sql_lines.append("DELETE FROM flood_evacuation_plans;")
    sql_lines.append("")
    
    evacuation_count = 0
    for reservoir_name, plan_data in data.items():
        reservoir_code = reservoir_codes.get(reservoir_name)
        
        for category, items in plan_data.items():
            if "人员转移" in category or "下泄" in category:
                for item in items:
                    region = item.get("区域")
                    if not region:
                        continue
                    
                    discharge = item.get("需转移")
                    transfer_person = escape_sql_string(item.get("转移责任人"))
                    transfer_phone = escape_sql_string(item.get("转移电话"))
                    resettle_person = escape_sql_string(item.get("安置责任人"))
                    resettle_phone = escape_sql_string(item.get("安置电话"))
                    
                    sql = f"INSERT INTO flood_evacuation_plans (reservoir_code, discharge_range, region, evacuate_count, transfer_person, transfer_phone, resettle_person, resettle_phone) VALUES ({escape_sql_string(reservoir_code)}, {escape_sql_string(category)}, {escape_sql_string(region)}, {discharge}, {transfer_person}, {transfer_phone}, {resettle_person}, {resettle_phone});"
                    sql_lines.append(sql)
                    evacuation_count += 1
    
    sql_lines.append("")
    sql_lines.append(f"-- 共 {evacuation_count} 条转移安置计划数据")
    sql_lines.append("")
    
    # 4. 库区滞留人员
    sql_lines.append("-- ============================================")
    sql_lines.append("-- 4. 库区滞留人员数据")
    sql_lines.append("-- ============================================")
    sql_lines.append("")
    sql_lines.append("DELETE FROM flood_reservoir_staff;")
    sql_lines.append("")
    
    staff_count = 0
    for reservoir_name, plan_data in data.items():
        reservoir_code = reservoir_codes.get(reservoir_name)
        
        for category, items in plan_data.items():
            if "滞留养殖人员" in category:
                for item in items:
                    name = item.get("姓名")
                    if not name:
                        continue
                    
                    phone = escape_sql_string(item.get("联系方式"))
                    stay = item.get("留守人员")
                    staff_type = escape_sql_string(item.get("人员性质"))
                    sheep = item.get("羊数量")
                    residence = escape_sql_string(item.get("居住地点"))
                    transfer_location = escape_sql_string(item.get("转移地点"))
                    transfer_contact = escape_sql_string(item.get("转移联系人"))
                    
                    sql = f"INSERT INTO flood_reservoir_staff (reservoir_code, name, phone, stay_count, staff_type, sheep_count, residence, transfer_location, transfer_contact) VALUES ({escape_sql_string(reservoir_code)}, {escape_sql_string(name)}, {phone}, {stay}, {staff_type}, {sheep}, {residence}, {transfer_location}, {transfer_contact});"
                    sql_lines.append(sql)
                    staff_count += 1
    
    sql_lines.append("")
    sql_lines.append(f"-- 共 {staff_count} 条库区滞留人员数据")
    sql_lines.append("")
    
    # 5. 淹没损失统计
    sql_lines.append("-- ============================================")
    sql_lines.append("-- 5. 淹没损失统计数据")
    sql_lines.append("-- ============================================")
    sql_lines.append("")
    sql_lines.append("DELETE FROM flood_inundation_stats;")
    sql_lines.append("")
    
    inundation_count = 0
    for reservoir_name, plan_data in data.items():
        reservoir_code = reservoir_codes.get(reservoir_name)
        
        for category, items in plan_data.items():
            if "淹没损失统计" in category:
                for item in items:
                    leader = escape_sql_string(item.get("乡镇领导"))
                    village = escape_sql_string(item.get("村庄"))
                    name = escape_sql_string(item.get("姓名"))
                    title = escape_sql_string(item.get("职务"))
                    phone = escape_sql_string(item.get("联系电话"))
                    evac_location = escape_sql_string(item.get("撤离地点"))
                    evac_route = escape_sql_string(item.get("撤离路线"))
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
                    
                    sql = f"INSERT INTO flood_inundation_stats (reservoir_code, level_range, township_leader, village, contact_name, contact_title, contact_phone, evacuation_location, evacuation_route, household_count, permanent_residents, temporary_staff, house_count, cave_count, farmland_area, forest_area, orchard_area, well_count, pump_count) VALUES ({escape_sql_string(reservoir_code)}, {escape_sql_string(category)}, {leader}, {village}, {name}, {title}, {phone}, {evac_location}, {evac_route}, {household}, {permanent}, {temporary}, {house}, {cave}, {farmland}, {forest}, {orchard}, {well}, {pump});"
                    sql_lines.append(sql)
                    inundation_count += 1
    
    sql_lines.append("")
    sql_lines.append(f"-- 共 {inundation_count} 条淹没损失统计数据")
    sql_lines.append("")
    
    # 6. 常用联系电话
    sql_lines.append("-- ============================================")
    sql_lines.append("-- 6. 常用联系电话数据")
    sql_lines.append("-- ============================================")
    sql_lines.append("")
    sql_lines.append("DELETE FROM flood_contact_phones;")
    sql_lines.append("")
    
    phones_count = 0
    for reservoir_name, plan_data in data.items():
        reservoir_code = reservoir_codes.get(reservoir_name)
        
        for category, items in plan_data.items():
            if "常用电话" in category:
                sort_order = 0
                for item in items:
                    sort_order += 1
                    unit = item.get("单位名称")
                    if not unit:
                        continue
                    
                    phone = escape_sql_string(item.get("电话"))
                    fax = escape_sql_string(item.get("传真"))
                    remark = escape_sql_string(item.get("备注"))
                    
                    sql = f"INSERT INTO flood_contact_phones (reservoir_code, unit_name, phone, fax, remark, sort_order) VALUES ({escape_sql_string(reservoir_code)}, {escape_sql_string(unit)}, {phone}, {fax}, {remark}, {sort_order});"
                    sql_lines.append(sql)
                    phones_count += 1
    
    sql_lines.append("")
    sql_lines.append(f"-- 共 {phones_count} 条常用联系电话数据")
    sql_lines.append("")
    
    # 写入文件
    sql_content = "\n".join(sql_lines)
    sql_path = project_root / "sql" / "05_seed_flood_plan.sql"
    with open(sql_path, "w", encoding="utf-8") as f:
        f.write(sql_content)
    
    print(f"✓ 已生成 {sql_path}")
    print(f"  物资: {materials_count} 条")
    print(f"  联系人: {contacts_count} 条")
    print(f"  转移安置: {evacuation_count} 条")
    print(f"  滞留人员: {staff_count} 条")
    print(f"  淹没损失: {inundation_count} 条")
    print(f"  常用电话: {phones_count} 条")


def generate_dispatch_schemes_sql():
    """生成调度方案 SQL"""
    print("\n生成 06_seed_dispatch_schemes.sql ...")
    
    data = load_json_data("dispatch_scheme_data_base.json")
    if not data:
        return
    
    sql_lines = []
    sql_lines.append("-- 调度方案时间序列数据")
    sql_lines.append("-- 来源: 从 dispatch_scheme_data_base.json 迁移")
    sql_lines.append("")
    
    # 水库编码映射
    station_codes = {
        "三门峡": "BDA00000111",
        "小浪底": "BDA00000121",
        "陆浑": "BDA80200721",
        "故县": "BDA80000661",
        "河口村": "BDA00000761",
        "龙门镇": "40103800",
        "白马寺": "40103000",
        "黑石关": "40104950",
        "花园口": "40105150",
    }
    
    # 1. 调度方案基础信息
    sql_lines.append("-- ============================================")
    sql_lines.append("-- 1. 调度方案基础信息")
    sql_lines.append("-- ============================================")
    sql_lines.append("")
    sql_lines.append("DELETE FROM dispatch_schemes;")
    sql_lines.append("")
    
    scheme_date = None
    if data.get("data") and len(data["data"]) > 2:
        first_data_row = data["data"][2]
        time_str = first_data_row.get("时间", "")
        if time_str:
            try:
                scheme_date = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S").date()
            except:
                scheme_date = None
    
    scheme_name = "调度方案时间序列数据"
    data_source = "dispatch_scheme_data_base.json"
    row_count = data.get("row_count")
    column_count = data.get("column_count")
    
    sql_lines.append(f"INSERT INTO dispatch_schemes (scheme_name, scheme_date, data_source, row_count, column_count) VALUES ({escape_sql_string(scheme_name)}, {escape_sql_string(scheme_date)}, {escape_sql_string(data_source)}, {row_count}, {column_count});")
    sql_lines.append("")
    sql_lines.append("-- ============================================")
    sql_lines.append("-- 2. 调度方案时间序列数据")
    sql_lines.append("-- ============================================")
    sql_lines.append("")
    sql_lines.append("DELETE FROM dispatch_timeseries;")
    sql_lines.append("")
    
    # 跳过前两行（表头和单位行）
    data_rows = data.get("data", [])[2:]
    
    timeseries_count = 0
    batch_size = 100
    batch_data = []
    
    for row in data_rows:
        timestamp_str = row.get("时间", "")
        if not timestamp_str:
            continue
        
        try:
            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        except:
            continue
        
        for col_name, value in row.items():
            if col_name == "时间":
                continue
            if value is None:
                continue
            
            # 解析列名
            station_name = col_name
            if "." in col_name:
                parts = col_name.rsplit(".", 1)
                station_name = parts[0]
            
            station_code = station_codes.get(station_name)
            
            # 确定指标类型和单位
            if col_name.endswith(".1"):
                metric_type = "storage"
                unit = "亿m³"
            elif col_name.endswith(".2"):
                metric_type = "inflow"
                unit = "m³/s"
            elif col_name.endswith(".3"):
                metric_type = "outflow"
                unit = "m³/s"
            else:
                if station_name in ["龙门镇", "白马寺", "黑石关", "花园口"]:
                    metric_type = "flow"
                    unit = "m³/s"
                else:
                    metric_type = "level"
                    unit = "m"
            
            timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            value_str = f"{float(value):.4f}" if value else "NULL"
            
            sql = f"INSERT INTO dispatch_timeseries (scheme_id, timestamp, station_code, station_name, metric_type, metric_value, unit) VALUES (1, {escape_sql_string(timestamp_str)}, {escape_sql_string(station_code)}, {escape_sql_string(station_name)}, {escape_sql_string(metric_type)}, {value_str}, {escape_sql_string(unit)});"
            sql_lines.append(sql)
            timeseries_count += 1
    
    sql_lines.append("")
    sql_lines.append(f"-- 共 {timeseries_count} 条时间序列数据")
    sql_lines.append("")
    
    # 写入文件
    sql_content = "\n".join(sql_lines)
    sql_path = project_root / "sql" / "06_seed_dispatch_schemes.sql"
    with open(sql_path, "w", encoding="utf-8") as f:
        f.write(sql_content)
    
    print(f"✓ 已生成 {sql_path}")
    print(f"  时间序列数据: {timeseries_count} 条")


def main():
    """主函数"""
    print("=" * 60)
    print("SQL 种子数据生成工具")
    print("=" * 60)
    print()
    
    generate_flood_plan_sql()
    generate_dispatch_schemes_sql()
    
    print()
    print("=" * 60)
    print("所有 SQL 文件已生成完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
