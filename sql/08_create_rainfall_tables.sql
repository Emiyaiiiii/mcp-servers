-- ============================================
-- 雨量数据表
-- ============================================

-- 小时雨量数据表
CREATE TABLE IF NOT EXISTS rainfall_hourly (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_code VARCHAR(50) NOT NULL,
    station_name VARCHAR(100) NOT NULL,
    timestamp DATETIME NOT NULL,
    rainfall DECIMAL(10,2) NOT NULL,
    step INTEGER DEFAULT 60,
    river_name VARCHAR(100) DEFAULT '黄河',
    water_system VARCHAR(100) DEFAULT '黄河水系',
    longitude DECIMAL(10,6),
    latitude DECIMAL(10,6),
    reservoir_code VARCHAR(50) DEFAULT 'BDA00000121',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(station_code, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_rainfall_hourly_station ON rainfall_hourly(station_code);
CREATE INDEX IF NOT EXISTS idx_rainfall_hourly_timestamp ON rainfall_hourly(timestamp);
CREATE INDEX IF NOT EXISTS idx_rainfall_hourly_station_timestamp ON rainfall_hourly(station_code, timestamp);
CREATE INDEX IF NOT EXISTS idx_rainfall_hourly_reservoir ON rainfall_hourly(reservoir_code);
