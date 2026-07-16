import requests
import time
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from src.config.settings import settings
from src.utils.logger import get_logger
from src.services.external_api.base_auth_service import BaseTokenAuthService

logger = get_logger(__name__)


class WaterForecastAuthService(BaseTokenAuthService):
    """来水预报API认证服务，管理token的获取和刷新"""

    def __init__(self):
        super().__init__(name="来水预报API", token_filename=".water_forecast_token.json")

    def init_from_settings(self):
        self._base_url = settings.WATER_FORECAST_API_BASE_URL
        self._username = settings.WATER_FORECAST_API_USERNAME
        self._password = settings.WATER_FORECAST_API_PASSWORD
        self._client_id = settings.WATER_FORECAST_API_CLIENT_ID

    def _login(self) -> Dict[str, Any]:
        """登录获取token"""
        url = f"{self._base_url}/huangheApi/auth/login"

        # 计算时间范围（最近7天）
        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        start_time = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")

        headers = {
            "Content-Type": "application/json",
            "ClientId": self._client_id,
            "Start-Time": start_time,
            "End-Time": end_time
        }

        data = {
            "username": self._username,
            "password": self._password,
            "clientId": self._client_id,
            "grantType": "password"
        }

        logger.info(f"正在登录来水预报API: {url}")
        response = self._session.post(url, json=data, headers=headers, timeout=30)

        logger.debug(f"登录响应状态码: {response.status_code}, body_len={len(response.text)}")

        response.raise_for_status()

        result = response.json()
        # 兼容多种token字段名
        token = result.get("accessToken") or result.get("token") or result.get("access_token") or result.get("data", {}).get("access_token")
        if token:
            # 设置token过期时间为1小时（提前60秒过期，避免边界问题）
            expiry = time.time() + 3600 - 60
            logger.info(f"来水预报API登录成功，token有效期: 1小时")
            return {"token": token, "expiry": expiry}
        else:
            raise Exception(f"来水预报登录失败: 未找到token字段，完整响应: {result}")

    def get_auth_headers(self) -> dict:
        """获取包含认证信息的请求头"""
        token = self.get_token()
        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        start_time = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")

        headers = {
            "ClientId": self._client_id,
            "Start-Time": start_time,
            "End-Time": end_time
        }

        if token:
            headers["Authorization"] = f"Bearer {token}"

        return headers


water_forecast_auth_service = WaterForecastAuthService()


class WaterForecastService:
    """来水预报服务"""

    def __init__(self):
        self._base_url = settings.WATER_FORECAST_API_BASE_URL
        self._session = requests.Session()
        # 从配置读取SSL验证设置
        self._session.verify = settings.SSL_CERT_PATH if settings.SSL_CERT_PATH else settings.SSL_VERIFY

    def get_scheme_list(self, start_time: str, end_time: str) -> Dict[str, Any]:
        """获取预报方案清单"""
        try:
            url = f"{self._base_url}/huangheApi/preSch/getRecommendedOrLatestSchList?startTime={start_time}&endTime={end_time}"
            headers = {
                **water_forecast_auth_service.get_auth_headers(),
                "Content-Type": "application/json"
            }

            logger.info(f"正在获取预报方案清单: {url}")
            response = self._session.get(url, headers=headers, timeout=30)

            response.raise_for_status()

            result = response.json()
            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"获取预报方案清单请求异常: {e}")
            if 'response' in locals():
                logger.error(f"异常响应状态码: {response.status_code}")
                logger.error(f"异常响应内容: {response.text}")
            return {"success": False, "error": str(e)}

    def get_scheme_data_by_station_name(self, sch_id: str, station_name: str) -> Dict[str, Any]:
        """根据方案ID和站点名称获取预报数据"""
        try:
            url = f"{self._base_url}/huangheApi/preSch/getRecommendSchDataByStationName"
            headers = {
                **water_forecast_auth_service.get_auth_headers(),
                "Content-Type": "application/json"
            }

            params = {
                "schId": sch_id,
                "stationName": station_name
            }

            logger.info(f"正在获取站点预报数据: {url}, 参数: {params}")
            response = self._session.get(url, params=params, headers=headers, timeout=30)

            response.raise_for_status()

            result = response.json()
            logger.info(f"站点预报数据获取成功")
            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"获取站点预报数据请求异常: {e}")
            return {"success": False, "error": str(e)}


water_forecast_service = WaterForecastService()