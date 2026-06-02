-- 新安江模型参数配置表
CREATE TABLE IF NOT EXISTS xinanjiang_model_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_name TEXT NOT NULL UNIQUE,           -- 站点名称
    station_type TEXT NOT NULL,                   -- 站点类型：reservoir（水库）, hydrology（水文站）
    station_code TEXT,                            -- 站点编码
    basin_name TEXT DEFAULT '伊洛河',              -- 流域名称
    basin_area REAL DEFAULT 101.7298,              -- 流域面积（km²）
    KC REAL DEFAULT 0.9,                          -- 流域蒸散发折算系数
    B REAL DEFAULT 0.4,                           -- 流域蓄水容量分布曲线指数
    UM REAL DEFAULT 30,                           -- 上层张力水容量（mm）
    LM REAL DEFAULT 80,                           -- 下层张力水容量（mm）
    EX REAL DEFAULT 1.5,                          -- 流域自由水容量分布曲线指数
    C REAL DEFAULT 0.12,                          -- 深层蒸散发折算系数
    IM REAL DEFAULT 0,                            -- 不透水面积比例
    WM REAL DEFAULT 120,                          -- 张力水容量（mm）
    SM REAL DEFAULT 25,                           -- 自由水容量（mm）
    KG REAL DEFAULT 0.3,                          -- 地下水日出流系数
    KI REAL DEFAULT 0.3,                          -- 壤中流日出流系数
    CS REAL DEFAULT 0.8,                          -- 地表水流消退系数
    CG REAL DEFAULT 1,                            -- 地下水日消退系数
    CI REAL DEFAULT 1,                            -- 壤中流日消退系数
    CR REAL DEFAULT 0.2,                          -- 日模型河网蓄水消退系数
    XE REAL DEFAULT 0.2,                          -- 马斯京跟法演算参数
    KE INTEGER DEFAULT 1,                          -- 马斯京跟法演算参数
    description TEXT,                              -- 备注说明
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_xinanjiang_station ON xinanjiang_model_config(station_name, station_type);

-- 初始化五库参数配置
INSERT OR REPLACE INTO xinanjiang_model_config 
(station_name, station_type, station_code, basin_name, basin_area, KC, B, UM, LM, EX, C, IM, WM, SM, KG, KI, CS, CG, CI, CR, XE, KE, description) VALUES
('陆浑水库', 'reservoir', 'BDA80200721', '伊洛河', 349.0, 0.85, 0.35, 25, 75, 1.3, 0.15, 0.02, 110, 22, 0.35, 0.28, 0.75, 0.98, 0.98, 0.18, 0.22, 1, '陆浑水库-伊洛河流域'),
('故县水库', 'reservoir', 'BDA80000661', '洛河', 537.0, 0.88, 0.38, 28, 78, 1.4, 0.14, 0.01, 115, 24, 0.32, 0.30, 0.78, 0.99, 0.99, 0.20, 0.21, 1, '故县水库-洛河流域'),
('三门峡水库', 'reservoir', 'BDA00000111', '黄河干流', 688.0, 0.90, 0.42, 32, 82, 1.5, 0.12, 0.0, 120, 25, 0.30, 0.30, 0.80, 1.0, 1.0, 0.20, 0.20, 1, '三门峡水库-黄河干流'),
('小浪底水库', 'reservoir', 'BDA00000121', '黄河干流', 722.0, 0.92, 0.40, 30, 80, 1.5, 0.13, 0.0, 118, 25, 0.30, 0.30, 0.80, 1.0, 1.0, 0.20, 0.20, 1, '小浪底水库-黄河干流'),
('河口村水库', 'reservoir', 'BDA00000761', '黄河最下游', 285.0, 0.82, 0.32, 22, 70, 1.2, 0.16, 0.03, 105, 20, 0.38, 0.26, 0.72, 0.95, 0.95, 0.16, 0.24, 1, '河口村水库-黄河最下游'),
('龙门镇', 'hydrology', '40103800', '伊洛河', 450.0, 0.86, 0.36, 26, 76, 1.35, 0.14, 0.02, 112, 23, 0.33, 0.29, 0.76, 0.97, 0.97, 0.19, 0.22, 1, '龙门镇水文站-伊洛河流域'),
('白马寺', 'hydrology', '40103000', '伊洛河', 380.0, 0.84, 0.34, 24, 74, 1.28, 0.15, 0.02, 108, 21, 0.36, 0.27, 0.74, 0.96, 0.96, 0.17, 0.23, 1, '白马寺水文站-伊洛河流域'),
('黑石关', 'hydrology', '40104950', '伊洛河', 510.0, 0.87, 0.37, 27, 77, 1.42, 0.13, 0.01, 114, 24, 0.31, 0.30, 0.77, 0.98, 0.98, 0.19, 0.21, 1, '黑石关水文站-伊洛河流域'),
('花园口', 'hydrology', '40105150', '黄河干流', 730.0, 0.91, 0.41, 31, 81, 1.48, 0.12, 0.0, 119, 25, 0.30, 0.30, 0.79, 1.0, 1.0, 0.20, 0.20, 1, '花园口水文站-黄河干流');
