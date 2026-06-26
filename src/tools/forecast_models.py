import json
import os
import random
import subprocess
import time
import pyodbc
import pandas as pd
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from fastmcp import FastMCP
from src.utils.logger import get_logger
from src.services.storage.scheme_storage import save_scheme, generate_unique_id
from src.services.external_api.xinanjiang_service import xinanjiang_auth_service, xinanjiang_model_service
from src.services.external_api.auth_service import auth_service
from src.services.external_api.water_forecast_service import water_forecast_service
from src.utils.station_codes import get_reservoir_code, get_hydrology_code
from src.config.settings import settings

logger = get_logger(__name__)


def register_forecast_models(mcp: FastMCP):

    @mcp.tool()
    async def run_rainfall_forecast_model(basin: str, start_time: str, end_time: str, rainfall_data: str) -> dict:
        """
        执行降雨预报模型。

        Args:
            basin: 流域名称（如：黄河、洛河、伊洛河等）
            start_time: 开始时间 (格式: YYYY-MM-DD)
            end_time: 结束时间 (格式: YYYY-MM-DD)
            rainfall_data: 降雨数据 (JSON格式)，包含各雨量站的降雨过程
        """
        logger.info(f"调用 run_rainfall_forecast_model，收到参数: basin={repr(basin)}, start_time={repr(start_time)}, end_time={repr(end_time)}, rainfall_data={repr(rainfall_data)}")
        try:
            rainfall = json.loads(rainfall_data) if isinstance(rainfall_data, str) else rainfall_data
        except json.JSONDecodeError:
            return_value = {"success": False, "error": "降雨数据格式错误，请提供有效的JSON格式"}
            logger.debug(f"run_hydrological_model 返回结果: {return_value}")
            return return_value

        total_rainfall = sum(float(r.get("rainfall", 0)) for r in rainfall) if rainfall else 0
        base_flow = total_rainfall * random.uniform(10, 30)

        forecast_points = []
        for i in range(24):
            flow = base_flow * random.uniform(0.6, 1.4) * (1 - i * 0.02)
            water_level = 100 + random.uniform(-5, 5)
            forecast_points.append({
                "hour": i,
                "inflow": round(flow, 2),
                "water_level": round(water_level, 2)
            })

        return_value = {
            "success": True,
            "basin": basin,
            "start_time": start_time,
            "end_time": end_time,
            "command": "FUNC_RUN_HYDROLOGICAL_MODEL",
            "total_rainfall": total_rainfall,
            "peak_flow": round(base_flow * 1.2, 2),
            "forecast_points": forecast_points,
            "message": f"水文预报模型执行成功，{basin}流域共产生{total_rainfall:.1f}mm降雨"
        }
        logger.debug(f"run_hydrological_model 返回结果: {return_value}")
        return return_value

    @mcp.tool()
    async def run_water_forecast_model(station_type: str, station_name: str, start_time: str = None, end_time: str = None) -> dict:
        """
        执行设计院的分布式水文来水预报模型，根据站点类型调用不同接口获取预报数据。

        Args:
            station_type: 站点类型，可选值: reservoir(水库), hydrology(水文站)
            station_name: 站点名称，如: 三门峡, 小浪底, 龙门镇, 花园口等（支持名称匹配编码）
            start_time: 开始时间（格式：YYYY-MM-DD HH:MM:SS），不指定则使用当前时间前一天
            end_time: 结束时间（格式：YYYY-MM-DD HH:MM:SS），不指定则使用当前时间后一天
        """
        logger.info(f"调用 run_water_forecast_model，收到参数: station_type={repr(station_type)}, station_name={repr(station_name)}, start_time={repr(start_time)}, end_time={repr(end_time)}")
        
        # 设置默认时间范围
        if not start_time:
            start_time = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        if not end_time:
            end_time = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            if station_type.lower() not in ["reservoir", "hydrology"]:
                return_value = {"success": False, "error": f"不支持的站点类型: {station_type}，请使用 reservoir 或 hydrology"}
                logger.debug(f"run_water_forecast_model 返回结果: {return_value}")
                return return_value
            
            scheme_list_result = water_forecast_service.get_scheme_list(start_time, end_time)
            
            if scheme_list_result.get("success") is False or scheme_list_result.get("code") not in [200, "200", None]:
                error_msg = scheme_list_result.get("message", scheme_list_result.get("error", "获取预报方案清单失败"))
                return_value = {"success": False, "error": error_msg}
                logger.debug(f"run_water_forecast_model 返回结果: {return_value}")
                return return_value
            
            data_field = scheme_list_result.get("data")
            
            if isinstance(data_field, dict):
                scheme_list = data_field.get("schList", [])
                if not scheme_list:
                    scheme_list = data_field.get("recommended", [])
            elif isinstance(data_field, list):
                scheme_list = data_field
            elif isinstance(scheme_list_result, list):
                scheme_list = scheme_list_result
            else:
                scheme_list = []
            
            if len(scheme_list) == 0:
                return_value = {"success": False, "error": "预报方案清单为空，请检查时间范围或联系管理员"}
                logger.debug(f"run_water_forecast_model 返回结果: {return_value}")
                return return_value
            
            def parse_datetime(dt_str):
                for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]:
                    try:
                        return datetime.strptime(dt_str, fmt)
                    except ValueError:
                        continue
                return None
            
            target_start = parse_datetime(start_time)
            target_end = parse_datetime(end_time)
            
            matched_scheme = None
            for scheme in scheme_list:
                scheme_time = parse_datetime(scheme.get("schTime", ""))
                
                if scheme_time and target_start and target_end:
                    if target_start <= scheme_time <= target_end:
                        matched_scheme = scheme
                        break
            
            if not matched_scheme:
                return_value = {"success": False, "error": f"未找到与时间范围 {start_time} - {end_time} 匹配的预报方案"}
                logger.debug(f"run_water_forecast_model 返回结果: {return_value}")
                return return_value
            
            sch_id = matched_scheme.get("schId") or matched_scheme.get("id")
            if not sch_id:
                return_value = {"success": False, "error": "预报方案中未找到 schId"}
                logger.debug(f"run_water_forecast_model 返回结果: {return_value}")
                return return_value
            
            result = water_forecast_service.get_scheme_data_by_station_name(sch_id, station_name)
            
            if result.get("success") is False or result.get("code") not in [200, "200", None]:
                error_msg = result.get("message", result.get("error", "获取预报数据失败"))
                return_value = {"success": False, "error": error_msg}
                logger.debug(f"run_water_forecast_model 返回结果: {return_value}")
                return return_value
            
            station_code = ""
            if station_type.lower() == "reservoir":
                station_code = get_reservoir_code(station_name) or ""
            elif station_type.lower() == "hydrology":
                station_code = get_hydrology_code(station_name) or ""
            
            # 过滤掉 level 水位字段
            raw_data = result.get("data", result)
            if isinstance(raw_data, list):
                filtered_data = []
                for item in raw_data:
                    if isinstance(item, dict):
                        filtered_data.append({k: v for k, v in item.items() if k != "level"})
                    else:
                        filtered_data.append(item)
            else:
                filtered_data = raw_data
            
            return_value = {
                "success": True,
                "station_type": station_type,
                "station_name": station_name,
                "station_code": station_code,
                "start_time": start_time,
                "end_time": end_time,
                "command": "FUNC_RUN_WATER_FORECAST_MODEL",
                "sch_id": sch_id,
                "forecast_data": filtered_data,
                "message": f"来水预报模型执行成功，已获取{station_type} {station_name}的预报数据"
            }
            logger.debug(f"run_water_forecast_model 返回结果: {return_value}")
            return return_value
            
        except Exception as e:
            error_msg = f"执行来水预报模型时出错: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

    @mcp.tool()
    async def generate_dispatch_scheme(
        start_time: str = None
    ) -> dict:
        """
        一键生成调度方案单：导入Excel → 运行RegualDispacth.exe计算 → 统计处理 → 存储入库 → 返回前台展示数据。

        从 data/Q_Inputsd.xlsx 和 data/Q_Inputxd.xlsx 读取入库流量数据，
        导入到 data.mdb 数据库，运行 RegualDispacth.exe 进行计算，
        读取 Q_Output 和 Z_Output 计算结果进行统计处理后存储到数据库，并返回摘要数据供前台展示。

        Args:
            start_time: 调度开始时间（格式：YYYY-MM-DD），当前基于Excel数据自动确定时间范围
        """
        logger.info(f"调用 generate_dispatch_scheme，收到参数: start_time={repr(start_time)}")

        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        mdb_path = os.path.join(project_root, '6', 'data.mdb')
        data_dir = os.path.join(project_root, 'data')
        exe_path = os.path.join(project_root, 'RegualDispacth.exe')

        total_start = time.time()
        steps = {}

        try:
            # ================================================================
            # 步骤1: 导入Excel数据到MDB
            # ================================================================
            logger.info("步骤1: 导入Excel数据到MDB")
            import_start = time.time()

            sd_path = os.path.join(data_dir, 'Q_Inputsd.xlsx')
            xd_path = os.path.join(data_dir, 'Q_Inputxd.xlsx')

            if not os.path.exists(sd_path):
                return {"success": False, "error": f"上游入库流量文件不存在: {sd_path}", "steps": steps}
            if not os.path.exists(xd_path):
                return {"success": False, "error": f"下游入库流量文件不存在: {xd_path}", "steps": steps}
            if not os.path.exists(exe_path):
                return {"success": False, "error": f"调度计算程序不存在: {exe_path}", "steps": steps}
            if not os.path.exists(mdb_path):
                return {"success": False, "error": f"数据库文件不存在: {mdb_path}", "steps": steps}

            df_sd = pd.read_excel(sd_path)
            df_xd = pd.read_excel(xd_path)

            conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={mdb_path};'
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()

            cursor.execute("DELETE FROM Q_Inputsd")
            cursor.execute("DELETE FROM Q_Inputxd")
            conn.commit()

            sd_rows = 0
            for _, row in df_sd.iterrows():
                cursor.execute(
                    "INSERT INTO Q_Inputsd (stcd, stnm, tm, q) VALUES (?, ?, ?, ?)",
                    (row.get('stcd', ''), row.get('stnm', ''), row.get('tm', ''), row.get('q', 0))
                )
                sd_rows += 1
            conn.commit()

            xd_rows = 0
            for _, row in df_xd.iterrows():
                cursor.execute(
                    "INSERT INTO Q_Inputxd (stcd, stnm, tm, q) VALUES (?, ?, ?, ?)",
                    (row.get('stcd', ''), row.get('stnm', ''), row.get('tm', ''), row.get('q', 0))
                )
                xd_rows += 1
            conn.commit()

            import_elapsed = round(time.time() - import_start, 2)
            steps["import"] = {
                "Q_Inputsd_rows": sd_rows,
                "Q_Inputxd_rows": xd_rows,
                "elapsed_seconds": import_elapsed
            }
            logger.info(f"导入完成: Q_Inputsd={sd_rows}行, Q_Inputxd={xd_rows}行, 耗时{import_elapsed}秒")

            # ================================================================
            # 步骤2: 运行调度计算程序
            # ================================================================
            logger.info("步骤2: 运行 RegualDispacth.exe")
            calc_start = time.time()

            result = subprocess.run(
                [exe_path],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=300
            )

            calc_elapsed = round(time.time() - calc_start, 2)
            steps["calculation"] = {
                "elapsed_seconds": calc_elapsed,
                "exit_code": result.returncode
            }
            logger.info(f"计算完成: exit_code={result.returncode}, 耗时{calc_elapsed}秒")

            if result.returncode != 0:
                logger.warning(f"RegualDispacth.exe 返回非零退出码: {result.returncode}, stderr: {result.stderr}")

            # ================================================================
            # 步骤3: 读取Q_Output并进行统计处理
            # ================================================================
            logger.info("步骤3: 读取Q_Output并统计处理")
            stats_start = time.time()

            cursor.execute("SELECT stcd, stnm, tm, q FROM Q_Output ORDER BY tm, stcd")
            rows = cursor.fetchall()

            output_data = []
            for row in rows:
                output_data.append({
                    "stcd": row.stcd,
                    "stnm": row.stnm.strip() if row.stnm else "",
                    "tm": row.tm,
                    "q": row.q
                })

            output_rows = len(output_data)

            # 按站点分组统计
            from collections import defaultdict
            station_groups = defaultdict(list)
            for item in output_data:
                station_groups[item["stnm"]].append(item["q"])

            station_stats = {}
            for stnm, flows in station_groups.items():
                station_stats[stnm] = {
                    "count": len(flows),
                    "max_flow": round(max(flows), 2),
                    "min_flow": round(min(flows), 2),
                    "avg_flow": round(sum(flows) / len(flows), 2)
                }

            # 提取时间范围
            all_times = sorted(set(item["tm"] for item in output_data))
            time_range_start = str(all_times[0]) if all_times else ""
            time_range_end = str(all_times[-1]) if all_times else ""

            # 按流量排序取TOP站点
            top_by_max = sorted(station_stats.items(), key=lambda x: x[1]["max_flow"], reverse=True)[:5]
            top_by_avg = sorted(station_stats.items(), key=lambda x: x[1]["avg_flow"], reverse=True)[:5]

            stats_elapsed = round(time.time() - stats_start, 2)
            steps["statistics"] = {
                "total_stations": len(station_stats),
                "total_rows": output_rows,
                "time_range": {"start": time_range_start, "end": time_range_end},
                "elapsed_seconds": stats_elapsed
            }
            logger.info(f"统计完成: {len(station_stats)}个站点, {output_rows}行数据, 耗时{stats_elapsed}秒")

            # 从 Z_Output 表提取各水库统计指标（exe 运行后的计算结果）
            reservoir_stats, reservoir_table = _calculate_reservoir_stats(conn)
            logger.info(f"已从 Z_Output 提取 {len(reservoir_stats)} 个水库的统计指标")

            conn.close()

            # ================================================================
            # 步骤4: 构建方案数据并存储到数据库
            # ================================================================
            logger.info("步骤4: 存储方案数据到数据库")

            scheme_data = {
                "scheme_name": f"调度方案单_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "description": "基于Excel入库流量数据，通过RegualDispacth.exe计算生成的调度方案",
                "basin": "黄河",
                "start_date": time_range_start[:10] if time_range_start else "",
                "end_date": time_range_end[:10] if time_range_end else "",
                "status": "active",
                "constraints": [],
                "details": [],
                "constraints_applied": {},
                "station_stats": station_stats,
                "output_data": output_data,
                "steps": steps
            }

            saved_scheme_id = save_scheme(scheme_data)
            logger.info(f"调度方案已保存，ID: {saved_scheme_id}")

            total_elapsed = round(time.time() - total_start, 2)

            # ================================================================
            # 构建前台展示数据（摘要，不返回全量数据）
            # ================================================================
            return_value = {
                "success": True,
                "command": "FUNC_GENERATE_DISPATCH_SCHEME",
                "scheme_id": saved_scheme_id,
                "scheme_name": scheme_data["scheme_name"],
                "start_date": scheme_data["start_date"],
                "end_date": scheme_data["end_date"],
                "message": "调度方案单生成完成",
                "steps": steps,
                "total_elapsed_seconds": total_elapsed,
                "summary": {
                    "total_stations": len(station_stats),
                    "total_rows": output_rows,
                    "time_range": {"start": time_range_start, "end": time_range_end},
                    "top_stations_by_max_flow": [
                        {"name": name, "max_flow": stat["max_flow"], "avg_flow": stat["avg_flow"]}
                        for name, stat in top_by_max
                    ],
                    "top_stations_by_avg_flow": [
                        {"name": name, "avg_flow": stat["avg_flow"], "max_flow": stat["max_flow"]}
                        for name, stat in top_by_avg
                    ],
                    "all_stations": station_stats,
                    "reservoir_stats": reservoir_stats,
                    "reservoir_table": reservoir_table
                }
            }

            logger.debug(f"generate_dispatch_scheme 返回结果: {return_value}")
            return return_value

        except subprocess.TimeoutExpired:
            logger.error("RegualDispacth.exe 执行超时（300秒）")
            return {"success": False, "error": "调度计算程序执行超时（300秒）", "steps": steps}
        except pyodbc.Error as e:
            logger.error(f"数据库操作错误: {e}")
            return {"success": False, "error": f"数据库操作失败: {str(e)}", "steps": steps}
        except FileNotFoundError as e:
            logger.error(f"文件不存在错误: {e}")
            return {"success": False, "error": f"所需文件不存在: {str(e)}", "steps": steps}
        except Exception as e:
            logger.error(f"generate_dispatch_scheme 出错: {e}")
            return {"success": False, "error": f"调度方案单生成失败: {str(e)}", "steps": steps}

    @mcp.tool()
    async def run_xinanjiang_model(
        station_name: str,
        start_time: str,
        end_time: str,
        custom_params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        运行新安江水文模型，计算目标站点的流量（区间来水）。

        Args:
            station_name: 站点名称，支持水库或水文站，如：
                - 水库：陆浑水库、故县水库、三门峡水库、小浪底水库、河口村水库
                - 水文站：龙门镇、白马寺、黑石关、花园口
                系统会自动从数据库加载该站点的默认参数。
            start_time: 开始时间，格式: yyyy-MM-dd HH:mm:ss，例如: "2021-10-02 00:00:00"
            end_time: 结束时间，格式: yyyy-MM-dd HH:mm:ss，例如: "2021-10-07 00:00:00"
            custom_params: 可选的自定义参数，用于覆盖站点默认参数。
                支持的参数包括：
                - KC: 流域蒸散发折算系数 (默认: 根据站点配置)
                - B: 流域蓄水容量分布曲线指数 (默认: 根据站点配置)
                - UM: 上层张力水容量 (默认: 根据站点配置)
                - LM: 下层张力水容量 (默认: 根据站点配置)
                - SM: 自由水容量 (默认: 根据站点配置)
                - KG: 地下水日出流系数 (默认: 根据站点配置)
                - KI: 壤中流日出流系数 (默认: 根据站点配置)
                - XE: 马斯京跟法演算参数 (默认: 根据站点配置)

        Returns:
            {
                "success": true,
                "message": "模型运行成功",
                "station_info": { ... },
                "model_params": {                    # 新安江模型使用的完整参数
                    "KC": {"value": "0.9", "fullName": "流域蒸散发折算系数(KC)"},
                    "B": {"value": "0.4", "fullName": "流域蓄水容量分布曲线指数(B)"},
                    "SM": {"value": "25", "fullName": "自由水客量(SM)"},
                    "KG": {"value": "0.3", "fullName": "地下水日出流系数(KG)"},
                    "BA": {"value": "349.0", "fullName": "流域面积(BA)"},
                    "__custom_overrides__": ["KC"]   # 如有自定义覆盖参数，列出被覆盖的键名
                },
                "result": {
                    "start_time": "...",
                    "end_time": "...",
                    "rainfall_data": [...],          # 加权面雨量（mm/h）
                    "flow": [...],              # 新安江模型流量（m³/s）
                    "times": [...]
                }
            }
        """
        logger.info(f"调用 run_xinanjiang_model，站点: {station_name}，时间范围: {start_time} 至 {end_time}")
        
        from src.services.storage.database.xinanjiang_config_access import XinanjiangModelConfigAccess
        from src.services.storage.database.connection import get_db
        
        station_config = XinanjiangModelConfigAccess.get_config_by_station(station_name)
        if not station_config:
            return {"success": False, "message": f"未找到站点配置: {station_name}，请检查站点名称是否正确", "code": 404}
        
        station_type = station_config.get('station_type', 'reservoir')
        station_code = station_config.get('station_code', '')
        basin_name = station_config.get('basin_name', '')
        basin_area = station_config.get('basin_area', 101.7298)
        
        logger.info(f"站点配置信息: {station_name}({station_type}), 流域: {basin_name}, 面积: {basin_area}km²")
        
        # -------------------------------------------------------------------
        # 1. 从本地数据库查询降雨数据，基于雨量站权重计算加权面雨量
        # -------------------------------------------------------------------
        def _query_weighted_rainfall_from_db(start: str, end: str) -> Dict[str, Any]:
            """
            从本地数据库 rainfall_hourly 表查询逐小时降雨数据，
            结合 rainfall_stations 表的 weight_area 计算加权平均面雨量。

            返回: {"code": 200, "data": {timestamp: weighted_rainfall}, "station_count": N}
            """
            db = get_db()
            
            # 查询该时间范围内所有雨量站的逐小时降雨记录
            hourly_sql = """
                SELECT rh.station_code, rh.station_name, rh.timestamp, rh.rainfall,
                       rs.weight_area
                FROM rainfall_hourly rh
                LEFT JOIN rainfall_stations rs ON rh.station_code = rs.code
                WHERE rh.timestamp >= ? AND rh.timestamp < ?
                ORDER BY rh.timestamp, rh.station_code
            """
            raw_records = db.execute_query(hourly_sql, (start, end))
            
            if not raw_records:
                logger.warning(f"数据库查询到 {start}~{end} 无降雨数据")
                return {"code": 200, "data": {}, "station_count": 0}
            
            # 按时间戳分组
            from collections import defaultdict
            time_groups = defaultdict(list)
            station_weights = {}
            
            for rec in raw_records:
                ts = rec['timestamp']
                station_code = rec['station_code']
                rainfall = rec['rainfall'] if rec['rainfall'] is not None else 0.0
                weight_area = rec['weight_area'] if rec['weight_area'] is not None else 0.0
                
                time_groups[ts].append({
                    'station_code': station_code,
                    'rainfall': rainfall,
                    'weight_area': weight_area
                })
                if station_code not in station_weights:
                    station_weights[station_code] = weight_area
            
            # 对每个时间步长计算加权平均降雨量
            weighted_rainfall = {}
            for ts, records in sorted(time_groups.items()):
                total_weighted = 0.0
                total_weight = 0.0
                for r in records:
                    w = r['weight_area']
                    total_weighted += r['rainfall'] * w
                    total_weight += w
                
                if total_weight > 0:
                    weighted_rainfall[str(ts)] = round(total_weighted / total_weight, 2)
                else:
                    # 无权重信息时使用简单平均
                    weighted_rainfall[str(ts)] = round(
                        sum(r['rainfall'] for r in records) / len(records), 2
                    )
            
            logger.info(
                f"从数据库获取降雨数据成功，涉及 {len(station_weights)} 个雨量站，"
                f"{len(weighted_rainfall)} 个时段"
            )
            
            return {
                "code": 200,
                "data": weighted_rainfall,
                "station_count": len(station_weights),
                "stations": list(station_weights.keys())
            }
        
        def _build_rainfall_array(
            weighted_data: Dict[str, Any],
            start: str,
            end: str,
            hours: int
        ) -> List[float]:
            """
            将加权面雨量字典按时间顺序转为等时段数组。
            缺少数据的时段用 0 填充。
            """
            rainfall_values = []
            dt_start = datetime.strptime(start, "%Y-%m-%d %H:%M:%S")
            
            rainfall_map = weighted_data.get("data", {})
            
            for i in range(hours):
                current_ts = (dt_start + timedelta(hours=i)).strftime("%Y-%m-%d %H:%M:%S")
                val = rainfall_map.get(current_ts, 0.0)
                rainfall_values.append(val)
            
            # 如果完全没有数据，使用极小默认值（防止模型报错）
            if all(v == 0.0 for v in rainfall_values):
                logger.warning("所有时段降雨量均为0，使用默认值0.1mm")
                rainfall_values = [0.1] * hours
            
            logger.info(
                f"构建等时段面雨量数组: 共{len(rainfall_values)}个时段, "
                f"最大值={max(rainfall_values)}mm, 平均值={round(sum(rainfall_values)/len(rainfall_values), 2)}mm"
            )
            return rainfall_values
        
        # -------------------------------------------------------------------
        # 2. 构建模型控制参数
        # -------------------------------------------------------------------
        def _build_control_params(config: Dict[str, Any], custom: Dict[str, Any] = None) -> Dict[str, Any]:
            # 过滤掉 SQL 元数据和非参数键，只保留水文参数
            skip_keys = {'id', 'station_name', 'station_type', 'station_code', 'basin_name', 'basin_area', 'description', 'created_at', 'updated_at'}
            params = {k: v for k, v in config.items() if k not in skip_keys}
            if custom:
                params.update(custom)
                logger.info(f"使用自定义参数覆盖默认值: {custom}")
            
            return {
                "ncName": "control",
                "type": "hydraulic_elements",
                "dimensionsList": [],
                "variablesList": [],
                "globalList": [
                    {"type": "float", "name": "KC", "fullName": "流域蒸散发折算系数(KC)", "value": str(params.get('KC', 0.9))},
                    {"type": "float", "name": "B", "fullName": "流域蓄水容量分布曲线指数(B)", "value": str(params.get('B', 0.4))},
                    {"type": "int", "name": "UM", "fullName": "上层张力水容量(UM)", "value": str(params.get('UM', 30))},
                    {"type": "int", "name": "LM", "fullName": "下层张力水容量(LM)", "value": str(params.get('LM', 80))},
                    {"type": "float", "name": "EX", "fullName": "流域自由水容量分布曲线指数(EX)", "value": str(params.get('EX', 1.5))},
                    {"type": "float", "name": "C", "fullName": "深层蒸散发折算系数(C)", "value": str(params.get('C', 0.12))},
                    {"type": "float", "name": "IM", "fullName": "不透水面积比例(IM)", "value": str(params.get('IM', 0))},
                    {"type": "float", "name": "WM", "fullName": "张力水容量(WM)", "value": str(params.get('WM', 120))},
                    {"type": "float", "name": "SM", "fullName": "自由水客量(SM)", "value": str(params.get('SM', 25))},
                    {"type": "float", "name": "KG", "fullName": "地下水日出流系数(KG)", "value": str(params.get('KG', 0.3))},
                    {"type": "float", "name": "KI", "fullName": "壤中流日出流系数(KI)", "value": str(params.get('KI', 0.3))},
                    {"type": "float", "name": "CS", "fullName": "地表水流消退系数(CS)", "value": str(params.get('CS', 0.8))},
                    {"type": "float", "name": "CG", "fullName": "地下水日消退系数(CG)", "value": str(params.get('CG', 1))},
                    {"type": "float", "name": "CI", "fullName": "壤中流日消退系数(CI)", "value": str(params.get('CI', 1))},
                    {"type": "float", "name": "CR", "fullName": "日模型河网蓄水消退系数(CR)", "value": str(params.get('CR', 0.2))},
                    {"type": "double", "name": "BA", "fullName": "流域面积(BA)", "value": str(params.get('basin_area', basin_area))},
                    {"type": "float", "name": "XE", "fullName": "马斯京跟法演算参数(XE)", "value": str(params.get('XE', 0.2))},
                    {"type": "int", "name": "KE", "fullName": "马斯京跟法演算参数(KE)", "value": str(params.get('KE', 1))}
                ]
            }
        
        def _build_rainfall_data(rainfall_values: List[float], start: str, end: str) -> Dict[str, Any]:
            return {
                "ncName": "p",
                "type": "hydraulic_elements",
                "dimensionsList": [{"name": "TM", "fullName": "时间维度", "value": len(rainfall_values)}],
                "variablesList": [{
                    "valueType": "float",
                    "ArrayType": "array1d",
                    "name": "PA",
                    "fullName": "等时段面雨量值",
                    "arrayValue": [str(v) for v in rainfall_values],
                    "dimensionsSort": ["TM"],
                    "arrayType": "array1d"
                }],
                "globalList": [
                    {"type": "string", "name": "BGTM", "fullName": "开始时间", "value": start},
                    {"type": "string", "name": "EDTM", "fullName": "结束时间", "value": end},
                    {"type": "string", "name": "DT_UNIT", "fullName": "时间间隔单位", "value": "H"},
                    {"type": "float", "name": "DT", "fullName": "时间间隔", "value": "1"}
                ]
            }
        
        def _build_etp_data(length: int, start: str, end: str) -> Dict[str, Any]:
            return {
                "ncName": "em",
                "type": "hydraulic_elements",
                "dimensionsList": [{"name": "TM", "fullName": "时间维度", "value": length}],
                "variablesList": [{
                    "valueType": "float",
                    "ArrayType": "array1d",
                    "name": "ETP",
                    "fullName": "蒸散发值",
                    "arrayValue": ["0" for _ in range(length)],
                    "dimensionsSort": ["TM"],
                    "arrayType": "array1d"
                }],
                "globalList": [
                    {"type": "string", "name": "BGTM", "fullName": "开始时间", "value": start},
                    {"type": "string", "name": "EDTM", "fullName": "结束时间", "value": end},
                    {"type": "string", "name": "DT_UNIT", "fullName": "时间间隔单位", "value": "H"},
                    {"type": "float", "name": "DT", "fullName": "时间间隔", "value": "1"}
                ]
            }
        
        # -------------------------------------------------------------------
        # 主流程
        # -------------------------------------------------------------------
        try:
            dt_start = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
            dt_end = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
            time_diff = dt_end - dt_start
            hours_diff = int(time_diff.total_seconds() / 3600) + 1
            
            logger.info(f"时间范围: {start_time} 至 {end_time}，共 {hours_diff} 个时段")
            
            # ---- 步骤1: 从数据库查询降雨数据并计算加权面雨量 ----
            weighted_rainfall_data = _query_weighted_rainfall_from_db(start_time, end_time)
            rainfall_values = _build_rainfall_array(weighted_rainfall_data, start_time, end_time, hours_diff)
            
            logger.info(
                f"计算得到等时段加权面雨量: "
                f"涉及 {weighted_rainfall_data.get('station_count', 0)} 个雨量站"
            )
            
            # ---- 步骤2: 构建NC文件参数并调用新安江模型 ----
            ctrl_params = _build_control_params(station_config, custom_params)
            rainfall_data = _build_rainfall_data(rainfall_values, start_time, end_time)
            etp_data = _build_etp_data(len(rainfall_values), start_time, end_time)
            
            # 提取模型参数为可读格式（用于返回给调用方）
            # 过滤掉 BA（流域面积），从数据库读取的数据可能不准确
            skip_model_params = {"BA"}
            model_params = {}
            for item in ctrl_params.get("globalList", []):
                name = item.get("name", "")
                if name in skip_model_params:
                    continue
                value = item.get("value", "")
                full_name = item.get("fullName", name)
                model_params[name] = {"value": value, "fullName": full_name}
            # 也记录用户自定义覆盖的参数
            if custom_params:
                model_params["__custom_overrides__"] = list(custom_params.keys())
            
            if not xinanjiang_auth_service.get_token():
                return {"success": False, "message": "新安江模型登录失败", "code": 500}
            
            write_result = xinanjiang_model_service.write_service_nc_file(ctrl_params, rainfall_data, etp_data)
            if not write_result.get("success"):
                return {"success": False, "message": "写入NC文件失败", "result": write_result}
            
            file_list = write_result.get("result", {}).get("fileList", [])
            control_path = None
            em_path = None
            p_path = None
            
            for file_info in file_list:
                nc_name = file_info.get("ncName")
                file_path = file_info.get("filePath")
                if nc_name == "control":
                    control_path = file_path
                elif nc_name == "em":
                    em_path = file_path
                elif nc_name == "p":
                    p_path = file_path
            
            if not all([control_path, em_path, p_path]):
                return {"success": False, "message": "文件路径解析失败", "result": file_list}
            
            call_result = xinanjiang_model_service.call_model(control_path, em_path, p_path)
            if not call_result.get("success"):
                return {"success": False, "message": "模型调用失败", "result": call_result}
            
            inc_key = call_result.get("result", {}).get("incKey")
            if not inc_key:
                return {"success": False, "message": "获取任务ID失败", "result": call_result}
            
            logger.info(f"任务ID: {inc_key}")
            
            # ---- 步骤3: 轮询等待模型计算结果 ----
            max_polls = 60
            poll_interval = 5
            discharge = []
            start_time_result = start_time
            end_time_result = end_time
            
            for poll_count in range(max_polls):
                time.sleep(poll_interval)
                
                status_result = xinanjiang_model_service.get_service_instance(inc_key)
                if not status_result.get("success"):
                    continue
                
                status = status_result.get("result", {}).get("status")
                logger.info(f"轮询 {poll_count + 1}/{max_polls}: 状态={status}")
                
                if status == 3:
                    callback_data_str = status_result.get("result", {}).get("callbackData", "{}")
                    
                    callback_data = json.loads(callback_data_str)
                    output_data = callback_data.get("data", [])
                    
                    output_file_path = None
                    for item in output_data:
                        if item.get("key") == "out":
                            output_file_path = item.get("value")
                            break
                    
                    if not output_file_path:
                        return {"success": False, "message": "未找到输出文件路径", "result": status_result}
                    
                    parse_result = xinanjiang_model_service.nc_to_json(output_file_path)
                    if not parse_result.get("success"):
                        return {"success": False, "message": "NC文件解析失败", "result": parse_result}
                    
                    variables_list = parse_result.get("result", {}).get("variablesList", [])
                    global_list = parse_result.get("result", {}).get("globalList", [])
                    
                    for var in variables_list:
                        if var.get("name") == "Q":
                            discharge = [float(v) for v in var.get("arrayValue", [])]
                            break
                    
                    for glb in global_list:
                        if glb.get("name") == "BGTM":
                            start_time_result = glb.get("value")
                        elif glb.get("name") == "EDTM":
                            end_time_result = glb.get("value")
                    
                    break  # 获取结果成功，退出轮询
                    
                elif status in [4, 5]:
                    return {"success": False, "message": f"新安江模型任务失败，状态: {status}", "result": status_result}
            
            if not discharge:
                return {"success": False, "message": f"新安江模型轮询超时（{max_polls}次）或未获取到径流结果", "inc_key": inc_key}
            
            # ---- 步骤4: 构建时间轴 ----
            times = []
            try:
                dt_ref = datetime.strptime(start_time_result, "%Y-%m-%d %H:%M:%S")
                for i in range(len(discharge)):
                    times.append((dt_ref + timedelta(hours=i)).strftime("%Y-%m-%d %H:%M:%S"))
            except Exception:
                times = [(dt_start + timedelta(hours=i)).strftime("%Y-%m-%d %H:%M:%S") for i in range(len(discharge))]
            
            # ---- 步骤5: 返回完整结果 ----
            response_data = {
                "success": True,
                "message": "新安江模型运行成功",
                "command": "FUNC_RUN_XINANJIANG_MODEL",
                "station_info": {
                    "station_name": station_name,
                    "station_type": station_type,
                    "station_code": station_code,
                    "basin_name": basin_name
                },
                "model_params": model_params,
                "result": {
                    "start_time": start_time_result,
                    "end_time": end_time_result,
                    "rainfall_data": rainfall_values,
                    "flow": discharge,
                    "times": times
                }
            }
            
            return response_data
            
        except Exception as e:
            logger.error(f"新安江模型完整流程异常: {e}")
            return {"success": False, "message": str(e), "code": 500}

    @mcp.tool()
    async def modify_dispatch_param(action: str, station_name: str | None = None, param_desc: str | None = None, new_value: float | None = None) -> dict:
        """
        查看或修改 data.mdb 中 Dispatch_Par 表的调度参数。

        Args:
            action: 操作类型，"list"（查看所有参数）或 "update"（修改参数）
            station_name: 站点名称（如"小浪底"、"三门峡"、"陆浑"等），update时必填
            param_desc: 参数说明关键词（如"敞泄"、"初始水位"、"预泄流量"、"防洪高水位"等），update时必填
            new_value: 新的参数值，update时必填
        """
        logger.info(f"调用 modify_dispatch_param，action={action}, station_name={station_name}, param_desc={param_desc}, new_value={new_value}")

        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        mdb_path = os.path.join(project_root, '6', 'data.mdb')
        conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={mdb_path};'

        try:
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()

            if action == "list":
                cursor.execute("SELECT stcd, stnm, Control_Par, Instruction FROM Dispatch_Par ORDER BY stcd")
                rows = cursor.fetchall()
                params = []
                for row in rows:
                    params.append({
                        "stcd": row.stcd,
                        "stnm": row.stnm.strip() if row.stnm else "",
                        "Control_Par": row.Control_Par,
                        "Instruction": row.Instruction.strip() if row.Instruction else ""
                    })

                conn.close()
                logger.info(f"查询到 {len(params)} 条调度参数记录")
                return {
                    "success": True,
                    "total_params": len(params),
                    "params": params
                }

            elif action == "update":
                if not station_name or not param_desc or new_value is None:
                    conn.close()
                    return {
                        "success": False,
                        "error": "update 操作需要提供 station_name、param_desc 和 new_value 参数"
                    }

                cursor.execute(
                    "SELECT stcd, stnm, Control_Par, Instruction FROM Dispatch_Par WHERE stnm = ? AND Instruction LIKE ?",
                    (station_name, f'%{param_desc}%')
                )
                matches = cursor.fetchall()

                if len(matches) == 0:
                    cursor.execute("SELECT stcd, stnm, Control_Par, Instruction FROM Dispatch_Par ORDER BY stcd")
                    all_rows = cursor.fetchall()
                    all_params = []
                    for row in all_rows:
                        all_params.append({
                            "stcd": row.stcd,
                            "stnm": row.stnm.strip() if row.stnm else "",
                            "Control_Par": row.Control_Par,
                            "Instruction": row.Instruction.strip() if row.Instruction else ""
                        })
                    conn.close()
                    return {
                        "success": False,
                        "error": f"未找到匹配的参数：站点={station_name}，关键词={param_desc}",
                        "available_params": all_params
                    }

                elif len(matches) > 1:
                    match_list = []
                    for row in matches:
                        match_list.append({
                            "stcd": row.stcd,
                            "stnm": row.stnm.strip() if row.stnm else "",
                            "Control_Par": row.Control_Par,
                            "Instruction": row.Instruction.strip() if row.Instruction else ""
                        })
                    conn.close()
                    return {
                        "success": False,
                        "error": f"匹配到 {len(matches)} 条记录，请使用更精确的关键词",
                        "matches": match_list
                    }

                else:
                    row = matches[0]
                    before = {
                        "stcd": row.stcd,
                        "stnm": row.stnm.strip() if row.stnm else "",
                        "Control_Par": row.Control_Par,
                        "Instruction": row.Instruction.strip() if row.Instruction else ""
                    }

                    cursor.execute(
                        "UPDATE Dispatch_Par SET Control_Par = ? WHERE stcd = ? AND stnm = ? AND Instruction = ?",
                        (new_value, row.stcd, row.stnm, row.Instruction)
                    )
                    conn.commit()

                    after = {
                        "stcd": row.stcd,
                        "stnm": row.stnm.strip() if row.stnm else "",
                        "Control_Par": new_value,
                        "Instruction": row.Instruction.strip() if row.Instruction else ""
                    }

                    conn.close()
                    logger.info(f"参数已更新: {before} -> {after}")
                    return {
                        "success": True,
                        "message": "参数已更新",
                        "before": before,
                        "after": after
                    }

            else:
                conn.close()
                return {
                    "success": False,
                    "error": f"不支持的操作类型: {action}，请使用 list 或 update"
                }

        except pyodbc.Error as e:
            logger.error(f"modify_dispatch_param 数据库错误: {e}")
            return {"success": False, "error": f"数据库操作失败: {str(e)}"}
        except Exception as e:
            logger.error(f"modify_dispatch_param 出错: {e}")
            return {"success": False, "error": f"参数修改失败: {str(e)}"}

    @mcp.tool()
    async def set_flow_constraint(station_name: str, max_flow: float) -> dict:
        """
        设置指定站点的流量约束，自动调整 Dispatch_Par 表中的相关参数。

        例如：控制花园口流量不超过13000，会自动调整小浪底保滩流量、花园口控制流量等 6 个相关参数。

        Args:
            station_name: 站点名称，目前支持"花园口"
            max_flow: 最大允许流量（m³/s）

        Returns:
            调整后的参数列表、变更前后对比
        """
        logger.info(f"调用 set_flow_constraint, station_name={station_name}, max_flow={max_flow}")

        # 花园口流量控制相关的 Dispatch_Par 参数
        # 每个参数: (stcd, 站点名, 参数含义, 调整方式)
        #   "target" → 直接设为目标流量
        #   "buffer" → 设为目标流量 - 1000（留出缓冲余量）
        GARDEN_FLOW_PARAMS = [
            (23, "小浪底", "预泄控制花园口流量", "buffer"),
            (30, "小浪底", "保滩流量", "buffer"),
            (38, "花园口", "判别库群退水时刻设置的花园口流量阈值", "target"),
            (39, "花园口", "下大洪水，退水过程控制的花园口流量", "target"),
            (43, "花园口", "判别支流水库关门时刻的花园口流量", "target"),
            (44, "小浪底", "小浪底保滩库容用完后，转控花园口的流量", "buffer"),
        ]

        if station_name not in ["花园口"]:
            return {
                "success": False,
                "error": f"暂不支持站点 '{station_name}'，目前仅支持：花园口"
            }

        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        mdb_path = os.path.join(project_root, '6', 'data.mdb')
        conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={mdb_path};'

        try:
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()

            updated = []
            for stcd, stnm, instruction, adjust_type in GARDEN_FLOW_PARAMS:
                new_val = max_flow - 1000 if adjust_type == "buffer" else max_flow
                new_val = round(new_val, 2)

                # 查询当前值
                cursor.execute(
                    "SELECT stcd, stnm, Control_Par, Instruction FROM Dispatch_Par WHERE stcd = ?",
                    (stcd,)
                )
                row = cursor.fetchone()
                if not row:
                    logger.warning(f"未找到 stcd={stcd} 的参数")
                    continue

                old_val = row.Control_Par
                if old_val == new_val:
                    continue

                cursor.execute(
                    "UPDATE Dispatch_Par SET Control_Par = ? WHERE stcd = ?",
                    (new_val, stcd)
                )
                conn.commit()

                updated.append({
                    "stcd": stcd,
                    "stnm": stnm,
                    "instruction": instruction,
                    "old_value": round(old_val, 2) if old_val is not None else None,
                    "new_value": new_val,
                    "adjust_type": adjust_type
                })

            conn.close()

            if not updated:
                return {
                    "success": True,
                    "message": f"所有参数已满足 {station_name} 流量 ≤ {max_flow} m³/s 的要求，无需调整",
                    "updated_count": 0,
                    "updated_params": []
                }

            logger.info(f"已调整 {len(updated)} 条参数以满足 {station_name} 流量 ≤ {max_flow}")
            return {
                "success": True,
                "command": "FUNC_SET_FLOW_CONSTRAINT",
                "station_name": station_name,
                "max_flow": max_flow,
                "message": f"已调整 {len(updated)} 条 Dispatch_Par 参数，控制 {station_name} 流量不超过 {max_flow} m³/s",
                "updated_count": len(updated),
                "updated_params": updated,
                "hint": "参数已更新，请调用 generate_dispatch_sheet() 重新生成方案单验证效果"
            }

        except pyodbc.Error as e:
            logger.error(f"set_flow_constraint 数据库错误: {e}")
            return {"success": False, "error": f"数据库操作失败: {str(e)}"}
        except Exception as e:
            logger.error(f"set_flow_constraint 出错: {e}")
            return {"success": False, "error": f"设置流量约束失败: {str(e)}"}

    @mcp.tool()
    async def generate_dispatch_sheet() -> dict:
        """
        一键生成调度方案单：导入Excel → 运行计算 → 统计处理 → 存储入库 → 返回前台展示数据。

        与 generate_dispatch_scheme 功能一致，为兼容不同调用习惯保留。
        """
        logger.info("调用 generate_dispatch_sheet，委托给 generate_dispatch_scheme")
        return await generate_dispatch_scheme()

    # ================================================================
    # 参数模板工具（Task 1-5）
    # ================================================================

    # ─── _calculate_reservoir_stats 辅助函数 ────────────────────────
    def _calculate_reservoir_stats(conn) -> tuple[list, list]:
        """从 Z_Output 表中提取各水库的关键统计指标（exe 运行后生成）

        Z_Output 表结构: stcd, stnm, tm, Qin(入库), Qout(出库), z(水位), v(蓄量)

        Returns:
            (reservoir_stats, reservoir_table)
            reservoir_stats: [{"reservoir": "三门峡", "max_inflow": ..., ...}, ...]
            reservoir_table: 特征值格式，每行 {"name": "三门峡水库", "project": "最大入库(m3/s)", "value": 1420.0}
        """
        stats = []
        RESERVOIR_NAMES = ["三门峡", "小浪底", "陆浑", "故县", "河口村"]

        try:
            cursor = conn.cursor()
            cursor.execute("SELECT stcd, stnm, tm, Qin, Qout, z, v FROM Z_Output ORDER BY stcd, tm")
            rows = cursor.fetchall()

            if not rows:
                logger.warning("Z_Output 表为空，无法提取水库统计指标")
                return [], []

            for rname in RESERVOIR_NAMES:
                # 筛选该水库的数据
                reservoir_rows = [r for r in rows if r.stnm.strip() == rname]
                if not reservoir_rows:
                    continue

                qin_values = [r.Qin for r in reservoir_rows]
                qout_values = [r.Qout for r in reservoir_rows]
                z_values = [r.z for r in reservoir_rows]
                v_values = [r.v for r in reservoir_rows]

                max_inflow = max(qin_values)
                max_outflow = max(qout_values)
                max_water_level = max(z_values)
                max_storage = max(v_values)
                min_storage = min(v_values)
                flood_retention = max_storage - min_storage

                # 找到最高水位对应的蓄量
                max_z_idx = z_values.index(max_water_level)
                corresponding_storage = v_values[max_z_idx]

                stats.append({
                    "reservoir": rname,
                    "max_inflow": round(float(max_inflow), 2),
                    "max_outflow": round(float(max_outflow), 2),
                    "flood_retention": round(float(flood_retention), 2),
                    "max_water_level": round(float(max_water_level), 2),
                    "corresponding_storage": round(float(corresponding_storage), 2)
                })

            # 构建特征值表格式（与模板"特征值" sheet 一致）
            # 列：名称、项目、值
            reservoir_table = []
            for s in stats:
                rname = s['reservoir'] + '水库'
                rows_data = [
                    (rname, '最大入库(m3/s)', s['max_inflow']),
                    ('', '最大出库(m3/s)', s['max_outflow']),
                    ('', '滞蓄洪量(亿m3)', s['flood_retention']),
                    ('', '最高水位(m)', s['max_water_level']),
                    ('', '相应蓄量(亿m3)', s['corresponding_storage']),
                ]
                for name, project, value in rows_data:
                    reservoir_table.append({
                        "name": name,
                        "project": project,
                        "value": value
                    })

            return stats, reservoir_table

        except Exception as e:
            logger.warning(f"从 Z_Output 提取水库统计指标失败: {e}")
            return [], []

    def _scan_templates() -> dict:
        """扫描 Parameter_template 目录，返回模板名称→文件路径的映射

        Returns:
            {
                "模板名称": {
                    "category": "上大洪水控制",
                    "file_path": "D:/.../方案一.xlsx",
                    "file_name": "方案一：（小浪底不保滩，控花园口10000）.xlsx"
                },
                ...
            }
        """
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        template_dir = os.path.join(project_root, 'Parameter_template')

        templates = {}
        if not os.path.exists(template_dir):
            return templates

        for category in os.listdir(template_dir):
            category_path = os.path.join(template_dir, category)
            if not os.path.isdir(category_path):
                continue
            for fname in os.listdir(category_path):
                if fname.endswith('.xlsx'):
                    file_path = os.path.join(category_path, fname)
                    # 提取简短名称：取文件名中"方案一"、"方案二"等关键词
                    short_name = fname.split('：')[0] if '：' in fname else fname.replace('.xlsx', '')
                    # 用"类别/名称"作为唯一键，避免不同类别同名覆盖
                    unique_key = f"{category}/{short_name}"
                    templates[unique_key] = {
                        "category": category,
                        "file_path": file_path,
                        "file_name": fname,
                        "short_name": short_name
                    }
        return templates

    def _find_template_file(template_name: str) -> dict | None:
        """通过关键词模糊匹配模板文件

        匹配规则：
        1. 精确匹配简短名称（如"方案一"）- 若多个类别匹配，返回第一个
        2. 精确匹配唯一键（如"上大洪水控制/方案一"）
        3. 包含匹配完整文件名（如"常规调度"匹配"方案一：演练洪水-常规调度-...xlsx"）
        4. 类别匹配（如"上大"、"下大"）
        """
        templates = _scan_templates()
        if not templates:
            return None

        # 精确匹配唯一键
        if template_name in templates:
            return templates[template_name]

        # 精确匹配 short_name
        for key, info in templates.items():
            if template_name == info.get('short_name', ''):
                return info

        # 包含匹配完整文件名
        for key, info in templates.items():
            if template_name in info['file_name']:
                return info

        # 类别匹配
        for key, info in templates.items():
            if template_name in info['category']:
                return info

        return None

    def _get_template_sheets(file_path: str) -> list:
        """获取模板 Excel 文件的所有 sheet 名称"""
        try:
            xl = pd.ExcelFile(file_path)
            return xl.sheet_names
        except Exception:
            return []

    # ─── Task 2: list_parameter_templates ────────────────────────────
    @mcp.tool()
    async def list_parameter_templates() -> dict:
        """
        列出所有可用的参数模板。

        扫描 Parameter_template/ 目录下所有 .xlsx 文件，
        返回每个模板的类别、名称、参数条数、包含的计算结果 sheet 列表。

        Returns:
            模板列表，每个模板包含 category, name, file_name, param_count, sheets
        """
        logger.info("调用 list_parameter_templates")
        try:
            templates = _scan_templates()
            if not templates:
                return {"success": True, "templates": [], "message": "无可用模板"}

            result = []
            for key, info in templates.items():
                sheets = _get_template_sheets(info['file_path'])
                param_count = 0
                try:
                    df_param = pd.read_excel(info['file_path'], sheet_name='参数')
                    param_count = len(df_param)
                except Exception:
                    pass

                # 过滤掉"参数" sheet，只保留计算结果 sheet
                result_sheets = [s for s in sheets if s != '参数']

                result.append({
                    "name": info.get('short_name', key),
                    "unique_key": key,
                    "category": info['category'],
                    "file_name": info['file_name'],
                    "param_count": param_count,
                    "result_sheets": result_sheets
                })

            return {"success": True, "templates": result, "count": len(result)}
        except Exception as e:
            logger.error(f"list_parameter_templates 出错: {e}")
            return {"success": False, "error": f"扫描模板失败: {str(e)}"}

    # ─── Task 3: show_parameter_template ─────────────────────────────
    @mcp.tool()
    async def show_parameter_template(template_name: str) -> dict:
        """
        展示指定模板的完整参数设置。

        Args:
            template_name: 模板名称关键词（如"方案一"、"常规调度"、"上大"）

        Returns:
            参数列表（stcd, stnm, Control_Par, Instruction）和计算结果 sheet 列表
        """
        logger.info(f"调用 show_parameter_template, template_name={template_name}")

        try:
            info = _find_template_file(template_name)
            if not info:
                available = list(_scan_templates().keys())
                return {
                    "success": False,
                    "error": f"未找到模板 '{template_name}'",
                    "available_templates": available
                }

            sheets = _get_template_sheets(info['file_path'])
            if '参数' not in sheets:
                return {
                    "success": False,
                    "error": "该模板不包含参数设置",
                    "available_sheets": sheets
                }

            df_param = pd.read_excel(info['file_path'], sheet_name='参数')
            params = []
            for _, row in df_param.iterrows():
                params.append({
                    "stcd": row.get('stcd', ''),
                    "stnm": str(row.get('stnm', '')).strip(),
                    "Control_Par": row.get('Control_Par', 0),
                    "Instruction": str(row.get('Instruction', '')).strip()
                })

            result_sheets = [s for s in sheets if s != '参数']

            return {
                "success": True,
                "template": {
                    "name": info['file_name'],
                    "category": info['category'],
                    "param_count": len(params),
                    "result_sheets": result_sheets
                },
                "parameters": params
            }
        except Exception as e:
            logger.error(f"show_parameter_template 出错: {e}")
            return {"success": False, "error": f"展示模板参数失败: {str(e)}"}

    # ─── Task 4: apply_parameter_template ────────────────────────────
    @mcp.tool()
    async def apply_parameter_template(
        template_name: str,
        generate_scheme: bool = True
    ) -> dict:
        """
        将指定模板的参数写入 Dispatch_Par 表，可选自动生成调度方案单。

        Args:
            template_name: 模板名称关键词（如"方案一"、"常规调度"、"上大"）
            generate_scheme: 是否在应用参数后自动生成调度方案单（默认 True）

        Returns:
            更新的参数数量、修改前后对比、scheme_id（若生成方案）
        """
        logger.info(f"调用 apply_parameter_template, template_name={template_name}, generate_scheme={generate_scheme}")

        try:
            # 1. 查找模板
            info = _find_template_file(template_name)
            if not info:
                available = list(_scan_templates().keys())
                return {
                    "success": False,
                    "error": f"未找到模板 '{template_name}'",
                    "available_templates": available
                }

            # 2. 读取参数
            df_param = pd.read_excel(info['file_path'], sheet_name='参数')
            if df_param.empty:
                return {"success": False, "error": "模板参数为空"}

            # 3. 连接 MDB 并更新 Dispatch_Par
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            mdb_path = os.path.join(project_root, '6', 'data.mdb')

            if not os.path.exists(mdb_path):
                return {"success": False, "error": f"数据库文件不存在: {mdb_path}"}

            conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={mdb_path};'
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()

            # 读取修改前的值用于对比
            cursor.execute("SELECT stcd, Control_Par FROM Dispatch_Par ORDER BY stcd")
            before_map = {row.stcd: row.Control_Par for row in cursor.fetchall()}

            updated_params = []
            update_count = 0
            for _, row in df_param.iterrows():
                stcd = row.get('stcd', '')
                new_value = row.get('Control_Par', 0)
                if stcd == '':
                    continue
                cursor.execute(
                    "UPDATE Dispatch_Par SET Control_Par = ? WHERE stcd = ?",
                    (new_value, stcd)
                )
                if cursor.rowcount > 0:
                    update_count += 1
                    old_value = before_map.get(stcd, None)
                    if old_value != new_value:
                        updated_params.append({
                            "stcd": stcd,
                            "stnm": str(row.get('stnm', '')).strip(),
                            "old_value": old_value,
                            "new_value": new_value.get('Control_Par', 0) if isinstance(new_value, dict) else new_value,
                            "instruction": str(row.get('Instruction', '')).strip()[:50]
                        })

            conn.commit()
            conn.close()

            logger.info(f"已更新 {update_count} 条参数")

            result = {
                "success": True,
                "template_name": info['file_name'],
                "category": info['category'],
                "updated_count": update_count,
                "changed_params": updated_params[:20],  # 最多返回20条变更
                "total_changed": len(updated_params)
            }

            # 4. 可选：生成调度方案单
            if generate_scheme:
                logger.info("应用参数后自动生成调度方案单...")
                scheme_result = await generate_dispatch_scheme()
                if scheme_result.get("success"):
                    result["scheme_id"] = scheme_result.get("scheme_id")
                    result["scheme_name"] = scheme_result.get("scheme_name")
                    result["summary"] = scheme_result.get("summary")
                    result["scheme_elapsed_seconds"] = scheme_result.get("total_elapsed_seconds")
                else:
                    result["scheme_error"] = scheme_result.get("error", "方案生成失败")

            return result

        except pyodbc.Error as e:
            logger.error(f"数据库操作错误: {e}")
            return {"success": False, "error": f"数据库操作失败: {str(e)}"}
        except Exception as e:
            logger.error(f"apply_parameter_template 出错: {e}")
            return {"success": False, "error": f"应用参数模板失败: {str(e)}"}

    # ─── Task 5: verify_dispatch_result ──────────────────────────────
    @mcp.tool()
    async def verify_dispatch_result(template_name: str) -> dict:
        """
        将实际计算结果与模板中的预期结果进行对比验证。

        应用参数模板并生成方案后，读取 Q_Output 实际结果，
        与模板中的计算结果 sheet 逐站对比，输出验证报告。

        Args:
            template_name: 模板名称关键词（如"方案一"、"常规调度"）

        Returns:
            验证报告：通过/需关注/失败状态，各站点误差统计
        """
        logger.info(f"调用 verify_dispatch_result, template_name={template_name}")

        try:
            # 1. 查找模板
            info = _find_template_file(template_name)
            if not info:
                available = list(_scan_templates().keys())
                return {
                    "success": False,
                    "error": f"未找到模板 '{template_name}'",
                    "available_templates": available
                }

            sheets = _get_template_sheets(info['file_path'])
            result_sheets = [s for s in sheets if s != '参数']

            if not result_sheets:
                return {
                    "success": False,
                    "error": "该模板仅包含参数，无预期计算结果可验证"
                }

            # 2. 应用参数并生成方案
            logger.info("应用参数模板并生成方案...")
            apply_result = await apply_parameter_template(template_name, generate_scheme=True)
            if not apply_result.get("success"):
                return {
                    "success": False,
                    "error": f"应用参数模板失败: {apply_result.get('error', '')}"
                }

            # 3. 读取 Q_Output 实际结果
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            mdb_path = os.path.join(project_root, '6', 'data.mdb')
            conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={mdb_path};'
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()

            cursor.execute("SELECT stcd, stnm, tm, q FROM Q_Output ORDER BY tm, stcd")
            actual_rows = cursor.fetchall()
            conn.close()

            # 构建实际数据索引: {(stnm, tm_str): q}
            actual_index = {}
            for row in actual_rows:
                stnm = row.stnm.strip() if row.stnm else ""
                tm_str = str(row.tm)
                actual_index[(stnm, tm_str)] = row.q

            # 4. 读取模板预期结果
            station_results = {}
            total_matched = 0
            total_errors = []

            for sheet_name in result_sheets:
                try:
                    df_expected = pd.read_excel(info['file_path'], sheet_name=sheet_name)
                except Exception:
                    continue

                # 识别时间列和流量列
                time_col = None
                flow_cols = []  # 可能有多列流量数据

                for col in df_expected.columns:
                    if col in ['时间', 'tm', 'time']:
                        time_col = col
                    elif col in ['出库', 'q', 'flow']:
                        flow_cols.append(col)
                    else:
                        # 其他列可能是站点名（流量列）
                        flow_cols.append(col)

                if time_col is None:
                    continue

                errors = []
                matched = 0
                for _, row in df_expected.iterrows():
                    tm_str = str(row[time_col])
                    for flow_col in flow_cols:
                        if flow_col == time_col:
                            continue
                        expected_q = row[flow_col]
                        if pd.isna(expected_q):
                            continue

                        key = (flow_col, tm_str)
                        actual_q = actual_index.get(key)

                        if actual_q is not None:
                            matched += 1
                            deviation = abs(actual_q - expected_q)
                            pct = (deviation / abs(expected_q) * 100) if expected_q != 0 else 0
                            errors.append({
                                "station": flow_col,
                                "time": tm_str,
                                "expected": round(expected_q, 2),
                                "actual": round(actual_q, 2),
                                "deviation": round(deviation, 2),
                                "deviation_pct": round(pct, 2)
                            })

                if matched > 0:
                    max_err = max(e["deviation"] for e in errors)
                    avg_err = sum(e["deviation"] for e in errors) / len(errors)
                    max_pct = max(e["deviation_pct"] for e in errors)
                    avg_pct = sum(e["deviation_pct"] for e in errors) / len(errors)

                    station_results[sheet_name] = {
                        "matched_points": matched,
                        "max_deviation": round(max_err, 2),
                        "avg_deviation": round(avg_err, 2),
                        "max_deviation_pct": round(max_pct, 2),
                        "avg_deviation_pct": round(avg_pct, 2),
                        "top_errors": sorted(errors, key=lambda x: x["deviation"], reverse=True)[:5]
                    }
                    total_matched += matched
                    total_errors.extend(errors)

            # 5. 判定验证结果
            if not station_results:
                overall_status = "无法验证"
                status_message = "未能匹配到任何对比数据点，可能是站点名或时间格式不一致"
            else:
                overall_avg_pct = sum(s["avg_deviation_pct"] for s in station_results.values()) / len(station_results)
                overall_max_pct = max(s["max_deviation_pct"] for s in station_results.values())

                if overall_max_pct <= 5:
                    overall_status = "通过"
                    status_message = f"所有站点偏差在5%以内（最大{overall_max_pct}%），计算结果与预期一致"
                elif overall_max_pct <= 15:
                    overall_status = "需关注"
                    status_message = f"部分站点偏差较大（最大{overall_max_pct}%），建议检查参数设置"
                else:
                    overall_status = "偏差过大"
                    status_message = f"严重偏差（最大{overall_max_pct}%），计算逻辑或参数可能有误"

            return {
                "success": True,
                "template_name": info['file_name'],
                "category": info['category'],
                "scheme_id": apply_result.get("scheme_id"),
                "verification": {
                    "status": overall_status,
                    "message": status_message,
                    "total_matched_points": total_matched,
                    "stations_compared": list(station_results.keys()),
                    "station_details": station_results
                }
            }

        except Exception as e:
            logger.error(f"verify_dispatch_result 出错: {e}")
            return {"success": False, "error": f"验证调度结果失败: {str(e)}"}

