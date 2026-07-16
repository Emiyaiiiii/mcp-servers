import asyncio
import os
import pyodbc
import time
from collections import defaultdict
from datetime import datetime
from typing import Optional

from src.utils.logger import get_logger
from src.utils.dispatch.mdb_utils import get_mdb_connection
from src.utils.analysis.flood_utils import calculate_flood_submergence, check_dongpinghu_diversion
from src.utils.analysis.stats_utils import build_reservoir_data, build_hydrological_data
from src.utils.model.template_utils import generate_natural_language_summary
from src.services.storage.scheme_storage import save_scheme

logger = get_logger(__name__)


# === generate_dispatch_scheme 辅助函数 ===


def _check_dispatch_data_source(exe_path: str, mdb_path: str) -> dict:
    """步骤1: 检查调度数据源文件和数据库数据

    独立获取 MDB 连接检查 Q_Inputsd/Q_Inputxd 行数，检查完即释放。

    Returns:
        成功时返回 {"success": True, "sd_count": int, "xd_count": int, "data_check": dict}
        失败时返回 {"success": False, "error": str, ...}
    """
    steps = {}

    if not os.path.exists(exe_path):
        return {"success": False, "error": f"调度计算程序不存在: {exe_path}", "steps": steps}
    if not os.path.exists(mdb_path):
        return {"success": False, "error": f"数据库文件不存在: {mdb_path}", "steps": steps}

    try:
        with get_mdb_connection() as (cursor, conn):
            cursor.execute("SELECT COUNT(*) FROM Q_Inputsd")
            sd_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM Q_Inputxd")
            xd_count = cursor.fetchone()[0]
    except pyodbc.Error as e:
        logger.error(f"_check_dispatch_data_source 数据库错误: {e}")
        return {"success": False, "error": f"数据库操作失败: {str(e)}", "steps": steps}

    if sd_count == 0 or xd_count == 0:
        return {
            "success": False,
            "command": "FUNC_GENERATE_DISPATCH_SCHEME",
            "error": "数据库为空，请先获取水文局预报数据",
            "hint": "调用 get_hydrology_forecast_plans(date_time) 获取方案列表 → 用户选择方案 → 调用 get_hydrology_forecast_data(plcd, time) 写入数据",
            "Q_Inputsd_rows": sd_count,
            "Q_Inputxd_rows": xd_count,
            "steps": steps
        }

    return {
        "success": True,
        "sd_count": sd_count,
        "xd_count": xd_count,
        "data_check": {
            "source": "dynamic",
            "Q_Inputsd_rows": sd_count,
            "Q_Inputxd_rows": xd_count,
        }
    }


async def _run_regualdispacth(exe_path: str, dispatch_dir: str, steps: dict) -> dict:
    """步骤2: 运行 RegualDispacth.exe 调度计算程序

    Returns:
        成功时返回 {"success": True, "exit_code": int}
        失败时返回 {"success": False, "error": str}
    """
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
        calc_elapsed = round(time.time() - calc_start, 2)
        steps["calculation"] = {"elapsed_seconds": calc_elapsed, "exit_code": -1}
        return {"success": False, "error": "RegualDispacth.exe 执行超时（300秒）"}

    calc_elapsed = round(time.time() - calc_start, 2)
    steps["calculation"] = {
        "elapsed_seconds": calc_elapsed,
        "exit_code": exit_code
    }
    logger.info(f"计算完成: exit_code={exit_code}, 耗时{calc_elapsed}秒")

    if exit_code != 0:
        return {"success": False, "error": f"RegualDispacth.exe 返回非零退出码: {exit_code}, stderr: {stderr_str}"}

    return {"success": True, "exit_code": exit_code}


def _process_calculation_results(mdb_path: str, steps: dict, flood_type: str) -> dict:
    """步骤3: 读取 Q_Output 计算结果并进行统计处理

    独立获取 MDB 连接读取 Q_Output、Z_Output，构建时序数据，
    调用 build_reservoir_data / build_hydrological_data / calculate_flood_submergence
    / check_dongpinghu_diversion / generate_natural_language_summary。

    Args:
        mdb_path: MDB 数据库路径（用于日志，实际连接由 get_mdb_connection 管理）
        steps: 步骤计时字典
        flood_type: 洪水类型

    Returns:
        成功时返回 {"success": True, ...} 包含所有处理结果
        失败时返回 {"success": False, "error": str}
    """
    logger.info("步骤3: 读取Q_Output并统计处理")
    stats_start = time.time()

    try:
        with get_mdb_connection() as (cursor, conn):
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

            # 从 Z_Output / Q_Output 构建时序数据 + 统计指标
            reservoirs, reservoir_stats, reservoir_table = build_reservoir_data(cursor)
            logger.info(f"已从 Z_Output 提取 {len(reservoir_stats)} 个水库的统计指标")

            hydrological_stations, hydrologic_stats, hydrologic_table = build_hydrological_data(cursor, flood_type)
            logger.info(f"已从 Q_Output 提取 {len(hydrologic_stats)} 个水文站的统计指标")

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

    except pyodbc.Error as e:
        logger.error(f"_process_calculation_results 数据库错误: {e}")
        return {"success": False, "error": f"数据库操作失败: {str(e)}"}
    except Exception as e:
        logger.error(f"_process_calculation_results 出错: {e}")
        return {"success": False, "error": f"统计处理失败: {str(e)}"}

    return {
        "success": True,
        "output_data": output_data,
        "output_rows": output_rows,
        "station_stats": station_stats,
        "time_range_start": time_range_start,
        "time_range_end": time_range_end,
        "top_by_max": top_by_max,
        "top_by_avg": top_by_avg,
        "reservoirs": reservoirs,
        "reservoir_stats": reservoir_stats,
        "reservoir_table": reservoir_table,
        "hydrological_stations": hydrological_stations,
        "hydrologic_stats": hydrologic_stats,
        "hydrologic_table": hydrologic_table,
        "flood_submergence": flood_submergence,
        "dongpinghu_diversion": dongpinghu_diversion,
        "natural_language_summary": natural_language_summary,
    }


def _save_and_format_scheme(steps: dict, result_data: dict) -> dict:
    """步骤4: 构建方案数据、保存到数据库、格式化前台展示返回值

    Args:
        steps: 步骤计时字典
        result_data: _process_calculation_results 的返回值

    Returns:
        前台展示用的返回值字典
    """
    logger.info("步骤4: 存储方案数据到数据库")

    station_stats = result_data["station_stats"]
    output_rows = result_data["output_rows"]
    time_range_start = result_data["time_range_start"]
    time_range_end = result_data["time_range_end"]
    top_by_max = result_data["top_by_max"]
    top_by_avg = result_data["top_by_avg"]
    flood_type_hint = result_data.get("flood_type", "")
    flood_submergence = result_data["flood_submergence"]
    dongpinghu_diversion = result_data["dongpinghu_diversion"]
    natural_language_summary = result_data["natural_language_summary"]
    reservoirs = result_data["reservoirs"]
    hydrological_stations = result_data["hydrological_stations"]
    reservoir_stats = result_data["reservoir_stats"]
    reservoir_table = result_data["reservoir_table"]
    hydrologic_stats = result_data["hydrologic_stats"]
    hydrologic_table = result_data["hydrologic_table"]

    # 从 steps 中提取 flood_type（主函数通过 result_data 传入）
    # flood_type 已在 _process_calculation_results 中用于生成总结，这里从 details 重建

    scheme_data = {
        "scheme_name": f"调度方案单_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "description": "基于水文局预报数据，通过RegualDispacth.exe计算生成的调度方案",
        "basin": "黄河",
        "start_date": time_range_start[:10] if time_range_start else "",
        "end_date": time_range_end[:10] if time_range_end else "",
        "status": "active",
        "constraints": [],
        "details": {
            "flood_type": result_data.get("flood_type", ""),
            "flood_submergence": flood_submergence,
            "dongpinghu_diversion": dongpinghu_diversion,
            "natural_language_summary": natural_language_summary,
            "time_range": {"start": time_range_start, "end": time_range_end},
            "total_stations": len(station_stats),
            "total_rows": output_rows,
            "steps": steps
        },
        "constraints_applied": {},
        "reservoirs": reservoirs,
        "hydrological_stations": hydrological_stations
    }

    saved_scheme_id = save_scheme(scheme_data)
    logger.info(f"调度方案已保存，ID: {saved_scheme_id}")

    return_value = {
        "success": True,
        "command": "FUNC_GENERATE_DISPATCH_SCHEME",
        "scheme_id": saved_scheme_id,
        "scheme_name": scheme_data["scheme_name"],
        "start_date": scheme_data["start_date"],
        "end_date": scheme_data["end_date"],
        "message": "调度方案单生成完成",
        "steps": steps,
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
            "flood_type": result_data.get("flood_type", "")
        },
        "natural_language_summary": natural_language_summary
    }

    logger.debug(f"generate_dispatch_scheme 返回结果: {return_value}")
    return return_value
