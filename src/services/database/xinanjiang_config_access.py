from typing import Optional, List, Dict, Any
from src.services.database.connection import get_db
from src.utils.logger import get_logger

logger = get_logger(__name__)


class XinanjiangModelConfigAccess:
    """新安江模型参数配置数据库访问"""
    
    @staticmethod
    def get_config_by_station(station_name: str) -> Optional[Dict[str, Any]]:
        """
        根据站点名称获取模型配置
        
        Args:
            station_name: 站点名称，如"陆浑水库"、"花园口"等
            
        Returns:
            配置字典，如果未找到返回None
        """
        try:
            db = get_db()
            result = db.execute_query(
                """
                SELECT * FROM xinanjiang_model_config 
                WHERE station_name = ?
                """,
                (station_name,)
            )
            
            if result and len(result) > 0:
                config = result[0]
                logger.info(f"找到站点配置: {station_name}, 流域面积: {config.get('basin_area')}km²")
                return dict(config)
            else:
                logger.warning(f"未找到站点配置: {station_name}")
                return None
                
        except Exception as e:
            logger.error(f"查询站点配置失败: {e}")
            return None
    
    @staticmethod
    def get_all_configs() -> List[Dict[str, Any]]:
        """
        获取所有站点配置
        
        Returns:
            配置列表
        """
        try:
            db = get_db()
            result = db.execute_query(
                """
                SELECT station_name, station_type, station_code, basin_name, basin_area, description 
                FROM xinanjiang_model_config 
                ORDER BY station_type, station_name
                """
            )
            
            return [dict(row) for row in result] if result else []
            
        except Exception as e:
            logger.error(f"查询所有站点配置失败: {e}")
            return []
    
    @staticmethod
    def update_config(station_name: str, params: Dict[str, Any]) -> bool:
        """
        更新站点配置参数
        
        Args:
            station_name: 站点名称
            params: 要更新的参数字典
            
        Returns:
            是否更新成功
        """
        try:
            # 构建更新SQL
            update_fields = []
            values = []
            
            valid_fields = {
                'basin_name', 'basin_area', 'KC', 'B', 'UM', 'LM', 'EX', 
                'C', 'IM', 'WM', 'SM', 'KG', 'KI', 'CS', 'CG', 'CI', 'CR', 'XE', 'KE'
            }
            
            for key, value in params.items():
                if key in valid_fields:
                    update_fields.append(f"{key} = ?")
                    values.append(value)
            
            if not update_fields:
                logger.warning(f"没有有效的参数需要更新")
                return False
            
            values.append(station_name)
            update_sql = f"""
                UPDATE xinanjiang_model_config 
                SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP
                WHERE station_name = ?
            """
            
            db = get_db()
            db.execute_query(update_sql, tuple(values))
            
            logger.info(f"成功更新站点配置: {station_name}")
            return True
            
        except Exception as e:
            logger.error(f"更新站点配置失败: {e}")
            return False
    
    @staticmethod
    def build_control_params_from_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据数据库配置构建模型控制参数
        
        Args:
            config: 数据库配置字典
            
        Returns:
            模型控制参数字典
        """
        return {
            "ncName": "control",
            "type": "hydraulic_elements",
            "dimensionsList": [],
            "variablesList": [],
            "globalList": [
                {"type": "float", "name": "KC", "fullName": "流域蒸散发折算系数(KC)", "value": str(config.get('KC', 0.9))},
                {"type": "float", "name": "B", "fullName": "流域蓄水容量分布曲线指数(B)", "value": str(config.get('B', 0.4))},
                {"type": "int", "name": "UM", "fullName": "上层张力水容量(UM)", "value": str(config.get('UM', 30))},
                {"type": "int", "name": "LM", "fullName": "下层张力水容量(LM)", "value": str(config.get('LM', 80))},
                {"type": "float", "name": "EX", "fullName": "流域自由水容量分布曲线指数(EX)", "value": str(config.get('EX', 1.5))},
                {"type": "float", "name": "C", "fullName": "深层蒸散发折算系数(C)", "value": str(config.get('C', 0.12))},
                {"type": "float", "name": "IM", "fullName": "不透水面积比例(IM)", "value": str(config.get('IM', 0))},
                {"type": "float", "name": "WM", "fullName": "张力水容量(WM)", "value": str(config.get('WM', 120))},
                {"type": "float", "name": "SM", "fullName": "自由水容量(SM)", "value": str(config.get('SM', 25))},
                {"type": "float", "name": "KG", "fullName": "地下水日出流系数(KG)", "value": str(config.get('KG', 0.3))},
                {"type": "float", "name": "KI", "fullName": "壤中流日出流系数(KI)", "value": str(config.get('KI', 0.3))},
                {"type": "float", "name": "CS", "fullName": "地表水流消退系数(CS)", "value": str(config.get('CS', 0.8))},
                {"type": "float", "name": "CG", "fullName": "地下水日消退系数(CG)", "value": str(config.get('CG', 1))},
                {"type": "float", "name": "CI", "fullName": "壤中流日消退系数(CI)", "value": str(config.get('CI', 1))},
                {"type": "float", "name": "CR", "fullName": "日模型河网蓄水消退系数(CR)", "value": str(config.get('CR', 0.2))},
                {"type": "double", "name": "BA", "fullName": "流域面积(BA)", "value": str(config.get('basin_area', 101.7298))},
                {"type": "float", "name": "XE", "fullName": "马斯京跟法演算参数(XE)", "value": str(config.get('XE', 0.2))},
                {"type": "int", "name": "KE", "fullName": "马斯京跟法演算参数(KE)", "value": str(config.get('KE', 1))}
            ]
        }
