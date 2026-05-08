import json
import random
from typing import List, Dict, Any
from mcp.server.fastmcp import FastMCP
from src.utils.logger import get_logger
from src.services.scheme_storage import save_scheme, generate_unique_id

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
            logger.info(f"run_hydrological_model 返回结果: {return_value}")
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
        logger.info(f"run_hydrological_model 返回结果: {return_value}")
        return return_value

    @mcp.tool()
    async def run_flood_routing_model(river_section: str, inflow: str, initial_conditions: str) -> dict:
        """
        执行洪水演进模型。

        Args:
            river_section: 河段名称（如：三门峡-小浪底、洛河段等）
            inflow: 入流数据 (JSON格式)，包含上游站的流量过程
            initial_conditions: 初始条件 (JSON格式)，包含初始水位、流量等
        """
        logger.info(f"调用 run_flood_routing_model，收到参数: river_section={repr(river_section)}, inflow={repr(inflow)}, initial_conditions={repr(initial_conditions)}")
        try:
            inflow_data = json.loads(inflow) if isinstance(inflow, str) else inflow
            init_cond = json.loads(initial_conditions) if isinstance(initial_conditions, str) else initial_conditions
        except json.JSONDecodeError:
            return_value = {"success": False, "error": "输入数据格式错误，请提供有效的JSON格式"}
            logger.info(f"run_flood_routing_model 返回结果: {return_value}")
            return return_value

        initial_level = init_cond.get("initial_water_level", 100)

        routing_result = []
        for i, point in enumerate(inflow_data):
            inflow_val = float(point.get("inflow", 0))
            attenuation = 0.85 + random.uniform(0, 0.1)
            routed_flow = inflow_val * attenuation
            routed_level = initial_level + random.uniform(-2, 3)
            routing_result.append({
                "hour": i,
                "inflow": inflow_val,
                "outflow": round(routed_flow, 2),
                "water_level": round(routed_level, 2)
            })

        return_value = {
            "success": True,
            "river_section": river_section,
            "command": "FUNC_RUN_FLOOD_ROUTING_MODEL",
            "initial_conditions": init_cond,
            "routing_result": routing_result,
            "peak_attenuation": round(100 * (1 - 0.88), 2),
            "message": f"洪水演进模型执行成功，{river_section}演进计算完成"
        }
        logger.info(f"run_flood_routing_model 返回结果: {return_value}")
        return return_value

    @mcp.tool()
    async def generate_dispatch_scheme(
        count: int = 1,
        control_huayuankou_flow: bool = False,
        huayuankou_max_flow: float = 2500.0,
        flood_season_empty_storage: bool = False,
        target_storage_ratio: float = 0.7,
        smx_max_level: float = None,
        smx_max_storage: float = None,
        xld_max_level: float = None,
        xld_max_storage: float = None,
        lh_max_level: float = None,
        lh_max_storage: float = None,
        gx_max_level: float = None,
        gx_max_storage: float = None,
        hkc_max_level: float = None,
        hkc_max_storage: float = None,
        start_time: str = None
    ) -> dict:
        """
        生成调度方案单。

        Args:
            count: 生成的调度方案数量，默认1个
            control_huayuankou_flow: 是否控制花园口流量
            huayuankou_max_flow: 花园口最大流量限制（m³/s），默认2500
            flood_season_empty_storage: 是否需要汛前腾空库容
            target_storage_ratio: 汛前目标库容比例，默认0.7（70%）
            
            # 三门峡水库约束
            smx_max_level: 三门峡水库最大水位限制（m），不设置则无限制
            smx_max_storage: 三门峡水库最大库容限制（亿m³），不设置则无限制
            
            # 小浪底水库约束
            xld_max_level: 小浪底水库最大水位限制（m），不设置则无限制
            xld_max_storage: 小浪底水库最大库容限制（亿m³），不设置则无限制
            
            # 陆浑水库约束
            lh_max_level: 陆浑水库最大水位限制（m），不设置则无限制
            lh_max_storage: 陆浑水库最大库容限制（亿m³），不设置则无限制
            
            # 故县水库约束
            gx_max_level: 故县水库最大水位限制（m），不设置则无限制
            gx_max_storage: 故县水库最大库容限制（亿m³），不设置则无限制
            
            # 河口村水库约束
            hkc_max_level: 河口村水库最大水位限制（m），不设置则无限制
            hkc_max_storage: 河口村水库最大库容限制（亿m³），不设置则无限制
            
            start_time: 调度开始时间（格式：YYYY-MM-DD），不设置则使用当前时间
        """
        logger.info(f"调用 generate_dispatch_scheme，收到参数: count={count}, control_huayuankou_flow={control_huayuankou_flow}, huayuankou_max_flow={huayuankou_max_flow}, flood_season_empty_storage={flood_season_empty_storage}, target_storage_ratio={target_storage_ratio}")
        
        if count <= 0:
            count = 3
        
        import time
        from datetime import datetime, timedelta
        
        if start_time:
            try:
                base_datetime = datetime.strptime(start_time, "%Y-%m-%d")
            except ValueError:
                base_datetime = datetime.now()
        else:
            base_datetime = datetime.now()
        
        base_timestamp = int(base_datetime.timestamp() * 1000)
        
        reservoir_config = {
            "三门峡水库": {"base_level": 305, "base_storage": 60.0, "max_level": smx_max_level, "max_storage": smx_max_storage, "code": "BDA00000111"},
            "小浪底水库": {"base_level": 235, "base_storage": 139.1, "max_level": xld_max_level, "max_storage": xld_max_storage, "code": "BDA00000121"},
            "陆浑水库": {"base_level": 317, "base_storage": 5.68, "max_level": lh_max_level, "max_storage": lh_max_storage, "code": "BDA80200721"},
            "故县水库": {"base_level": 527.3, "base_storage": 5.14, "max_level": gx_max_level, "max_storage": gx_max_storage, "code": "BDA80000661"},
            "河口村水库": {"base_level": 238, "base_storage": 0.78, "max_level": hkc_max_level, "max_storage": hkc_max_storage, "code": "BDA00000761"}
        }
        
        hydrological_stations = ["龙门镇", "白马寺", "黑石关", "花园口"]
        
        def apply_constraints(res_name, level, storage, outflow, inflow):
            config = reservoir_config[res_name]
            max_level = config["max_level"]
            max_storage = config["max_storage"]
            
            adjusted_level = level
            adjusted_storage = storage
            adjusted_outflow = outflow
            
            if max_level is not None and level > max_level:
                adjusted_level = round(max_level + random.uniform(-1, 0), 4)
                adjusted_outflow = round(min(outflow, inflow + 100), 4)
            
            if max_storage is not None and storage > max_storage:
                adjusted_storage = round(max_storage + random.uniform(-10, 0), 4)
                excess_storage = storage - max_storage
                adjusted_outflow = round(outflow + excess_storage * 10, 4)
            
            return adjusted_level, adjusted_storage, adjusted_outflow
        
        def load_base_data():
            import json
            import os
            
            data_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "dispatch_scheme_data_base.json")
            
            try:
                with open(data_path, 'r', encoding='utf-8') as f:
                    raw_data = json.load(f)
                
                header_row = raw_data["data"][0]
                unit_row = raw_data["data"][1]
                data_rows = raw_data["data"][2:]
                
                reservoir_columns = {
                    "三门峡水库": ["三门峡", "三门峡.1", "三门峡.2", "三门峡.3"],
                    "小浪底水库": ["小浪底", "小浪底.1", "小浪底.2", "小浪底.3"],
                    "陆浑水库": ["陆浑", "陆浑.1", "陆浑.2", "陆浑.3"],
                    "故县水库": ["故县", "故县.1", "故县.2", "故县.3"],
                    "河口村水库": ["河口村", "河口村.1", "河口村.2", "河口村.3"]
                }
                
                base_data = {res: {"water_level": [], "storage": [], "inflow": [], "outflow": []} for res in reservoir_columns}
                station_data = {"龙门镇": [], "白马寺": [], "黑石关": [], "花园口": []}
                timestamps = []
                
                for row in data_rows:
                    time_str = row.get("时间", "")
                    if time_str:
                        timestamps.append(time_str)
                    
                    for res_name, cols in reservoir_columns.items():
                        try:
                            base_data[res_name]["water_level"].append(float(row.get(cols[0], 0)))
                            base_data[res_name]["storage"].append(float(row.get(cols[1], 0)))
                            base_data[res_name]["inflow"].append(float(row.get(cols[2], 0)))
                            base_data[res_name]["outflow"].append(float(row.get(cols[3], 0)))
                        except (ValueError, TypeError):
                            base_data[res_name]["water_level"].append(0)
                            base_data[res_name]["storage"].append(0)
                            base_data[res_name]["inflow"].append(0)
                            base_data[res_name]["outflow"].append(0)
                    
                    try:
                        station_data["龙门镇"].append(float(row.get("龙门镇", 0)))
                        station_data["白马寺"].append(float(row.get("白马寺", 0)))
                        station_data["黑石关"].append(float(row.get("黑石关", 0)))
                        station_data["花园口"].append(float(row.get("花园口", 0)))
                    except (ValueError, TypeError):
                        station_data["龙门镇"].append(0)
                        station_data["白马寺"].append(0)
                        station_data["黑石关"].append(0)
                        station_data["花园口"].append(0)
                
                return base_data, station_data, timestamps
            
            except Exception as e:
                logger.warning(f"加载基础数据失败: {e}，使用默认随机数据")
                return None, None, None
        
        base_data, base_stations, base_timestamps = load_base_data()
        
        def generate_scheme(scheme_id: int):
            current_base_time = base_timestamp + (scheme_id - 1) * 86400000 * 7
            
            timestamps = []
            reservoirs_data = {res_name: {"water_level": [], "storage": [], "inflow": [], "outflow": []} for res_name in reservoir_config}
            stations_data = {station: {"flow": []} for station in hydrological_stations}
            
            for hour in range(168):
                time_stamp = current_base_time + hour * 3600000
                timestamps.append(time_stamp)
                
                total_outflow = 0
                
                for res_name, config in reservoir_config.items():
                    base_level = config["base_level"]
                    base_storage = config["base_storage"]
                    
                    data_index = hour % len(base_data[res_name]["water_level"]) if base_data else hour
                    
                    if base_data and data_index < len(base_data[res_name]["water_level"]):
                        ref_level = base_data[res_name]["water_level"][data_index]
                        ref_storage = base_data[res_name]["storage"][data_index]
                        ref_inflow = base_data[res_name]["inflow"][data_index]
                        ref_outflow = base_data[res_name]["outflow"][data_index]
                        
                        level = round(ref_level * (1 + random.uniform(-0.05, 0.05)), 2)
                        storage = round(ref_storage * (1 + random.uniform(-0.1, 0.1)), 2)
                        inflow = round(ref_inflow * (1 + random.uniform(-0.15, 0.15)), 2)
                        outflow = round(ref_outflow * (1 + random.uniform(-0.15, 0.15)), 2)
                    else:
                        inflow = round(500 + random.uniform(-100, 500), 2)
                        outflow = round(500 + random.uniform(-100, 500), 2)
                        storage = round(base_storage * (1 + random.uniform(-0.1, 0.1)), 2)
                        level = round(base_level + random.uniform(-5, 15), 2)
                    
                    if flood_season_empty_storage:
                        storage = round(storage * target_storage_ratio, 2)
                    
                    level, storage, outflow = apply_constraints(res_name, level, storage, outflow, inflow)
                    
                    reservoirs_data[res_name]["water_level"].append(max(0, level))
                    reservoirs_data[res_name]["storage"].append(max(0, storage))
                    reservoirs_data[res_name]["inflow"].append(max(0, inflow))
                    reservoirs_data[res_name]["outflow"].append(max(0, outflow))
                    
                    total_outflow += outflow
                
                if control_huayuankou_flow:
                    huayuankou_flow = total_outflow * 0.85
                    if huayuankou_flow > huayuankou_max_flow:
                        exceed_ratio = huayuankou_flow / huayuankou_max_flow
                        for res_name in reservoir_config:
                            orig_outflow = reservoirs_data[res_name]["outflow"][-1]
                            reservoirs_data[res_name]["outflow"][-1] = max(0, round(orig_outflow / exceed_ratio, 2))
                        total_outflow = round(total_outflow / exceed_ratio, 2)
            
                if base_stations and hour < len(base_stations["花园口"]):
                    stations_data["龙门镇"]["flow"].append(round(base_stations["龙门镇"][hour] * (1 + random.uniform(-0.1, 0.1)), 2))
                    stations_data["白马寺"]["flow"].append(round(base_stations["白马寺"][hour] * (1 + random.uniform(-0.1, 0.1)), 2))
                    stations_data["黑石关"]["flow"].append(round(base_stations["黑石关"][hour] * (1 + random.uniform(-0.1, 0.1)), 2))
                    stations_data["花园口"]["flow"].append(round(base_stations["花园口"][hour] * (1 + random.uniform(-0.1, 0.1)), 2))
                else:
                    base_flow = total_outflow * 0.85
                    stations_data["龙门镇"]["flow"].append(max(0, round(base_flow * random.uniform(0.05, 0.1), 2)))
                    stations_data["白马寺"]["flow"].append(max(0, round(base_flow * random.uniform(0.05, 0.15), 2)))
                    stations_data["黑石关"]["flow"].append(max(0, round(base_flow * random.uniform(0.08, 0.2), 2)))
                    stations_data["花园口"]["flow"].append(max(0, round(base_flow * random.uniform(0.6, 0.85), 2)))
            
            scheme_start_date = (base_datetime + timedelta(days=(scheme_id - 1) * 7)).strftime("%Y-%m-%d")
            scheme_end_date = (base_datetime + timedelta(days=(scheme_id - 1) * 7 + 7)).strftime("%Y-%m-%d")
            
            unique_id = generate_unique_id()
            
            reservoirs_output = {}
            for res_name, config in reservoir_config.items():
                reservoirs_output[res_name] = {
                    "water_level": reservoirs_data[res_name]["water_level"],
                    "storage": reservoirs_data[res_name]["storage"],
                    "inflow": reservoirs_data[res_name]["inflow"],
                    "outflow": reservoirs_data[res_name]["outflow"]
                }
            
            return {
                "scheme_id": unique_id,
                "scheme_name": f"{base_datetime.year}年汛期调度方案{unique_id.split('-')[1]}",
                "start_date": scheme_start_date,
                "end_date": scheme_end_date,
                "timestamps": timestamps,
                "reservoirs": reservoirs_output,
                "hydrological_stations": stations_data
            }
        
        schemes = [generate_scheme(i + 1) for i in range(min(count, 5))]
        
        for scheme in schemes:
            save_scheme(scheme)
        
        return_value = {
            "success": True,
            "command": "FUNC_GENERATE_DISPATCH_SCHEME",
            "count": len(schemes),
            "constraints_applied": {
                "control_huayuankou_flow": control_huayuankou_flow,
                "huayuankou_max_flow": huayuankou_max_flow if control_huayuankou_flow else None,
                "flood_season_empty_storage": flood_season_empty_storage,
                "target_storage_ratio": target_storage_ratio if flood_season_empty_storage else None,
                "reservoir_constraints": {
                    "三门峡水库": {"max_level": smx_max_level, "max_storage": smx_max_storage},
                    "小浪底水库": {"max_level": xld_max_level, "max_storage": xld_max_storage},
                    "陆浑水库": {"max_level": lh_max_level, "max_storage": lh_max_storage},
                    "故县水库": {"max_level": gx_max_level, "max_storage": gx_max_storage},
                    "河口村水库": {"max_level": hkc_max_level, "max_storage": hkc_max_storage}
                }
            },
            "schemes": schemes,
            "message": f"成功生成{len(schemes)}个调度方案单"
        }
        logger.info(f"generate_dispatch_scheme 返回结果: {return_value}")
        return return_value

