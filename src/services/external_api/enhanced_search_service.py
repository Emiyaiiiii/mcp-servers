import requests
import time
from typing import Optional, Dict, Any
from src.config.settings import settings
from src.utils.logger import get_logger
from src.services.external_api.base_auth_service import BaseTokenAuthService

logger = get_logger(__name__)


class EnhancedSearchAuthService(BaseTokenAuthService):
    """增强搜索API认证服务，管理token的获取和刷新（有效期1小时）"""

    def __init__(self):
        super().__init__(name="增强搜索API", token_filename=".enhanced_search_token.json")

    def init_from_settings(self):
        self._base_url = settings.ENHANCED_SEARCH_API_BASE_URL
        self._username = settings.ENHANCED_SEARCH_API_USERNAME
        self._password = settings.ENHANCED_SEARCH_API_PASSWORD

    def _login(self) -> Dict[str, Any]:
        """登录获取token（有效期1小时）"""
        url = f"{self._base_url}/api/auth/token/"
        headers = {"Content-Type": "application/json"}
        data = {
            "username": self._username,
            "password": self._password
        }

        logger.info(f"正在登录增强搜索API: {url}")
        response = self._session.post(url, json=data, headers=headers, timeout=30)

        logger.debug(f"登录响应状态码: {response.status_code}, body_len={len(response.text)}")

        response.raise_for_status()

        result = response.json()
        # 兼容多种token字段名
        token = result.get("access") or result.get("access_token") or result.get("token") or result.get("data", {}).get("access_token")
        if token:
            # 设置token过期时间为1小时（提前60秒过期，避免边界问题）
            expiry = time.time() + 3600 - 60
            logger.info(f"增强搜索API登录成功，token有效期: 1小时")
            return {"token": token, "expiry": expiry}
        else:
            raise Exception(f"增强搜索登录失败: 未找到token字段，完整响应: {result}")

    def get_auth_headers(self) -> dict:
        """获取包含认证信息的请求头"""
        token = self.get_token()
        if token:
            return {"Authorization": f"Bearer {token}"}
        return {}


enhanced_search_auth_service = EnhancedSearchAuthService()


class EnhancedSearchService:
    """增强搜索服务"""

    def __init__(self):
        self._base_url = settings.ENHANCED_SEARCH_API_BASE_URL
        self._session = requests.Session()
        # 从配置读取SSL验证设置
        self._session.verify = settings.SSL_CERT_PATH if settings.SSL_CERT_PATH else settings.SSL_VERIFY

    def search_documents(self, query: str, knowledge_base_ids: list = None, top_k: int = 5) -> Dict[str, Any]:
        """搜索文档"""
        try:
            url = f"{self._base_url}/api/enhanced_search/unified/"
            auth_headers = enhanced_search_auth_service.get_auth_headers()
            headers = {
                **auth_headers,
                "Content-Type": "application/json"
            }

            # 记录请求头（不要记录完整token，只记录是否存在）
            logger.info(f"搜索请求 - Authorization头是否存在: {bool(auth_headers.get('Authorization'))}")

            payload = {
                "query": query,
                "filters": {
                    "knowledge_base_ids": knowledge_base_ids or [],
                    "source_type": "document"
                },
                "search_type": "unified",
                "top_k": top_k,
                "use_intent_analysis": True,
                "use_parallel": True,
                "enable_cache": True
            }

            logger.info(f"正在调用增强搜索接口: {url}")
            response = self._session.post(url, json=payload, headers=headers, timeout=30)

            logger.debug(f"搜索响应状态码: {response.status_code}, body_len={len(response.text)}")

            response.raise_for_status()

            result = response.json()
            logger.info(f"增强搜索接口返回成功")
            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"增强搜索请求异常: {e}")
            return {"success": False, "error": str(e)}


enhanced_search_service = EnhancedSearchService()