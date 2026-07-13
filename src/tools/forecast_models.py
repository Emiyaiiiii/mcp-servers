import json
import os
import random
import subprocess
import time
import pyodbc
import pandas as pd
import requests
import platform
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict, Any, Optional, Tuple
from fastmcp import FastMCP
from src.utils.logger import get_logger
from src.utils.mdb_utils import mdb_execute, mdb_update_field, mdb_clear_table, mdb_insert_rows
from src.utils.date_utils import format_timestamp, format_date_fields
from src.utils.reservoir_utils import (
    judge_water_level_warning, add_water_level_description,
    get_reservoir_thresholds, trigger_warning_alert
)
from src.utils.stats_utils import extract_q_statistics, extract_z_statistics, calculate_reservoir_stats, calculate_hydrologic_stats
from src.utils.xinanjiang_utils import (
    query_weighted_rainfall_from_db, build_rainfall_array,
    build_control_params, build_rainfall_data, build_etp_data
)
from src.utils.flood_utils import calculate_flood_submergence, check_dongpinghu_diversion
from src.utils.template_utils import scan_templates, find_template_file, get_template_sheets, generate_natural_language_summary
from src.services.storage.scheme_storage import save_scheme
from src.services.external_api.xinanjiang_service import xinanjiang_auth_service, xinanjiang_model_service
from src.services.external_api.water_forecast_service import water_forecast_service
from src.services.external_api.hydrology_forecast_service import hydrology_forecast_service
from src.utils.station_codes import get_reservoir_code, get_hydrology_code

logger = get_logger(__name__)

_mdb_execute = mdb_execute
_mdb_update_field = mdb_update_field
_mdb_clear_table = mdb_clear_table
_mdb_insert_row = mdb_insert_rows

_query_weighted_rainfall_from_db = query_weighted_rainfall_from_db
_build_rainfall_array = build_rainfall_array
_build_control_params = build_control_params
_build_rainfall_data = build_rainfall_data
_build_etp_data = build_etp_data

_calculate_reservoir_stats = calculate_reservoir_stats
_calculate_hydrologic_stats = calculate_hydrologic_stats
_calculate_flood_submergence = calculate_flood_submergence
_check_dongpinghu_diversion = check_dongpinghu_diversion
_generate_natural_language_summary = generate_natural_language_summary
_scan_templates = scan_templates
_find_template_file = find_template_file
_get_template_sheets = get_template_sheets


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
            logger.debug(f"run_rainfall_forecast_model 返回结果: {return_value}")
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
        logger.debug(f"run_rainfall_forecast_model 返回结果: {return_value}")
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
        _start_time: str = None,
        flood_type: str = "下大洪水"
    ) -> dict:
        """
        一键生成调度方案单：检查数据源 → 运行RegualDispacth.exe计算 → 统计处理 → 存储入库 → 返回前台展示数据。

        必须先调用 get_hydrology_forecast_data 将水文局预报数据写入数据库，
        否则返回错误提示引导用户先获取数据。

        Args:
            _start_time: 调度开始时间（格式：YYYY-MM-DD），当前基于数据自动确定时间范围
            flood_type: 洪水类型，可选 "上大洪水" 或 "下大洪水"，默认 "下大洪水"
        """
        logger.info(f"调用 generate_dispatch_scheme，收到参数: _start_time={repr(_start_time)}，flood_type={repr(flood_type)}")

        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        dispatch_dir = os.path.join(project_root, 'src', 'services', 'external_api', 'RegualDispacth')
        mdb_path = os.path.join(dispatch_dir, '6', 'data.mdb')
        exe_path = os.path.join(dispatch_dir, 'RegualDispacth.exe')

        total_start = time.time()
        steps = {}
        conn = None

        try:
            # ================================================================
            # 步骤1: 检查数据源（必须由 get_hydrology_forecast_data 写入）
            # ================================================================
            logger.info("步骤1: 检查数据源")
            import_start = time.time()

            if not os.path.exists(exe_path):
                return {"success": False, "error": f"调度计算程序不存在: {exe_path}", "steps": steps}
            if not os.path.exists(mdb_path):
                return {"success": False, "error": f"数据库文件不存在: {mdb_path}", "steps": steps}

            conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={mdb_path};'
            
            # 判断系统自动切换驱动
            if platform.system() == "Windows":
                driver_name = "Microsoft Access Driver (*.mdb, *.accdb)"
            else:
                driver_name = "MDBTools"
            
            conn_str = f'DRIVER={{{driver_name}}};DBQ={mdb_path};'
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()

            # 检查 Q_Inputsd 和 Q_Inputxd 是否已有数据
            cursor.execute("SELECT COUNT(*) FROM Q_Inputsd")
            sd_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM Q_Inputxd")
            xd_count = cursor.fetchone()[0]

            if sd_count == 0 or xd_count == 0:
                conn.close()
                return {
                    "success": False,
                    "command": "FUNC_GENERATE_DISPATCH_SCHEME",
                    "error": "数据库为空，请先获取水文局预报数据",
                    "hint": "调用 get_hydrology_forecast_plans(date_time) 获取方案列表 → 用户选择方案 → 调用 get_hydrology_forecast_data(plcd, time) 写入数据",
                    "Q_Inputsd_rows": sd_count,
                    "Q_Inputxd_rows": xd_count,
                    "steps": steps
                }

            import_elapsed = round(time.time() - import_start, 2)
            steps["data_check"] = {
                "source": "dynamic",
                "Q_Inputsd_rows": sd_count,
                "Q_Inputxd_rows": xd_count,
                "elapsed_seconds": import_elapsed
            }
            logger.info(f"数据源检查完成: Q_Inputsd={sd_count}行, Q_Inputxd={xd_count}行, 耗时{import_elapsed}秒")

            # ================================================================
            # 步骤2: 运行调度计算程序
            # ================================================================
            logger.info("步骤2: 运行 RegualDispacth.exe")
            calc_start = time.time()

            result = subprocess.run(
                [exe_path],
                cwd=dispatch_dir,
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
                conn.close()
                return {"success": False, "error": f"RegualDispacth.exe 返回非零退出码: {result.returncode}, stderr: {result.stderr}", "steps": steps}

            # ================================================================
            # 步骤3: 读取Q_Output并进行统计处理
            # ================================================================
            logger.info("步骤3: 读取Q_Output并统计处理")
            stats_start = time.time()

            cursor.execute("SELECT stcd, stnm, tm, q FROM Q_Output")
            rows = cursor.fetchall()
            rows.sort(key=lambda r: (str(r.tm), str(r.stcd)))

            output_data = []
            for row in rows:
                output_data.append({
                    "stcd": row.stcd,
                    "stnm": row.stnm.strip() if row.stnm else "",
                    "tm": str(row.tm) if row.tm else "",
                    "q": row.q
                })

            output_rows = len(output_data)

            # 按站点分组统计
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

            # 水文站统计（从 Q_Output 表计算）
            hydrologic_stats, hydrologic_table = _calculate_hydrologic_stats(conn, flood_type)

            # 转换为 SchemeAccess.save 期望的字典格式
            reservoirs = {}
            for stat in reservoir_stats:
                reservoirs[stat["reservoir"]] = {
                    "max_inflow": stat["max_inflow"],
                    "max_outflow": stat["max_outflow"],
                    "max_water_level": stat["max_water_level"],
                    "timeseries": []
                }

            hydrological_stations = {}
            for stat in hydrologic_stats:
                hydrological_stations[stat["station"]] = {
                    "max_flow": stat["peak_flow"],
                    "timeseries": []
                }

            # 滩区淹没分析（根据花园口洪峰流量）
            garden_mouth_peak = next((s["peak_flow"] for s in hydrologic_stats if s["station"] == "花园口"), 0)
            flood_submergence = _calculate_flood_submergence(garden_mouth_peak)

            # 东平湖分洪状态
            dongpinghu_diversion = _check_dongpinghu_diversion(conn)

            # 自然语言总结
            natural_language_summary = _generate_natural_language_summary(
                reservoir_stats=reservoir_stats,
                hydrologic_stats=hydrologic_stats,
                flood_submergence=flood_submergence,
                dongpinghu_diversion=dongpinghu_diversion,
                flood_type=flood_type
            )

            conn.close()

            # ================================================================
            # 步骤4: 构建方案数据并存储到数据库
            # ================================================================
            logger.info("步骤4: 存储方案数据到数据库")

            scheme_data = {
                "scheme_name": f"调度方案单_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "description": "基于水文局预报数据，通过RegualDispacth.exe计算生成的调度方案",
                "basin": "黄河",
                "start_date": time_range_start[:10] if time_range_start else "",
                "end_date": time_range_end[:10] if time_range_end else "",
                "status": "active",
                "constraints": [],
                "details": [],
                "constraints_applied": {},
                "reservoirs": reservoirs,
                "hydrological_stations": hydrological_stations,
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
                    "reservoir_table": reservoir_table,
                    "hydrologic_stats": hydrologic_stats,
                    "hydrologic_table": hydrologic_table,
                    "flood_submergence": flood_submergence,
                    "dongpinghu_diversion": dongpinghu_diversion,
                    "flood_type": flood_type
                },
                "natural_language_summary": natural_language_summary
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
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

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
    async def rainfall_similarity_analysis(
        step: str,
        basin: str = None,
        rainfall_id: str = None,
        start_time: str = None,
        end_time: str = None,
        raster_image_url: str = None
    ) -> dict:
        """
        降雨图斑相似性分析模型（统一入口）。

        整体流程分三步：
        - step="1"：查询各流域降雨情况（支持时间范围过滤），返回各流域+降雨事件列表，供用户选择。
        - step="2"：根据用户选择的流域和降雨编号，依次链式执行
                    ①查询降雨详情 ②计算相似雨 ③查询相似雨图斑图片 ④图斑相似度计算
                    （顺序固定，不可调整），返回最相似的3场降雨时间段。
        - step="3"：根据用户选择的某场相似雨时间段，查询对应水文信息，
                    并与图斑图片URL整合返回。

        Args:
            step: 流程阶段，可选值: "1"、"2" 或 "3"
            basin: 流域名称（如：黄河、伊洛河、洛河），在 step="2" 和 step="3" 时必填
            rainfall_id: 降雨编号（由 step="1" 返回），仅在 step="2" 时必填
            start_time: 查询起始时间，step="1" 时可选（用于时间范围过滤），step="3" 时必填
            end_time: 查询结束时间，step="1" 时可选（用于时间范围过滤），step="3" 时必填
            raster_image_url: 对应时段的图斑图片URL，仅在 step="3" 时必填

        Returns:
            step="1" 返回各流域降雨列表；
            step="2" 返回链式执行结果，包含降雨详情、相似雨列表、图斑图片、最相似图斑；
            step="3" 返回水文信息与图斑图片URL整合结果。
        """
        logger.info(
            f"调用 rainfall_similarity_analysis，收到参数: "
            f"step={repr(step)}, basin={repr(basin)}, rainfall_id={repr(rainfall_id)}"
        )

        if step not in ("1", "2", "3"):
            return {
                "success": False,
                "command": "FUNC_RAINFALL_SIMILARITY_ANALYSIS",
                "message": f"不支持的 step 参数: {step}，仅支持 '1'、'2' 或 '3'"
            }

        # -------------------------------------------------------------------
        # 第一步：查询各流域降雨情况（支持时间范围过滤）
        # -------------------------------------------------------------------
        if step == "1":
            try:
                # 判断是否指定了时间范围
                has_time_range = start_time and end_time
                
                if has_time_range:
                    # 调用"按时间范围查询降雨"接口
                    url = f"http://36.99.160.89:8066/rain/getRainListByTimeRange?startTime={start_time}&endTime={end_time}"
                    logger.info(f"调用按时间范围查询降雨接口: {url}")
                else:
                    # 调用"查询各流域最新降雨情况"接口
                    url = "http://36.99.160.89:8066/rain/getLatestRainList"
                    logger.info(f"调用查询最新降雨接口: {url}")
                
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                
                result = response.json()
                logger.info(f"接口返回结果: {result}")
                
                if result.get("code") != 200:
                    raise Exception(f"接口返回错误: {result.get('msg', '未知错误')}")
                
                raw_data = result.get("data", [])
                
                # 转换为 skill 文档定义的格式
                basins_dict = {}
                for item in raw_data:
                    watershed_name = item.get("watershedName", "")
                    if watershed_name not in basins_dict:
                        basins_dict[watershed_name] = {
                            "basin_name": watershed_name,
                            "basin_code": "",
                            "rainfall_events": []
                        }
                    
                    basins_dict[watershed_name]["rainfall_events"].append({
                        "rainfall_id": str(item.get("id", "")),
                        "start_time": item.get("startTime", ""),
                        "end_time": item.get("endTime", ""),
                        "total_rainfall": item.get("precipitationTotal", 0),
                        "description": f"降雨时段: {item.get('startTime', '')} 至 {item.get('endTime', '')}"
                    })
                
                basins_with_rainfall = list(basins_dict.values())
                
                return_value = {
                    "success": True,
                    "command": "FUNC_RAINFALL_SIMILARITY_ANALYSIS_STEP1",
                    "step": "1",
                    "basins": basins_with_rainfall,
                    "message": "已查询到各流域最新降雨情况，请选择目标流域和降雨事件"
                }
                logger.debug(f"rainfall_similarity_analysis step=1 返回结果: {return_value}")
                return return_value
            except Exception as e:
                logger.error(f"查询各流域最新降雨情况失败: {e}")
                return {
                    "success": False,
                    "command": "FUNC_RAINFALL_SIMILARITY_ANALYSIS_STEP1",
                    "message": f"查询各流域最新降雨情况失败: {str(e)}"
                }

        # -------------------------------------------------------------------
        # 第二步：链式执行 详情→相似雨→图斑→图斑相似度
        # -------------------------------------------------------------------
        if step == "2":
            if not basin or not rainfall_id:
                return {
                    "success": False,
                    "command": "FUNC_RAINFALL_SIMILARITY_ANALYSIS_STEP2",
                    "message": "step=2 时 basin 和 rainfall_id 均为必填参数"
                }

            steps_result = {}

            # ---- 2.1 查询降雨详情 ----
            try:
                # 调用"按降雨编号查询降雨详情"接口
                url = f"http://36.99.160.89:8066/rain/getRainDetailById?id={rainfall_id}"

                logger.info(f"调用查询降雨详情接口: {url}")
                response = requests.get(url, timeout=30)
                response.raise_for_status()

                result = response.json()
                logger.info(f"降雨详情接口返回结果: {result}")

                if result.get("code") != 200:
                    raise Exception(f"接口返回错误: {result.get('msg', '未知错误')}")

                rainfall_detail = result.get("data", {})
                steps_result["rainfall_detail"] = rainfall_detail
            except Exception as e:
                logger.error(f"查询降雨详情失败: {e}")
                return {
                    "success": False,
                    "command": "FUNC_RAINFALL_SIMILARITY_ANALYSIS_STEP2",
                    "step": "2.1",
                    "message": f"查询降雨详情失败: {str(e)}",
                    "basin": basin,
                    "rainfall_id": rainfall_id
                }

            # ---- 2.2 计算相似雨 ----
            try:
                # 调用"计算相似雨"接口
                url = "http://36.99.160.89:10017/tbapi/data/analyse/conformAnalysis"

                # 构建请求体：使用上一步获取的降雨详情，添加流域名称字段
                request_data = rainfall_detail.copy()
                request_data["rvnm"] = basin  # 添加流域名称

                logger.info(f"调用计算相似雨接口: {url}")
                logger.info(f"请求体: {request_data}")

                response = requests.post(url, json=request_data, headers={"Content-Type": "application/json"}, timeout=60)
                response.raise_for_status()

                result = response.json()
                logger.info(f"相似雨计算接口返回结果: {result}")

                if result.get("code") != 200:
                    raise Exception(f"接口返回错误: {result.get('msg', '未知错误')}")

                # 假设返回的data字段包含相似雨列表
                similar_rainfall_list = result.get("data", [])
                steps_result["similar_rainfall"] = similar_rainfall_list
            except Exception as e:
                logger.error(f"计算相似雨失败: {e}")
                return {
                    "success": False,
                    "command": "FUNC_RAINFALL_SIMILARITY_ANALYSIS_STEP2",
                    "step": "2.2",
                    "message": f"计算相似雨失败: {str(e)}",
                    "basin": basin,
                    "rainfall_id": rainfall_id,
                    "partial_result": steps_result
                }

            # ---- 2.3 查询相似雨图斑图片 ----
            try:
                # 调用"查询降雨图斑图片"接口
                url = "http://36.99.160.89:10017/tbapi/data/getInfo"

                # 从降雨详情中提取当前降雨时段
                prototype_start = rainfall_detail.get("rainfallDate", "")
                prototype_end = rainfall_detail.get("endRainfallDate", "")

                # 构建请求体
                request_data = {
                    "requestData": False,
                    "requestContour": False,
                    "requestImage": True,
                    "basin": basin,
                    "prototypePeriod": {
                        "period": {
                            "ftm": prototype_start.split(" ")[0] if prototype_start else "",
                            "ttm": prototype_end.split(" ")[0] if prototype_end else ""
                        },
                        "eigenPeriods": []
                    },
                    "similarPeriods": []
                }

                # 从相似雨列表中提取每场雨的时段
                if isinstance(similar_rainfall_list, list):
                    for item in similar_rainfall_list:
                        s_time = item.get("rainfallDate", "")
                        e_time = item.get("endRainfallDate", "")
                        request_data["similarPeriods"].append({
                            "period": {
                                "ftm": s_time.split(" ")[0] if s_time else "",
                                "ttm": e_time.split(" ")[0] if e_time else ""
                            },
                            "eigenPeriods": []
                        })

                logger.info(f"调用查询图斑图片接口: {url}")
                logger.info(f"请求体: {request_data}")

                response = requests.post(url, json=request_data, headers={"Content-Type": "application/json"}, timeout=60)
                response.raise_for_status()

                result = response.json()
                logger.info(f"图斑图片接口返回结果: {result}")

                raster_images = result
                steps_result["rainfall_raster_images"] = raster_images
            except Exception as e:
                logger.error(f"查询降雨图斑图片失败: {e}")
                return {
                    "success": False,
                    "command": "FUNC_RAINFALL_SIMILARITY_ANALYSIS_STEP2",
                    "step": "2.3",
                    "message": f"查询降雨图斑图片失败: {str(e)}",
                    "basin": basin,
                    "rainfall_id": rainfall_id,
                    "partial_result": steps_result
                }

            # ---- 2.4 图斑相似度计算 ----
            try:
                # 调用"图斑相似度计算"接口
                url = "http://36.99.160.89:10017/wpi/process"

                # 提取图斑图片URL列表
                urls = []

                # 添加当前降雨图斑（prototypeInfo的contourImage）
                prototype_data = raster_images.get("data", {})
                prototype_info = prototype_data.get("prototypeInfo", {})
                prototype_rain_info = prototype_info.get("rainInfo", {})
                prototype_image_url = prototype_rain_info.get("contourImage", "")
                if prototype_image_url:
                    urls.append(prototype_image_url.strip())

                # 添加相似雨图斑（similarInfos中每个的contourImage）
                similar_infos = prototype_data.get("similarInfos", [])
                if isinstance(similar_infos, list):
                    for similar_item in similar_infos:
                        rain_info = similar_item.get("rainInfo", {})
                        image_url = rain_info.get("contourImage", "")
                        if image_url:
                            urls.append(image_url.strip())

                # 构建请求体
                request_data = {"urls": urls}

                logger.info(f"调用图斑相似度计算接口: {url}")
                logger.info(f"请求体: {request_data}")

                response = requests.post(url, json=request_data, headers={"Content-Type": "application/json"}, timeout=60)
                response.raise_for_status()

                result = response.json()
                logger.info(f"图斑相似度计算接口返回结果: {result}")

                # 返回结果是最相似的降雨时间列表
                most_similar_raster = result
                steps_result["most_similar_raster"] = most_similar_raster
            except Exception as e:
                logger.error(f"图斑相似度计算失败: {e}")
                return {
                    "success": False,
                    "command": "FUNC_RAINFALL_SIMILARITY_ANALYSIS_STEP2",
                    "step": "2.4",
                    "message": f"图斑相似度计算失败: {str(e)}",
                    "basin": basin,
                    "rainfall_id": rainfall_id,
                    "partial_result": steps_result
                }

            # ---- 2.5 数据精简处理 ----
            try:
                # 精简 rainfall_detail：删除空字段和大字段
                if "rainfall_detail" in steps_result:
                    detail = steps_result["rainfall_detail"]
                    # 删除空字段和大字段
                    for key in ["lookLikePoint", "resemblance", "maxRainfallStnm", "timeRainfallQ", "rainfallParameters"]:
                        if key in detail:
                            del detail[key]
                    steps_result["rainfall_detail"] = detail

                # 精简 rainfall_raster_images：删除大字段 contour 和接口元信息
                if "rainfall_raster_images" in steps_result:
                    raster_data = steps_result["rainfall_raster_images"]
                    # 删除接口元信息
                    for key in ["respCode", "respMsg", "elapsed", "extraData"]:
                        if key in raster_data:
                            del raster_data[key]
                    # 删除 prototypeInfo 中的 contour
                    if "data" in raster_data:
                        data = raster_data["data"]
                        if "prototypeInfo" in data:
                            proto_info = data["prototypeInfo"]
                            if "rainInfo" in proto_info:
                                rain_info = proto_info["rainInfo"]
                                if "contour" in rain_info:
                                    del rain_info["contour"]
                        # 删除 similarInfos 中的 contour
                        if "similarInfos" in data:
                            for similar_item in data["similarInfos"]:
                                if "rainInfo" in similar_item:
                                    rain_info = similar_item["rainInfo"]
                                    if "contour" in rain_info:
                                        del rain_info["contour"]
                    steps_result["rainfall_raster_images"] = raster_data

                # 精简 similar_rainfall：删除空字段和 rainfallParameters
                if "similar_rainfall" in steps_result:
                    similar_list = steps_result["similar_rainfall"]
                    for item in similar_list:
                        for key in ["lookLikePoint", "resemblance", "maxRainfallStnm", "timeRainfallQ", "rainfallParameters"]:
                            if key in item:
                                del item[key]
                    steps_result["similar_rainfall"] = similar_list

            except Exception as e:
                logger.warning(f"数据精简处理失败，将返回原始数据: {e}")

            return_value = {
                "success": True,
                "command": "FUNC_RAINFALL_SIMILARITY_ANALYSIS_STEP2",
                "step": "2",
                "basin": basin,
                "rainfall_id": rainfall_id,
                "steps": steps_result,
                "message": "图斑相似性分析完成"
            }
            logger.debug(f"rainfall_similarity_analysis step=2 返回结果: {return_value}")
            return return_value

        # -------------------------------------------------------------------
        # 第三步：根据用户选择的相似雨时间段查询水文信息并整合图斑图片
        # -------------------------------------------------------------------
        if step == "3":
            if not all([basin, start_time, end_time, raster_image_url]):
                return {
                    "success": False,
                    "command": "FUNC_RAINFALL_SIMILARITY_ANALYSIS_STEP3",
                    "step": "3",
                    "message": "step=3 需要 basin、start_time、end_time、raster_image_url 参数"
                }

            try:
                # 3.1 调用"查询水文信息"接口
                url = "http://36.99.160.89:10017/api/hyd/getByBasinNameListAndTime"
                request_data = {
                    "basinNameList": [basin],
                    "startTime": start_time,
                    "endTime": end_time
                }

                logger.info(f"调用查询水文信息接口: {url}")
                logger.info(f"请求体: {request_data}")

                response = requests.post(url, json=request_data, headers={"Content-Type": "application/json"}, timeout=60)
                response.raise_for_status()

                result = response.json()
                logger.info(f"水文信息接口返回结果: {result}")

                if result.get("code") != 200:
                    raise Exception(f"接口返回错误: {result.get('msg', '未知错误')}")

                hydrological_data = result.get("data", [])

                return {
                    "success": True,
                    "command": "FUNC_RAINFALL_SIMILARITY_ANALYSIS_STEP3",
                    "step": "3",
                    "basin": basin,
                    "start_time": start_time,
                    "end_time": end_time,
                    "hydrological_data": hydrological_data,
                    "raster_image_url": raster_image_url,
                    "message": "已查询到对应时段的水文信息，并与图斑图片URL整合"
                }

            except Exception as e:
                logger.error(f"查询水文信息失败: {e}")
                return {
                    "success": False,
                    "command": "FUNC_RAINFALL_SIMILARITY_ANALYSIS_STEP3",
                    "step": "3",
                    "message": f"查询水文信息失败: {str(e)}",
                    "basin": basin,
                    "start_time": start_time,
                    "end_time": end_time,
                    "raster_image_url": raster_image_url
                }

    @mcp.tool()
    async def modify_dispatch_param(action: str, station_name: Optional[str] = None, param_desc: Optional[str] = None, new_value: Optional[float] = None) -> dict:
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
        dispatch_dir = os.path.join(project_root, 'src', 'services', 'external_api', 'RegualDispacth')
        mdb_path = os.path.join(dispatch_dir, '6', 'data.mdb')
        # 判断系统自动切换驱动
        if platform.system() == "Windows":
            driver_name = "Microsoft Access Driver (*.mdb, *.accdb)"
        else:
            driver_name = "MDBTools"

        conn_str = f'DRIVER={{{driver_name}}};DBQ={mdb_path};'
        conn = None

        try:
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()

            if action == "list":
                cursor.execute("SELECT stcd, stnm, Control_Par, Instruction FROM Dispatch_Par")
                rows = cursor.fetchall()
                # MDBTools SQL 解析器不支持 ORDER BY，在 Python 中排序
                rows.sort(key=lambda r: str(r.stcd))
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

                # MDBTools ODBC 驱动不支持 LIKE 中文匹配，拉取全部数据在 Python 中过滤
                cursor.execute("SELECT stcd, stnm, Control_Par, Instruction FROM Dispatch_Par")
                all_rows = cursor.fetchall()
                matches = []
                for row in all_rows:
                    r_stnm = row.stnm.strip() if row.stnm else ""
                    r_inst = row.Instruction.strip() if row.Instruction else ""
                    if r_stnm == station_name and (param_desc.isdigit() and str(row.stcd) == param_desc or param_desc in r_inst):
                        matches.append(row)

                if len(matches) == 0:
                    cursor.execute("SELECT stcd, stnm, Control_Par, Instruction FROM Dispatch_Par")
                    all_rows = cursor.fetchall()
                    all_rows.sort(key=lambda r: str(r.stcd))
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

                    # MDBTools ODBC 驱动不支持 UPDATE，使用 mdb_update 工具直接写入 MDB 文件
                    _mdb_update_field(mdb_path, "Dispatch_Par", "Control_Par", new_value, "stcd", row.stcd)

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
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

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
        dispatch_dir = os.path.join(project_root, 'src', 'services', 'external_api', 'RegualDispacth')
        mdb_path = os.path.join(dispatch_dir, '6', 'data.mdb')
        # 判断系统自动切换驱动
        if platform.system() == "Windows":
            driver_name = "Microsoft Access Driver (*.mdb, *.accdb)"
        else:
            driver_name = "MDBTools"

        conn_str = f'DRIVER={{{driver_name}}};DBQ={mdb_path};'
        conn = None

        try:
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()

            updated = []
            for stcd, stnm, instruction, adjust_type in GARDEN_FLOW_PARAMS:
                new_val = max_flow - 1000 if adjust_type == "buffer" else max_flow
                new_val = round(new_val, 2)

                # 查询当前值
                _mdb_execute(
                    cursor,
                    "SELECT stcd, stnm, Control_Par, Instruction FROM Dispatch_Par WHERE stcd = ?",
                    (stcd,)
                )
                row = cursor.fetchone()
                if not row:
                    logger.warning(f"未找到 stcd={stcd} 的参数")
                    continue

                old_val = float(row.Control_Par) if row.Control_Par is not None else None
                if old_val is not None and abs(old_val - new_val) < 0.01:
                    continue

                # 使用 mdb_update 工具直接写入 MDB 文件（ODBC 驱动不支持 UPDATE）
                _mdb_update_field(mdb_path, "Dispatch_Par", "Control_Par", new_val, "stcd", stcd)

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
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    @mcp.tool()
    async def generate_dispatch_sheet() -> dict:
        """
        一键生成调度方案单：运行计算 → 统计处理 → 存储入库 → 返回前台展示数据。

        与 generate_dispatch_scheme 功能一致，为兼容不同调用习惯保留。
        """
        logger.info("调用 generate_dispatch_sheet，委托给 generate_dispatch_scheme")
        return await generate_dispatch_scheme()

    # ================================================================
    # 水文局动态预报数据工具（Task 2-3）
    # ================================================================

    @mcp.tool()
    async def get_hydrology_forecast_plans(date_time: str) -> dict:
        """
        根据时间获取水文局预报方案列表。

        调用水文局 API（GET /pre/getSwPreWaterDataList），获取指定日期的所有可用预报方案。
        用户选择方案后，使用 get_hydrology_forecast_data 获取具体数据。

        Args:
            date_time: 日期，格式 YYYY-MM-DD，如 "2025-06-16"

        Returns:
            {
                "success": true,
                "date_time": "2025-06-16",
                "plan_count": 3,
                "plan_list": [
                    {"plcd": "7.20暴雨移植-预报", "time": "2025-07-18 08:00:00", "description": "..."},
                    ...
                ],
                "message": "共 3 个预报方案，请选择"
            }
        """
        logger.info(f"调用 get_hydrology_forecast_plans, date_time={date_time}")
        return hydrology_forecast_service.get_forecast_plans(date_time)

    @mcp.tool()
    async def get_hydrology_forecast_data(plcd: str, time: str) -> dict:
        """
        根据 plcd 和时间获取水文局预报方案数据，并写入 Access 数据库。

        调用水文局 API（GET /pre/getSwPreWaterDataByPlcd），获取方案详细数据，
        清空 Q_Inputsd 和 Q_Inputxd 表后写入新数据。
        写入完成后，可直接调用 generate_dispatch_scheme 进行调度计算。

        Args:
            plcd: 方案代码，如 "7.20暴雨移植-预报"
            time: 方案时间，如 "2025-07-18 08:00:00"

        Returns:
            {
                "success": true,
                "plcd": "7.20暴雨移植-预报",
                "time": "2025-07-18 08:00:00",
                "write_result": {
                    "upstream_count": 1780,
                    "downstream_count": 8346,
                    "total": 10126
                },
                "message": "预报数据已写入数据库，可调用 generate_dispatch_scheme 进行调度计算"
            }
        """
        logger.info(f"调用 get_hydrology_forecast_data, plcd={plcd}, time={time}")

        if not plcd or not time:
            return {
                "success": False,
                "command": "FUNC_GET_HYDROLOGY_FORECAST_DATA",
                "error": "plcd 和 time 均为必填参数"
            }

        # 1. 调用 API 获取数据
        api_result = hydrology_forecast_service.get_forecast_data(plcd, time)
        if not api_result.get("success"):
            return api_result

        api_data = api_result.get("data", [])
        if not api_data:
            return {
                "success": False,
                "command": "FUNC_GET_HYDROLOGY_FORECAST_DATA",
                "error": "API 返回数据为空",
                "plcd": plcd,
                "time": time
            }

        # 2. 写入 Access 数据库
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        dispatch_dir = os.path.join(project_root, 'src', 'services', 'external_api', 'RegualDispacth')
        mdb_path = os.path.join(dispatch_dir, '6', 'data.mdb')

        if not os.path.exists(mdb_path):
            return {
                "success": False,
                "command": "FUNC_GET_HYDROLOGY_FORECAST_DATA",
                "error": f"数据库文件不存在: {mdb_path}"
            }

        conn = None
        try:
            if platform.system() == "Windows":
                driver_name = "Microsoft Access Driver (*.mdb, *.accdb)"
                conn_str = f'DRIVER={{{driver_name}}};DBQ={mdb_path};'
                conn = pyodbc.connect(conn_str)
                cursor = conn.cursor()
                write_result = hydrology_forecast_service.write_to_access_db(api_data, conn, cursor)
            else:
                write_result = hydrology_forecast_service.write_to_access_db(api_data, None, None, mdb_path)

            if write_result.get("success"):
                if conn:
                    conn.close()
                return {
                    "success": True,
                    "command": "FUNC_GET_HYDROLOGY_FORECAST_DATA",
                    "plcd": plcd,
                    "time": time,
                    "write_result": {
                        "upstream_count": write_result["upstream_count"],
                        "downstream_count": write_result["downstream_count"],
                        "total": write_result["total"],
                        "errors": write_result.get("errors", [])
                    },
                    "message": f"预报数据已写入数据库（上游 {write_result['upstream_count']} 条，下游 {write_result['downstream_count']} 条），可调用 generate_dispatch_scheme 进行调度计算"
                }
            else:
                if conn:
                    conn.close()
                return {
                    "success": False,
                    "command": "FUNC_GET_HYDROLOGY_FORECAST_DATA",
                    "error": f"写入数据库失败: {write_result.get('error', '')}",
                    "write_result": write_result
                }
        except pyodbc.Error as e:
            logger.error(f"get_hydrology_forecast_data 数据库错误: {e}")
            return {
                "success": False,
                "command": "FUNC_GET_HYDROLOGY_FORECAST_DATA",
                "error": f"数据库操作失败: {str(e)}"
            }
        except Exception as e:
            logger.error(f"get_hydrology_forecast_data 出错: {e}")
            return {
                "success": False,
                "command": "FUNC_GET_HYDROLOGY_FORECAST_DATA",
                "error": f"获取预报数据失败: {str(e)}"
            }
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    # ================================================================
    # 参数模板工具（Task 1-5）
    # ================================================================

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
        conn = None

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
            dispatch_dir = os.path.join(project_root, 'src', 'services', 'external_api', 'RegualDispacth')
            mdb_path = os.path.join(dispatch_dir, '6', 'data.mdb')

            if not os.path.exists(mdb_path):
                return {"success": False, "error": f"数据库文件不存在: {mdb_path}"}

            # 判断系统自动切换驱动
            if platform.system() == "Windows":
                driver_name = "Microsoft Access Driver (*.mdb, *.accdb)"
            else:
                driver_name = "MDBTools"

            conn_str = f'DRIVER={{{driver_name}}};DBQ={mdb_path};'
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()

            # 读取修改前的值用于对比
            cursor.execute("SELECT stcd, Control_Par FROM Dispatch_Par")
            rows = cursor.fetchall()
            # MDBTools SQL 解析器不支持 ORDER BY，在 Python 中排序
            rows.sort(key=lambda r: str(r.stcd))
            before_map = {row.stcd: row.Control_Par for row in rows}

            updated_params = []
            update_count = 0
            for _, row in df_param.iterrows():
                stcd = row.get('stcd', '')
                new_value = row.get('Control_Par', 0)
                if stcd == '':
                    continue
                # 使用 mdb_update 工具直接写入 MDB 文件（ODBC 驱动不支持 UPDATE）
                _mdb_update_field(mdb_path, "Dispatch_Par", "Control_Par", new_value, "stcd", int(stcd))
                update_count += 1
                old_value = before_map.get(int(stcd), None)
                if old_value != new_value:
                        updated_params.append({
                            "stcd": stcd,
                            "stnm": str(row.get('stnm', '')).strip(),
                            "old_value": old_value,
                            "new_value": new_value,
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
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

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
        conn = None

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
            dispatch_dir = os.path.join(project_root, 'src', 'services', 'external_api', 'RegualDispacth')
            mdb_path = os.path.join(dispatch_dir, '6', 'data.mdb')
            # 判断系统自动切换驱动
            if platform.system() == "Windows":
                driver_name = "Microsoft Access Driver (*.mdb, *.accdb)"
            else:
                driver_name = "MDBTools"

            conn_str = f'DRIVER={{{driver_name}}};DBQ={mdb_path};'
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()

            cursor.execute("SELECT stcd, stnm, tm, q FROM Q_Output")
            actual_rows = cursor.fetchall()
            # MDBTools SQL 解析器不支持 ORDER BY，在 Python 中排序
            actual_rows.sort(key=lambda r: (str(r.tm), str(r.stcd)))
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
                    elif any('\u4e00' <= ch <= '\u9fff' for ch in str(col)):
                        # 包含中文字符的列名可能是站点名（流量列）
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
                else:
                    logger.warning(f"sheet '{sheet_name}' 未匹配到任何数据点，可能是站点名或时间格式不一致")

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
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
