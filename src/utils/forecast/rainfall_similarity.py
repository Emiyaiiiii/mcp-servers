import requests

from src.utils.logger import get_logger
from src.config.settings import settings

logger = get_logger(__name__)


def _step1_query_rainfall(basin, start_time, end_time):
    """第一步：查询各流域降雨情况（支持时间范围过滤）"""
    try:
        has_time_range = start_time and end_time

        if has_time_range:
            url = f"{settings.RAINFALL_SIMILARITY_API_URL}/rain/getRainListByTimeRange?startTime={start_time}&endTime={end_time}"
            logger.info(f"调用按时间范围查询降雨接口: {url}")
        else:
            url = f"{settings.RAINFALL_SIMILARITY_API_URL}/rain/getLatestRainList"
            logger.info(f"调用查询最新降雨接口: {url}")

        response = requests.get(url, timeout=30)
        response.raise_for_status()

        result = response.json()
        logger.info(f"接口返回结果: {result}")

        if result.get("code") != 200:
            raise Exception(f"接口返回错误: {result.get('msg', '未知错误')}")

        raw_data = result.get("data", [])

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


def _step2_calculate_similarity(basin, rainfall_id, start_time, end_time, raster_image_url):
    """第二步：链式执行 详情→相似雨→图斑→图斑相似度"""
    steps_result = {}

    # ---- 2.1 查询降雨详情 ----
    try:
        url = f"{settings.RAINFALL_SIMILARITY_API_URL}/rain/getRainDetailById?id={rainfall_id}"

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
            "rainfall_id": rainfall_id
        }

    # ---- 2.2 计算相似雨 ----
    try:
        url = f"{settings.RAINFALL_SIMILARITY_RASTER_URL}/tbapi/data/analyse/conformAnalysis"

        request_data = rainfall_detail.copy()
        request_data["rvnm"] = basin

        logger.info(f"调用计算相似雨接口: {url}")
        logger.info(f"请求体: {request_data}")

        response = requests.post(url, json=request_data, headers={"Content-Type": "application/json"}, timeout=60)
        response.raise_for_status()

        result = response.json()
        logger.info(f"相似雨计算接口返回结果: {result}")

        if result.get("code") != 200:
            raise Exception(f"接口返回错误: {result.get('msg', '未知错误')}")

        similar_rainfall_list = result.get("data", [])
        steps_result["similar_rainfall"] = similar_rainfall_list
    except Exception as e:
        logger.error(f"计算相似雨失败: {e}")
        return {
            "success": False,
            "command": "FUNC_RAINFALL_SIMILARITY_ANALYSIS_STEP2",
            "step": "2.2",
            "message": f"计算相似雨失败: {str(e)}",
            "rainfall_id": rainfall_id,
            "partial_result": steps_result
        }

    # ---- 2.3 查询相似雨图斑图片 ----
    try:
        url = f"{settings.RAINFALL_SIMILARITY_RASTER_URL}/tbapi/data/getInfo"

        prototype_start = rainfall_detail.get("rainfallDate", "")
        prototype_end = rainfall_detail.get("endRainfallDate", "")

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
            "rainfall_id": rainfall_id,
            "partial_result": steps_result
        }

    # ---- 2.4 图斑相似度计算 ----
    try:
        url = f"{settings.RAINFALL_SIMILARITY_RASTER_URL}/wpi/process"

        urls = []

        prototype_data = raster_images.get("data", {})
        prototype_info = prototype_data.get("prototypeInfo", {})
        prototype_rain_info = prototype_info.get("rainInfo", {})
        prototype_image_url = prototype_rain_info.get("contourImage", "")
        if prototype_image_url:
            urls.append(prototype_image_url.strip())

        similar_infos = prototype_data.get("similarInfos", [])
        if isinstance(similar_infos, list):
            for similar_item in similar_infos:
                rain_info = similar_item.get("rainInfo", {})
                image_url = rain_info.get("contourImage", "")
                if image_url:
                    urls.append(image_url.strip())

        request_data = {"urls": urls}

        logger.info(f"调用图斑相似度计算接口: {url}")
        logger.info(f"请求体: {request_data}")

        response = requests.post(url, json=request_data, headers={"Content-Type": "application/json"}, timeout=60)
        response.raise_for_status()

        result = response.json()
        logger.info(f"图斑相似度计算接口返回结果: {result}")

        most_similar_raster = result
        steps_result["most_similar_raster"] = most_similar_raster
    except Exception as e:
        logger.error(f"图斑相似度计算失败: {e}")
        return {
            "success": False,
            "command": "FUNC_RAINFALL_SIMILARITY_ANALYSIS_STEP2",
            "step": "2.4",
            "message": f"图斑相似度计算失败: {str(e)}",
            "rainfall_id": rainfall_id,
            "partial_result": steps_result
        }

    # ---- 2.5 数据精简处理 ----
    try:
        if "rainfall_detail" in steps_result:
            detail = steps_result["rainfall_detail"]
            for key in ["lookLikePoint", "resemblance", "maxRainfallStnm", "timeRainfallQ", "rainfallParameters"]:
                if key in detail:
                    del detail[key]
            steps_result["rainfall_detail"] = detail

        if "rainfall_raster_images" in steps_result:
            raster_data = steps_result["rainfall_raster_images"]
            for key in ["respCode", "respMsg", "elapsed", "extraData"]:
                if key in raster_data:
                    del raster_data[key]
            if "data" in raster_data:
                data = raster_data["data"]
                if "prototypeInfo" in data:
                    proto_info = data["prototypeInfo"]
                    if "rainInfo" in proto_info:
                        rain_info = proto_info["rainInfo"]
                        if "contour" in rain_info:
                            del rain_info["contour"]
                if "similarInfos" in data:
                    for similar_item in data["similarInfos"]:
                        if "rainInfo" in similar_item:
                            rain_info = similar_item["rainInfo"]
                            if "contour" in rain_info:
                                del rain_info["contour"]
            steps_result["rainfall_raster_images"] = raster_data

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
        "rainfall_id": rainfall_id,
        "steps": steps_result,
        "message": "图斑相似性分析完成"
    }
    logger.debug(f"rainfall_similarity_analysis step=2 返回结果: {return_value}")
    return return_value


def _step3_integrate_hydrology(basin, start_time, end_time, raster_image_url):
    """第三步：根据用户选择的相似雨时间段查询水文信息并整合图斑图片"""
    try:
        url = f"{settings.RAINFALL_SIMILARITY_RASTER_URL}/api/hyd/getByBasinNameListAndTime"
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
