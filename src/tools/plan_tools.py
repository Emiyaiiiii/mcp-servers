from fastmcp import FastMCP
import os
import requests
import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from src.utils.logger import get_logger
from src.tools.data_api_tools import _resolve_reservoir_for_api, _resolve_station
from src.services.storage.database.data_access import (
    WaterLevelAccess, CoefficientAccess, HolePriorityAccess
)
from src.services.external_api.enhanced_search_service import enhanced_search_service

logger = get_logger(__name__)

from src.config.settings import settings

KNOWLEDGE_BASE_API_URL = settings.KNOWLEDGE_BASE_API_URL

TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates"


def _get_water_level_config(reservoir_code: str, level: float) -> dict:
    """从数据库获取水位-流量配置"""
    config = WaterLevelAccess.get_by_level(reservoir_code, level)
    if not config:
        logger.warning(f"未找到水位配置: {reservoir_code}, {level}")
    return config or {}


def _get_coefficient_table(reservoir_code: str, level_range: str) -> list:
    """从数据库获取调度系数表"""
    return CoefficientAccess.get_by_level_range(reservoir_code, level_range)


def _get_dikong_order(reservoir_code: str) -> list:
    """从数据库获取底孔优先级顺序"""
    return HolePriorityAccess.get_priority_order(reservoir_code)


def register_plan_tools(mcp: FastMCP):

    @mcp.tool()
    async def list_plan_templates() -> dict:
        """
        列出所有可用的预案模板。

        Returns:
            模板列表，每个模板包含name和description
        """
        logger.info(f"调用 list_plan_templates，收到参数: (无)")
        try:
            templates = []
            descriptions = {
                "flood_control.md": "防洪应急预案模板",
                "reservoir_dispatch.md": "水库调度方案模板"
            }
            for f in os.listdir(TEMPLATE_DIR):
                if f.endswith(('.md', '.j2', '.jinja')):
                    templates.append({
                        "name": f,
                        "description": descriptions.get(f, "预案模板")
                    })
            return_value = {"templates": templates}
            logger.debug(f"list_plan_templates 返回结果: {return_value}")
            return return_value
        except Exception as e:
            return_value = {"error": f"获取模板列表时出错: {str(e)}"}
            logger.debug(f"list_plan_templates 返回结果: {return_value}")
            return return_value

    @mcp.tool()
    async def load_plan_template(generation_time: str, scheme_id: str = None) -> str:
        """
        自动查询数据并生成完整的洪水调度预案。

        该函数会自动：
        1. 根据指定时间查询水库水位数据（小浪底、三门峡、陆浑、故县、河口村、东平湖）
        2. 根据指定时间查询水文站流量数据（潼关、龙门、花园口、高村、华县等）
        3. 判断黄河总体应急响应等级
        4. 判断小浪底、三门峡预警等级
        5. 判断花园口出险等级和滩区淹没情况
        6. 生成各水库调度方案
        7. 渲染预案模板

        Args:
            generation_time: 调度方案的**开始时间**（必传），即预案对应调度时段的起始时刻。支持历史时间查询。格式: "yyyy-MM-dd HH:mm:ss" 或 "yyyy-MM-dd"，例如 "2021-10-02" 对应2021年秋汛调度方案的开始时间
            scheme_id: 调度方案ID，如果提供，则从调度方案中获取各水库数据（取最大值）

        Returns:
            渲染后的完整预案内容（HTML格式）
        """
        logger.info(f"调用 load_plan_template，generation_time={repr(generation_time)}, scheme_id={repr(scheme_id)}")
        try:
            from datetime import datetime, timedelta
            from src.tools.data_api_tools import _get, BASE_URL

            current_time = datetime.now()
            specified_time = None

            try:
                specified_time = datetime.strptime(generation_time, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
                    specified_time = datetime.strptime(generation_time, "%Y-%m-%d")
                except ValueError:
                    return_value = f"生成预案时出错: 时间格式无效，请使用 'yyyy-MM-dd HH:mm:ss' 或 'yyyy-MM-dd' 格式，例如 '2026-04-15 00:00:00' 或 '2026-04-15'"
                    logger.error(f"load_plan_template 错误: {return_value}")
                    return return_value

            is_historical = specified_time < current_time - timedelta(hours=1)
            logger.info(f"历史场景判断: {is_historical}, 指定时间: {specified_time}, 当前时间: {current_time}")

            reservoir_data = {}
            hydrology_data = {}
            rainfall_data = {}

            RESERVOIRS = ["小浪底", "三门峡", "陆浑", "故县", "河口村"]
            STATIONS = ["潼关", "龙门", "花园口", "高村", "华县"]

            use_scheme_data = False
            if scheme_id:
                try:
                    from src.tools.ui_tools import get_scheme
                    scheme = get_scheme(scheme_id)
                    if scheme:
                        reservoirs = scheme.get("reservoirs", {})
                        for res_name, res_data in reservoirs.items():
                            timeseries = res_data.get("timeseries", [])
                            if timeseries:
                                max_level = None
                                max_inflow = None
                                max_outflow = None
                                max_storage = None
                                for ts in timeseries:
                                    level = ts.get("water_level")
                                    inflow = ts.get("inflow")
                                    outflow = ts.get("outflow")
                                    storage = ts.get("storage")
                                    if level is not None and (max_level is None or level > max_level):
                                        max_level = level
                                    if inflow is not None and (max_inflow is None or inflow > max_inflow):
                                        max_inflow = inflow
                                    if outflow is not None and (max_outflow is None or outflow > max_outflow):
                                        max_outflow = outflow
                                    if storage is not None and (max_storage is None or storage > max_storage):
                                        max_storage = storage
                                if max_level is not None:
                                    normalized_name = res_name.replace("水库", "")
                                    reservoir_data[normalized_name] = {
                                        "shui_wei": max_level,
                                        "ru_ku_liu_liang": max_inflow,
                                        "chu_ku_liu_liang": max_outflow,
                                        "xu_liang": max_storage
                                    }
                        
                        stations = scheme.get("hydrological_stations", {})
                        station_name_mapping = {
                            "龙门镇": "龙门",
                            "白马寺": "白马寺",
                            "黑石关": "黑石关",
                            "花园口": "花园口"
                        }
                        for station_name, station_data in stations.items():
                            timeseries = station_data.get("timeseries", [])
                            if timeseries:
                                max_flow = None
                                max_level = None
                                for ts in timeseries:
                                    flow = ts.get("flow")
                                    level = ts.get("level")
                                    if flow is not None and (max_flow is None or flow > max_flow):
                                        max_flow = flow
                                    if level is not None and (max_level is None or level > max_level):
                                        max_level = level
                                if max_flow is not None:
                                    normalized_name = station_name_mapping.get(station_name, station_name)
                                    hydrology_data[normalized_name] = {
                                        "liu_liang": max_flow,
                                        "shui_wei": max_level
                                    }
                        
                        use_scheme_data = True
                        logger.info(f"已从调度方案 {scheme_id} 中提取数据")
                except Exception as e:
                    logger.warning(f"从调度方案获取数据失败: {e}")

            if not use_scheme_data:
                try:
                    if is_historical:
                        query_date = specified_time.strftime("%Y-%m-%d")
                        for reservoir in RESERVOIRS:
                            url = f"{BASE_URL}/hydrometric/rhourrt/list"
                            reservoir_code = _resolve_reservoir_for_api(reservoir)
                            if not reservoir_code:
                                continue
                            params = {"resname": reservoir_code, "startDate": query_date, "endDate": query_date}
                            result = _get(url, params)
                            if isinstance(result, dict) and "data" in result and result["data"]:
                                max_level = None
                                max_inflow = None
                                max_outflow = None
                                max_storage = None
                                for item in result["data"]:
                                    level = item.get("level")
                                    inflow = item.get("inflow")
                                    outflow = item.get("outflow")
                                    storage = item.get("wq")
                                    if level is not None and (max_level is None or level > max_level):
                                        max_level = level
                                    if inflow is not None and (max_inflow is None or inflow > max_inflow):
                                        max_inflow = inflow
                                    if outflow is not None and (max_outflow is None or outflow > max_outflow):
                                        max_outflow = outflow
                                    if storage is not None and (max_storage is None or storage > max_storage):
                                        max_storage = storage
                                if max_level is not None:
                                    reservoir_data[reservoir] = {
                                        "shui_wei": max_level,
                                        "ru_ku_liu_liang": max_inflow,
                                        "chu_ku_liu_liang": max_outflow,
                                        "xu_liang": max_storage
                                    }
                    else:
                        url = f"{BASE_URL}/hydrometric/rhourrt/listLatest"
                        result = _get(url)
                        if isinstance(result, dict) and "data" in result:
                            for item in result["data"]:
                                name = item.get("ennm") or item.get("stnm")
                                if name:
                                    reservoir_data[name] = {
                                        "shui_wei": item.get("level"),
                                        "ru_ku_liu_liang": item.get("inflow"),
                                        "chu_ku_liu_liang": item.get("outflow"),
                                        "xu_liang": item.get("wq")
                                    }
                except Exception as e:
                    logger.warning(f"查询水库数据失败: {e}")

                try:
                    if is_historical:
                        query_date = specified_time.strftime("%Y-%m-%d")
                        for station in STATIONS:
                            url = f"{BASE_URL}/hydrometric/hourrt/list"
                            station_code = _resolve_station(station)
                            if not station_code:
                                continue
                            params = {"hysta": station_code, "startDate": query_date, "endDate": query_date}
                            result = _get(url, params)
                            if isinstance(result, dict) and "data" in result and result["data"]:
                                max_flow = None
                                max_level = None
                                for item in result["data"]:
                                    flow = item.get("flow")
                                    level = item.get("level")
                                    if flow is not None and (max_flow is None or flow > max_flow):
                                        max_flow = flow
                                    if level is not None and (max_level is None or level > max_level):
                                        max_level = level
                                if max_flow is not None:
                                    hydrology_data[station] = {
                                        "liu_liang": max_flow,
                                        "shui_wei": max_level
                                    }
                    else:
                        url = f"{BASE_URL}/hydrometric/hourrt/listLatest"
                        result = _get(url)
                        if isinstance(result, dict) and "data" in result:
                            for item in result["data"]:
                                name = item.get("stnm")
                                if name:
                                    hydrology_data[name] = {
                                        "liu_liang": item.get("flow"),
                                        "shui_wei": item.get("level")
                                    }
                except Exception as e:
                    logger.warning(f"查询水文站数据失败: {e}")

            try:
                if is_historical:
                    end_time = specified_time.strftime("%Y-%m-%d %H:%M:%S")
                    start_time = (specified_time - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
                else:
                    end_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
                    start_time = (current_time - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
                
                url = f"{BASE_URL}/rainfall/hourrth/getRainfall"
                params = {"startTime": start_time, "endTime": end_time}
                result = _get(url, params)
                if isinstance(result, dict) and result.get("code") == 200 and "data" in result:
                    data = result["data"]
                    if isinstance(data, list):
                        rainfall_sum = 0
                        count = 0
                        for item in data:
                            rainfall = item.get("rf", 0)
                            if rainfall and isinstance(rainfall, (int, float)):
                                rainfall_sum += rainfall
                                count += 1
                        if count > 0:
                            rainfall_data["avg_rainfall"] = round(rainfall_sum / count, 2)
                            rainfall_data["station_count"] = count
            except Exception as e:
                logger.warning(f"查询雨量数据失败: {e}")

            reservoir_level = reservoir_data.get("小浪底", {}).get("shui_wei")
            sanmenxia_level = reservoir_data.get("三门峡", {}).get("shui_wei")
            luhun_level = reservoir_data.get("陆浑", {}).get("shui_wei")
            guxian_level = reservoir_data.get("故县", {}).get("shui_wei")
            hekoucun_level = reservoir_data.get("河口村", {}).get("shui_wei")
            tongguan_flow = hydrology_data.get("潼关", {}).get("liu_liang")
            longmen_flow = hydrology_data.get("龙门", {}).get("liu_liang")
            huayuankou_flow = hydrology_data.get("花园口", {}).get("liu_liang")
            huaxian_flow = hydrology_data.get("华县", {}).get("liu_liang")
            xiaolangdi_outflow = reservoir_data.get("小浪底", {}).get("chu_ku_liu_liang")
            
            if scheme_id and not tongguan_flow:
                tongguan_flow = reservoir_data.get("小浪底", {}).get("ru_ku_liu_liang")

            risk_result = {}
            try:
                if huayuankou_flow:
                    risk_result = _get_risk_by_huayuankou_flow_core(float(huayuankou_flow))
            except Exception as e:
                logger.warning(f"出险判断失败: {e}")

            submerge_result = {}
            try:
                if huayuankou_flow:
                    submerge_result = _get_flood_submerge_core(float(huayuankou_flow))
            except Exception as e:
                logger.warning(f"淹没分析失败: {e}")

            xld_scheme = {}
            try:
                if reservoir_level or tongguan_flow:
                    data = _generate_xiaolangdi_scheme_core(
                        date=generation_time,
                        liu_liang=float(tongguan_flow) if tongguan_flow else 1500,
                        shui_wei=float(reservoir_level) if reservoir_level else 240,
                        han_sha_liang=10.0
                    )
                    xld_scheme = data
            except Exception as e:
                logger.warning(f"小浪底调度方案生成失败: {e}")

            smx_scheme = {}
            try:
                if sanmenxia_level or tongguan_flow:
                    data = _generate_sanmenxia_scheme_core(
                        date=generation_time,
                        liu_liang=float(tongguan_flow) if tongguan_flow else 1000,
                        shui_wei=float(sanmenxia_level) if sanmenxia_level else 310,
                        han_sha_liang=10.0
                    )
                    smx_scheme = data
            except Exception as e:
                logger.warning(f"三门峡调度方案生成失败: {e}")

            xld_warning = {}
            try:
                if tongguan_flow or reservoir_level or xiaolangdi_outflow:
                    xld_warning = await _get_xiaolangdi_warning(
                        float(tongguan_flow) if tongguan_flow else 0,
                        float(reservoir_level) if reservoir_level else 0,
                        float(xiaolangdi_outflow) if xiaolangdi_outflow else 0
                    )
            except Exception as e:
                logger.warning(f"小浪底预警判断失败: {e}")

            smx_warning = {}
            try:
                if longmen_flow or tongguan_flow or huaxian_flow:
                    smx_warning = await _get_sanmenxia_warning(
                        float(longmen_flow) if longmen_flow else 0,
                        float(tongguan_flow) if tongguan_flow else 0,
                        float(huaxian_flow) if huaxian_flow else 0
                    )
            except Exception as e:
                logger.warning(f"三门峡预警判断失败: {e}")

            overall_response = {}
            try:
                overall_response = await _get_overall_emergency_response(
                    luhun_level=float(luhun_level) if luhun_level else None,
                    hekoucun_level=float(hekoucun_level) if hekoucun_level else None,
                    xiaolangdi_level=float(reservoir_level) if reservoir_level else None,
                    sanmenxia_level=float(sanmenxia_level) if sanmenxia_level else None,
                    tongguan_flow=float(tongguan_flow) if tongguan_flow else None,
                    huayuankou_flow=float(huayuankou_flow) if huayuankou_flow else None
                )
            except Exception as e:
                logger.warning(f"黄河总体应急响应判断失败: {e}")

            engineering_warnings = []
            try:
                url = f"{BASE_URL}/hydrometric/warn/getResEWarnInfo"
                result = _get(url)
                if isinstance(result, dict) and result.get("code") == 200 and "data" in result:
                    for item in result["data"]:
                        stnm = item.get("stnm", "未知")
                        dvalue = item.get("dvalue", 0)
                        level = item.get("level", 0)
                        engineering_warnings.append(f"{stnm}超汛限{dvalue}米")
            except Exception as e:
                logger.warning(f"查询水库预警失败: {e}")

            try:
                url = f"{BASE_URL}/hydrometric/warn/getQEWarnInfo"
                result = _get(url)
                if isinstance(result, dict) and result.get("code") == 200 and "data" in result:
                    for item in result["data"]:
                        stnm = item.get("stnm", "未知")
                        dvalue = item.get("dvalue", 0)
                        engineering_warnings.append(f"{stnm}超限{dvalue}立方米每秒")
            except Exception as e:
                logger.warning(f"查询水文站预警失败: {e}")

            env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))

            template_name = "flood_control_html.j2"
            template = env.get_template(template_name)

            risk_level_str = ""
            if risk_result:
                risk_level_str = risk_result.get("level", "正常")
                if risk_result.get("suggestion"):
                    risk_level_str += f"，{risk_result.get('suggestion', '')}"

            submerge_str = ""
            if submerge_result:
                submerge_str = submerge_result.get("description", "")
                if submerge_result.get("henan"):
                    hn = submerge_result["henan"]
                    if hn.get("进水人口"):
                        submerge_str += f"河南进水村庄{hn.get('进水村庄数', 0)}个,人口{hn.get('进水人口', 0)}万"
                if submerge_result.get("shandong"):
                    sd = submerge_result["shandong"]
                    if sd.get("漫滩面积(万亩)"):
                        submerge_str += f";山东漫滩{sd.get('漫滩面积(万亩)', 0)}万亩"

            xld_scheme_str = xld_scheme.get("tuijianfangan", "") if isinstance(xld_scheme, dict) else ""
            smx_scheme_str = smx_scheme.get("tuijianfangan", "") if isinstance(smx_scheme, dict) else ""

            river_situation_str = "待更新"
            if hydrology_data:
                parts = []
                for station, data in hydrology_data.items():
                    if isinstance(data, dict) and data.get("liu_liang"):
                        parts.append(f"{station}:{data['liu_liang']}m³/s")
                if parts:
                    river_situation_str = "、".join(parts)

            reservoir_situation_str = "待更新"
            if reservoir_data:
                parts = []
                for name, data in reservoir_data.items():
                    if isinstance(data, dict) and data.get("shui_wei"):
                        parts.append(f"{name}:{data['shui_wei']}m")
                if parts:
                    reservoir_situation_str = "、".join(parts)

            suggestions_str = "加强监测，密切关注水情变化，做好应急准备"
            if risk_result and risk_result.get("suggestion"):
                suggestions_str = risk_result.get("suggestion")

            rainfall_situation_str = "待更新"
            if rainfall_data:
                rainfall_situation_str = f"平均降雨量 {rainfall_data.get('avg_rainfall', 0)}mm（{rainfall_data.get('station_count', 0)}个站点）"

            xld_warning_str = xld_warning.get("level", "待判断") if isinstance(xld_warning, dict) else "待判断"
            smx_warning_str = smx_warning.get("level", "待判断") if isinstance(smx_warning, dict) else "待判断"
            overall_response_str = overall_response.get("response_level", "待判断") if isinstance(overall_response, dict) else "待判断"

            engineering_situation_str = "暂无险情"
            if engineering_warnings:
                engineering_situation_str = "；".join(engineering_warnings)

            context = {
                'generation_time': generation_time,
                'rainfall_situation': rainfall_situation_str if rainfall_situation_str != '待更新' else '【大模型需调用工具获取雨量数据】',
                'river_situation': river_situation_str if river_situation_str != '待更新' else '【大模型需调用 get_river_latest_realtime 或 list_realtime_hydrology 获取河道水情数据】',
                'reservoir_situation': reservoir_situation_str if reservoir_situation_str != '待更新' else '【大模型需调用 get_reservoir_latest_realtime 或 get_reservoir_realtime 获取水库水情数据】',
                'engineering_situation': engineering_situation_str if engineering_situation_str != '暂无险情' else '【大模型需查询工程险情信息】',
                'rainfall_forecast': '【大模型需调用降雨预报接口获取未来降雨预报】',
                'area_rainfall': '【大模型需调用 get_rainfall_statistics 获取流域面雨量】',
                'upstream_forecast': '【大模型需调用洪水预报接口获取上游径流预报】',
                'downstream_forecast': '【大模型需调用洪水预报接口获取中下游洪峰预报】',
                'sanmenxia_scheme': smx_scheme_str if smx_scheme_str else '【大模型需调用 generate_sanmenxia_scheme 生成三门峡调度方案】',
                'xiaolangdi_scheme': xld_scheme_str if xld_scheme_str else '【大模型需调用 generate_xiaolangdi_scheme 生成小浪底调度方案】',
                'luhun_scheme': '【大模型需根据陆浑水库实时数据补充调度方案】',
                'guxian_scheme': '【大模型需根据故县水库实时数据补充调度方案】',
                'hekoucun_scheme': '【大模型需根据河口村水库实时数据补充调度方案】',
                'overall_response': overall_response_str if overall_response_str != '待判断' else '【大模型需根据水情数据判断黄河总体应急响应等级】',
                'xiaolangdi_warning': xld_warning_str if xld_warning_str != '待判断' else '【大模型需根据潼关流量和小浪底水位判断预警等级】',
                'sanmenxia_warning': smx_warning_str if smx_warning_str != '待判断' else '【大模型需根据龙门、潼关、华县流量判断三门峡预警等级】',
                'risk_level': risk_level_str if risk_level_str else '【大模型需根据花园口流量判断出险等级】',
                'submerge_analysis': submerge_str if submerge_str else '【大模型需调用 get_flood_submerge 分析滩区淹没情况】',
                'beach_impact': submerge_str if submerge_str else '【大模型需分析滩区影响】',
                'danger_prediction': risk_level_str if risk_level_str else '【大模型需预判工情险情】',
                'emergency_measures': '【大模型需根据预警等级制定应急保障措施】',
                'suggestions': suggestions_str if suggestions_str else '【大模型需根据当前水情给出处置建议】',
                'data_source': f"数据时间基准: {generation_time}",
                'historical_mode': is_historical
            }

            return_value = template.render(context)
            logger.info(f"load_plan_template 返回结果长度: {len(return_value)}")
            return return_value

        except TemplateNotFound:
            available = [f for f in os.listdir(TEMPLATE_DIR) if f.endswith(('.md', '.j2', '.jinja'))]
            return_value = f"模板 '{template_name}' 不存在。可用模板: {available}"
            logger.debug(f"load_plan_template 返回结果: {repr(return_value)}")
            return return_value
        except Exception as e:
            return_value = f"生成预案时出错: {str(e)}"
            logger.error(f"load_plan_template 错误: {str(e)}")
            return return_value

    @mcp.tool()
    async def query_knowledge_base(
        query: str,
        mode: str = "hybrid",
        top_k: int = 10
    ) -> dict:
        """
        查询防洪知识库。

        Args:
            query: 用户的具体水利业务问题的自然语言问句，如: "黄河流域有哪些贫困县？", "当前水库调度方案是什么？", "如何应对超标洪水？", "小浪底水库的汛限水位是多少？"
            mode: 知识图谱查询模式，可选: local(本地实体关系), global(全局模式), hybrid(混合模式), naive(向量检索), mix(知识图谱+向量)
            top_k: 返回结果数量（默认10），混合模式下各数据源各取一半

        Returns:
            查询结果，包含entities(实体), relationships(关系), chunks(文本片段), references(参考文献)
        """
        source = "knowledge_base"
        logger.info(f"调用 query_knowledge_base，query={query}, mode={mode}, source={source}, top_k={top_k}")
        # 根据 source 参数决定查询哪些数据源
        use_graph = source in ("knowledge_graph", "hybrid")
        use_kb = source in ("knowledge_base", "hybrid")
        
        # 混合模式下各取一半，非混合模式取全部 top_k
        graph_top_k = top_k // 2 if source == "hybrid" else top_k
        kb_top_k = top_k - graph_top_k if source == "hybrid" else top_k
        
        # 存储两个数据源的结果
        results = {
            "knowledge_graph": None,
            "knowledge_base": None
        }
        
        # 第一个数据源：知识图谱接口
        if use_graph:
            try:
                payload = {
                    "query": query,
                    "mode": mode,
                    "top_k": graph_top_k
                }
                
                response = requests.post(KNOWLEDGE_BASE_API_URL, json=payload, timeout=30)
                response.raise_for_status()
                
                result = response.json()
                
                if result.get("status") == "success":
                    results["knowledge_graph"] = result
                    logger.debug(f"知识图谱查询成功: {result.get('data', {})}")
                else:
                    logger.warning(f"知识图谱查询失败: {result.get('message', '未知错误')}")
            
            except requests.exceptions.RequestException as e:
                logger.warning(f"调用知识图谱接口失败: {str(e)}")
        else:
            logger.info("跳过知识图谱查询（source=knowledge_base）")
        
        # 第二个数据源：知识库接口
        if use_kb:
            try:
                knowledge_base_result = enhanced_search_service.search_documents(query, knowledge_base_ids=[3,7,8,35,2790,2879,3212], top_k=kb_top_k)
                if knowledge_base_result:
                    results["knowledge_base"] = knowledge_base_result
                    logger.debug(f"知识库接口查询成功")
            except Exception as e:
                logger.warning(f"调用知识库接口失败: {str(e)}")
        else:
            logger.info("跳过知识库查询（source=knowledge_graph）")
        
        # 合并两个数据源的结果
        entities = []
        relationships = []
        chunks = []
        references = []
        knowledge_base_chunks = []
        summary = []
        
        # 处理知识图谱结果
        if results["knowledge_graph"] and results["knowledge_graph"].get("status") == "success":
            data = results["knowledge_graph"].get("data", {})
            entities.extend(data.get("entities", []))
            relationships.extend(data.get("relationships", []))
            chunks.extend(data.get("chunks", []))
            references.extend(data.get("references", []))
            
            if chunks:
                for chunk in chunks:
                    content = chunk.get("content", "")[:300]
                    source = chunk.get("file_path", "")
                    summary.append(f"【知识图谱-内容片段】{content}...\n来源: {source}")
            
            if entities:
                for entity in entities:
                    name = entity.get("entity_name", "")
                    entity_type = entity.get("entity_type", "")
                    desc = entity.get("description", "")[:200]
                    summary.append(f"【知识图谱-实体】{name} ({entity_type}): {desc}...")
            
            if relationships:
                for rel in relationships:
                    src = rel.get("src_id", "")
                    tgt = rel.get("tgt_id", "")
                    desc = rel.get("description", "")[:150]
                    summary.append(f"【知识图谱-关系】{src} -> {tgt}: {desc}...")
        
        # 处理知识库结果
        if results["knowledge_base"]:
            knowledge_base_data = results["knowledge_base"].get("data", results["knowledge_base"])
            
            if isinstance(knowledge_base_data, list):
                for item in knowledge_base_data:
                    content = item.get("content", "") or item.get("text", "")[:300]
                    title = item.get("title", "")
                    source = item.get("source", "") or item.get("file_name", "")
                    if content:
                        knowledge_base_chunks.append({
                            "content": content,
                            "title": title,
                            "source": source
                        })
                        summary.append(f"【知识库-文档】{title}\n{content}...\n来源: {source}")
            elif isinstance(knowledge_base_data, dict):
                docs = knowledge_base_data.get("documents", []) or knowledge_base_data.get("results", [])
                for doc in docs:
                    content = doc.get("content", "") or doc.get("text", "")[:300]
                    title = doc.get("title", "")
                    source = doc.get("source", "") or doc.get("file_name", "")
                    if content:
                        knowledge_base_chunks.append({
                            "content": content,
                            "title": title,
                            "source": source
                        })
                        summary.append(f"【知识库-文档】{title}\n{content}...\n来源: {source}")
        
        return_value = {
            "success": True,
            "query": query,
            "mode": mode,
            "source": source,
            "top_k": top_k,
            "entities": entities,
            "relationships": relationships,
            "chunks": chunks,
            "knowledge_base_chunks": knowledge_base_chunks,
            "references": references,
            "summary": "\n\n".join(summary) if summary else "未找到相关知识",
            "sources": {
                "knowledge_graph": results["knowledge_graph"] is not None,
                "knowledge_base": results["knowledge_base"] is not None
            }
        }
        
        logger.debug(f"query_knowledge_base 返回结果: 成功检索到 {len(entities)} 个实体, {len(relationships)} 个关系, {len(chunks)} 个文本片段, {len(knowledge_base_chunks)} 个知识库文档")
        return return_value


    async def _get_xiaolangdi_warning(tongguan_flow: float, reservoir_level: float, outflow_flow: float) -> dict:
        """小浪底预警等级判断"""
        result = {
            "level": "未达到预警级别",
            "source": "",
            "measures": []
        }

        warnings = []

        if tongguan_flow is not None:
            if tongguan_flow > 15000:
                warnings.append(("I级", "潼关流量>15000m³/s"))
            elif 10000 <= tongguan_flow < 15000:
                warnings.append(("I级", "潼关流量10000~15000m³/s"))
            elif 8000 <= tongguan_flow < 10000:
                warnings.append(("II级", "潼关流量8000~10000m³/s"))
            elif 5000 <= tongguan_flow < 8000:
                warnings.append(("III级", "潼关流量5000~8000m³/s"))

        if reservoir_level is not None:
            if reservoir_level > 275:
                warnings.append(("I级", "水库蓄水位>275m"))
            elif reservoir_level == 275:
                warnings.append(("I级", "水库蓄水位=275m"))
            elif 272.5 <= reservoir_level < 275:
                warnings.append(("II级", "水库蓄水位272.5~275m"))
            elif 270 <= reservoir_level < 272.5:
                warnings.append(("III级", "水库蓄水位270~272.5m"))

        if outflow_flow is not None:
            if outflow_flow >= 10000:
                warnings.append(("I级", "出库流量≥10000m³/s"))
            elif 8000 <= outflow_flow < 10000:
                warnings.append(("I级", "出库流量8000~10000m³/s"))
            elif 6000 <= outflow_flow < 8000:
                warnings.append(("II级", "出库流量6000~8000m³/s"))
            elif 4000 <= outflow_flow < 6000:
                warnings.append(("III级", "出库流量4000~6000m³/s"))

        if warnings:
            warnings.sort(key=lambda x: {"I级": 0, "II级": 1, "III级": 2}[x[0]])
            highest = warnings[0]
            result["level"] = highest[0]
            result["source"] = highest[1]

        return result

    async def _get_sanmenxia_warning(longmen_flow: float, tongguan_flow: float, huaxian_flow: float) -> dict:
        """三门峡预警等级判断"""
        result = {
            "level": "无预警",
            "trigger_source": ""
        }

        warnings = []

        if longmen_flow is not None:
            if longmen_flow >= 8000:
                warnings.append(("I级", "龙门流量≥8000m³/s"))
            elif 6000 <= longmen_flow < 8000:
                warnings.append(("II级", "龙门流量6000~8000m³/s"))
            elif 4000 <= longmen_flow < 6000:
                warnings.append(("III级", "龙门流量4000~6000m³/s"))

        if tongguan_flow is not None:
            if tongguan_flow >= 8000:
                warnings.append(("I级", "潼关流量≥8000m³/s"))
            elif 6000 <= tongguan_flow < 8000:
                warnings.append(("II级", "潼关流量6000~8000m³/s"))
            elif 4000 <= tongguan_flow < 6000:
                warnings.append(("III级", "潼关流量4000~6000m³/s"))

        if huaxian_flow is not None:
            if huaxian_flow >= 3000:
                warnings.append(("I级", "华县流量≥3000m³/s"))
            elif 2000 <= huaxian_flow < 3000:
                warnings.append(("II级", "华县流量2000~3000m³/s"))
            elif 1000 <= huaxian_flow < 2000:
                warnings.append(("III级", "华县流量1000~2000m³/s"))

        if warnings:
            warnings.sort(key=lambda x: {"I级": 0, "II级": 1, "III级": 2}[x[0]])
            highest = warnings[0]
            result["level"] = highest[0]
            result["trigger_source"] = highest[1]

        return result

    async def _get_overall_emergency_response(
        luhun_level: float = None,
        hekoucun_level: float = None,
        xiaolangdi_level: float = None,
        sanmenxia_level: float = None,
        tongguan_flow: float = None,
        huayuankou_flow: float = None
    ) -> dict:
        """黄河总体应急响应判断"""
        result = {
            "response_level": "无预警",
            "description": "根据洪水预报及各水库水位分析，当前无预警"
        }

        warnings = []

        if luhun_level is not None and luhun_level >= 319.5:
            warnings.append(("I级", "陆浑水库水位≥319.5m"))
        elif luhun_level is not None and luhun_level >= 318:
            warnings.append(("II级", "陆浑水库水位≥318m"))

        if hekoucun_level is not None and hekoucun_level >= 275:
            warnings.append(("I级", "河口村水库水位≥275m"))
        elif hekoucun_level is not None and hekoucun_level >= 270:
            warnings.append(("II级", "河口村水库水位≥270m"))

        if xiaolangdi_level is not None and xiaolangdi_level >= 275:
            warnings.append(("I级", "小浪底水库水位≥275m"))
        elif xiaolangdi_level is not None and xiaolangdi_level >= 272.5:
            warnings.append(("II级", "小浪底水库水位≥272.5m"))

        if sanmenxia_level is not None and sanmenxia_level >= 325:
            warnings.append(("I级", "三门峡水库水位≥325m"))
        elif sanmenxia_level is not None and sanmenxia_level >= 320:
            warnings.append(("II级", "三门峡水库水位≥320m"))

        if tongguan_flow is not None and tongguan_flow >= 8000:
            warnings.append(("I级", "潼关流量≥8000m³/s"))
        elif tongguan_flow is not None and tongguan_flow >= 5000:
            warnings.append(("II级", "潼关流量≥5000m³/s"))

        if huayuankou_flow is not None and huayuankou_flow >= 8000:
            warnings.append(("I级", "花园口流量≥8000m³/s"))
        elif huayuankou_flow is not None and huayuankou_flow >= 4000:
            warnings.append(("II级", "花园口流量≥4000m³/s"))

        if warnings:
            warnings.sort(key=lambda x: {"I级": 0, "II级": 1, "III级": 2}[x[0]])
            highest = warnings[0]
            level_map = {
                "I级": "I级应急响应",
                "II级": "II级应急响应",
                "III级": "III级应急响应"
            }
            result["response_level"] = level_map.get(highest[0], highest[0])
            result["description"] = f"触发条件: {highest[1]}"

        return result

def _generate_xiaolangdi_scheme_core(
    date: str,
    liu_liang: float,
    shui_wei: float,
    han_sha_liang: float
) -> dict:
    """
    生成小浪底水库机组孔洞调度方案（内部函数）。

    Args:
        date: 日期时间，格式: yyyy-MM-dd HH:mm:ss
        liu_liang: 出库流量（m³/s）
        shui_wei: 当前水位（m）
        han_sha_liang: 含沙量（kg/m³）

    Returns:
        调度方案建议，包含推荐方案描述
    """
    try:
        q = int(round(liu_liang))
        wl = shui_wei
        sand = han_sha_liang
        
        cfg = _get_water_level_config("XLD", wl)
        
        if not cfg or not cfg.get("hole_details"):
            return {"date": date, "tuijianfangan": "水位不匹配，无法生成调度方案"}
        
        stop_turb = wl < 215 or sand > 20
        
        if stop_turb:
            turb_txt = "根据当前机组状态推荐全停，结合实际调整机组。"
            hole_target = q
        else:
            turb_txt = "根据当前机组状态推荐全开6台机组，每台300m³/s，合计1800m³/s，结合实际调整。"
            hole_target = max(q - 1800, 0)
        
        holes = cfg.get("hole_details", [])
        
        total = 0
        used = []
        hole_list = []
        for hole in holes:
            if total >= hole_target:
                break
            max_flow = hole.get("流量", 0)
            take = min(max_flow, hole_target - total)
            hole_number = hole.get("编号", "")
            hole_index = int(hole_number.replace("号", "").replace("洞", "")) if hole_number else 0
            used.append((hole.get("type", "未知"), hole_number, take))
            hole_list.append({
                "type": hole.get("type"),
                "number": hole_number,
                "index": hole_index,
                "flow": take,
                "max_flow": max_flow
            })
            total += take
        
        if not used:
            hole_txt = "无需开启孔洞"
        else:
            group = {}
            for hole_type, number, value in used:
                group.setdefault(hole_type, []).append(f"{number}：{value}m³/s")
            
            parts = []
            for hole_type in ["排沙洞", "孔板洞", "明流洞"]:
                if hole_type in group:
                    parts.append(f"{len(group[hole_type])}条{hole_type}（{', '.join(group[hole_type])}）")
            
            last_type, last_number, last_value = used[-1]
            for hole in holes:
                if hole.get("编号") == last_number:
                    max_flow = hole.get("流量", 0)
                    if last_value < max_flow:
                        parts.append(f"{last_number}{last_type}剩余流量补足：{last_value}m³/s")
                    break
            
            hole_txt = "，".join(parts)
        
        reason = f"因为当前泥沙含量为{sand}kg/m³，水位是{wl}m，出库流量为{q}m³/s，{turb_txt}根据孔洞检修情况推荐：{hole_txt}，结合实际调整。"
        return {
            "date": date,
            "tuijianfangan": reason,
            "holes": hole_list,
            "total_flow": total,
            "unit_status": "全停" if stop_turb else "全开6台机组"
        }
        
    except Exception as e:
        error_msg = f"生成调度方案时出错: {str(e)}"
        logger.error(error_msg)
        return {"date": date, "tuijianfangan": f"生成调度方案失败: {error_msg}"}

    @mcp.tool()
    async def generate_xiaolangdi_scheme(
        date: str,
        liu_liang: float,
        shui_wei: float,
        han_sha_liang: float
    ) -> dict:
        """
        生成小浪底水库机组孔洞调度方案。

        Args:
            date: 日期时间，格式: yyyy-MM-dd HH:mm:ss
            liu_liang: 出库流量（m³/s）
            shui_wei: 当前水位（m）
            han_sha_liang: 含沙量（kg/m³）

        Returns:
            调度方案建议，包含推荐方案描述
        """
        logger.info(f"调用 generate_xiaolangdi_scheme，收到参数: date={repr(date)}, liu_liang={liu_liang}, shui_wei={shui_wei}, han_sha_liang={han_sha_liang}")
        
        return_value = _generate_xiaolangdi_scheme_core(date, liu_liang, shui_wei, han_sha_liang)
        
        logger.debug(f"generate_xiaolangdi_scheme 返回结果: {return_value}")
        return return_value

def _generate_sanmenxia_scheme_core(
    date: str,
    liu_liang: float,
    shui_wei: float,
    han_sha_liang: float
) -> dict:
    """
    生成三门峡水库机组孔洞调度方案（内部函数）。

    Args:
        date: 日期时间，格式: yyyy-MM-dd HH:mm:ss
        liu_liang: 出库流量（m³/s）
        shui_wei: 当前水位（m）
        han_sha_liang: 含沙量（kg/m³）

    Returns:
        调度方案建议，包含推荐方案描述及各部件状态
    """
    try:
        q_total = round(liu_liang)
        wl = shui_wei
        sand = han_sha_liang

        cfg = _get_water_level_config("SMX", wl)
        
        if not cfg:
            return {"date": date, "tuijianfangan": "水位不匹配，无法生成调度方案"}
        
        q_dk = round(cfg.get("bottom_hole_flow", 0))
        q_sk = round(cfg.get("deep_hole_flow", 0))
        q_sd_full = cfg.get("tunnel_flow", 0)

        scene1 = wl < 302 or sand > 60
        jizu_text = ""
        q_jz = 0
        req = q_total

        if scene1:
            jizu_text = "根据当前泥沙含量和水位条件推荐机组全停"
            q_jz = 0
            req = q_total
        else:
            if wl > 322:
                jizu_text = "水位>322m，机组全部关停，仅使用底孔、隧洞、深孔、钢管泄流"
                scene1 = True
                q_jz = 0
                req = q_total
            elif 302 <= wl < 312:
                if q_total < 1200:
                    q_jz = q_total
                    jizu_text = f"推荐5台机组运行，合计{q_jz}m³/s，无需开启孔洞"
                else:
                    q_jz = 1200
                    jizu_text = f"推荐5台机组满负荷运行，合计{q_jz}m³/s"
            elif 312 <= wl < 314:
                if q_total < 1500:
                    q_jz = q_total
                    jizu_text = f"推荐7台机组运行，合计{q_jz}m³/s，无需开启孔洞"
                else:
                    q_jz = 1500
                    jizu_text = f"推荐7台机组满负荷运行，合计{q_jz}m³/s"
            else:
                if q_total < 1300:
                    q_jz = q_total
                    jizu_text = f"推荐7台机组运行，合计{q_jz}m³/s，无需开启孔洞"
                else:
                    q_jz = 1300
                    jizu_text = f"推荐7台机组满负荷运行，合计{q_jz}m³/s"
            if not scene1:
                req = max(q_total - q_jz, 0)

        dk_list = []
        sk_list = []
        sd_q = 0
        sd_open = 0.0
        sk_text = "无需开启深孔"
        
        dikong_order = _get_dikong_order("SMX")
        if not dikong_order:
            dikong_order = list(range(1, 13))

        if req > 0:
            for no in dikong_order:
                if req >= q_dk:
                    dk_list.append((no, q_dk))
                    req -= q_dk
                else:
                    break
            
            if req > 0 and q_sk > 0:
                for no in range(1, 13):
                    if req >= q_sk:
                        sk_list.append((no, q_sk))
                        req -= q_sk
                    else:
                        break
                if sk_list:
                    sk_text = f"开启{len(sk_list)}条深孔（{', '.join([f'{n}号深孔：{q}m³/s' for n, q in sk_list])}），合计{sum(q for _, q in sk_list)}m³/s"
            
            if req > 0 and q_sd_full > 0:
                sd_q = req
                if 300 <= wl <= 310:
                    coeff_key = "300-310"
                elif 311 <= wl <= 315:
                    coeff_key = "311-315"
                else:
                    coeff_key = "315以上"
                
                coeff_rules = _get_coefficient_table("SMX", coeff_key)
                if coeff_rules:
                    n_est = (sd_q * 8) / (q_sd_full * 0.9)
                    for rule in coeff_rules:
                        low, high = rule["range_min"], rule["range_max"]
                        k = rule["coeff_value"]
                        n = (sd_q * 8) / (q_sd_full * k)
                        if low <= round(n, 2) <= high:
                            sd_open = round(n, 1)
                            break
                    else:
                        sd_open = round((sd_q * 8) / q_sd_full, 1)
                else:
                    sd_open = round((sd_q * 8) / q_sd_full, 1)

        dk_items = [f"{n}号底孔：{q}m³/s" for n, q in dk_list]
        dk_count = len(dk_list)
        dk_sum = sum(q for _, q in dk_list)
        dikong_text = f"开启{dk_count}条底孔（{', '.join(dk_items)}），合计{dk_sum}m³/s" if dk_count else "无需开启底孔"

        sk_sum = sum(q for _, q in sk_list)

        if sd_q > 0:
            single_tunnel_flow = q_sd_full
            if sd_q <= single_tunnel_flow:
                suidong_text = f"开启1号隧洞，开度{sd_open}m，流量{sd_q}m³/s"
            else:
                first_flow = min(sd_q, single_tunnel_flow)
                second_flow = sd_q - first_flow
                first_open = sd_open
                second_open = round((second_flow * 8) / single_tunnel_flow, 1)
                suidong_text = f"开启1号隧洞（开度{first_open}m，流量{first_flow}m³/s）、2号隧洞（开度{second_open}m，流量{second_flow}m³/s），合计{sd_q}m³/s"
        else:
            suidong_text = "无需开启隧洞"

        tuan = []
        if dk_list:
            tuan.append(dikong_text.split("，")[0])
        if sk_list:
            tuan.append(sk_text.split("，")[0])
        if sd_q:
            tuan.append(suidong_text)
        hole_str = "，".join(tuan) if tuan else "无需开启泄流孔洞"

        tui = f"因为当前泥沙含量为{sand}kg/m³，水位是{wl}m，出库流量为{q_total}m³/s，{jizu_text}，结合实际调整机组。根据孔洞检修情况推荐：{hole_str}，结合实际调整。"

        hole_list = []
        for no, q in dk_list:
            hole_list.append({
                "type": "底孔",
                "number": f"{no}号",
                "index": no,
                "flow": q,
                "max_flow": q_dk
            })
        for no, q in sk_list:
            hole_list.append({
                "type": "深孔",
                "number": f"{no}号",
                "index": no,
                "flow": q,
                "max_flow": q_sk
            })
        if sd_q > 0:
            single_tunnel_flow = q_sd_full
            
            if sd_q <= single_tunnel_flow:
                hole_list.append({
                    "type": "隧洞",
                    "number": "1号",
                    "index": 1,
                    "flow": sd_q,
                    "opening": sd_open,
                    "max_flow": single_tunnel_flow
                })
            else:
                remaining_flow = sd_q
                tunnel_count = 1
                
                while remaining_flow > 0 and tunnel_count <= 2:
                    tunnel_flow = min(remaining_flow, single_tunnel_flow)
                    hole_list.append({
                        "type": "隧洞",
                        "number": f"{tunnel_count}号",
                        "index": tunnel_count,
                        "flow": tunnel_flow,
                        "opening": sd_open if tunnel_count == 1 else round((tunnel_flow * 8) / single_tunnel_flow, 1),
                        "max_flow": single_tunnel_flow
                    })
                    remaining_flow -= tunnel_flow
                    tunnel_count += 1

        return {
            "date": date,
            "tuijianfangan": tui,
            "jizu": jizu_text + "，结合实际调整",
            "dikong": dikong_text,
            "shenkong": sk_text,
            "suidong": suidong_text,
            "holes": hole_list,
            "total_flow": dk_sum + sk_sum + sd_q,
            "unit_status": "全停" if scene1 else "部分运行"
        }

    except Exception as e:
        error_msg = f"生成调度方案时出错: {str(e)}"
        logger.error(error_msg)
        return {"date": date, "tuijianfangan": f"生成调度方案失败: {error_msg}"}

    @mcp.tool()
    async def generate_sanmenxia_scheme(
        date: str,
        liu_liang: float,
        shui_wei: float,
        han_sha_liang: float
    ) -> dict:
        """
        生成三门峡水库机组孔洞调度方案。

        Args:
            date: 日期时间，格式: yyyy-MM-dd HH:mm:ss
            liu_liang: 出库流量（m³/s）
            shui_wei: 当前水位（m）
            han_sha_liang: 含沙量（kg/m³）

        Returns:
            调度方案建议，包含推荐方案描述及各部件状态
        """
        logger.info(f"调用 generate_sanmenxia_scheme，收到参数: date={repr(date)}, liu_liang={liu_liang}, shui_wei={shui_wei}, han_sha_liang={han_sha_liang}")

        return_value = _generate_sanmenxia_scheme_core(date, liu_liang, shui_wei, han_sha_liang)

        logger.debug(f"generate_sanmenxia_scheme 返回结果: {return_value}")
        return return_value

def _get_risk_by_huayuankou_flow_core(flow: float) -> dict:
    """
    根据花园口流量判断黄河出险状况（内部函数）。

    Args:
        flow: 花园口流量，单位 m³/s

    Returns:
        完整出险信息，包含流量等级、河南和山西的风险描述、危险类型和处置建议
    """
    try:
        result = {
            "flow": flow,
            "level": "",
            "henan": "",
            "shanxi": "",
            "danger_type": [],
            "suggestion": ""
        }

        if flow < 4000:
            result["level"] = "4000m³/s 以下"
            result["henan"] = "流量持续较久时，花园口以下宽河道河势可能较大变化，部分河道工程长期受冲可能发生较大及以上险情。"
            result["shanxi"] = "由黄河河务部门查险抢险；河势突变、漫滩或较大险情时，市县领导靠前指挥。"
            result["danger_type"] = ["河势变化", "河道工程受冲险情"]
            result["suggestion"] = "正常巡查防守，关注河势变化。"

        elif 4000 <= flow < 6000:
            result["level"] = "4000～6000m³/s"
            result["henan"] = "部分工程接近或超标准，低滩区可能漫水，河势易上提/下挫、坐湾生险，工程出险几率增大。"
            result["shanxi"] = "冲刷力强，局部河势变化大；险工、控导、新修工程易根石走失、坦石坍塌、墩蛰；部分控导可能漫顶；漫滩偎堤易风浪淘刷、渗水、管涌；道路可能中断。"
            result["danger_type"] = ["低滩漫水", "河势变化", "工程出险", "风浪淘刷", "渗水", "管涌"]
            result["suggestion"] = "重点盯防控导、险工、新修工程，加强巡查。"

        elif 6000 <= flow < 10000:
            result["level"] = "6000～10000m³/s"
            result["henan"] = "部分高滩、全部低滩漫水，水深1~3m；偎堤水深1~4m；涉及6市，人口62.90~198.97万，转移6.77~91.75万人。"
            result["shanxi"] = "临黄大堤大部/全部偎水，堤根水深2~6m；薄弱堤段易渗水、管涌、裂缝、坍塌、顺堤行洪、风浪淘刷；控导大部/全部漫顶，可能揭顶后溃；河口流路可能摆动/分汊；险工易根石走失、坝岸墩蛰。"
            result["danger_type"] = ["滩区漫水", "偎堤", "渗水", "管涌", "坍塌", "控导漫顶", "河势变化", "河口分汊"]
            result["suggestion"] = "全面巡查堤防，重点防守薄弱段、控导工程，做好滩区转移准备。"

        elif 10000 <= flow < 15000:
            result["level"] = "10000～15000m³/s"
            result["henan"] = "滩区大部分被淹；偎堤长度约560km，水深2~5m；涉及6市，人口198.97~209.50万，转移91.75~113.94万人。"
            result["shanxi"] = "工程面临严峻考验；险工易坍塌、墩蛰、垮坝；控导全部漫顶、部分揭顶后溃；河势巨变，可能斜河、横河；多堤段易顺堤行洪；堤防易严重渗水、管涌、滑坡、漏洞、风浪塌坡；河口流路可能摆动/分汊；东平湖围坝可能出险；桥梁、管线易受撞击。"
            result["danger_type"] = ["滩区大部淹没", "偎堤", "渗水", "管涌", "滑坡", "漏洞", "垮坝", "控导溃失", "斜河横河", "顺堤行洪", "河口分汊"]
            result["suggestion"] = "全线设防，人员全部上堤，重点防控漏洞、滑坡、顺堤行洪。"

        elif 15000 <= flow < 22000:
            result["level"] = "15000～22000m³/s"
            result["henan"] = "堤防全线偎水，最大水深8m；滩区全部上水，局部水深超5m；涉及人口209.50~211.13万，转移113.94~120.81万人。"
            result["shanxi"] = "水位高、流速大、持续久；险工普遍坍塌、墩蛰、垮坝；堤防险情剧增，易漏洞；控导严重揭顶后溃；河势巨变；多堤段极易顺堤行洪；流量>18000时东明河段可能滚河；东平湖围堤险情严重；河口可能顺堤行洪、流路摆动/分汊；桥梁设施易撞击损毁。"
            result["danger_type"] = ["全线偎堤", "滩区全淹", "垮坝", "漏洞", "顺堤行洪", "滚河风险", "控导溃失", "河势巨变", "河口分汊"]
            result["suggestion"] = "一级战备，全员上堤，严防滚河、漏洞、顺堤行洪，启用应急抢险预案。"

        elif flow >= 22000:
            result["level"] = "≥22000m³/s（超标准洪水）"
            result["henan"] = "堤防全线偎水，随时可能渗漏、管涌、脱坡等重大险情；滩区全部被淹。"
            result["shanxi"] = "滩区全部漫滩，堤根水深≥8.5m；水位超标准；高村以上利用超高/子堰行洪；高村以下启用北金堤滞洪区；东平湖滞洪，控制艾山以下≤10000m³/s。"
            result["danger_type"] = ["全线重大险情", "漫滩", "偎水", "超标准运用", "滞洪区运用"]
            result["suggestion"] = "启动超标准洪水预案，启用北金堤、东平湖滞洪，全力保堤防安全。"

        return result

    except Exception as e:
        error_msg = f"判断出险情况时出错: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg}

    @mcp.tool()
    async def get_risk_by_huayuankou_flow(flow: float) -> dict:
        """
        根据花园口流量判断黄河出险状况。

        Args:
            flow: 花园口流量，单位 m³/s

        Returns:
            完整出险信息，包含流量等级、河南和山西的风险描述、危险类型和处置建议
        """
        logger.info(f"调用 get_risk_by_huayuankou_flow，收到参数: flow={flow}")

        result = _get_risk_by_huayuankou_flow_core(flow)

        logger.debug(f"get_risk_by_huayuankou_flow 返回结果: {result}")
        return result

def _get_flood_submerge_core(huayuankou_flow: float) -> dict:
    """
    黄河滩区淹没分析（内部函数）。

    Args:
        huayuankou_flow: 花园口流量，单位 m³/s

    Returns:
        淹没结果，包含河南、山东的淹没数据、等级和描述
    """
    try:
        q = huayuankou_flow
        result = {
            "flow": q,
            "level": "",
            "description": "",
            "henan": {},
            "shandong": {}
        }

        if q < 6000:
            result["level"] = "<6000 m³/s"
            result["description"] = "主河道正常行洪，不会漫滩，无村庄围困，无需迁移安置"
            result["henan"] = {
                "进水村庄数": 0,
                "进水人口": 0,
                "水围村庄数": 0,
                "水围人口": 0,
                "淹没滩地(万亩)": 0,
                "淹没耕地(万亩)": 0,
                "经济损失(亿元)": 0,
                "备注": "无淹没"
            }
            result["shandong"] = {
                "漫滩面积(万亩)": 0,
                "淹没耕地(万亩)": 0,
                "滩区进水数": 0,
                "自然村进水数": 0,
                "自然村围困数": 0,
                "涉及人口": 0,
                "需转移安置": 0,
                "就地就近安置": 0,
                "备注": "无淹没"
            }

        elif 6000 <= q < 8000:
            result["level"] = "6000 m³/s"
            result["description"] = "开始漫滩，河南、山东滩区局部进水、围困"
            result["henan"] = {
                "进水村庄数": 70,
                "进水人口": 6.18,
                "水围村庄数": 273,
                "水围人口": 24.85,
                "淹没滩地(万亩)": 110.29,
                "淹没耕地(万亩)": 70.81,
                "经济损失(亿元)": 140.87,
                "备注": "局部淹没"
            }
            result["shandong"] = {
                "漫滩面积(万亩)": 39.07,
                "淹没耕地(万亩)": 31.40,
                "滩区进水数": 93,
                "自然村进水数": 18,
                "自然村围困数": 46,
                "涉及人口": 4.54,
                "需转移安置": 2.46,
                "就地就近安置": 2.09,
                "备注": "局部漫滩"
            }

        elif 6000 < q <= 8000:
            result["level"] = "8000 m³/s"
            result["description"] = "大面积漫滩，河南、山东淹没范围显著扩大"
            result["henan"] = {
                "进水村庄数": 438,
                "进水人口": 51.47,
                "水围村庄数": 280,
                "水围人口": 27.07,
                "淹没滩地(万亩)": 215.53,
                "淹没耕地(万亩)": 152.85,
                "经济损失(亿元)": 327.17,
                "备注": "大面积淹没"
            }
            result["shandong"] = {
                "漫滩面积(万亩)": 204.05,
                "淹没耕地(万亩)": 134.34,
                "滩区进水数": 108,
                "自然村进水数": 105,
                "自然村围困数": 206,
                "涉及人口": 25.26,
                "需转移安置": 5.70,
                "就地就近安置": 16.98,
                "备注": "大面积漫滩"
            }

        elif 8000 < q <= 10000:
            result["level"] = "10000 m³/s"
            result["description"] = "山东滩区全部漫滩，河南大规模淹没"
            result["henan"] = {
                "进水村庄数": 905,
                "进水人口": 112.70,
                "水围村庄数": 191,
                "水围人口": 18.53,
                "淹没滩地(万亩)": 323.22,
                "淹没耕地(万亩)": 219.20,
                "经济损失(亿元)": 467.43,
                "备注": "大规模淹没"
            }
            result["shandong"] = {
                "漫滩面积(万亩)": 228.35,
                "淹没耕地(万亩)": 174.27,
                "滩区进水数": 109,
                "自然村进水数": 222,
                "自然村围困数": 161,
                "涉及人口": 31.42,
                "需转移安置": 7.44,
                "就地就近安置": 22.63,
                "备注": "全部漫滩"
            }

        elif 10000 < q <= 12370:
            result["level"] = "12370 m³/s"
            result["description"] = "河南接近全淹没，山东维持全漫滩"
            result["henan"] = {
                "进水村庄数": 1029,
                "进水人口": 125.22,
                "水围村庄数": 80,
                "水围人口": 6.97,
                "淹没滩地(万亩)": 329.80,
                "淹没耕地(万亩)": 223.09,
                "经济损失(亿元)": 494.89,
                "备注": "接近全淹没"
            }
            result["shandong"] = {
                "漫滩面积(万亩)": 234.71,
                "淹没耕地(万亩)": 176.90,
                "滩区进水数": 109,
                "自然村进水数": 243,
                "自然村围困数": 157,
                "涉及人口": 31.68,
                "需转移安置": 20.09,
                "就地就近安置": 11.59,
                "备注": "全漫滩"
            }

        elif 12370 < q <= 15700:
            result["level"] = "15700 m³/s"
            result["description"] = "河南全滩区淹没，山东保持全漫滩"
            result["henan"] = {
                "进水村庄数": 1103,
                "进水人口": 134.30,
                "水围村庄数": 48,
                "水围人口": 3.99,
                "淹没滩地(万亩)": 342.10,
                "淹没耕地(万亩)": 234.10,
                "经济损失(亿元)": 507.66,
                "备注": "全滩区淹没"
            }
            result["shandong"] = {
                "漫滩面积(万亩)": 234.71,
                "淹没耕地(万亩)": 176.90,
                "滩区进水数": 109,
                "自然村进水数": 243,
                "自然村围困数": 157,
                "涉及人口": 31.68,
                "需转移安置": 20.09,
                "就地就近安置": 11.59,
                "备注": "全漫滩"
            }

        elif 15700 < q < 22000:
            result["level"] = "15700~22000 m³/s（大洪水）"
            result["description"] = "河南全滩区淹没，山东全漫滩"
            result["henan"] = {
                "进水村庄数": 1103,
                "进水人口": 134.30,
                "水围村庄数": 48,
                "水围人口": 3.99,
                "淹没滩地(万亩)": 342.10,
                "淹没耕地(万亩)": 234.10,
                "经济损失(亿元)": 507.66,
                "备注": "全滩区淹没"
            }
            result["shandong"] = {
                "漫滩面积(万亩)": 234.71,
                "淹没耕地(万亩)": 176.90,
                "滩区进水数": 109,
                "自然村进水数": 243,
                "自然村围困数": 157,
                "涉及人口": 31.68,
                "需转移安置": 20.09,
                "就地就近安置": 11.59,
                "备注": "全漫滩"
            }

        elif q >= 22000:
            result["level"] = "≥22000 m³/s（超标准洪水）"
            result["description"] = "河南、山东全滩区淹没，最高等级淹没"
            result["henan"] = {
                "进水村庄数": 1196,
                "进水人口": 144.66,
                "水围村庄数": 0,
                "水围人口": 0,
                "淹没滩地(万亩)": 365.00,
                "淹没耕地(万亩)": 253.10,
                "经济损失(亿元)": 529.20,
                "备注": "全淹没（超标准）"
            }
            result["shandong"] = {
                "漫滩面积(万亩)": 234.71,
                "淹没耕地(万亩)": 176.90,
                "滩区进水数": 109,
                "自然村进水数": 243,
                "自然村围困数": 157,
                "涉及人口": 31.68,
                "需转移安置": 20.09,
                "就地就近安置": 11.59,
                "备注": "全漫滩"
            }

        else:
            result["level"] = "未知流量"
            result["description"] = "无法判断"

        return result

    except Exception as e:
        error_msg = f"分析滩区淹没时出错: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg}

    @mcp.tool()
    async def get_flood_submerge(huayuankou_flow: float) -> dict:
        """
        黄河滩区淹没分析（依据文档：滩区淹没（参数【花园口流量】））。

        Args:
            huayuankou_flow: 花园口流量，单位 m³/s

        Returns:
            淹没结果，包含河南、山东的淹没数据、等级和描述
        """
        logger.info(f"调用 get_flood_submerge，收到参数: huayuankou_flow={huayuankou_flow}")

        result = _get_flood_submerge_core(huayuankou_flow)

        logger.debug(f"get_flood_submerge 返回结果: {result}")
        return result
