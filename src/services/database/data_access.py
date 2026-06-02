import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from src.services.database.connection import get_db
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ReservoirAccess:
    """水库数据访问"""
    
    @staticmethod
    def get_by_code(code: str) -> Optional[Dict]:
        sql = "SELECT * FROM reservoirs WHERE code = ?"
        return get_db().execute_one(sql, (code,))
    
    @staticmethod
    def get_by_name(name: str) -> Optional[Dict]:
        sql = "SELECT * FROM reservoirs WHERE name = ?"
        return get_db().execute_one(sql, (name,))
    
    @staticmethod
    def get_all() -> List[Dict]:
        sql = "SELECT * FROM reservoirs ORDER BY name"
        return get_db().execute_query(sql)
    
    @staticmethod
    def get_all_name_code() -> Dict[str, str]:
        results = get_db().execute_query("SELECT code, name FROM reservoirs ORDER BY name")
        return {r['name']: r['code'] for r in results if r['name'] and r['code']}
    
    @staticmethod
    def search(keyword: str, limit: int = 20) -> List[Dict]:
        sql = """
            SELECT * FROM reservoirs 
            WHERE name LIKE ? OR name_alias LIKE ? OR code LIKE ?
            ORDER BY name
            LIMIT ?
        """
        like_pattern = f"%{keyword}%"
        return get_db().execute_query(sql, (like_pattern, like_pattern, like_pattern, limit))
    
    @staticmethod
    def get_capacity(reservoir_code: str) -> Optional[Dict]:
        sql = """
            SELECT capacity_total, capacity_flood, level_normal, 
                   level_flood_limit, level_flood_max, level_warning
            FROM reservoirs WHERE code = ?
        """
        return get_db().execute_one(sql, (reservoir_code,))


class WaterLevelAccess:
    """水位配置数据访问"""
    
    @staticmethod
    def _resolve_code(reservoir_code: str) -> str:
        """解析水库编码，支持别名"""
        from .config_loader import resolve_station_code
        return resolve_station_code(reservoir_code)
    
    @staticmethod
    def get_by_level(reservoir_code: str, level: float) -> Optional[Dict]:
        resolved_code = WaterLevelAccess._resolve_code(reservoir_code)
        sql = """
            SELECT * FROM water_levels 
            WHERE reservoir_code = ? 
              AND level_min <= ? 
              AND (level_max > ? OR level_max IS NULL)
            ORDER BY effective_date DESC
            LIMIT 1
        """
        # 尝试用解析后的编码查询，如果失败再尝试原始编码
        result = get_db().execute_one(sql, (resolved_code, level, level))
        if not result and resolved_code != reservoir_code:
            result = get_db().execute_one(sql, (reservoir_code, level, level))
        if result and result.get('hole_details'):
            result['hole_details'] = json.loads(result['hole_details'])
        return result
    
    @staticmethod
    def get_all_levels(reservoir_code: str) -> List[Dict]:
        resolved_code = WaterLevelAccess._resolve_code(reservoir_code)
        sql = """
            SELECT * FROM water_levels 
            WHERE reservoir_code = ?
            ORDER BY level_min
        """
        results = get_db().execute_query(sql, (resolved_code,))
        if not results and resolved_code != reservoir_code:
            results = get_db().execute_query(sql, (reservoir_code,))
        for r in results:
            if r.get('hole_details'):
                r['hole_details'] = json.loads(r['hole_details'])
        return results
    
    @staticmethod
    def get_latest_level_config(reservoir_code: str, level: float) -> Dict[str, Any]:
        config = WaterLevelAccess.get_by_level(reservoir_code, level)
        if not config:
            logger.warning(f"未找到水位配置: {reservoir_code}, {level}")
            return {}
        
        return {
            'level': level,
            'tunnel_flow': config.get('tunnel_flow', 0),
            'bottom_hole_flow': config.get('bottom_hole_flow', 0),
            'deep_hole_flow': config.get('deep_hole_flow', 0),
            'pipe_flow': config.get('pipe_flow', 0),
            'hole_details': config.get('hole_details', [])
        }


class CoefficientAccess:
    """调度系数数据访问"""
    
    @staticmethod
    def get_by_level_range(reservoir_code: str, level: float) -> Optional[Dict]:
        resolved_code = WaterLevelAccess._resolve_code(reservoir_code)
        sql = """
            SELECT * FROM coefficients 
            WHERE reservoir_code = ? 
              AND range_min <= ? 
              AND range_max > ?
            ORDER BY level_range
            LIMIT 1
        """
        result = get_db().execute_one(sql, (resolved_code, level, level))
        if not result and resolved_code != reservoir_code:
            result = get_db().execute_one(sql, (reservoir_code, level, level))
        return result
    
    @staticmethod
    def get_all_coefficients(reservoir_code: str) -> List[Dict]:
        resolved_code = WaterLevelAccess._resolve_code(reservoir_code)
        sql = """
            SELECT * FROM coefficients 
            WHERE reservoir_code = ?
            ORDER BY range_min
        """
        results = get_db().execute_query(sql, (resolved_code,))
        if not results and resolved_code != reservoir_code:
            results = get_db().execute_query(sql, (reservoir_code,))
        return results


class HolePriorityAccess:
    """孔洞优先级数据访问"""
    
    @staticmethod
    def get_by_reservoir(reservoir_code: str) -> List[Dict]:
        resolved_code = WaterLevelAccess._resolve_code(reservoir_code)
        sql = """
            SELECT * FROM hole_priority 
            WHERE reservoir_code = ?
            ORDER BY priority_order
        """
        results = get_db().execute_query(sql, (resolved_code,))
        if not results and resolved_code != reservoir_code:
            results = get_db().execute_query(sql, (reservoir_code,))
        return results
    
    @staticmethod
    def get_priority_order(reservoir_code: str) -> List[int]:
        """
        获取底孔优先级顺序（返回编号列表）
        
        Args:
            reservoir_code: 水库编码（支持名称别名如 "SMX"）
        
        Returns:
            按优先级排序的底孔编号列表，例如 [1, 2, 3, ...]
        """
        resolved_code = WaterLevelAccess._resolve_code(reservoir_code)
        
        sql = """
            SELECT priority_order 
            FROM hole_priority 
            WHERE reservoir_code = ?
            ORDER BY priority_order
        """
        results = get_db().execute_query(sql, (resolved_code,))
        
        # 如果用新编码没找到，尝试用原始编码查找
        if not results and resolved_code != reservoir_code:
            results = get_db().execute_query(sql, (reservoir_code,))
        
        # 如果还是没有数据，返回默认值
        if not results:
            if reservoir_code in ["BDA00000111", "SMX", "三门峡"]:
                return list(range(1, 13))  # 三门峡默认12个底孔
            return list(range(1, 11))  # 默认10个底孔
        
        # 返回按优先级排序的编号列表
        return [result['priority_order'] for result in results]


class HydrologyStationAccess:
    """水文站数据访问"""
    
    @staticmethod
    def get_by_code(code: str) -> Optional[Dict]:
        sql = "SELECT * FROM hydrology_stations WHERE code = ?"
        return get_db().execute_one(sql, (code,))
    
    @staticmethod
    def get_by_name(name: str) -> Optional[Dict]:
        sql = "SELECT * FROM hydrology_stations WHERE name = ?"
        return get_db().execute_one(sql, (name,))
    
    @staticmethod
    def get_all() -> List[Dict]:
        sql = "SELECT * FROM hydrology_stations ORDER BY name"
        return get_db().execute_query(sql)
    
    @staticmethod
    def get_all_name_code() -> Dict[str, str]:
        results = get_db().execute_query(
            "SELECT code, name FROM hydrology_stations ORDER BY name"
        )
        return {r['name']: r['code'] for r in results if r['name'] and r['code']}


class RainfallStationAccess:
    """雨量站数据访问"""
    
    @staticmethod
    def get_by_code(code: str) -> Optional[Dict]:
        sql = "SELECT * FROM rainfall_stations WHERE code = ?"
        return get_db().execute_one(sql, (code,))
    
    @staticmethod
    def get_by_name(name: str) -> Optional[Dict]:
        sql = "SELECT * FROM rainfall_stations WHERE name = ?"
        return get_db().execute_one(sql, (name,))
    
    @staticmethod
    def get_all() -> List[Dict]:
        sql = "SELECT * FROM rainfall_stations ORDER BY name"
        return get_db().execute_query(sql)
    
    @staticmethod
    def get_all_name_code() -> Dict[str, str]:
        results = get_db().execute_query(
            "SELECT code, name FROM rainfall_stations ORDER BY name"
        )
        return {r['name']: r['code'] for r in results if r['name'] and r['code']}


class StationAliasAccess:
    """站点别名数据访问"""
    
    @staticmethod
    def get_all() -> List[Dict]:
        sql = "SELECT * FROM station_aliases"
        return get_db().execute_query(sql)
    
    @staticmethod
    def get_by_type(station_type: str) -> List[Dict]:
        sql = "SELECT * FROM station_aliases WHERE station_type = ?"
        return get_db().execute_query(sql, (station_type,))


class SimulationParamsAccess:
    """仿真参数数据访问"""
    
    @staticmethod
    def get_param(param_key: str) -> Optional[Any]:
        """获取仿真参数"""
        sql = "SELECT * FROM simulation_params WHERE param_key = ?"
        result = get_db().execute_one(sql, (param_key,))
        if result:
            return json.loads(result['param_value'])
        return None
    
    @staticmethod
    def get_all_params() -> List[Dict]:
        """获取所有仿真参数"""
        sql = "SELECT * FROM simulation_params ORDER BY param_key"
        return get_db().execute_query(sql)
    
    @staticmethod
    def get_default_params(reservoir_code: str) -> Dict[str, Any]:
        """获取水库默认参数"""
        prefix = f"{reservoir_code}_"
        sql = "SELECT * FROM simulation_params WHERE param_key LIKE ? ORDER BY param_key"
        results = get_db().execute_query(sql, (f"{prefix}%",))
        params = {}
        for r in results:
            params[r['param_key']] = json.loads(r['param_value'])
        return params


class LevelCapacityCurveAccess:
    """水位库容曲线数据访问"""
    
    @staticmethod
    def get_curve(reservoir_code: str) -> tuple:
        """获取水位-库容曲线"""
        sql = """
            SELECT level, capacity FROM level_capacity_curves 
            WHERE reservoir_code = ?
            ORDER BY level
        """
        results = get_db().execute_query(sql, (reservoir_code,))
        if results:
            levels = [r['level'] for r in results]
            capacities = [r['capacity'] for r in results]
            return (levels, capacities)
        return None, None
    
    @staticmethod
    def get_capacity(reservoir_code: str, level: float) -> Optional[float]:
        """根据水位获取库容"""
        sql = """
            SELECT capacity FROM level_capacity_curves 
            WHERE reservoir_code = ? AND level = ?
        """
        result = get_db().execute_one(sql, (reservoir_code, level))
        return result['capacity'] if result else None


class FloodControlMaterialsAccess:
    """防汛物资数据访问"""
    
    @staticmethod
    def get_by_reservoir(reservoir_code: str, category: Optional[str] = None) -> List[Dict]:
        """获取水库的防汛物资"""
        if category:
            sql = """
                SELECT * FROM flood_control_materials 
                WHERE reservoir_code = ? AND plan_category = ?
                ORDER BY material_name
            """
            return get_db().execute_query(sql, (reservoir_code, category))
        else:
            sql = """
                SELECT * FROM flood_control_materials 
                WHERE reservoir_code = ?
                ORDER BY plan_category, material_name
            """
            return get_db().execute_query(sql, (reservoir_code,))
    
    @staticmethod
    def get_all_categories(reservoir_code: str) -> List[str]:
        """获取水库的物资分类"""
        sql = """
            SELECT DISTINCT plan_category FROM flood_control_materials 
            WHERE reservoir_code = ?
            ORDER BY plan_category
        """
        results = get_db().execute_query(sql, (reservoir_code,))
        return [r['plan_category'] for r in results]


class FloodControlContactsAccess:
    """防汛联系人数据访问"""
    
    @staticmethod
    def get_by_reservoir(reservoir_code: str, category: Optional[str] = None) -> List[Dict]:
        """获取水库的联系人"""
        if category:
            sql = """
                SELECT * FROM flood_control_contacts 
                WHERE reservoir_code = ? AND plan_category = ?
                ORDER BY sort_order
            """
            return get_db().execute_query(sql, (reservoir_code, category))
        else:
            sql = """
                SELECT * FROM flood_control_contacts 
                WHERE reservoir_code = ?
                ORDER BY plan_category, sort_order
            """
            return get_db().execute_query(sql, (reservoir_code,))
    
    @staticmethod
    def get_all_categories(reservoir_code: str) -> List[str]:
        """获取水库的联系人分类"""
        sql = """
            SELECT DISTINCT plan_category FROM flood_control_contacts 
            WHERE reservoir_code = ?
            ORDER BY plan_category
        """
        results = get_db().execute_query(sql, (reservoir_code,))
        return [r['plan_category'] for r in results]


class FloodEvacuationPlansAccess:
    """人员转移安置计划数据访问"""
    
    @staticmethod
    def get_by_reservoir(reservoir_code: str, discharge_range: Optional[str] = None) -> List[Dict]:
        """获取水库的转移安置计划"""
        if discharge_range:
            sql = """
                SELECT * FROM flood_evacuation_plans 
                WHERE reservoir_code = ? AND discharge_range = ?
                ORDER BY region
            """
            return get_db().execute_query(sql, (reservoir_code, discharge_range))
        else:
            sql = """
                SELECT * FROM flood_evacuation_plans 
                WHERE reservoir_code = ?
                ORDER BY discharge_range, region
            """
            return get_db().execute_query(sql, (reservoir_code,))
    
    @staticmethod
    def get_all_discharge_ranges(reservoir_code: str) -> List[str]:
        """获取水库的下泄流量范围"""
        sql = """
            SELECT DISTINCT discharge_range FROM flood_evacuation_plans 
            WHERE reservoir_code = ?
            ORDER BY discharge_range
        """
        results = get_db().execute_query(sql, (reservoir_code,))
        return [r['discharge_range'] for r in results]


class FloodReservoirStaffAccess:
    """库区滞留人员数据访问"""
    
    @staticmethod
    def get_by_reservoir(reservoir_code: str) -> List[Dict]:
        """获取水库的滞留人员"""
        sql = """
            SELECT * FROM flood_reservoir_staff 
            WHERE reservoir_code = ?
            ORDER BY name
        """
        return get_db().execute_query(sql, (reservoir_code,))


class FloodInundationStatsAccess:
    """淹没损失统计数据访问"""
    
    @staticmethod
    def get_by_reservoir(reservoir_code: str, level_range: Optional[str] = None) -> List[Dict]:
        """获取水库的淹没损失统计"""
        if level_range:
            sql = """
                SELECT * FROM flood_inundation_stats 
                WHERE reservoir_code = ? AND level_range = ?
                ORDER BY village
            """
            return get_db().execute_query(sql, (reservoir_code, level_range))
        else:
            sql = """
                SELECT * FROM flood_inundation_stats 
                WHERE reservoir_code = ?
                ORDER BY level_range, village
            """
            return get_db().execute_query(sql, (reservoir_code,))
    
    @staticmethod
    def get_all_level_ranges(reservoir_code: str) -> List[str]:
        """获取水库的水位范围"""
        sql = """
            SELECT DISTINCT level_range FROM flood_inundation_stats 
            WHERE reservoir_code = ?
            ORDER BY level_range
        """
        results = get_db().execute_query(sql, (reservoir_code,))
        return [r['level_range'] for r in results]


class FloodContactPhonesAccess:
    """常用联系电话数据访问"""
    
    @staticmethod
    def get_by_reservoir(reservoir_code: str) -> List[Dict]:
        """获取水库的常用电话"""
        sql = """
            SELECT * FROM flood_contact_phones 
            WHERE reservoir_code = ?
            ORDER BY sort_order
        """
        return get_db().execute_query(sql, (reservoir_code,))


class LevelFlowCurveAccess:
    """水位泄流曲线数据访问"""
    
    @staticmethod
    def get_curve(reservoir_code: str) -> tuple:
        """获取水位-泄流曲线"""
        sql = """
            SELECT level, flow FROM level_flow_curves 
            WHERE reservoir_code = ?
            ORDER BY level
        """
        results = get_db().execute_query(sql, (reservoir_code,))
        if results:
            levels = [r['level'] for r in results]
            flows = [r['flow'] for r in results]
            return (levels, flows)
        return None, None


class SchemeAccess:
    """调度方案数据访问"""
    
    @staticmethod
    def save(scheme: Dict) -> str:
        """保存调度方案"""
        scheme_id = scheme.get('scheme_id')
        
        if not scheme_id:
            sql = """
                SELECT MAX(CAST(SUBSTR(scheme_id, 4) AS INTEGER)) as max_id 
                FROM schemes
            """
            result = get_db().execute_one(sql)
            max_id = result['max_id'] or 0
            scheme_id = f"DS-{max_id + 1:04d}"
            scheme['scheme_id'] = scheme_id
        
        existing = SchemeAccess.get_by_id(scheme_id)

        if existing:
            sql = """
                UPDATE schemes SET
                    scheme_name = ?,
                    description = ?,
                    basin = ?,
                    start_date = ?,
                    end_date = ?,
                    status = ?,
                    constraints = ?,
                    details = ?,
                    constraints_applied = ?,
                    updated_at = CURRENT_TIMESTAMP,
                    version = version + 1
                WHERE scheme_id = ?
            """
            get_db().execute_update(sql, (
                scheme.get('scheme_name'),
                scheme.get('description'),
                scheme.get('basin'),
                scheme.get('start_date'),
                scheme.get('end_date'),
                scheme.get('status', 'draft'),
                json.dumps(scheme.get('constraints', [])),
                json.dumps(scheme.get('details', [])),
                json.dumps(scheme.get('constraints_applied', {})),
                scheme_id,
            ))
        else:
            sql = """
                INSERT INTO schemes (
                    scheme_id, scheme_name, description, basin,
                    start_date, end_date, status,
                    constraints, details, constraints_applied
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            get_db().execute_insert(sql, (
                scheme_id,
                scheme.get('scheme_name'),
                scheme.get('description'),
                scheme.get('basin'),
                scheme.get('start_date'),
                scheme.get('end_date'),
                scheme.get('status', 'draft'),
                json.dumps(scheme.get('constraints', [])),
                json.dumps(scheme.get('details', [])),
                json.dumps(scheme.get('constraints_applied', {})),
            ))
        
        if scheme.get('reservoirs'):
            get_db().execute_update(
                "DELETE FROM scheme_reservoirs WHERE scheme_id = ?",
                (scheme_id,)
            )
            for res_code, res_data in scheme['reservoirs'].items():
                timeseries = res_data.get('timeseries', [])
                if timeseries:
                    levels = [t['water_level'] for t in timeseries if t.get('water_level') is not None]
                    inflows = [t['inflow'] for t in timeseries if t.get('inflow') is not None]
                    outflows = [t['outflow'] for t in timeseries if t.get('outflow') is not None]
                    storages = [t['storage'] for t in timeseries if t.get('storage') is not None]
                    max_level = round(max(levels), 2) if levels else None
                    max_inflow = round(max(inflows)) if inflows else None
                    max_outflow = round(max(outflows)) if outflows else None
                    max_storage = round(max(storages), 2) if storages else None
                    avg_level = round(sum(levels) / len(levels), 2) if levels else None
                    avg_inflow = round(sum(inflows) / len(inflows), 2) if inflows else None
                    avg_outflow = round(sum(outflows) / len(outflows), 2) if outflows else None
                else:
                    max_level = max_inflow = max_outflow = max_storage = None
                    avg_level = avg_inflow = avg_outflow = None
                sql = """
                    INSERT INTO scheme_reservoirs (
                        scheme_id, reservoir_code, timeseries,
                        max_level, max_inflow, max_outflow, max_storage,
                        avg_level, avg_inflow, avg_outflow
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                get_db().execute_insert(sql, (
                    scheme_id,
                    res_code,
                    json.dumps(timeseries),
                    max_level,
                    max_inflow,
                    max_outflow,
                    max_storage,
                    avg_level,
                    avg_inflow,
                    avg_outflow,
                ))

        if scheme.get('hydrological_stations'):
            get_db().execute_update(
                "DELETE FROM scheme_stations WHERE scheme_id = ?",
                (scheme_id,)
            )
            for station_code, station_data in scheme['hydrological_stations'].items():
                timeseries = station_data.get('timeseries', [])
                if timeseries:
                    flows = [t['flow'] for t in timeseries if t.get('flow') is not None]
                    max_flow = round(max(flows)) if flows else None
                    avg_flow = round(sum(flows) / len(flows), 2) if flows else None
                else:
                    max_flow = avg_flow = None
                sql = """
                    INSERT INTO scheme_stations (
                        scheme_id, station_code, timeseries,
                        max_flow, avg_flow
                    ) VALUES (?, ?, ?, ?, ?)
                """
                get_db().execute_insert(sql, (
                    scheme_id,
                    station_code,
                    json.dumps(timeseries),
                    max_flow,
                    avg_flow,
                ))
        
        logger.info(f"调度方案 {scheme_id} 已保存")
        return scheme_id
    
    @staticmethod
    def get_by_id(scheme_id: str) -> Optional[Dict]:
        """根据ID获取调度方案"""
        sql = "SELECT * FROM schemes WHERE scheme_id = ?"
        result = get_db().execute_one(sql, (scheme_id,))
        
        if not result:
            return None
        
        if result.get('constraints'):
            result['constraints'] = json.loads(result['constraints'])
        if result.get('details'):
            result['details'] = json.loads(result['details'])
        if result.get('constraints_applied'):
            result['constraints_applied'] = json.loads(result['constraints_applied'])
        
        reservoirs_sql = """
            SELECT * FROM scheme_reservoirs WHERE scheme_id = ?
        """
        reservoirs = get_db().execute_query(reservoirs_sql, (scheme_id,))
        result['reservoirs'] = {}
        for r in reservoirs:
            res_data = {
                'timeseries': json.loads(r['timeseries']) if r['timeseries'] else []
            }
            if r['max_level'] is not None:
                res_data['max_level'] = r['max_level']
            if r['max_inflow'] is not None:
                res_data['max_inflow'] = r['max_inflow']
            if r['max_outflow'] is not None:
                res_data['max_outflow'] = r['max_outflow']
            if r['max_storage'] is not None:
                res_data['max_storage'] = r['max_storage']
            result['reservoirs'][r['reservoir_code']] = res_data
        
        stations_sql = """
            SELECT * FROM scheme_stations WHERE scheme_id = ?
        """
        stations = get_db().execute_query(stations_sql, (scheme_id,))
        result['hydrological_stations'] = {}
        for s in stations:
            station_data = {
                'timeseries': json.loads(s['timeseries']) if s['timeseries'] else []
            }
            if s['max_flow'] is not None:
                station_data['max_flow'] = s['max_flow']
            if s['max_level'] is not None:
                station_data['max_level'] = s['max_level']
            result['hydrological_stations'][s['station_code']] = station_data
        
        return result
    
    @staticmethod
    def get_all() -> List[Dict]:
        """获取所有调度方案"""
        sql = "SELECT * FROM schemes ORDER BY created_at DESC"
        results = get_db().execute_query(sql)
        for r in results:
            if r.get('constraints'):
                r['constraints'] = json.loads(r['constraints'])
            if r.get('details'):
                r['details'] = json.loads(r['details'])
        return results
    
    @staticmethod
    def delete(scheme_id: str) -> bool:
        """删除调度方案"""
        rows = get_db().execute_update(
            "DELETE FROM schemes WHERE scheme_id = ?",
            (scheme_id,)
        )
        logger.info(f"调度方案 {scheme_id} 已删除")
        return rows > 0
    
    @staticmethod
    def clear_all() -> int:
        """清空所有调度方案"""
        rows = get_db().execute_update("DELETE FROM schemes")
        logger.info(f"已清空所有调度方案")
        return rows


class DispatchTimeseriesAccess:
    """调度方案时间序列数据访问"""

    @staticmethod
    def get_scheme_info(scheme_id: int) -> Optional[Dict]:
        """获取调度方案基础信息"""
        sql = "SELECT * FROM dispatch_schemes WHERE id = ?"
        return get_db().execute_one(sql, (scheme_id,))

    @staticmethod
    def get_all_schemes() -> List[Dict]:
        """获取所有调度方案"""
        sql = "SELECT * FROM dispatch_schemes ORDER BY created_at DESC"
        return get_db().execute_query(sql)

    @staticmethod
    def get_timeseries(scheme_id: int, station_code: Optional[str] = None, metric_type: Optional[str] = None) -> List[Dict]:
        """获取时间序列数据"""
        if station_code and metric_type:
            sql = """
                SELECT * FROM dispatch_timeseries 
                WHERE scheme_id = ? AND station_code = ? AND metric_type = ?
                ORDER BY timestamp
            """
            return get_db().execute_query(sql, (scheme_id, station_code, metric_type))
        elif station_code:
            sql = """
                SELECT * FROM dispatch_timeseries 
                WHERE scheme_id = ? AND station_code = ?
                ORDER BY timestamp
            """
            return get_db().execute_query(sql, (scheme_id, station_code))
        elif metric_type:
            sql = """
                SELECT * FROM dispatch_timeseries 
                WHERE scheme_id = ? AND metric_type = ?
                ORDER BY timestamp, station_code
            """
            return get_db().execute_query(sql, (scheme_id, metric_type))
        else:
            sql = """
                SELECT * FROM dispatch_timeseries 
                WHERE scheme_id = ?
                ORDER BY timestamp, station_code, metric_type
            """
            return get_db().execute_query(sql, (scheme_id,))

    @staticmethod
    def get_latest_value(scheme_id: int, station_code: str, metric_type: str) -> Optional[Dict]:
        """获取最新的时间序列值"""
        sql = """
            SELECT * FROM dispatch_timeseries 
            WHERE scheme_id = ? AND station_code = ? AND metric_type = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """
        return get_db().execute_one(sql, (scheme_id, station_code, metric_type))

    @staticmethod
    def get_stations(scheme_id: int) -> List[Dict]:
        """获取方案中的所有站点"""
        sql = """
            SELECT DISTINCT station_code, station_name 
            FROM dispatch_timeseries 
            WHERE scheme_id = ?
            ORDER BY station_name
        """
        return get_db().execute_query(sql, (scheme_id,))

    @staticmethod
    def get_metrics(scheme_id: int, station_code: str) -> List[str]:
        """获取站点的所有指标类型"""
        sql = """
            SELECT DISTINCT metric_type 
            FROM dispatch_timeseries 
            WHERE scheme_id = ? AND station_code = ?
            ORDER BY metric_type
        """
        results = get_db().execute_query(sql, (scheme_id, station_code))
        return [r['metric_type'] for r in results]

    @staticmethod
    def get_timeseries_by_range(
        scheme_id: int,
        start_time: datetime,
        end_time: datetime,
        station_code: Optional[str] = None
    ) -> List[Dict]:
        """获取时间范围内的数据"""
        if station_code:
            sql = """
                SELECT * FROM dispatch_timeseries 
                WHERE scheme_id = ? AND station_code = ? AND timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp, station_code, metric_type
            """
            return get_db().execute_query(sql, (scheme_id, station_code, start_time, end_time))
        else:
            sql = """
                SELECT * FROM dispatch_timeseries 
                WHERE scheme_id = ? AND timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp, station_code, metric_type
            """
            return get_db().execute_query(sql, (scheme_id, start_time, end_time))

    @staticmethod
    def delete_scheme(scheme_id: int) -> int:
        """删除调度方案（会级联删除时间序列）"""
        rows = get_db().execute_update(
            "DELETE FROM dispatch_schemes WHERE id = ?",
            (scheme_id,)
        )
        logger.info(f"调度方案 {scheme_id} 及其时间序列已删除")
        return rows


class FloodEvacuationPlanAccess:
    """洪水转移计划数据访问"""
    
    @staticmethod
    def get_by_reservoir_code(reservoir_code: str) -> List[Dict]:
        """根据水库编码获取转移计划"""
        sql = """
            SELECT * FROM flood_evacuation_plans 
            WHERE reservoir_code = ?
            ORDER BY region, discharge_range
        """
        return get_db().execute_query(sql, (reservoir_code,))
    
    @staticmethod
    def get_by_region(region: str) -> List[Dict]:
        """根据区域名称获取转移计划（支持模糊匹配）"""
        sql = """
            SELECT * FROM flood_evacuation_plans 
            WHERE region LIKE ?
            ORDER BY reservoir_code, discharge_range
        """
        like_pattern = f"%{region}%"
        return get_db().execute_query(sql, (like_pattern,))
    
    @staticmethod
    def get_all() -> List[Dict]:
        """获取所有转移计划"""
        sql = "SELECT * FROM flood_evacuation_plans ORDER BY reservoir_code, region"
        return get_db().execute_query(sql)
    
    @staticmethod
    def search_by_reservoir_or_region(keyword: str) -> List[Dict]:
        """根据水库编码或区域名称搜索转移计划"""
        # 首先尝试作为水库编码精确匹配
        sql = """
            SELECT * FROM flood_evacuation_plans 
            WHERE reservoir_code = ? OR region LIKE ?
            ORDER BY reservoir_code, region
        """
        like_pattern = f"%{keyword}%"
        results = get_db().execute_query(sql, (keyword, like_pattern))
        
        # 如果没有结果，尝试模糊匹配水库编码
        if not results:
            sql = """
                SELECT * FROM flood_evacuation_plans 
                WHERE reservoir_code LIKE ? OR region LIKE ?
                ORDER BY reservoir_code, region
            """
            code_pattern = f"%{keyword}%"
            results = get_db().execute_query(sql, (code_pattern, like_pattern))
        
        return results


class FloodControlMaterialAccess:
    """防汛物资数据访问"""
    
    @staticmethod
    def get_by_reservoir_code(reservoir_code: str) -> List[Dict]:
        """根据水库编码获取防汛物资"""
        sql = """
            SELECT * FROM flood_control_materials 
            WHERE reservoir_code = ? OR reservoir_code IS NULL
            ORDER BY plan_category, material_name
        """
        return get_db().execute_query(sql, (reservoir_code,))
    
    @staticmethod
    def get_by_category(category: str) -> List[Dict]:
        """根据物资类别获取防汛物资"""
        sql = """
            SELECT * FROM flood_control_materials 
            WHERE plan_category LIKE ?
            ORDER BY material_name
        """
        like_pattern = f"%{category}%"
        return get_db().execute_query(sql, (like_pattern,))
    
    @staticmethod
    def get_all() -> List[Dict]:
        """获取所有防汛物资"""
        sql = "SELECT * FROM flood_control_materials ORDER BY plan_category, material_name"
        return get_db().execute_query(sql)
    
    @staticmethod
    def search(keyword: str) -> List[Dict]:
        """根据物资名称或类别搜索"""
        sql = """
            SELECT * FROM flood_control_materials 
            WHERE material_name LIKE ? OR plan_category LIKE ? OR keeper LIKE ?
            ORDER BY plan_category, material_name
        """
        like_pattern = f"%{keyword}%"
        return get_db().execute_query(sql, (like_pattern, like_pattern, like_pattern))


class FloodReservoirStaffAccess:
    """水库人员数据访问"""
    
    @staticmethod
    def get_by_reservoir_code(reservoir_code: str) -> List[Dict]:
        """根据水库编码获取水库人员"""
        sql = """
            SELECT * FROM flood_reservoir_staff 
            WHERE reservoir_code = ?
            ORDER BY staff_type, name
        """
        return get_db().execute_query(sql, (reservoir_code,))
    
    @staticmethod
    def get_by_staff_type(staff_type: str) -> List[Dict]:
        """根据人员类型获取水库人员"""
        sql = """
            SELECT * FROM flood_reservoir_staff 
            WHERE staff_type = ?
            ORDER BY reservoir_code, name
        """
        return get_db().execute_query(sql, (staff_type,))
    
    @staticmethod
    def get_all() -> List[Dict]:
        """获取所有水库人员"""
        sql = "SELECT * FROM flood_reservoir_staff ORDER BY reservoir_code, staff_type, name"
        return get_db().execute_query(sql)
    
    @staticmethod
    def search(keyword: str) -> List[Dict]:
        """根据姓名、住所或转移地点搜索"""
        sql = """
            SELECT * FROM flood_reservoir_staff 
            WHERE name LIKE ? OR residence LIKE ? OR transfer_location LIKE ? OR transfer_contact LIKE ?
            ORDER BY reservoir_code, name
        """
        like_pattern = f"%{keyword}%"
        return get_db().execute_query(sql, (like_pattern, like_pattern, like_pattern, like_pattern))


class EvacuationQueryAccess:
    """新表结构的撤离信息查询"""

    @staticmethod
    def get_by_reservoir(reservoir_name: str, township: str = None,
                         water_level: float = None, village: str = None) -> List[Dict]:
        """按水库名查询撤离信息，支持乡镇/水位/村庄过滤"""
        conditions = ["r.name = ?"]
        params = [reservoir_name]

        if township:
            conditions.append("t.township_name = ?")
            params.append(township)
        if water_level is not None:
            conditions.append("ABS(w.water_level - ?) < 0.01")
            params.append(water_level)
        if village:
            conditions.append("v.village_name LIKE ?")
            params.append(f"%{village}%")

        sql = f"""
            SELECT r.name AS reservoir_name, r.code AS reservoir_code,
                   w.water_level, w.level_description,
                   t.township_name, v.id AS village_id, v.village_name,
                   e.id AS evacuation_id, e.contact_name, e.contact_title, e.contact_phone,
                   e.evacuation_location, e.evacuation_route, e.evacuation_method,
                   e.discharge_range, e.flow_rate,
                   e.transfer_person, e.transfer_person_phone,
                   e.resettlement_person, e.resettlement_phone,
                   e.region, e.department, e.responsibility, e.remark
            FROM reservoirs r
            JOIN water_level_thresholds w ON r.code = w.reservoir_code
            JOIN townships t ON w.id = t.water_level_id
            JOIN villages v ON t.id = v.township_id
            LEFT JOIN evacuation_details e ON v.id = e.village_id
            WHERE {' AND '.join(conditions)}
            ORDER BY r.name, w.water_level, t.township_name, v.village_name
        """
        return get_db().execute_query(sql, params)

    @staticmethod
    def search_village(keyword: str) -> List[Dict]:
        """按村庄名模糊搜索"""
        sql = """
            SELECT r.name AS reservoir_name, r.code AS reservoir_code,
                   w.water_level, t.township_name, v.id AS village_id, v.village_name,
                   e.id AS evacuation_id, e.contact_name, e.contact_phone,
                   e.evacuation_location, e.evacuation_route
            FROM reservoirs r
            JOIN water_level_thresholds w ON r.code = w.reservoir_code
            JOIN townships t ON w.id = t.water_level_id
            JOIN villages v ON t.id = v.township_id
            LEFT JOIN evacuation_details e ON v.id = e.village_id
            WHERE v.village_name LIKE ?
            ORDER BY r.name, v.village_name
        """
        return get_db().execute_query(sql, (f"%{keyword}%",))

    @staticmethod
    def get_water_levels(reservoir_name: str) -> List[Dict]:
        """获取某水库的所有水位阈值"""
        sql = """
            SELECT DISTINCT w.water_level, w.level_description,
                   COUNT(DISTINCT t.id) AS township_count,
                   COUNT(DISTINCT v.id) AS village_count
            FROM reservoirs r
            JOIN water_level_thresholds w ON r.code = w.reservoir_code
            LEFT JOIN townships t ON w.id = t.water_level_id
            LEFT JOIN villages v ON t.id = v.township_id
            WHERE r.name = ?
            GROUP BY w.water_level
            ORDER BY w.water_level
        """
        return get_db().execute_query(sql, (reservoir_name,))

    @staticmethod
    def get_townships(reservoir_name: str, water_level: float = None) -> List[Dict]:
        """获取某水库-水位下的所有乡镇"""
        conditions = ["r.name = ?"]
        params = [reservoir_name]
        if water_level is not None:
            conditions.append("ABS(w.water_level - ?) < 0.01")
            params.append(water_level)

        sql = f"""
            SELECT DISTINCT t.township_name,
                   COUNT(DISTINCT v.id) AS village_count
            FROM reservoirs r
            JOIN water_level_thresholds w ON r.code = w.reservoir_code
            JOIN townships t ON w.id = t.water_level_id
            LEFT JOIN villages v ON t.id = v.township_id
            WHERE {' AND '.join(conditions)}
            GROUP BY t.township_name
            ORDER BY t.township_name
        """
        return get_db().execute_query(sql, params)


class FloodInundationStatsAccess:
    """淹没损失统计数据访问"""
    
    @staticmethod
    def get_by_reservoir_code(reservoir_code: str) -> List[Dict]:
        """根据水库编码获取淹没损失统计"""
        sql = """
            SELECT * FROM flood_inundation_stats 
            WHERE reservoir_code = ?
            ORDER BY level_range, village
        """
        return get_db().execute_query(sql, (reservoir_code,))
    
    @staticmethod
    def get_by_level_range(level_range: str) -> List[Dict]:
        """根据水位区间获取淹没损失统计"""
        sql = """
            SELECT * FROM flood_inundation_stats 
            WHERE level_range LIKE ?
            ORDER BY reservoir_code, village
        """
        like_pattern = f"%{level_range}%"
        return get_db().execute_query(sql, (like_pattern,))
    
    @staticmethod
    def get_by_village(village: str) -> List[Dict]:
        """根据村庄名称获取淹没损失统计"""
        sql = """
            SELECT * FROM flood_inundation_stats 
            WHERE village LIKE ?
            ORDER BY reservoir_code, level_range
        """
        like_pattern = f"%{village}%"
        return get_db().execute_query(sql, (like_pattern,))
    
    @staticmethod
    def get_all() -> List[Dict]:
        """获取所有淹没损失统计"""
        sql = "SELECT * FROM flood_inundation_stats ORDER BY reservoir_code, level_range, village"
        return get_db().execute_query(sql)
    
    @staticmethod
    def search(keyword: str) -> List[Dict]:
        """根据水库编码、水位区间或村庄名称搜索"""
        sql = """
            SELECT * FROM flood_inundation_stats 
            WHERE reservoir_code = ? OR level_range LIKE ? OR village LIKE ?
            ORDER BY reservoir_code, level_range, village
        """
        like_pattern = f"%{keyword}%"
        results = get_db().execute_query(sql, (keyword, like_pattern, like_pattern))
        
        # 如果没有结果，尝试模糊匹配水库编码
        if not results:
            sql = """
                SELECT * FROM flood_inundation_stats 
                WHERE reservoir_code LIKE ? OR level_range LIKE ? OR village LIKE ?
                ORDER BY reservoir_code, level_range, village
            """
            code_pattern = f"%{keyword}%"
            results = get_db().execute_query(sql, (code_pattern, like_pattern, like_pattern))
        
        return results


class FloodContactPhoneAccess:
    """防汛联系电话数据访问"""
    
    @staticmethod
    def get_by_reservoir_code(reservoir_code: str) -> List[Dict]:
        """根据水库编码获取联系电话"""
        sql = """
            SELECT * FROM flood_contact_phones 
            WHERE reservoir_code = ?
            ORDER BY sort_order, unit_name
        """
        return get_db().execute_query(sql, (reservoir_code,))
    
    @staticmethod
    def get_by_unit_name(unit_name: str) -> List[Dict]:
        """根据单位名称获取联系电话"""
        sql = """
            SELECT * FROM flood_contact_phones 
            WHERE unit_name LIKE ?
            ORDER BY sort_order, reservoir_code
        """
        like_pattern = f"%{unit_name}%"
        return get_db().execute_query(sql, (like_pattern,))
    
    @staticmethod
    def get_all() -> List[Dict]:
        """获取所有联系电话"""
        sql = "SELECT * FROM flood_contact_phones ORDER BY reservoir_code, sort_order, unit_name"
        return get_db().execute_query(sql)
    
    @staticmethod
    def search(keyword: str) -> List[Dict]:
        """根据水库编码或单位名称搜索"""
        sql = """
            SELECT * FROM flood_contact_phones 
            WHERE reservoir_code = ? OR unit_name LIKE ? OR phone LIKE ?
            ORDER BY reservoir_code, sort_order, unit_name
        """
        like_pattern = f"%{keyword}%"
        results = get_db().execute_query(sql, (keyword, like_pattern, like_pattern))
        
        # 如果没有结果，尝试模糊匹配水库编码
        if not results:
            sql = """
                SELECT * FROM flood_contact_phones 
                WHERE reservoir_code LIKE ? OR unit_name LIKE ?
                ORDER BY reservoir_code, sort_order, unit_name
            """
            code_pattern = f"%{keyword}%"
            results = get_db().execute_query(sql, (code_pattern, like_pattern))
        
        return results


class FloodControlContactAccess:
    """防汛联系人数据访问"""
    
    @staticmethod
    def get_by_reservoir_code(reservoir_code: str) -> List[Dict]:
        """根据水库编码获取防汛联系人"""
        sql = """
            SELECT * FROM flood_control_contacts 
            WHERE reservoir_code = ?
            ORDER BY sort_order, name
        """
        return get_db().execute_query(sql, (reservoir_code,))
    
    @staticmethod
    def get_by_category(category: str) -> List[Dict]:
        """根据联系人类别获取防汛联系人"""
        sql = """
            SELECT * FROM flood_control_contacts 
            WHERE plan_category LIKE ?
            ORDER BY sort_order, name
        """
        like_pattern = f"%{category}%"
        return get_db().execute_query(sql, (like_pattern,))
    
    @staticmethod
    def get_all() -> List[Dict]:
        """获取所有防汛联系人"""
        sql = "SELECT * FROM flood_control_contacts ORDER BY plan_category, sort_order, name"
        return get_db().execute_query(sql)
    
    @staticmethod
    def search(keyword: str) -> List[Dict]:
        """根据姓名、职务或单位名称搜索"""
        sql = """
            SELECT * FROM flood_control_contacts 
            WHERE name LIKE ? OR title LIKE ? OR unit LIKE ? OR plan_category LIKE ?
            ORDER BY plan_category, sort_order, name
        """
        like_pattern = f"%{keyword}%"
        return get_db().execute_query(sql, (like_pattern, like_pattern, like_pattern, like_pattern))
