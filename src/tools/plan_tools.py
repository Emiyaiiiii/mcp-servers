import os
import requests
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from fastmcp import FastMCP
from fastmcp.server.auth import require_scopes
from src.utils.logger import get_logger
from src.utils.api.data_api_utils import api_get, resolve_reservoir_for_api, resolve_station
from src.utils.dispatch.dispatch_utils import (
    generate_xiaolangdi_scheme_core, generate_sanmenxia_scheme_core
)
from src.utils.analysis.warning_utils import (
    get_xiaolangdi_warning_core, get_sanmenxia_warning_core, get_yellow_river_emergency_response_core
)
from src.utils.analysis.flood_utils import (
    get_risk_by_huayuankou_flow_core, get_flood_submerge_core
)
from src.services.external_api.enhanced_search_service import enhanced_search_service

logger = get_logger(__name__)

from src.config.settings import settings

KNOWLEDGE_BASE_API_URL = settings.KNOWLEDGE_BASE_API_URL

TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates"

_get = api_get
_resolve_reservoir_for_api = resolve_reservoir_for_api
_resolve_station = resolve_station

_generate_xiaolangdi_scheme_core = generate_xiaolangdi_scheme_core
_generate_sanmenxia_scheme_core = generate_sanmenxia_scheme_core
_get_xiaolangdi_warning = get_xiaolangdi_warning_core
_get_sanmenxia_warning = get_sanmenxia_warning_core
_get_overall_emergency_response = get_yellow_river_emergency_response_core
_get_risk_by_huayuankou_flow_core = get_risk_by_huayuankou_flow_core
_get_flood_submerge_core = get_flood_submerge_core


def register_plan_tools(mcp: FastMCP):

    @mcp.tool(auth=require_scopes("plan"))
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
                    risk_result = get_risk_by_huayuankou_flow_core(float(huayuankou_flow))
            except Exception as e:
                logger.warning(f"出险判断失败: {e}")

            submerge_result = {}
            try:
                if huayuankou_flow:
                    submerge_result = get_flood_submerge_core(float(huayuankou_flow))
            except Exception as e:
                logger.warning(f"淹没分析失败: {e}")

            xld_scheme = {}
            try:
                if reservoir_level or tongguan_flow:
                    data = generate_xiaolangdi_scheme_core(
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
                    data = generate_sanmenxia_scheme_core(
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
                    xld_warning = get_xiaolangdi_warning_core(
                        float(tongguan_flow) if tongguan_flow else 0,
                        float(reservoir_level) if reservoir_level else 0,
                        float(xiaolangdi_outflow) if xiaolangdi_outflow else 0
                    )
            except Exception as e:
                logger.warning(f"小浪底预警判断失败: {e}")

            smx_warning = {}
            try:
                if longmen_flow or tongguan_flow or huaxian_flow:
                    smx_warning = get_sanmenxia_warning_core(
                        float(longmen_flow) if longmen_flow else 0,
                        float(tongguan_flow) if tongguan_flow else 0,
                        float(huaxian_flow) if huaxian_flow else 0
                    )
            except Exception as e:
                logger.warning(f"三门峡预警判断失败: {e}")

            overall_response = {}
            try:
                overall_response = get_yellow_river_emergency_response_core(
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

    @mcp.tool(auth=require_scopes("plan"))
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

    @mcp.tool(auth=require_scopes("plan"))
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

    @mcp.tool(auth=require_scopes("plan"))
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

    @mcp.tool(auth=require_scopes("plan"))
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

    @mcp.tool(auth=require_scopes("plan"))
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
