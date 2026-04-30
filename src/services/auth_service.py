import requests
import time
import threading
from typing import Optional
from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AuthService:
    """数据API认证服务，管理token的获取和刷新"""

    def __init__(self):
        self._token: Optional[str] = None
        self._token_expiry: float = 0
        self._lock = threading.Lock()
        self._base_url = getattr(settings, 'DATA_API_BASE_URL', 'http://wt.hxyai.cn/fx')
        self._access_key = getattr(settings, 'DATA_API_ACCESS_KEY', 'yhllm')
        self._secret_key = getattr(settings, 'DATA_API_SECRETKEY', '5f75d154f9cc50ad0ad8790d0a7f5301')
        self._session = requests.Session()

    def _login(self) -> bool:
        """登录获取token"""
        try:
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
                self._token = result.get("data")
                # 设置token过期时间为7天（提前5分钟过期，避免边界问题）
                self._token_expiry = time.time() + 7 * 24 * 3600 - 300
                logger.info("数据API登录成功，token已获取")
                return True
            else:
                logger.error(f"登录失败: {result.get('msg', '未知错误')}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"登录请求异常: {e}")
            return False

    def get_token(self) -> Optional[str]:
        """获取有效token，如果过期则自动刷新"""
        with self._lock:
            # 检查token是否存在且未过期
            if self._token and time.time() < self._token_expiry:
                return self._token

            # 需要重新登录
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
            logger.info("Token已清除")

    def get_auth_headers(self) -> dict:
        """获取包含认证信息的请求头"""
        token = self.get_token()
        if token:
            return {"Authorization": token}
        return {}


# 全局认证服务实例
auth_service = AuthService()
