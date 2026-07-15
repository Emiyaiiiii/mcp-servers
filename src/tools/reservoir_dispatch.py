import asyncio
import json
import os
import platform
import pyodbc
import subprocess
import time
import requests
import pandas as pd
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from fastmcp import FastMCP
from src.utils.logger import get_logger
from src.utils.mdb_utils import mdb_execute, mdb_update_field
from src.utils.stats_utils import calculate_reservoir_stats, calculate_hydrologic_stats
from src.utils.flood_utils import calculate_flood_submergence, check_dongpinghu_diversion
from src.utils.template_utils import generate_natural_language_summary, scan_templates, find_template_file, get_template_sheets
from src.services.storage.scheme_storage import save_scheme
from src.services.storage.database.data_access import SimulationParamsAccess, LevelCapacityCurveAccess, LevelFlowCurveAccess
from src.config.settings import settings

logger = get_logger(__name__)

DEFAULT_QY_BC = SimulationParamsAccess.get_param('XLD_QY_BC')
DEFAULT_SW_BC = SimulationParamsAccess.get_param('XLD_SW_BC')
DEFAULT_CK_BC = SimulationParamsAccess.get_param('XLD_CK_BC')
DEFAULT_QUJIAN_BC = SimulationParamsAccess.get_param('XLD_QUJIAN_BC')

DEFAULT_QY_SW = SimulationParamsAccess.get_param('XLD_QY_SW')
DEFAULT_SW_SW = SimulationParamsAccess.get_param('XLD_SW_SW')
DEFAULT_QUJIAN_SW = SimulationParamsAccess.get_param('XLD_QUJIAN_SW')

DEFAULT_ZV = SimulationParamsAccess.get_param('XLD_ZV')
DEFAULT_ZQXL = SimulationParamsAccess.get_param('XLD_ZQXL')

_mdb_execute = mdb_execute
_mdb_update_field = mdb_update_field

_scan_templates = scan_templates
_find_template_file = find_template_file
_get_template_sheets = get_template_sheets


def register_reservoir_dispatch(mcp: FastMCP):

    @mcp.tool()
    async def run_xiaolangdi_compensation_dispatch(
        qy: str = None,
        sw: str = None,
        ck: str = None,
        qujian: str = None,
        num1: int = 168,
        zmin: float = 230.0,
        dq: float = 1500.0,
        dtt: int = 1,
        ze: float = 264.0,
        q0: float = 2000.0,
        z0: float = 260.5,
        time: str = "2021-10-01 00:00:00",
        last_time: int = 1,
        reservoir_id: str = "40104690",
        zv: str = None,
        zqxl: str = None
    ) -> dict:
        """
        调用小浪底水库补偿调度模式接口。

        Args:
            qy: 入流流量数据 (JSON格式数组)，单位m³/s，包含168个时段的入流流量，不传则使用默认数据
            sw: 水位数据 (JSON格式数组)，单位m，默认全为265m
            ck: 出库流量数据 (JSON格式数组)，单位m³/s，默认全为20000m³/s
            qujian: 区间流量数据 (JSON格式数组)，单位m³/s，包含168个时段的区间流量，不传则使用默认数据
            num1: 计算时段数，默认168（小时）
            zmin: 最小水位，单位m，默认230m
            dq: 泄流量，单位m³/s，默认1500m³/s
            dtt: 时间步长，单位小时，默认1小时
            ze: 控制水位，单位m，默认264m
            q0: 初始出库流量，单位m³/s，默认2000m³/s
            z0: 初始水位，单位m，默认260.5m
            time: 开始时间，格式"YYYY-MM-DD HH:MM:SS"，默认"2021-10-01 00:00:00"
            last_time: 末段时间标识，默认1
            reservoir_id: 水库ID，默认"40104690"（小浪底水库）
            zv: 水位库容曲线 (JSON格式二维数组)，[[水位值...], [库容值...]]，不传则使用默认曲线
            zqxl: 水位泄流曲线 (JSON格式二维数组)，[[水位值...], [泄流量值...]]，不传则使用默认曲线

        Returns:
            dict: 调度计算结果，包含以下字段：
                - success: bool类型，接口调用是否成功，True表示成功，False表示失败
                - command: str类型，命令标识，固定为"FUNC_RUN_COMPENSATION_DISPATCH"
                - reservoir: str类型，水库名称，固定为"小浪底水库"
                - dispatch_mode: str类型，调度模式，固定为"补偿调度模式"
                - result: dict类型，模型计算返回的原始结果数据（具体结构由下游模型决定）
                - message: str类型，执行结果描述信息
                - error: str类型（仅失败时存在），失败原因描述
        """
        logger.info(f"调用 run_xiaolangdi_compensation_dispatch，收到参数")

        try:
            qy_data = json.loads(qy) if isinstance(qy, str) and qy else DEFAULT_QY_BC
            sw_data = json.loads(sw) if isinstance(sw, str) and sw else DEFAULT_SW_BC
            ck_data = json.loads(ck) if isinstance(ck, str) and ck else DEFAULT_CK_BC
            qujian_data = json.loads(qujian) if isinstance(qujian, str) and qujian else DEFAULT_QUJIAN_BC
            zv_data = json.loads(zv) if isinstance(zv, str) and zv else DEFAULT_ZV
            zqxl_data = json.loads(zqxl) if isinstance(zqxl, str) and zqxl else DEFAULT_ZQXL
        except json.JSONDecodeError:
            return_value = {"success": False, "error": "输入数据格式错误，请提供有效的JSON格式"}
            logger.debug(f"run_xiaolangdi_compensation_dispatch 返回结果: {return_value}")
            return return_value

        if qy_data is None:
            return_value = {"success": False, "error": "数据库中未配置XLD_QY_BC参数，请先配置"}
            logger.debug(f"run_xiaolangdi_compensation_dispatch 返回结果: {return_value}")
            return return_value
        if sw_data is None:
            return_value = {"success": False, "error": "数据库中未配置XLD_SW_BC参数，请先配置"}
            logger.debug(f"run_xiaolangdi_compensation_dispatch 返回结果: {return_value}")
            return return_value
        if ck_data is None:
            return_value = {"success": False, "error": "数据库中未配置XLD_CK_BC参数，请先配置"}
            logger.debug(f"run_xiaolangdi_compensation_dispatch 返回结果: {return_value}")
            return return_value
        if qujian_data is None:
            return_value = {"success": False, "error": "数据库中未配置XLD_QUJIAN_BC参数，请先配置"}
            logger.debug(f"run_xiaolangdi_compensation_dispatch 返回结果: {return_value}")
            return return_value
        if zv_data is None:
            return_value = {"success": False, "error": "数据库中未配置XLD_ZV参数，请先配置"}
            logger.debug(f"run_xiaolangdi_compensation_dispatch 返回结果: {return_value}")
            return return_value
        if zqxl_data is None:
            return_value = {"success": False, "error": "数据库中未配置XLD_ZQXL参数，请先配置"}
            logger.debug(f"run_xiaolangdi_compensation_dispatch 返回结果: {return_value}")
            return return_value

        try:
            url = settings.DISPATCH_API_BC_URL
            payload = {
                "qy": qy_data,
                "sw": sw_data,
                "ck": ck_data,
                "qujian": qujian_data,
                "num1": num1,
                "zmin": zmin,
                "dq": dq,
                "dtt": dtt,
                "ze": ze,
                "q0": q0,
                "z0": z0,
                "time": time,
                "lastTime": last_time,
                "id": reservoir_id,
                "zv": zv_data,
                "zqxl": zqxl_data
            }

            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()

            result = response.json()

            return_value = {
                "success": True,
                "command": "FUNC_RUN_COMPENSATION_DISPATCH",
                "reservoir": "小浪底水库",
                "dispatch_mode": "补偿调度模式",
                "result": result,
                "message": "小浪底水库补偿调度模式执行成功"
            }
            logger.debug(f"run_xiaolangdi_compensation_dispatch 返回结果: {return_value}")
            return return_value

        except requests.exceptions.RequestException as e:
            logger.error(f"调用补偿调度接口失败: {str(e)}")
            return_value = {
                "success": False,
                "error": f"调用补偿调度接口失败: {str(e)}",
                "command": "FUNC_RUN_COMPENSATION_DISPATCH",
                "reservoir": "小浪底水库",
                "dispatch_mode": "补偿调度模式"
            }
            logger.debug(f"run_xiaolangdi_compensation_dispatch 返回结果: {return_value}")
            return return_value

    @mcp.tool()
    async def run_xiaolangdi_water_level_control(
        qy: str = None,
        sw: str = None,
        qujian: str = None,
        zmin: float = 230.0,
        num1: int = 168,
        dq: float = 1000.0,
        dtt: int = 1,
        ze: float = 257.0,
        q0: float = 1000.0,
        z0: float = 254.0,
        time: str = "2021-10-01 00:00:00",
        reservoir_id: str = "40104690",
        zv: str = None,
        zqxl: str = None
    ) -> dict:
        """
        调用小浪底水库水位控制模式接口。

        Args:
            qy: 入流流量数据 (JSON格式数组)，单位m³/s，包含168个时段的入流流量，不传则使用默认数据
            sw: 水位数据 (JSON格式数组)，单位m，默认全为258m
            qujian: 区间流量数据 (JSON格式数组)，单位m³/s，包含168个时段的区间流量，不传则使用默认数据
            zmin: 最小水位，单位m，默认230m
            num1: 计算时段数，默认168（小时）
            dq: 泄流量，单位m³/s，默认1000m³/s
            dtt: 时间步长，单位小时，默认1小时
            ze: 控制水位，单位m，默认257m
            q0: 初始出库流量，单位m³/s，默认1000m³/s
            z0: 初始水位，单位m，默认254m
            time: 开始时间，格式"YYYY-MM-DD HH:MM:SS"，默认"2021-10-01 00:00:00"
            reservoir_id: 水库ID，默认"40104690"（小浪底水库）
            zv: 水位库容曲线 (JSON格式二维数组)，[[水位值...], [库容值...]]，不传则使用默认曲线
            zqxl: 水位泄流曲线 (JSON格式二维数组)，[[水位值...], [泄流量值...]]，不传则使用默认曲线

        Returns:
            dict: 调度计算结果，包含以下字段：
                - success: bool类型，接口调用是否成功，True表示成功，False表示失败
                - command: str类型，命令标识，固定为"FUNC_RUN_WATER_LEVEL_CONTROL"
                - reservoir: str类型，水库名称，固定为"小浪底水库"
                - dispatch_mode: str类型，调度模式，固定为"水位控制模式"
                - result: dict类型，模型计算返回的原始结果数据（具体结构由下游模型决定）
                - message: str类型，执行结果描述信息
                - error: str类型（仅失败时存在），失败原因描述
        """
        logger.info(f"调用 run_xiaolangdi_water_level_control，收到参数")

        try:
            qy_data = json.loads(qy) if isinstance(qy, str) and qy else DEFAULT_QY_SW
            sw_data = json.loads(sw) if isinstance(sw, str) and sw else DEFAULT_SW_SW
            qujian_data = json.loads(qujian) if isinstance(qujian, str) and qujian else DEFAULT_QUJIAN_SW
            zv_data = json.loads(zv) if isinstance(zv, str) and zv else DEFAULT_ZV
            zqxl_data = json.loads(zqxl) if isinstance(zqxl, str) and zqxl else DEFAULT_ZQXL
        except json.JSONDecodeError:
            return_value = {"success": False, "error": "输入数据格式错误，请提供有效的JSON格式"}
            logger.debug(f"run_xiaolangdi_water_level_control 返回结果: {return_value}")
            return return_value

        if qy_data is None:
            return_value = {"success": False, "error": "数据库中未配置XLD_QY_SW参数，请先配置"}
            logger.debug(f"run_xiaolangdi_water_level_control 返回结果: {return_value}")
            return return_value
        if sw_data is None:
            return_value = {"success": False, "error": "数据库中未配置XLD_SW_SW参数，请先配置"}
            logger.debug(f"run_xiaolangdi_water_level_control 返回结果: {return_value}")
            return return_value
        if qujian_data is None:
            return_value = {"success": False, "error": "数据库中未配置XLD_QUJIAN_SW参数，请先配置"}
            logger.debug(f"run_xiaolangdi_water_level_control 返回结果: {return_value}")
            return return_value
        if zv_data is None:
            return_value = {"success": False, "error": "数据库中未配置XLD_ZV参数，请先配置"}
            logger.debug(f"run_xiaolangdi_water_level_control 返回结果: {return_value}")
            return return_value
        if zqxl_data is None:
            return_value = {"success": False, "error": "数据库中未配置XLD_ZQXL参数，请先配置"}
            logger.debug(f"run_xiaolangdi_water_level_control 返回结果: {return_value}")
            return return_value

        try:
            url = settings.DISPATCH_API_SW_URL
            payload = {
                "qy": qy_data,
                "sw": sw_data,
                "qujian": qujian_data,
                "zmin": zmin,
                "num1": num1,
                "dq": dq,
                "dtt": dtt,
                "ze": ze,
                "q0": q0,
                "z0": z0,
                "time": time,
                "id": reservoir_id,
                "zv": zv_data,
                "zqxl": zqxl_data
            }

            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()

            result = response.json()

            return_value = {
                "success": True,
                "command": "FUNC_RUN_WATER_LEVEL_CONTROL",
                "reservoir": "小浪底水库",
                "dispatch_mode": "水位控制模式",
                "result": result,
                "message": "小浪底水库水位控制模式执行成功"
            }
            logger.debug(f"run_xiaolangdi_water_level_control 返回结果: {return_value}")
            return return_value

        except requests.exceptions.RequestException as e:
            logger.error(f"调用水位控制接口失败: {str(e)}")
            return_value = {
                "success": False,
                "error": f"调用水位控制接口失败: {str(e)}",
                "command": "FUNC_RUN_WATER_LEVEL_CONTROL",
                "reservoir": "小浪底水库",
                "dispatch_mode": "水位控制模式"
            }
            logger.debug(f"run_xiaolangdi_water_level_control 返回结果: {return_value}")
            return return_value

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

            proc = await asyncio.create_subprocess_exec(
                exe_path,
                cwd=dispatch_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
                exit_code = proc.returncode
                stdout_str = stdout.decode('gbk', errors='ignore') if stdout else ""
                stderr_str = stderr.decode('gbk', errors='ignore') if stderr else ""
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                conn.close()
                return {"success": False, "error": "RegualDispacth.exe 执行超时（300秒）", "steps": steps}

            calc_elapsed = round(time.time() - calc_start, 2)
            steps["calculation"] = {
                "elapsed_seconds": calc_elapsed,
                "exit_code": exit_code
            }
            logger.info(f"计算完成: exit_code={exit_code}, 耗时{calc_elapsed}秒")

            if exit_code != 0:
                conn.close()
                return {"success": False, "error": f"RegualDispacth.exe 返回非零退出码: {exit_code}, stderr: {stderr_str}", "steps": steps}

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
            reservoir_stats, reservoir_table = calculate_reservoir_stats(conn)
            logger.info(f"已从 Z_Output 提取 {len(reservoir_stats)} 个水库的统计指标")

            # 水文站统计（从 Q_Output 表计算）
            hydrologic_stats, hydrologic_table = calculate_hydrologic_stats(conn, flood_type)

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
            flood_submergence = calculate_flood_submergence(garden_mouth_peak)

            # 东平湖分洪状态
            dongpinghu_diversion = check_dongpinghu_diversion(conn)

            # 自然语言总结
            natural_language_summary = generate_natural_language_summary(
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
                    mdb_update_field(mdb_path, "Dispatch_Par", "Control_Par", new_value, "stcd", row.stcd)

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
                mdb_execute(
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
                mdb_update_field(mdb_path, "Dispatch_Par", "Control_Par", new_val, "stcd", stcd)

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
                "hint": "参数已更新，请调用 generate_dispatch_scheme() 重新生成方案单验证效果"
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

    # ================================================================
    # 参数模板工具（Task 1-5）
    # ================================================================

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
            info = _find_template_file(template_name)
            if not info:
                available = list(_scan_templates().keys())
                return {
                    "success": False,
                    "error": f"未找到模板 '{template_name}'",
                    "available_templates": available
                }

            df_param = pd.read_excel(info['file_path'], sheet_name='参数')
            if df_param.empty:
                return {"success": False, "error": "模板参数为空"}

            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            dispatch_dir = os.path.join(project_root, 'src', 'services', 'external_api', 'RegualDispacth')
            mdb_path = os.path.join(dispatch_dir, '6', 'data.mdb')

            if not os.path.exists(mdb_path):
                return {"success": False, "error": f"数据库文件不存在: {mdb_path}"}

            if platform.system() == "Windows":
                driver_name = "Microsoft Access Driver (*.mdb, *.accdb)"
            else:
                driver_name = "MDBTools"

            conn_str = f'DRIVER={{{driver_name}}};DBQ={mdb_path};'
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()

            cursor.execute("SELECT stcd, Control_Par FROM Dispatch_Par")
            rows = cursor.fetchall()
            rows.sort(key=lambda r: str(r.stcd))
            before_map = {row.stcd: row.Control_Par for row in rows}

            updated_params = []
            update_count = 0
            for _, row in df_param.iterrows():
                stcd = row.get('stcd', '')
                new_value = row.get('Control_Par', 0)
                if stcd == '':
                    continue
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
                "changed_params": updated_params[:20],
                "total_changed": len(updated_params)
            }

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

            logger.info("应用参数模板并生成方案...")
            apply_result = await apply_parameter_template(template_name, generate_scheme=True)
            if not apply_result.get("success"):
                return {
                    "success": False,
                    "error": f"应用参数模板失败: {apply_result.get('error', '')}"
                }

            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            dispatch_dir = os.path.join(project_root, 'src', 'services', 'external_api', 'RegualDispacth')
            mdb_path = os.path.join(dispatch_dir, '6', 'data.mdb')
            if platform.system() == "Windows":
                driver_name = "Microsoft Access Driver (*.mdb, *.accdb)"
            else:
                driver_name = "MDBTools"

            conn_str = f'DRIVER={{{driver_name}}};DBQ={mdb_path};'
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()

            cursor.execute("SELECT stcd, stnm, tm, q FROM Q_Output")
            actual_rows = cursor.fetchall()
            actual_rows.sort(key=lambda r: (str(r.tm), str(r.stcd)))
            conn.close()

            actual_index = {}
            for row in actual_rows:
                stnm = row.stnm.strip() if row.stnm else ""
                tm_str = str(row.tm)
                actual_index[(stnm, tm_str)] = row.q

            station_results = {}
            total_matched = 0
            total_errors = []

            for sheet_name in result_sheets:
                try:
                    df_expected = pd.read_excel(info['file_path'], sheet_name=sheet_name)
                except Exception:
                    continue

                time_col = None
                flow_cols = []

                for col in df_expected.columns:
                    if col in ['时间', 'tm', 'time']:
                        time_col = col
                    elif col in ['出库', 'q', 'flow']:
                        flow_cols.append(col)
                    elif any('\u4e00' <= ch <= '\u9fff' for ch in str(col)):
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
