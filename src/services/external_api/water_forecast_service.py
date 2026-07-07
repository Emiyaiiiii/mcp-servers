import requests
import time
import threading
import json
import os
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from src.utils.logger import get_logger

logger = get_logger(__name__)


class WaterForecastAuthService:
    """来水预报API认证服务，管理token的获取和刷新"""

    def __init__(self):
        self._token: Optional[str] = None
        self._token_expiry: float = 0
        self._lock = threading.Lock()
        self._base_url = 'http://10.4.158.37:11111'
        self._username = 'yh'
        self._password = 'Yrec!@#2025'
        self._client_id = 'e5cd7e4891bf95d1d19206ce24a7b32e'
        self._session = requests.Session()
        # 禁用SSL证书验证
        self._session.verify = False
        
        self._token_file = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', '.water_forecast_token.json')
        
        self._load_token_from_file()

    def _save_token_to_file(self):
        """将token保存到本地文件"""
        try:
            token_data = {
                'token': self._token,
                'expiry': self._token_expiry
            }
            
            token_dir = os.path.dirname(self._token_file)
            os.makedirs(token_dir, exist_ok=True)
            
            with open(self._token_file, 'w', encoding='utf-8') as f:
                json.dump(token_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"来水预报token已保存到文件: {self._token_file}")
        except Exception as e:
            logger.error(f"保存来水预报token到文件失败: {e}")

    def _load_token_from_file(self):
        """从本地文件加载token"""
        try:
            if os.path.exists(self._token_file):
                with open(self._token_file, 'r', encoding='utf-8') as f:
                    token_data = json.load(f)
                
                token = token_data.get('token')
                expiry = token_data.get('expiry', 0)
                
                if token and time.time() < expiry:
                    self._token = token
                    self._token_expiry = expiry
                    logger.info(f"已从文件加载有效来水预报token，过期时间: {time.ctime(expiry)}")
                else:
                    logger.info("文件中的来水预报token已过期或无效")
            else:
                logger.info("来水预报token文件不存在，需要重新登录")
        except Exception as e:
            logger.error(f"从文件加载来水预报token失败: {e}")

    def _login(self) -> bool:
        """登录获取token"""
        try:
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
            
            logger.info(f"登录响应状态码: {response.status_code}")
            logger.info(f"登录响应内容: {response.text}")
            
            response.raise_for_status()

            result = response.json()
            # 兼容多种token字段名
            token = result.get("accessToken") or result.get("token") or result.get("access_token") or result.get("data", {}).get("access_token")
            if token:
                self._token = token
                # 设置token过期时间为1小时（提前60秒过期，避免边界问题）
                self._token_expiry = time.time() + 3600 - 60
                logger.info(f"来水预报API登录成功，token有效期: 1小时")
                
                self._save_token_to_file()
                
                return True
            else:
                logger.error(f"来水预报登录失败: 未找到token字段，完整响应: {result}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"来水预报登录请求异常: {e}")
            return False

    def get_token(self) -> Optional[str]:
        """获取有效token，如果过期则自动刷新"""
        with self._lock:
            if self._token and time.time() < self._token_expiry:
                return self._token

            if self._login():
                return self._token
            return None

    def is_authenticated(self) -> bool:
        """检查是否已认证"""
        return self.get_token() is not None

    def clear_token(self):
        """清除token，强制下次重新登录"""
        with self._lock:
            self._token = None
            self._token_expiry = 0
            
            try:
                if os.path.exists(self._token_file):
                    os.remove(self._token_file)
                    logger.info(f"已删除本地来水预报token文件: {self._token_file}")
            except Exception as e:
                logger.error(f"删除来水预报token文件失败: {e}")
            
            logger.info("来水预报token已清除")

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
        self._base_url = 'http://10.4.158.37:11111'
        self._session = requests.Session()
        # 禁用SSL证书验证
        self._session.verify = False
    
    # def get_reservoir_forecast(self, station_code: str, start_time: str, end_time: str) -> Dict[str, Any]:
    #     """获取水库预报数据"""
    #     try:
    #         url = f"{self._base_url}/huangheApi/reservoir/xiaoyu/recordListByStationCode"
    #         headers = {
    #             **water_forecast_auth_service.get_auth_headers(),
    #             "Content-Type": "application/json"
    #         }
            
    #         params = {
    #             "stationCode": station_code,
    #             "startTime": start_time,
    #             "endTime": end_time
    #         }
            
    #         logger.info(f"正在调用水库预报接口: {url}, 参数: {params}")
    #         response = self._session.get(url, params=params, headers=headers, timeout=30)
            
    #         logger.info(f"水库预报响应状态码: {response.status_code}")
    #         logger.info(f"水库预报响应内容: {response.text}")
            
    #         response.raise_for_status()
            
    #         result = response.json()
    #         logger.info(f"水库预报接口返回成功")
    #         return result
                
    #     except requests.exceptions.RequestException as e:
    #         logger.error(f"水库预报请求异常: {e}")
    #         return {"success": False, "error": str(e)}
    
    # def get_hydrology_forecast(self, station_code: str, start_time: str, end_time: str) -> Dict[str, Any]:
    #     """获取水文站预报数据"""
    #     try:
    #         url = f"{self._base_url}/huangheApi/hydrologyStation/xiaoyu/recordListByCode"
    #         headers = {
    #             **water_forecast_auth_service.get_auth_headers(),
    #             "Content-Type": "application/json"
    #         }
            
    #         params = {
    #             "stationCode": station_code,
    #             "startTime": start_time,
    #             "endTime": end_time
    #         }
            
    #         logger.info(f"正在调用水文站预报接口: {url}, 参数: {params}")
    #         response = self._session.get(url, params=params, headers=headers, timeout=30)
            
    #         logger.info(f"水文站预报响应状态码: {response.status_code}")
    #         logger.info(f"水文站预报响应内容: {response.text}")
            
    #         response.raise_for_status()
            
    #         result = response.json()
    #         logger.info(f"水文站预报接口返回成功")
    #         return result
                
    #     except requests.exceptions.RequestException as e:
    #         logger.error(f"水文站预报请求异常: {e}")
    #         return {"success": False, "error": str(e)}

    def get_scheme_list(self, start_time: str, end_time: str) -> Dict[str, Any]:
        """获取预报方案清单"""
        try:
            url = f"{self._base_url}/huangheApi/preSch/getRecommendedOrLatestSchList?startTime={start_time}&endTime={end_time}"
            headers = {
                **water_forecast_auth_service.get_auth_headers(),
                "Content-Type": "application/json"
            }
            
            response = self._session.get(url, headers=headers, timeout=30)
            
            
            response.raise_for_status()
            
            result = response.json()
            return result
                
        except requests.exceptions.RequestException as e:
            logger.error(f"获取预报方案清单请求异常: {e}")
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
            
            logger.info(f"站点预报数据响应状态码: {response.status_code}")
            logger.info(f"站点预报数据响应内容: {response.text}")
            
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"站点预报数据获取成功")
            return result
                
        except requests.exceptions.RequestException as e:
            logger.error(f"获取站点预报数据请求异常: {e}")
            return {"success": False, "error": str(e)}


water_forecast_service = WaterForecastService()
