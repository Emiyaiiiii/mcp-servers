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
('陆浑水库', 'reservoir', 'BDA80200721', '伊洛河', 3492.0, 1.03, 0.32, 20, 80, 1.3, 0.13, 0.02, 115, 20, 0.22, 0.27, 0.80, 0.982, 0.94, 0.16, 0.27, 2, '陆浑水库-伊洛河流域'),
('故县水库', 'reservoir', 'BDA80000661', '洛河', 5370.0, 1.00, 0.30, 20, 80, 1.2, 0.12, 0.01, 120, 22, 0.25, 0.30, 0.82, 0.985, 0.95, 0.17, 0.28, 2, '故县水库-洛河流域'),
('三门峡水库', 'reservoir', 'BDA00000111', '黄河干流', 5781.0, 1.02, 0.33, 25, 75, 1.4, 0.14, 0.03, 105, 16, 0.18, 0.23, 0.76, 0.978, 0.925, 0.14, 0.23, 1, '三门峡水库-黄河干流'),
('小浪底水库', 'reservoir', 'BDA00000121', '黄河干流', 41615.0, 1.05, 0.35, 25, 75, 1.4, 0.15, 0.03, 110, 18, 0.20, 0.25, 0.78, 0.98, 0.93, 0.15, 0.25, 2, '小浪底水库-黄河干流'),
('河口村水库', 'reservoir', 'BDA00000761', '黄河最下游', 9223.0, 1.04, 0.34, 25, 75, 1.4, 0.14, 0.03, 100, 15, 0.17, 0.22, 0.75, 0.975, 0.92, 0.13, 0.22, 2, '河口村水库-黄河最下游'),
('龙门镇', 'hydrology', '40103800', '伊洛河', 450.0, 0.86, 0.36, 26, 76, 1.35, 0.14, 0.02, 112, 23, 0.33, 0.29, 0.76, 0.97, 0.97, 0.19, 0.22, 1, '龙门镇水文站-伊洛河流域'),
('白马寺', 'hydrology', '40103000', '伊洛河', 380.0, 0.84, 0.34, 24, 74, 1.28, 0.15, 0.02, 108, 21, 0.36, 0.27, 0.74, 0.96, 0.96, 0.17, 0.23, 1, '白马寺水文站-伊洛河流域'),
('黑石关', 'hydrology', '40104950', '伊洛河', 510.0, 0.87, 0.37, 27, 77, 1.42, 0.13, 0.01, 114, 24, 0.31, 0.30, 0.77, 0.98, 0.98, 0.19, 0.21, 1, '黑石关水文站-伊洛河流域'),
('花园口', 'hydrology', '40105150', '黄河干流', 730.0, 0.91, 0.41, 31, 81, 1.48, 0.12, 0.0, 119, 25, 0.30, 0.30, 0.79, 1.0, 1.0, 0.20, 0.20, 1, '花园口水文站-黄河干流');
