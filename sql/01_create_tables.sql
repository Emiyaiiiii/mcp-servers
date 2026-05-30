-- 黄河防洪调度系统数据库表结构
-- 版本: 1.0.0
-- 创建日期: 2026-05-30

-- ============================================
-- 1. 基础配置表
-- ============================================

-- 水位-流量配置表
CREATE TABLE IF NOT EXISTS water_levels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reservoir_code VARCHAR(50) NOT NULL,
    level_min DECIMAL(10,2) NOT NULL,
    level_max DECIMAL(10,2),
    tunnel_flow DECIMAL(10,2),
    bottom_hole_flow DECIMAL(10,2),
    deep_hole_flow DECIMAL(10,2),
    pipe_flow DECIMAL(10,2),
    hole_details TEXT,
    effective_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(reservoir_code, level_min, effective_date)
);

CREATE INDEX IF NOT EXISTS idx_water_levels_reservoir ON water_levels(reservoir_code);
CREATE INDEX IF NOT EXISTS idx_water_levels_level ON water_levels(level_min, level_max);

-- 调度系数表
CREATE TABLE IF NOT EXISTS coefficients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reservoir_code VARCHAR(50) NOT NULL,
    level_range VARCHAR(50) NOT NULL,
    range_min DECIMAL(10,2) NOT NULL,
    range_max DECIMAL(10,2) NOT NULL,
    coeff_value DECIMAL(10,4) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(reservoir_code, level_range, range_min)
);

CREATE INDEX IF NOT EXISTS idx_coefficients_reservoir ON coefficients(reservoir_code);

-- 孔洞优先级表
CREATE TABLE IF NOT EXISTS hole_priority (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reservoir_code VARCHAR(50) NOT NULL,
    hole_type VARCHAR(50) NOT NULL,
    priority_order INTEGER NOT NULL,
    max_holes INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_hole_priority_reservoir ON hole_priority(reservoir_code);

-- ============================================
-- 2. 基础数据表
-- ============================================

-- 水库信息表
CREATE TABLE IF NOT EXISTS reservoirs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(50) UNIQUE NOT NULL,
    station_code VARCHAR(50),
    name VARCHAR(100) NOT NULL,
    name_alias TEXT,
    river VARCHAR(100),
    location VARCHAR(200),
    capacity_total DECIMAL(15,2),
    capacity_flood DECIMAL(15,2),
    level_normal DECIMAL(10,2),
    level_flood_limit DECIMAL(10,2),
    level_flood_max DECIMAL(10,2),
    level_warning DECIMAL(10,2),
    level_flood_design DECIMAL(10,2),
    level_flood_check DECIMAL(10,2),
    functions TEXT,
    control_area DECIMAL(15,2),
    upstream_station VARCHAR(100),
    downstream_station VARCHAR(100),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_reservoirs_code ON reservoirs(code);
CREATE INDEX IF NOT EXISTS idx_reservoirs_name ON reservoirs(name);

-- 水文站信息表
CREATE TABLE IF NOT EXISTS hydrology_stations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    name_alias TEXT,
    station_type VARCHAR(20),
    river VARCHAR(100),
    section INTEGER,
    latitude DECIMAL(10,6),
    longitude DECIMAL(10,6),
    catchment_area DECIMAL(15,2),
    authority VARCHAR(100),
    established_year VARCHAR(10),
    location VARCHAR(200),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_hydrology_stations_code ON hydrology_stations(code);
CREATE INDEX IF NOT EXISTS idx_hydrology_stations_name ON hydrology_stations(name);
CREATE INDEX IF NOT EXISTS idx_hydrology_stations_type ON hydrology_stations(station_type);

-- 雨量站信息表
CREATE TABLE IF NOT EXISTS rainfall_stations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    name_alias TEXT,
    river VARCHAR(100),
    latitude DECIMAL(10,6),
    longitude DECIMAL(10,6),
    authority VARCHAR(100),
    established_year VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rainfall_stations_code ON rainfall_stations(code);

-- 站点别名表（支持模糊匹配）
CREATE TABLE IF NOT EXISTS station_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_code VARCHAR(50) NOT NULL,
    station_type VARCHAR(20) NOT NULL,
    alias VARCHAR(100) NOT NULL,
    alias_type VARCHAR(20) DEFAULT 'common',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_aliases_alias ON station_aliases(alias);
CREATE INDEX IF NOT EXISTS idx_aliases_station ON station_aliases(station_code);

-- ============================================
-- 3. 仿真参数表
-- ============================================

-- 仿真默认参数表
CREATE TABLE IF NOT EXISTS simulation_params (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    param_key VARCHAR(100) UNIQUE NOT NULL,
    param_name VARCHAR(200) NOT NULL,
    param_type VARCHAR(50) NOT NULL,
    param_value TEXT NOT NULL,
    unit VARCHAR(50),
    default_value TEXT,
    min_value TEXT,
    max_value TEXT,
    description TEXT,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_simulation_params_key ON simulation_params(param_key);

-- 水位-库容曲线表
CREATE TABLE IF NOT EXISTS level_capacity_curves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reservoir_code VARCHAR(50) NOT NULL,
    level DECIMAL(10,2) NOT NULL,
    capacity DECIMAL(15,2) NOT NULL,
    area DECIMAL(15,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(reservoir_code, level)
);

CREATE INDEX IF NOT EXISTS idx_level_capacity_reservoir ON level_capacity_curves(reservoir_code);

-- 水位-泄流曲线表
CREATE TABLE IF NOT EXISTS level_flow_curves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reservoir_code VARCHAR(50) NOT NULL,
    level DECIMAL(10,2) NOT NULL,
    flow DECIMAL(15,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(reservoir_code, level)
);

CREATE INDEX IF NOT EXISTS idx_level_flow_reservoir ON level_flow_curves(reservoir_code);

-- ============================================
-- 4. 调度方案表
-- ============================================

-- 调度方案主表
CREATE TABLE IF NOT EXISTS schemes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scheme_id VARCHAR(50) UNIQUE NOT NULL,
    scheme_name VARCHAR(200),
    description TEXT,
    basin VARCHAR(100),
    start_date DATE,
    end_date DATE,
    status VARCHAR(20) DEFAULT 'draft',
    constraints TEXT,
    details TEXT,
    constraints_applied TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    version INTEGER DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_schemes_id ON schemes(scheme_id);
CREATE INDEX IF NOT EXISTS idx_schemes_status ON schemes(status);
CREATE INDEX IF NOT EXISTS idx_schemes_created ON schemes(created_at);

-- 方案-水库关联表
CREATE TABLE IF NOT EXISTS scheme_reservoirs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scheme_id VARCHAR(50) NOT NULL,
    reservoir_code VARCHAR(50) NOT NULL,
    timeseries TEXT,
    max_level DECIMAL(10,2),
    max_inflow DECIMAL(15,2),
    max_outflow DECIMAL(15,2),
    max_storage DECIMAL(15,2),
    avg_level DECIMAL(10,2),
    avg_inflow DECIMAL(15,2),
    avg_outflow DECIMAL(15,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (scheme_id) REFERENCES schemes(scheme_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_scheme_reservoirs ON scheme_reservoirs(scheme_id);
CREATE INDEX IF NOT EXISTS idx_scheme_reservoirs_code ON scheme_reservoirs(reservoir_code);

-- 方案-水文站关联表
CREATE TABLE IF NOT EXISTS scheme_stations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scheme_id VARCHAR(50) NOT NULL,
    station_code VARCHAR(50) NOT NULL,
    timeseries TEXT,
    max_flow DECIMAL(15,2),
    max_level DECIMAL(10,2),
    avg_flow DECIMAL(15,2),
    avg_level DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (scheme_id) REFERENCES schemes(scheme_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_scheme_stations ON scheme_stations(scheme_id);
CREATE INDEX IF NOT EXISTS idx_scheme_stations_code ON scheme_stations(station_code);

-- ============================================
-- 5. 预案模板表
-- ============================================

-- 预案模板表
CREATE TABLE IF NOT EXISTS plan_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_name VARCHAR(200) NOT NULL,
    template_file VARCHAR(200) NOT NULL,
    template_type VARCHAR(50),
    description TEXT,
    content TEXT,
    variables TEXT,
    version INTEGER DEFAULT 1,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_plan_templates_name ON plan_templates(template_name);

-- ============================================
-- 6. 历史记录表
-- ============================================

-- 方案版本历史表
CREATE TABLE IF NOT EXISTS scheme_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scheme_id VARCHAR(50) NOT NULL,
    version INTEGER NOT NULL,
    scheme_data TEXT NOT NULL,
    change_description TEXT,
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (scheme_id) REFERENCES schemes(scheme_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_scheme_versions ON scheme_versions(scheme_id, version);

-- 操作审计日志表
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_type VARCHAR(50) NOT NULL,
    table_name VARCHAR(100),
    record_id VARCHAR(50),
    old_value TEXT,
    new_value TEXT,
    operator VARCHAR(100),
    ip_address VARCHAR(50),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_log_type ON audit_log(operation_type);
CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at);

-- ============================================
-- 触发器：自动更新 updated_at
-- ============================================

CREATE TRIGGER IF NOT EXISTS update_schemes_timestamp 
AFTER UPDATE ON schemes
BEGIN
    UPDATE schemes SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_reservoirs_timestamp 
AFTER UPDATE ON reservoirs
BEGIN
    UPDATE reservoirs SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_hydrology_stations_timestamp 
AFTER UPDATE ON hydrology_stations
BEGIN
    UPDATE hydrology_stations SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- ============================================
-- 7. 防汛物资与计划管理表
-- ============================================

-- 防汛物资表
CREATE TABLE IF NOT EXISTS flood_control_materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reservoir_code VARCHAR(50),
    plan_category VARCHAR(100),
    material_name VARCHAR(200) NOT NULL,
    unit VARCHAR(50),
    quantity DECIMAL(15,2),
    keeper VARCHAR(100),
    keeper_phone VARCHAR(50),
    remark TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_flood_materials_reservoir ON flood_control_materials(reservoir_code);
CREATE INDEX IF NOT EXISTS idx_flood_materials_category ON flood_control_materials(plan_category);

-- 防汛联系人表
CREATE TABLE IF NOT EXISTS flood_control_contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reservoir_code VARCHAR(50),
    plan_category VARCHAR(100),
    name VARCHAR(100) NOT NULL,
    title VARCHAR(200),
    unit VARCHAR(200),
    phone VARCHAR(50),
    remark TEXT,
    sort_order INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_flood_contacts_reservoir ON flood_control_contacts(reservoir_code);
CREATE INDEX IF NOT EXISTS idx_flood_contacts_category ON flood_control_contacts(plan_category);

-- 人员转移安置表
CREATE TABLE IF NOT EXISTS flood_evacuation_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reservoir_code VARCHAR(50),
    discharge_range VARCHAR(100) NOT NULL,
    region VARCHAR(100) NOT NULL,
    evacuate_count INTEGER,
    transfer_person VARCHAR(100),
    transfer_phone VARCHAR(50),
    resettle_person VARCHAR(100),
    resettle_phone VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_flood_evacuation_reservoir ON flood_evacuation_plans(reservoir_code);
CREATE INDEX IF NOT EXISTS idx_flood_evacuation_range ON flood_evacuation_plans(discharge_range);

-- 库区滞留人员表
CREATE TABLE IF NOT EXISTS flood_reservoir_staff (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reservoir_code VARCHAR(50),
    name VARCHAR(100) NOT NULL,
    phone VARCHAR(50),
    stay_count INTEGER,
    staff_type VARCHAR(50),
    sheep_count INTEGER,
    residence VARCHAR(200),
    transfer_location VARCHAR(200),
    transfer_contact VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_flood_reservoir_staff ON flood_reservoir_staff(reservoir_code);

-- 淹没损失统计表
CREATE TABLE IF NOT EXISTS flood_inundation_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reservoir_code VARCHAR(50),
    level_range VARCHAR(100) NOT NULL,
    township_leader VARCHAR(100),
    village VARCHAR(100),
    contact_name VARCHAR(100),
    contact_title VARCHAR(100),
    contact_phone VARCHAR(50),
    evacuation_location VARCHAR(200),
    evacuation_route VARCHAR(200),
    household_count INTEGER,
    permanent_residents INTEGER,
    temporary_staff INTEGER,
    house_count INTEGER,
    cave_count INTEGER,
    farmland_area DECIMAL(15,2),
    forest_area DECIMAL(15,2),
    orchard_area DECIMAL(15,2),
    well_count INTEGER,
    pump_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_flood_inundation_reservoir ON flood_inundation_stats(reservoir_code);
CREATE INDEX IF NOT EXISTS idx_flood_inundation_level ON flood_inundation_stats(level_range);

-- 常用联系电话表
CREATE TABLE IF NOT EXISTS flood_contact_phones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reservoir_code VARCHAR(50),
    unit_name VARCHAR(200) NOT NULL,
    phone VARCHAR(200),
    fax VARCHAR(200),
    remark TEXT,
    sort_order INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_flood_contact_phones_reservoir ON flood_contact_phones(reservoir_code);

-- ============================================
-- 8. 调度方案时间序列数据表
-- ============================================

-- 调度方案基础信息表
CREATE TABLE IF NOT EXISTS dispatch_schemes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scheme_name VARCHAR(200),
    scheme_date DATE,
    data_source VARCHAR(200),
    row_count INTEGER,
    column_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dispatch_schemes_date ON dispatch_schemes(scheme_date);

-- 调度方案时间序列表
CREATE TABLE IF NOT EXISTS dispatch_timeseries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scheme_id INTEGER NOT NULL,
    timestamp DATETIME NOT NULL,
    station_code VARCHAR(50) NOT NULL,
    station_name VARCHAR(100) NOT NULL,
    metric_type VARCHAR(50) NOT NULL,
    metric_value DECIMAL(15,4),
    unit VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (scheme_id) REFERENCES dispatch_schemes(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_dispatch_timeseries_scheme ON dispatch_timeseries(scheme_id);
CREATE INDEX IF NOT EXISTS idx_dispatch_timeseries_station ON dispatch_timeseries(station_code);
CREATE INDEX IF NOT EXISTS idx_dispatch_timeseries_timestamp ON dispatch_timeseries(timestamp);
CREATE INDEX IF NOT EXISTS idx_dispatch_timeseries_metric ON dispatch_timeseries(metric_type);
