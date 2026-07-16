-- ============================================================
-- 编码映射表
-- 统一管理水库/水文站在不同子系统中的编码映射关系
-- 
-- 问题背景：当前系统中，不同模块使用不同的编码体系：
--   - reservoirs.code: 水文局编码（如 BDA00000121）
--   - water_levels.reservoir_code: 缩写（如 XLD, SMX）
--   - simulation_params.param_name: 缩写前缀（如 XLD_QY_BC）
--   - RegualDispacth: 调度程序内部编码（如 stcd=31 对应小浪底）
--   - forecast_models.py: 外部 API 编码（如 XLD）
-- ============================================================

-- 水库编码映射表
CREATE TABLE IF NOT EXISTS encoding_mapping_reservoirs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- 标准名称
    standard_name TEXT NOT NULL UNIQUE,
    -- 水文局编码（reservoirs.code 使用）
    hydrology_code TEXT,
    -- 缩写编码（water_levels.reservoir_code 使用）
    abbreviation TEXT,
    -- 调度参数 stcd 编码（Dispatch_Par 表使用）
    dispatch_stcd TEXT,
    -- 仿真参数前缀（simulation_params 使用）
    simulation_prefix TEXT,
    -- 预报 API 编码（forecast_models 使用）
    forecast_api_code TEXT,
    -- 创建时间
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- 更新时间
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 水文站编码映射表
CREATE TABLE IF NOT EXISTS encoding_mapping_stations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    standard_name TEXT NOT NULL UNIQUE,
    -- 水文局编码
    hydrology_code TEXT,
    -- 缩写编码
    abbreviation TEXT,
    -- 预报 API 编码
    forecast_api_code TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 初始数据：水库编码映射
INSERT OR IGNORE INTO encoding_mapping_reservoirs (standard_name, hydrology_code, abbreviation, dispatch_stcd, simulation_prefix, forecast_api_code) VALUES
    ('小浪底', 'BDA00000121', 'XLD', '31', 'XLD', 'XLD'),
    ('三门峡', 'BDA00000112', 'SMX', '33', 'SMX', 'SMX'),
    ('故县', 'BDA10500010', 'GX', '34', 'GX', 'GX'),
    ('陆浑', 'BDA00000100', 'LH', '35', 'LH', 'LH'),
    ('河口村', 'BDA00000109', 'HKC', '36', 'HKC', 'HKC'),
    ('花园口', 'BDA00000135', 'HYK', '38', 'HYK', 'HYK'),
    ('夹河滩', 'BDA00000136', 'JHT', '39', 'JHT', 'JHT');

-- 初始数据：水文站编码映射
INSERT OR IGNORE INTO encoding_mapping_stations (standard_name, hydrology_code, abbreviation, forecast_api_code) VALUES
    ('花园口', 'BDA00000135', 'HYK', '花园口'),
    ('夹河滩', 'BDA00000136', 'JHT', '夹河滩'),
    ('高村', 'BDA00000137', 'GC', '高村'),
    ('孙口', 'BDA00000138', 'SK', '孙口'),
    ('艾山', 'BDA00000139', 'AS', '艾山'),
    ('泺口', 'BDA00000140', 'LK', '泺口'),
    ('利津', 'BDA00000141', 'LJ', '利津'),
    ('小浪底', 'BDA00000121', 'XLD', '小浪底'),
    ('三门峡', 'BDA00000112', 'SMX', '三门峡'),
    ('潼关', 'BDA00000125', 'TG', '潼关'),
    ('龙门', 'BDA00000114', 'LM', '龙门'),
    ('华县', 'BDA00000118', 'HX', '华县'),
    ('武陟', 'BDA00000133', 'WZ', '武陟');

-- 创建触发器：自动更新 updated_at
CREATE TRIGGER IF NOT EXISTS trg_encoding_mapping_reservoirs_update
    AFTER UPDATE ON encoding_mapping_reservoirs
    FOR EACH ROW
BEGIN
    UPDATE encoding_mapping_reservoirs SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_encoding_mapping_stations_update
    AFTER UPDATE ON encoding_mapping_stations
    FOR EACH ROW
BEGIN
    UPDATE encoding_mapping_stations SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;