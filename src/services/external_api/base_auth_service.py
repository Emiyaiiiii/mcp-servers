"""
Token 认证服务基类
提供 token 获取、缓存、刷新、文件持久化、日志脱敏的通用实现
"""
import os
import json
import time
import threading
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import requests
from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class BaseTokenAuthService(ABC):
    """Token 认证服务基类，子类仅需实现 _login() 和 init_from_settings()"""

    def __init__(self, name: str, token_filename: str):
        self.name = name
        self._token: Optional[str] = None
        self._token_expiry: float = 0
        self._lock = threading.Lock()
        self._session = requests.Session()
        self._session.verify = settings.SSL_CERT_PATH if settings.SSL_CERT_PATH else settings.SSL_VERIFY
        self._token_file = os.path.join(
            os.path.dirname(__file__), '..', '..', '..', 'data', token_filename
        )
        self.init_from_settings()
        self._load_token_from_file()

    @abstractmethod
    def init_from_settings(self):
        """从 settings 读取子类特有的配置"""
        pass

    @abstractmethod
    def _login(self) -> Dict[str, Any]:
        """
        执行登录请求，返回包含 token 和可选 expiry 的字典。
        子类必须实现此方法。
        """
        pass

    def get_token(self) -> Optional[str]:
        """获取有效 token，如过期则自动刷新"""
        if self._token and self._token_expiry > time.time():
            return self._token
        with self._lock:
            if self._token and self._token_expiry > time.time():
                return self._token
            return self._refresh_token()

    def _refresh_token(self) -> Optional[str]:
        """刷新 token"""
        try:
            token_data = self._login()
            self._token = token_data.get('token')
            self._token_expiry = token_data.get('expiry', time.time() + 3600)
            self._save_token_to_file()
            logger.info(f"{self.name}: token 刷新成功")
            return self._token
        except Exception as e:
            logger.error(f"{self.name}: token 刷新失败: {e}")
            return None

    def is_authenticated(self) -> bool:
        return self.get_token() is not None

    def get_auth_headers(self) -> Dict[str, str]:
        token = self.get_token()
        if token:
            return {"Authorization": f"Bearer {token[:8]}...{token[-4:]}"}
        # 即使 token 不存在也返回，让调用方处理
        return {}

    def clear_token(self):
        self._token = None
        self._token_expiry = 0
        if os.path.exists(self._token_file):
            os.remove(self._token_file)

    def _save_token_to_file(self):
        try:
            token_data = {
                'token': self._token,
                'expiry': self._token_expiry
            }
            token_dir = os.path.dirname(self._token_file)
            os.makedirs(token_dir, exist_ok=True)
            # 设置文件权限仅所有者可读写（Unix）
            with open(self._token_file, 'w', encoding='utf-8') as f:
                json.dump(token_data, f, ensure_ascii=False, indent=2)
            if os.name != 'nt':
                os.chmod(self._token_file, 0o600)
        except Exception as e:
            logger.error(f"{self.name}: 保存 token 到文件失败: {e}")

    def _load_token_from_file(self):
        try:
            if os.path.exists(self._token_file):
                with open(self._token_file, 'r', encoding='utf-8') as f:
                    token_data = json.load(f)
                self._token = token_data.get('token')
                self._token_expiry = token_data.get('expiry', 0)
                logger.info(f"{self.name}: 从文件加载 token 成功")
        except Exception as e:
            logger.error(f"{self.name}: 从文件加载 token 失败: {e}")