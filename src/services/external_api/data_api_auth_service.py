import time
from typing import Optional, Dict, Any
from src.config.settings import settings
from src.utils.logger import get_logger
from src.services.external_api.base_auth_service import BaseTokenAuthService

logger = get_logger(__name__)


class DataApiAuthService(BaseTokenAuthService):
    """数据API认证服务，管理token的获取和刷新"""

    def __init__(self):
        super().__init__(name="数据API", token_filename=".data_api_token.json")

    def init_from_settings(self):
        self._base_url = settings.DATA_API_BASE_URL
        self._access_key = settings.DATA_API_ACCESS_KEY
        self._secret_key = settings.DATA_API_SECRETKEY

    def _login(self) -> Dict[str, Any]:
        """登录获取token"""
        url = f"{self._base_url}/oauth/login"
        headers = {"Content-Type": "application/json"}
        data = {
            "accessKey": self._access_key,
            "secretKey": self._secret_key,
            "userType": 3
        }

        logger.info(f"正在登录数据API: {url}")
        response = self._session.post(url, json=data, headers=headers, timeout=30)
        response.raise_for_status()

        result = response.json()
        if result.get("code") == 200:
            token = result.get("data")
            # 设置token过期时间为7天（提前5分钟过期，避免边界问题）
            expiry = time.time() + 7 * 24 * 3600 - 300
            logger.info("数据API登录成功，token已获取")
            return {"token": token, "expiry": expiry}
        else:
            msg = result.get('msg', '未知错误')
            logger.error(f"登录失败: {msg}")

            # 如果服务器提示"5分钟内不允许再次认证"，说明token仍有效，保留旧token
            if "5分钟内不允许再次认证" in msg and self._token:
                logger.info("服务器提示已认证，保留现有token继续使用")
                # 延长token过期时间
                return {"token": self._token, "expiry": time.time() + 5 * 60}

            raise Exception(f"登录失败: {msg}")

    def get_auth_headers(self) -> dict:
        """获取包含认证信息的请求头"""
        token = self.get_token()
        if token:
            return {"Authorization": token}
        return {}


# 全局数据API认证服务实例
data_api_auth_service = DataApiAuthService()