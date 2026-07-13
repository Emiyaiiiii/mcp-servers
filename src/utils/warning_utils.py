from typing import Dict, Any, Optional
from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_xiaolangdi_warning_core(
    tongguan_flow: Optional[float] = None,
    reservoir_level: Optional[float] = None,
    outflow_flow: Optional[float] = None
) -> Dict[str, Any]:
    """
    根据潼关流量、水库蓄水位、出库流量判断小浪底预警等级。

    Returns:
        预警等级及应急保障措施
    """
    result = {
        "tongguan_flow": tongguan_flow,
        "reservoir_level": reservoir_level,
        "outflow_flow": outflow_flow,
        "level": "未达到预警级别",
        "source": "",
        "measures": []
    }

    def level1_measures():
        return [
            "（1）省防指小浪底、西霞院工程防汛应急抢险指挥部主持召集会议，现场指挥抢险工作。洛阳市、济源市开展本行政区域内的小浪底、西霞院水利枢纽防汛抢险工作。",
            "（2）小浪底管理中心防汛领导小组全体人员在4小时内抵达枢纽管理区，配合省防指开展防汛工作。",
            "（3）开发公司防汛指挥部全体人员及防汛工作人员在4小时内抵达枢纽管理区，按照防汛预案开展巡查监测及通讯后勤保障工作，做好抢险准备。",
            "（4）投资公司防汛指挥部总指挥、分管旅游公司的副总指挥、防办、旅游公司负责人及防汛相关工作人员在4小时内抵达枢纽管理区，按照预案开展防汛工作。"
        ]

    def level2_measures():
        return [
            "（1）小浪底管理中心防汛领导小组全体人员在6小时内抵达枢纽管理区，统筹部署防汛工作。",
            "（2）开发公司防汛指挥部全体人员及防汛工作人员6小时内抵达枢纽管理区，按照防汛预案开展巡查监测及通讯后勤保障工作，做好抢险准备。",
            "（3）投资公司防汛指挥部分管旅游公司的副总指挥、防办、旅游公司负责人及防汛相关工作人员在6小时内抵达枢纽管理区，按照预案开展防汛工作。"
        ]

    def level3_measures():
        return [
            "（1）小浪底管理中心防汛领导小组分管防汛建管的副组长，防办、建管处、安监处、库区管理中心负责人在8小时内抵达枢纽管理区，统筹部署防汛工作。",
            "（2）开发公司防汛指挥部分管防汛、水工部、运行部的副总指挥和防办、生产保障部、水工部、运行部、检修部、后勤管理部、保卫部、监测维修分公司、小浪底公安局负责人及防汛工作人员在8小时内抵达枢纽管理区，根据需要及时组织安全会商，按照防汛预案开展巡查监测及通讯后勤保障工作，做好抢险准备。",
            "（3）旅游公司值班（带班）班子成员及防汛相关工作人员在8小时内抵达枢纽管理区，按照预案开展防汛工作。"
        ]

    warnings = []

    if tongguan_flow is not None:
        if tongguan_flow > 15000:
            warnings.append(("I级", "潼关流量>15000m³/s", level1_measures()))
        elif 10000 <= tongguan_flow < 15000:
            warnings.append(("I级", "潼关流量10000~15000m³/s", level1_measures()))
        elif 8000 <= tongguan_flow < 10000:
            warnings.append(("II级", "潼关流量8000~10000m³/s", level2_measures()))
        elif 5000 <= tongguan_flow < 8000:
            warnings.append(("III级", "潼关流量5000~8000m³/s", level3_measures()))

    if reservoir_level is not None:
        if reservoir_level > 275:
            warnings.append(("I级", "水库蓄水位>275m", level1_measures()))
        elif reservoir_level == 275:
            warnings.append(("I级", "水库蓄水位=275m", level1_measures()))
        elif 272.5 <= reservoir_level < 275:
            warnings.append(("II级", "水库蓄水位272.5~275m", level2_measures()))
        elif 270 <= reservoir_level < 272.5:
            warnings.append(("III级", "水库蓄水位270~272.5m", level3_measures()))

    if outflow_flow is not None:
        if outflow_flow >= 10000:
            warnings.append(("I级", "出库流量≥10000m³/s", level1_measures()))
        elif 8000 <= outflow_flow < 10000:
            warnings.append(("I级", "出库流量8000~10000m³/s", level1_measures()))
        elif 6000 <= outflow_flow < 8000:
            warnings.append(("II级", "出库流量6000~8000m³/s", level2_measures()))
        elif 4000 <= outflow_flow < 6000:
            warnings.append(("III级", "出库流量4000~6000m³/s", level3_measures()))

    if warnings:
        warnings.sort(key=lambda x: {"I级": 0, "II级": 1, "III级": 2}[x[0]])
        highest = warnings[0]
        result["level"] = highest[0]
        result["source"] = highest[1]
        result["measures"] = highest[2]

        if len(warnings) > 1:
            other_sources = [w[1] for w in warnings[1:]]
            result["other_sources"] = other_sources

    return result


def get_sanmenxia_warning_core(
    longmen_flow: Optional[float] = None,
    tongguan_flow: Optional[float] = None,
    huaxian_flow: Optional[float] = None
) -> Dict[str, Any]:
    """
    根据龙门、潼关、华县流量判断三门峡预警等级及处置措施。

    Returns:
        预警等级及处置措施
    """
    result = {
        "longmen_flow": longmen_flow,
        "tongguan_flow": tongguan_flow,
        "huaxian_flow": huaxian_flow,
        "level": "无预警",
        "trigger_source": "",
        "measures": []
    }

    triggers = []

    if longmen_flow is not None:
        if longmen_flow >= 18000:
            triggers.append(("一级", "龙门流量≥18000m³/s"))
        elif 12000 <= longmen_flow < 18000:
            triggers.append(("二级", "龙门流量12000~18000m³/s"))
        elif 8000 <= longmen_flow < 12000:
            triggers.append(("三级", "龙门流量8000~12000m³/s"))
        elif 5000 <= longmen_flow < 8000:
            triggers.append(("四级", "龙门流量5000~8000m³/s"))

    if tongguan_flow is not None:
        if tongguan_flow >= 15000:
            triggers.append(("一级", "潼关流量≥15000m³/s"))
        elif 10000 <= tongguan_flow < 15000:
            triggers.append(("二级", "潼关流量10000~15000m³/s"))
        elif 8000 <= tongguan_flow < 10000:
            triggers.append(("三级", "潼关流量8000~10000m³/s"))
        elif 5000 <= tongguan_flow < 8000:
            triggers.append(("四级", "潼关流量5000~8000m³/s"))

    if huaxian_flow is not None:
        if huaxian_flow >= 8000:
            triggers.append(("一级", "华县流量≥8000m³/s"))
        elif 6000 <= huaxian_flow < 8000:
            triggers.append(("二级", "华县流量6000~8000m³/s"))
        elif 4000 <= huaxian_flow < 6000:
            triggers.append(("三级", "华县流量4000~6000m³/s"))
        elif 2500 <= huaxian_flow < 4000:
            triggers.append(("四级", "华县流量2500~4000m³/s"))

    if triggers:
        triggers.sort(key=lambda x: {"一级": 0, "二级": 1, "三级": 2, "四级": 3}[x[0]])
        highest = triggers[0]
        level = highest[0]
        result["level"] = f"{level}预警"
        result["trigger_source"] = highest[1]

        if len(triggers) > 1:
            result["other_triggers"] = [t[1] for t in triggers[1:]]

        if level == "一级":
            result["measures"] = [
                "（1）局防指向水库防汛行政责任人、河南省防指及黄河防总办公室汇报雨情、水情、汛情、工情、险情等情况，请示由水库抢险指挥机构全面部署水库防汛应急相关工作。",
                "（2）水库抢险指挥机构指挥长或其委托人主持召开三门峡水库防汛抢险会商会，部署开展枢纽防汛运用措施，研究制定枢纽运用方案。",
                "（3）局防指指挥长到枢纽现场指挥。组织局防汛抢险专家等技术力量研究应急处置方案，局防指办及各单位、部门组织实施。机关部门相关岗位人员全部上岗到位。局防指办全员到岗，及时滚动以短信等方式向局防指成员发布水雨情、水库调度、险情等最新信息。",
                "（4）三门峡发电公司、水电公司、服务中心等单位所有相关岗位人员全部上岗到位。紧盯电厂厂房、供电点、防汛设备启闭机室以及防汛道路等重点区域，严防雨水正（倒）灌引发事故灾害；加强枢纽防汛设备与水工建筑物险工、险点等巡视检查，发现险情，立即组织抢险并按应急处置程序逐级上报。",
                "（5）局防指办按工作部署及时向有关各方汇报枢纽防汛运用、险情处置等情况。"
            ]
        elif level == "二级":
            result["measures"] = [
                "（1）局防指向水库防汛行政责任人、河南省防指及黄河防总办公室汇报雨情、水情、汛情、工情、险情等情况，请示由水库抢险指挥机构指导部署水库防汛应急相关工作。",
                "（2）局防指指挥长主持召开三门峡枢纽防汛会商会，落实水库抢险指挥机构工作部署。通报雨水情、工情、险情等重要预警信息，组织开展枢纽防汛运用措施，根据黄委等调度要求研究制定枢纽运用方案。",
                "（3）局防指常务副指挥长到枢纽现场指挥。组织局防汛抢险专家等技术力量研究应急处置方案，局防指办及各单位、部门组织实施。机关部门主要负责人到岗。局防指办值班实行双人双岗值班，根据情况增加值班人员，及时以短信等方式向局防指成员发布水雨情、水库调度等最新信息（每日 8 时、14 时、20 时）。防汛督察与宣传报道人员上岗。",
                "（4）三门峡发电公司、水电公司、服务中心等单位主要负责人到岗，做好协调与分级指挥工作。防汛抢险队员上岗待命。增加防汛电源、防汛物资、交通、后勤保障、电厂厂房防正（倒）灌、通信、网络、大坝安全监测等岗位人员。加强对所辖坝区工作、生活的低洼区域以及防汛道路的巡查，严防雨水正灌引发事故灾害；加强枢纽防汛设备与水工建筑物险工、险点等巡视检查，发现险情，立即组织抢险并按应急处置程序逐级上报。",
                "（5）局防指办按工作部署及时向有关各方汇报枢纽防汛运用、险情处置等情况。"
            ]
        elif level == "三级":
            result["measures"] = [
                "（1）局防指常务副指挥长（或副指挥长）主持召开防汛会商会，安排部署枢纽防汛工作，并及时向指挥长汇报枢纽防汛运用情况。局防指成员参加会商。",
                "（2）根据会商意见，局防指向局属相关单位、部门发出通知，通报雨水情、工情、险情等重要预警信息，对枢纽防汛工作提出要求。",
                "（3）局防指办根据黄委等调度要求研究制定枢纽运用方案，经常务副指挥长批准后组织落实。局防指带班领导到枢纽现场指挥、带班。机关相关部门主要负责人到岗。局防指办值班实行双人双岗值班，根据情况增加值班人员，及时以短信等方式向局防指成员发布水雨情、水库调度等最新信息（每日 8 时、14 时、20 时）。",
                "（4）三门峡发电公司、水电公司、服务中心等单位主要负责人到岗，配合做好防汛会商、协调、部署与分级指挥工作。各单位防汛抢险队员待命。增加防汛电源、防汛物资、交通、后勤保障与电厂厂房防正（倒）灌、通信、网络等岗位人员，保障各系统可靠运转。",
                "（5）局防指办及时向三门峡市防指、河南省防指及黄河防总办公室报告启动响应及枢纽运用等情况。"
            ]
        elif level == "四级":
            result["measures"] = [
                "（1）局防指办主任主持召开防汛会商会，安排部署枢纽防汛工作，并及时向带班领导、常务副指挥长汇报枢纽防汛运用情况。局防指成员单位派员参加会商。",
                "（2）根据会商意见，局防指向局属相关单位、部门发出通知，通报雨水情、工情、险情等重要预警信息，对枢纽防汛工作提出要求。",
                "（3）局防指办根据黄委等调度要求研究制定枢纽运用方案，经常务副指挥长批准后组织落实。局防指带班领导到枢纽现场指挥、带班。局防指办值班实行双人双岗值班，及时以短信等方式向局防指成员发布水雨情、水库调度等最新信息（每日 8 时、20 时）。",
                "（4）三门峡发电公司、水电公司、服务中心等单位分管负责人到岗，配合做好防汛会商、协调、部署与分级指挥工作。枢纽闸门启闭、防汛电源、通信、网络、交通等重要防汛岗位人员，按照防汛预案保障防汛系统可靠运转。",
                "（5）局防指办及时向三门峡市防指、河南省防指及黄河防总办公室报告启动响应及枢纽运用等情况。"
            ]

    return result


def get_yellow_river_emergency_response_core(
    luhun_level: Optional[float] = None,
    hekoucun_level: Optional[float] = None,
    dongpinghu_level: Optional[float] = None,
    guxian_level: Optional[float] = None,
    xiaolangdi_level: Optional[float] = None,
    sanmenxia_level: Optional[float] = None,
    tangnaihai_flow: Optional[float] = None,
    lanzhou_flow: Optional[float] = None,
    xiaheyan_flow: Optional[float] = None,
    shizuishan_flow: Optional[float] = None,
    wubao_flow: Optional[float] = None,
    longmen_flow: Optional[float] = None,
    tongguan_flow: Optional[float] = None,
    huayuankou_flow: Optional[float] = None,
    gaocun_flow: Optional[float] = None,
    huaxian_flow: Optional[float] = None,
    baimasi_flow: Optional[float] = None,
    longmenzhen_flow: Optional[float] = None,
    wuzhi_flow: Optional[float] = None
) -> Dict[str, Any]:
    """
    根据黄河流域各水库水位和水文站流量判断总体应急响应等级。

    Returns:
        应急响应等级及启动条件
    """
    result = {
        "response_level": "无预警",
        "description": "根据洪水预报及各水库水位分析，当前无预警",
        "trigger_conditions": [],
        "start_conditions": [],
        "measures": []
    }

    triggers = []

    if luhun_level is not None:
        if luhun_level >= 331.8:
            triggers.append(("一级", "陆浑水位≥331.8m"))
        elif 327.5 <= luhun_level < 331.8:
            triggers.append(("二级", "陆浑水位327.5~331.8m"))
        elif 319.5 <= luhun_level < 327.5:
            triggers.append(("三级", "陆浑水位319.5~327.5m"))
        elif 317 <= luhun_level < 319.5:
            triggers.append(("四级", "陆浑水位317~319.5m"))

    if hekoucun_level is not None:
        if hekoucun_level >= 285.43:
            triggers.append(("一级", "河口村水位≥285.43m"))
        elif 275 <= hekoucun_level < 285.43:
            triggers.append(("三级", "河口村水位275~285.43m"))
        elif 238 <= hekoucun_level < 275:
            triggers.append(("四级", "河口村水位238~275m"))

    if dongpinghu_level is not None:
        if dongpinghu_level >= 43.22:
            triggers.append(("一级", "东平湖水位≥43.22m"))
        elif 42.72 <= dongpinghu_level < 43.22:
            triggers.append(("二级", "东平湖水位42.72~43.22m"))
        elif 41.72 <= dongpinghu_level < 42.72:
            triggers.append(("三级", "东平湖水位41.72~42.72m"))
        elif 40.72 <= dongpinghu_level < 41.72:
            triggers.append(("四级", "东平湖水位40.72~41.72m"))

    if guxian_level is not None:
        if guxian_level >= 549.86:
            triggers.append(("一级", "故县水位≥549.86m"))
        elif 547.39 <= guxian_level < 549.86:
            triggers.append(("二级", "故县水位547.39~549.86m"))
        elif 543.04 <= guxian_level < 547.39:
            triggers.append(("三级", "故县水位543.04~547.39m"))
        elif 527.3 <= guxian_level < 533.64:
            triggers.append(("四级", "故县水位527.3~533.64m"))

    if xiaolangdi_level is not None:
        if xiaolangdi_level >= 275:
            triggers.append(("一级", "小浪底水位≥275m"))
        elif 274 <= xiaolangdi_level < 275:
            triggers.append(("二级", "小浪底水位274~275m"))
        elif 248 <= xiaolangdi_level < 274:
            triggers.append(("三级", "小浪底水位248~274m"))
        elif 235 <= xiaolangdi_level < 248:
            triggers.append(("四级", "小浪底水位235~248m"))

    if sanmenxia_level is not None:
        if sanmenxia_level >= 335:
            triggers.append(("一级", "三门峡水位≥335m"))
        elif 305 <= sanmenxia_level < 335:
            triggers.append(("三/四级", "三门峡水位305~335m"))

    if tangnaihai_flow is not None:
        if tangnaihai_flow >= 5000:
            triggers.append(("一级", "唐乃亥流量≥5000m³/s"))
        elif 4000 <= tangnaihai_flow < 5000:
            triggers.append(("二级", "唐乃亥流量4000~5000m³/s"))
        elif 3000 <= tangnaihai_flow < 4000:
            triggers.append(("三级", "唐乃亥流量3000~4000m³/s"))
        elif 2500 <= tangnaihai_flow < 3000:
            triggers.append(("四级", "唐乃亥流量2500~3000m³/s"))

    if lanzhou_flow is not None:
        if lanzhou_flow >= 6500:
            triggers.append(("一级", "兰州流量≥6500m³/s"))
        elif 5000 <= lanzhou_flow < 6500:
            triggers.append(("二级", "兰州流量5000~6500m³/s"))
        elif 4000 <= lanzhou_flow < 5000:
            triggers.append(("三级", "兰州流量4000~5000m³/s"))
        elif 2500 <= lanzhou_flow < 4000:
            triggers.append(("四级", "兰州流量2500~4000m³/s"))

    if longmen_flow is not None:
        if longmen_flow >= 18000:
            triggers.append(("一级", "龙门流量≥18000m³/s"))
        elif 12000 <= longmen_flow < 18000:
            triggers.append(("二级", "龙门流量12000~18000m³/s"))
        elif 8000 <= longmen_flow < 12000:
            triggers.append(("三级", "龙门流量8000~12000m³/s"))
        elif 5000 <= longmen_flow < 8000:
            triggers.append(("四级", "龙门流量5000~8000m³/s"))

    if tongguan_flow is not None:
        if tongguan_flow >= 15000:
            triggers.append(("一级", "潼关流量≥15000m³/s"))
        elif 10000 <= tongguan_flow < 15000:
            triggers.append(("二级", "潼关流量10000~15000m³/s"))
        elif 8000 <= tongguan_flow < 10000:
            triggers.append(("三级", "潼关流量8000~10000m³/s"))
        elif 5000 <= tongguan_flow < 8000:
            triggers.append(("四级", "潼关流量5000~8000m³/s"))

    if huayuankou_flow is not None:
        if huayuankou_flow >= 15000:
            triggers.append(("一级", "花园口流量≥15000m³/s"))
        elif 8000 <= huayuankou_flow < 15000:
            triggers.append(("二级", "花园口流量8000~15000m³/s"))
        elif 6000 <= huayuankou_flow < 8000:
            triggers.append(("三级", "花园口流量6000~8000m³/s"))
        elif 4000 <= huayuankou_flow < 6000:
            triggers.append(("四级", "花园口流量4000~6000m³/s"))

    if huaxian_flow is not None:
        if huaxian_flow >= 8000:
            triggers.append(("一级", "华县流量≥8000m³/s"))
        elif 6000 <= huaxian_flow < 8000:
            triggers.append(("二级", "华县流量6000~8000m³/s"))
        elif 4000 <= huaxian_flow < 6000:
            triggers.append(("三级", "华县流量4000~6000m³/s"))
        elif 2500 <= huaxian_flow < 4000:
            triggers.append(("四级", "华县流量2500~4000m³/s"))

    if triggers:
        triggers.sort(key=lambda x: {"一级": 0, "二级": 1, "三级": 2, "四级": 3, "三/四级": 2.5}[x[0]])
        highest = triggers[0]
        level = highest[0]
        result["response_level"] = f"{level}应急响应"
        result["trigger_conditions"] = [t[1] for t in triggers]

        if level == "一级":
            result["description"] = "启动防汛一级应急响应"
            result["start_conditions"] = [
                "（1）预报将发生强降雨过程，可能引发黄河干流、重要支流达到红色预警量级洪水或区域性特大洪水；",
                "（2）黄河干流、重要支流发生特大洪水；",
                "（3）黄河干流多处发生冰塞、冰坝，水位急剧上涨，一般河段堤防发生凌汛决口；",
                "（4）黄河干流下游河段堤防有决口危险；",
                "（5）黄河下游河段大面积漫滩，或河势发生巨大变化严重威胁堤防安全；",
                "（6）东平湖滞洪区已启用或东平湖滞洪区老湖水位超过防洪运用水位，或预报北金堤滞洪区需启用；",
                "（7）黄河干流或重要支流控制性水库水位可能达到校核洪水位；",
                "（8）流域大型水库可能发生或已发生漫坝或垮坝，严重威胁周边城镇、下游重要基础设施、人员安全等；",
                "（9）国家防总启动涉及流域的一级应急响应或两个及以上省区防指启动涉及流域的一级应急响应时；",
                "（10）地震等自然灾害造成水利工程出现险情等需要启动一级应急响应的情况。"
            ]
            result["measures"] = [
                "（1）黄河防总总指挥或常务副总指挥坐镇指挥黄河抗洪工作，主持抗洪抢险会商会，研究部署抗洪抢险工作。视情与相关省区进行异地会商。",
                "（2）根据会商意见，黄河防总办公室向相关省区防指通报关于启动防汛一级应急响应的命令及黄河汛情，对防汛工作提出要求，并向黄河防总总指挥报告。黄河防总向国家防总、水利部报告有关情况，为国家防总和水利部提供调度参谋意见，请求加强对黄河抗洪抢险指导，动员社会力量支援黄河抗洪抢险救灾。",
                "（3）黄河防总办公室各成员单位按照黄委防御大洪水职责分工和机构设置上岗到位，全面开展工作，各职能组充实人员。黄委全体职工全力投入抗洪抢险工作。",
                "（4）黄河防总根据汛情需要，及时增派司局级领导带队的工作组、专家组赶赴现场，指导抗洪抢险救灾工作。",
                "（5）根据各地抗洪抢险需要，黄河防总按程序调度黄委防汛物资、黄河机动抢险队支援抗洪抢险，必要时请求国家防总调动流域内外抢险队、物资支援黄河抗洪抢险。",
                "（6）有关省区防汛抗旱指挥机构的主要负责同志主持会商，动员部署防汛工作；按照权限组织调度水工程；根据预案转移安置危险地区群众，组织强化巡堤查险和堤防防守，及时控制险情；增派工作组、专家组赴一线指导防汛工作；受灾地区的各级防汛抗旱指挥机构负责人、成员单位负责人，应按照职责到分管的区域组织指挥防汛工作，或驻点具体帮助重灾区做好防汛工作；可按照预案和程序适时请调人民解放军和武警部队支援黄河抗洪抢险；将工作情况上报省区人民政府及黄河防总。"
            ]
        elif level == "二级":
            result["description"] = "启动防汛二级应急响应"
            result["start_conditions"] = [
                "（1）预报将发生强降雨过程，可能引发黄河干流、重要支流达到橙色预警量级洪水或区域性大洪水；",
                "（2）黄河干流、重要支流发生大洪水；",
                "（3）黄河干流发生严重冰塞、冰坝，河道水位快速上涨，造成堤防、涵闸、河道整治工程等多处发生重大险情；",
                "（4）黄河干流一般河段堤防有决口危险或黄河干流下游河段堤防、穿堤涵闸等出现重大险情；",
                "（5）黄河下游河段发生大面积漫滩，或河势发生较大变化威胁堤防安全；",
                "（6）预报东平湖滞洪区需启用或东平湖滞洪区老湖水位接近防洪运用水位；",
                "（7）黄河干流或重要支流控制性水库水位达到设计洪水位并有继续上涨的趋势；",
                "（8）流域中型水库发生垮坝，威胁周边城镇、下游重要基础设施、人员安全等；",
                "（9）国家防总启动涉及流域的二级应急响应或两个及以上省区防指启动涉及流域的二级应急响应时；",
                "（10）地震等自然灾害造成水利工程出现险情等需要启动二级应急响应的情况。"
            ]
            result["measures"] = [
                "（1）黄河防总总指挥或常务副总指挥坐镇指挥黄河抗洪工作，主持抗洪抢险会商会，研究部署抗洪抢险工作。视情与相关省区进行异地会商。",
                "（2）根据会商意见，黄河防总办公室向相关省区防指通报关于启动防汛二级应急响应的命令及黄河汛情，对防汛工作提出要求，并向黄河防总总指挥报告。黄河防总向国家防总、水利部报告有关情况，为国家防总和水利部提供调度参谋意见，请求加强对黄河抗洪抢险指导。",
                "（3）黄河防总办公室各成员单位按照黄委防御大洪水职责分工和机构设置上岗到位，全面开展工作。黄委全体职工做好随时投入抗洪抢险工作的准备。",
                "（4）黄河防总实时掌握雨情、水情、汛情（凌情）、工情、险情、灾情动态。",
                "（5）黄河防总办公室根据汛情需要，及时派出司局级领导带队的工作组、专家组赶赴现场，检查、指导抗洪抢险救灾工作，核实汛情灾情。",
                "（6）根据各地抗洪抢险需要，黄河防总办公室按程序调度黄委防汛物资、黄河机动抢险队支援抗洪抢险。",
                "（7）有关省区防汛抗旱指挥机构负责同志主持会商，具体安排防汛工作；按照权限组织调度水工程；根据预案做好巡堤查险、抗洪抢险、群众转移安置等抗洪救灾工作，派出工作组、专家组赴一线指导防汛工作；将防汛工作情况上报省级人民政府主要负责同志、国家防总及黄河防总。"
            ]
        elif level == "三级":
            result["description"] = "启动防汛三级应急响应"
            result["start_conditions"] = [
                "（1）预报将发生强降雨过程，可能引发黄河干流、重要支流达到黄色预警量级洪水；",
                "（2）黄河干流、重要支流发生较大洪水；",
                "（3）黄河干流发生冰塞、冰坝，水库库尾、河道水位快速上涨，造成多处滩区村庄大面积进水且严重威胁滩区群众安全；",
                "（4）黄河干流下游河段堤防、穿堤涵闸等出现较大险情或重要支流堤防决口；",
                "（5）黄河下游河段部分漫滩，或河势可能发生大的改变影响堤防安全；",
                "（6）东平湖滞洪区因大汶河洪水达到警戒水位并有明显上涨趋势；",
                "（7）黄河干流或重要支流控制性水库水位达到征地水位或移民水位并有继续上涨趋势；",
                "（8）流域小型水库或大型淤地坝发生漫坝或垮坝，严重威胁下游重要基础设施、人员安全等；",
                "（9）流域大中型水库发生危及水库安全的重大险情，威胁周边城镇、下游重要基础设施、人员安全等；",
                "（10）国家防总启动涉及流域的三级应急响应或两个及以上省区防指启动涉及流域的三级应急响应时；",
                "（11）地震等自然灾害造成水利工程出现险情等需要启动三级应急响应的情况。"
            ]
            result["measures"] = [
                "（1）黄河防总秘书长主持防汛会商会，研究部署抗洪抢险工作。视情与相关省区进行异地会商。",
                "（2）根据会商意见，黄河防总办公室向相关省区防指通报关于启动防汛三级应急响应的命令及黄河汛情，对防汛工作提出要求，并向黄河防总总指挥、常务副总指挥报告。",
                "（3）黄河防总办公室各成员单位按照黄委防御大洪水职责分工和机构设置上岗到位，全面开展工作。",
                "（4）黄河防总办公室根据汛情需要，及时派出工作组、专家组赶赴现场，检查、指导抗洪抢险救灾工作，核实汛情灾情。",
                "（5）根据各地抗洪抢险需要，黄河防总办公室按程序调度黄委防汛物资、黄河机动抢险队支援抗洪抢险。",
                "（6）有关省区防汛抗旱指挥机构负责同志主持会商，具体安排防汛工作；按照权限组织调度水工程；根据预案做好巡堤查险、抗洪抢险、群众转移安置等抗洪救灾工作，派出工作组、专家组赴一线指导防汛工作；将防汛工作情况上报省级人民政府分管负责同志和黄河防总。"
            ]
        elif level == "四级" or level == "三/四级":
            result["description"] = "启动防汛四级应急响应"
            result["start_conditions"] = [
                "（1）预报将发生较强降雨过程，可能引发黄河干流、重要支流达到蓝色预警量级洪水；",
                "（2）黄河干流、重要支流发生蓝色预警量级洪水；",
                "（3）黄河干流发生冰塞、冰坝，水库库尾、河道水位快速上涨，造成滩区村庄进水且严重威胁滩区群众安全；",
                "（4）黄河干流一般河段堤防、穿堤涵闸等或重要支流堤防出现重大险情；",
                "（5）黄河宁蒙河段、小北干流河段发生漫滩，威胁滩区人员安全或黄河下游河段发生局部漫滩，河道整治工程大量出险，威胁滩区人员安全；",
                "（6）东平湖滞洪区因大汶河洪水达到汛限水位并有明显上涨趋势；",
                "（7）黄河干流或重要支流控制性水库水位达到汛限水位并有明显上涨趋势；",
                "（8）流域小型水库（含水电站）或大型淤地坝发生危及水库（大型淤地坝）安全的险情，威胁周边城镇、下游重要基础设施、人员安全等；",
                "（9）流域中型水库出现可能危及水库安全的险情或发生超设计水位情况；",
                "（10）国家防总启动涉及流域的四级应急响应或两个及以上省区防指启动涉及流域的四级应急响应时；",
                "（11）地震等自然灾害造成水利工程出现险情等需要启动四级应急响应的情况。"
            ]
            result["measures"] = [
                "（1）黄河防总秘书长主持会商，研究部署抗洪抢险工作，确定运行机制。",
                "（2）根据会商意见，黄河防总办公室向相关省区防指通报关于启动防汛四级应急响应的命令及黄河汛情，对防汛工作提出要求，并向国家防办、水利部报告有关情况，必要时向黄河防总总指挥、常务副总指挥报告。",
                "（3）黄河防总办公室成员单位人员坚守工作岗位，加强防汛值班值守。",
                "（4）黄委按照批准的洪水调度方案，结合当前汛情做好水库等水工程调度，监督指导地方水行政主管部门按照调度权限做好水工程调度。",
                "（5）黄河防总办公室根据汛情需要，及时派出工作组、专家组赶赴现场，检查、指导抗洪抢险救灾工作，核实汛情灾情。",
                "（6）有关省区防汛抗旱指挥机构负责同志主持会商，具体安排防汛工作；按照权限组织调度水工程；按照预案做好辖区内巡堤查险、抗洪抢险、群众转移安置等抗洪救灾工作，必要时请调解放军和武警部队、民兵参加重要堤段、重点工程的防守或突击抢险；派出工作组、专家组赴一线指导防汛工作；将防汛工作情况上报省级人民政府和黄河防总办公室。"
            ]

    return result