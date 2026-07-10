"""
水文局预报数据 API 服务

封装水文局预报系统的两个 API 接口：
1. GET /pre/getSwPreWaterDataList - 获取预报方案列表
2. GET /pre/getSwPreWaterDataByPlcd - 获取方案详细数据

并将数据写入 Access 数据库的 Q_Inputsd（上游）和 Q_Inputxd（下游）表。
"""

import os
import json
from typing import Dict, Any, List, Optional, Tuple
import requests
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ============================================================
# API 字段名 → 旧数据 stcd（从 Q_Inputsd.xlsx / Q_Inputxd.xlsx 提取）
# RegualDispacth.exe 需要这些特定的 stcd 编码
# ============================================================
API_FIELD_TO_STCD = {
    "sanmenxiaRuku": "40104430",    # 三门峡入库
    "sanmenxiaChuku": "40104430",   # 三门峡出库（同三门峡入库 stcd）
    "xiaolangdiRuku": "40104430",   # 小浪底入库（复用三门峡 stcd，小浪底数据来自三门峡出库+区间）
    "xiaolangdiChuku": "40104430",  # 小浪退出库
    "luhunRuku": "41602500",        # 陆浑入库
    "luhunChuku": "41602500",       # 陆浑出库
    "guxianRuku": "41605400",       # 故县入库
    "guxianChuku": "41605400",      # 故县出库
    "hekoucunRuku": "41702500",     # 河口村入库
    "hekoucunChuku": "41702500",    # 河口村出库
    "heishiguanLiuliang": "41600400",  # 黑石关
    "wuzhiLiuliang": "41702400",    # 武陟
    "sanxiaojianLiuliang": "QB40104700",  # 三小间
    "shanlupingLiuliang": "41704600",  # 山路平
    "longmenzhenLiuliang": "40104430",  # 龙门镇（复用三门峡 stcd，作为上游区间）
    "baimasiLiuliang": "41600400",   # 白马寺（复用黑石关 stcd）
    "tongguanLiuliang": "40104430",  # 潼关（复用三门峡 stcd）
    "tongsanjianLiuliang": "QB40104700",  # 潼三间（复用三小间 stcd）
    "huayuankouLiuliang": "41702400",  # 花园口（复用武陟 stcd）
    "xiaohuaganLiuliang": "41702400",  # 小花干
    "xiaohuajianLiuliang": "41702400",  # 小花间
    "jiahetanLiuliang": "41702400",   # 夹河滩
    "gaocunLiuliang": "41702400",     # 高村
    "sunkouLiuliang": "41702400",     # 孙口
    "aishanLiuliang": "41702400",     # 艾山
    "luokouLiuliang": "41702400",     # 泺口
    "lijinLiuliang": "41702400",      # 利津
    "dongpinghuFenhongLiuliang": "41702400",  # 东平湖分洪
    "xixiayuanRuku": "40104430",      # 西霞院入库
    "xixiayuanChuku": "40104430",     # 西霞院出库
}

# ============================================================
# 上游字段列表（写入 Q_Inputsd）
# ============================================================
UPSTREAM_FIELDS = {
    "sanmenxiaRuku", "xiaolangdiRuku", "luhunRuku", "guxianRuku",
    "hekoucunRuku", "xixiayuanRuku",
    "longmenzhenLiuliang", "baimasiLiuliang", "heishiguanLiuliang",
    "shanlupingLiuliang", "tongguanLiuliang", "tongsanjianLiuliang",
    "sanxiaojianLiuliang",
}

# ============================================================
# 下游字段列表（写入 Q_Inputxd）
# ============================================================
DOWNSTREAM_FIELDS = {
    "sanmenxiaChuku", "xiaolangdiChuku", "luhunChuku", "guxianChuku",
    "hekoucunChuku", "xixiayuanChuku",
    "huayuankouLiuliang", "jiahetanLiuliang", "gaocunLiuliang",
    "sunkouLiuliang", "aishanLiuliang", "luokouLiuliang",
    "lijinLiuliang", "wuzhiLiuliang", "xiaohuaganLiuliang",
    "xiaohuajianLiuliang", "dongpinghuFenhongLiuliang",
}


class HydrologyForecastService:
    """水文局预报数据 API 服务"""

    def __init__(self):
        self._base_url = os.getenv(
            'HYDROLOGY_API_BASE_URL',
            'http://10.4.158.35:8091'
        )
        self._client_id = os.getenv(
            'HYDROLOGY_API_CLIENT_ID',
            'e5cd7e4891bf95d1d19206ce24a7b32e'
        )
        # Token 优先从环境变量读取，其次使用默认值
        default_token = (
            'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.'
            'eyJsb2dpblR5cGUiOiJsb2dpbiIsImxvZ2luSWQiOiJzeXNfdXNlcjo0Iiwicm5TdHIiOiJvcDlXZjg5bFMycG95bU1N'
            'RkFZRnhUYnV6TDBkY2ZsSSIsImNsaWVudGlkIjoiZTVjZDdlNDg5MWJmOTVkMWQxOTIwNmNlMjRhN2IzMmUiLCJ0'
            'ZW5hbnRJZCI6IjAwMDAwMCIsInVzZXJJZCI6NCwidXNlck5hbWUiOiJ0ZXN0MSIsImRlcHRJZCI6MTAyLCJkZXB0'
            'TmFtZSI6IuS6keays-enkeaKgCIsImRlcHRDYXRlZ29yeSI6IiJ9.'
            'y2h-lz3qRpdnna2Z1pXwZTWW8QQvy0hXMx20kOV10j8'
        )
        self._token = os.getenv('HYDROLOGY_API_TOKEN', default_token)

    def _get_headers(self) -> Dict[str, str]:
        return {
            'ClientId': self._client_id,
            'Authorization': f'Bearer {self._token}'
        }

    def get_forecast_plans(self, date_time: str) -> Dict[str, Any]:
        """
        获取水文局预报方案列表

        API: GET /pre/getSwPreWaterDataList?dateTime=YYYY-MM-DD

        Args:
            date_time: 日期，格式 YYYY-MM-DD

        Returns:
            {
                "success": true,
                "date_time": "2025-06-16",
                "plan_count": 3,
                "plan_list": [
                    {"plcd": "...", "time": "...", "min_time": "...", "max_time": "..."},
                    ...
                ],
                "station_count": 5,
                "message": "共 3 个预报方案，请选择"
            }
        """
        logger.info(f"获取水文局预报方案列表, dateTime={date_time}")
        try:
            url = f"{self._base_url}/pre/getSwPreWaterDataList"
            params = {'dateTime': date_time}
            resp = requests.get(url, headers=self._get_headers(), params=params, timeout=30)

            if resp.status_code != 200:
                return {
                    "success": False,
                    "command": "FUNC_GET_HYDROLOGY_FORECAST_PLANS",
                    "error": f"API 返回 HTTP {resp.status_code}: {resp.text[:200]}"
                }

            result = resp.json()

            # API 返回格式: {"code": 200, "msg": "操作成功", "data": {"stationSch": {...}, "schList": [...]}}
            if result.get('code') != 200:
                return {
                    "success": False,
                    "command": "FUNC_GET_HYDROLOGY_FORECAST_PLANS",
                    "error": f"API 业务错误: {result.get('msg', '')}"
                }

            data = result.get('data', {})
            if not isinstance(data, dict):
                return {
                    "success": False,
                    "command": "FUNC_GET_HYDROLOGY_FORECAST_PLANS",
                    "error": f"API 返回数据格式异常: 期望 dict，实际 {type(data).__name__}"
                }

            sch_list = data.get('schList', [])
            station_sch = data.get('stationSch', {})

            plan_list = []
            for sch in sch_list:
                plan_list.append({
                    "plcd": sch.get('plcd', ''),
                    "time": sch.get('iymdh', ''),
                    "min_time": sch.get('minYmdh', ''),
                    "max_time": sch.get('maxYmdh', ''),
                    "description": f"{sch.get('plcd', '')} ({sch.get('iymdh', '')})"
                })

            return {
                "success": True,
                "command": "FUNC_GET_HYDROLOGY_FORECAST_PLANS",
                "date_time": date_time,
                "plan_count": len(plan_list),
                "station_count": len(station_sch),
                "plan_list": plan_list,
                "message": f"共 {len(plan_list)} 个预报方案，请选择"
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"水文局预报方案列表 API 请求失败: {e}")
            return {
                "success": False,
                "command": "FUNC_GET_HYDROLOGY_FORECAST_PLANS",
                "error": f"API 请求失败: {str(e)}"
            }
        except Exception as e:
            logger.error(f"get_forecast_plans 出错: {e}")
            return {
                "success": False,
                "command": "FUNC_GET_HYDROLOGY_FORECAST_PLANS",
                "error": f"获取预报方案列表失败: {str(e)}"
            }

    def get_forecast_data(self, plcd: str, time: str) -> Dict[str, Any]:
        """
        获取水文局预报方案数据

        API: GET /pre/getSwPreWaterDataByPlcd?plcd=xxx&time=xxx

        Args:
            plcd: 方案代码
            time: 方案时间

        Returns:
            {
                "success": true,
                "plcd": "...",
                "time": "...",
                "data": [...],  # 原始时间序列数组
                "record_count": 360
            }
        """
        logger.info(f"获取水文局预报方案数据, plcd={plcd}, time={time}")
        try:
            url = f"{self._base_url}/pre/getSwPreWaterDataByPlcd"
            params = {'plcd': plcd, 'time': time}
            resp = requests.get(url, headers=self._get_headers(), params=params, timeout=60)

            if resp.status_code != 200:
                return {
                    "success": False,
                    "command": "FUNC_GET_HYDROLOGY_FORECAST_DATA",
                    "error": f"API 返回 HTTP {resp.status_code}: {resp.text[:200]}"
                }

            raw_data = resp.json()

            # API 直接返回 JSON 数组或包装对象
            if isinstance(raw_data, dict):
                if raw_data.get('code') and raw_data.get('code') != 200:
                    return {
                        "success": False,
                        "command": "FUNC_GET_HYDROLOGY_FORECAST_DATA",
                        "error": f"API 业务错误: {raw_data.get('msg', '')}"
                    }
                data_list = raw_data.get('data', raw_data)
            elif isinstance(raw_data, list):
                data_list = raw_data
            else:
                return {
                    "success": False,
                    "command": "FUNC_GET_HYDROLOGY_FORECAST_DATA",
                    "error": f"API 返回数据格式异常: {type(raw_data).__name__}"
                }

            return {
                "success": True,
                "command": "FUNC_GET_HYDROLOGY_FORECAST_DATA",
                "plcd": plcd,
                "time": time,
                "data": data_list,
                "record_count": len(data_list) if isinstance(data_list, list) else 0
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"水文局预报方案数据 API 请求失败: {e}")
            return {
                "success": False,
                "command": "FUNC_GET_HYDROLOGY_FORECAST_DATA",
                "error": f"API 请求失败: {str(e)}"
            }
        except Exception as e:
            logger.error(f"get_forecast_data 出错: {e}")
            return {
                "success": False,
                "command": "FUNC_GET_HYDROLOGY_FORECAST_DATA",
                "error": f"获取预报方案数据失败: {str(e)}"
            }

    def _query_stcd_mapping(self, cursor) -> Dict[str, str]:
        """
        从 Access 数据库查询站点名称到 stcd 的映射。

        数据库中没有站点信息表，因此返回空字典。stcd 使用 API 字段名。

        Args:
            cursor: pyodbc cursor

        Returns:
            dict: 空字典（使用 API 字段名作为 stcd）
        """
        name_to_stcd = {}
        # 数据库中没有站点信息表，直接返回空字典
        logger.info("数据库中未找到站点信息表，使用 API 字段名作为 stcd")
        return name_to_stcd

    def _resolve_stcd(self, api_field_name: str) -> Tuple[str, str]:
        """
        根据 API 字段名解析 stcd。

        Args:
            api_field_name: API 返回的字段名，如 "sanmenxiaRuku"

        Returns:
            (stcd, station_name): stcd 和中文站名
        """
        stcd = API_FIELD_TO_STCD.get(api_field_name, api_field_name)
        station_name = self._get_station_name(api_field_name)
        return stcd, station_name

    def _get_station_name(self, api_field_name: str) -> str:
        """获取 API 字段名对应的中文站名"""
        _name_map = {
            "sanmenxiaRuku": "三门峡入库", "sanmenxiaChuku": "三门峡出库",
            "xiaolangdiRuku": "小浪底入库", "xiaolangdiChuku": "小浪退出库",
            "xixiayuanRuku": "西霞院入库", "xixiayuanChuku": "西霞院出库",
            "luhunRuku": "陆浑入库", "luhunChuku": "陆浑出库",
            "guxianRuku": "故县入库", "guxianChuku": "故县出库",
            "hekoucunRuku": "河口村入库", "hekoucunChuku": "河口村出库",
            "longmenzhenLiuliang": "龙门镇", "baimasiLiuliang": "白马寺",
            "heishiguanLiuliang": "黑石关", "shanlupingLiuliang": "山路平",
            "jiahetanLiuliang": "夹河滩", "gaocunLiuliang": "高村",
            "sunkouLiuliang": "孙口", "aishanLiuliang": "艾山",
            "luokouLiuliang": "泺口", "lijinLiuliang": "利津",
            "wuzhiLiuliang": "武陟", "huayuankouLiuliang": "花园口",
            "tongguanLiuliang": "潼关", "tongsanjianLiuliang": "潼三间",
            "sanxiaojianLiuliang": "三小间", "xiaohuaganLiuliang": "小花干",
            "xiaohuajianLiuliang": "小花间", "dongpinghuFenhongLiuliang": "东平湖分洪",
        }
        return _name_map.get(api_field_name, api_field_name)

    def write_to_access_db(self, api_data: List[Dict], conn, cursor) -> Dict[str, Any]:
        """
        将 API 返回的时间序列数据转换为 Q_Inputsd/Q_Inputxd 表格式并写入。

        API 数据格式（每个时间点一个对象）:
        [
            {
                "dateTime": "2025-06-06 18:00:00",
                "sanmenxiaRuku": 347.0,
                "xiaolangdiRuku": -1.0,
                "luhunRuku": 0.0,
                "huayuankouLiuliang": 352.0,
                ...
            },
            ...
        ]

        转换后写入 Q_Inputsd（上游）和 Q_Inputxd（下游）表:
        - stcd: 站点编码（从数据库查询）
        - stnm: 站点名称
        - tm: 时间
        - q: 流量值

        Args:
            api_data: API 返回的时间序列数组
            conn: pyodbc 连接
            cursor: pyodbc cursor

        Returns:
            {"success": true, "upstream_count": N, "downstream_count": N, "total": N, "errors": [...]}
        """
        errors = []
        upstream_count = 0
        downstream_count = 0

        if not api_data or not isinstance(api_data, list):
            return {
                "success": False,
                "error": "API 数据为空或格式错误"
            }

        # 1. 查询站点编码映射
        name_to_stcd = self._query_stcd_mapping(cursor)
        logger.info(f"站点编码映射: {len(name_to_stcd)} 个站点")

        # 2. 清空表
        try:
            cursor.execute("DELETE FROM Q_Inputsd")
            cursor.execute("DELETE FROM Q_Inputxd")
            conn.commit()
            logger.info("已清空 Q_Inputsd 和 Q_Inputxd 表")
        except Exception as e:
            errors.append(f"清空表失败: {e}")
            conn.rollback()

        # 3. 遍历每个时间点，展开为站点行
        # 使用批量插入提高性能
        upstream_rows = []
        downstream_rows = []

        for record in api_data:
            if not isinstance(record, dict):
                continue

            date_time = record.get('dateTime', '')

            for field_name, value in record.items():
                if field_name == 'dateTime':
                    continue

                # 只处理在映射表中的字段
                if field_name not in API_FIELD_TO_STCD:
                    continue

                # 跳过 -1.0（无效数据）
                try:
                    q_val = float(value)
                except (ValueError, TypeError):
                    continue
                if q_val < 0:
                    continue

                stcd, stnm = self._resolve_stcd(field_name)

                row = (stcd, stnm, date_time, q_val)

                if field_name in UPSTREAM_FIELDS:
                    upstream_rows.append(row)
                elif field_name in DOWNSTREAM_FIELDS:
                    downstream_rows.append(row)
                else:
                    # 未分类的字段，默认按 stcd 判断
                    try:
                        stcd_int = int(stcd) if stcd else 0
                    except (ValueError, TypeError):
                        stcd_int = 0
                    if stcd_int < 20:
                        upstream_rows.append(row)
                    else:
                        downstream_rows.append(row)

        # 4. 批量写入
        try:
            for row in upstream_rows:
                cursor.execute(
                    "INSERT INTO Q_Inputsd (stcd, stnm, tm, q) VALUES (?, ?, ?, ?)",
                    row
                )
                upstream_count += 1
            conn.commit()
        except Exception as e:
            errors.append(f"写入 Q_Inputsd 失败: {e}")
            conn.rollback()

        try:
            for row in downstream_rows:
                cursor.execute(
                    "INSERT INTO Q_Inputxd (stcd, stnm, tm, q) VALUES (?, ?, ?, ?)",
                    row
                )
                downstream_count += 1
            conn.commit()
        except Exception as e:
            errors.append(f"写入 Q_Inputxd 失败: {e}")
            conn.rollback()

        logger.info(f"写入完成: Q_Inputsd={upstream_count}行, Q_Inputxd={downstream_count}行")

        return {
            "success": True,
            "upstream_count": upstream_count,
            "downstream_count": downstream_count,
            "total": upstream_count + downstream_count,
            "errors": errors
        }


# 全局单例
hydrology_forecast_service = HydrologyForecastService()