import requests
import time
import threading
import json
import os
from typing import Optional, Dict, Any
from src.utils.logger import get_logger

logger = get_logger(__name__)


class EnhancedSearchAuthService:
    """增强搜索API认证服务，管理token的获取和刷新（有效期1小时）"""

    def __init__(self):
        self._token: Optional[str] = None
        self._token_expiry: float = 0
        self._lock = threading.Lock()
        self._base_url = 'https://10.4.158.43:18888'
        self._username = '4055036'
        self._password = '20221qaz@WSX'
        self._session = requests.Session()
        # 禁用SSL证书验证
        self._session.verify = False
        
        self._token_file = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', '.enhanced_search_token.json')
        
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
            
            logger.info(f"增强搜索token已保存到文件: {self._token_file}")
        except Exception as e:
            logger.error(f"保存增强搜索token到文件失败: {e}")

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
                    logger.info(f"已从文件加载有效增强搜索token，过期时间: {time.ctime(expiry)}")
                else:
                    logger.info("文件中的增强搜索token已过期或无效")
            else:
                logger.info("增强搜索token文件不存在，需要重新登录")
        except Exception as e:
            logger.error(f"从文件加载增强搜索token失败: {e}")

    def _login(self) -> bool:
        """登录获取token（有效期1小时）"""
        try:
            url = f"{self._base_url}/api/auth/token/"
            headers = {"Content-Type": "application/json"}
            data = {
                "username": self._username,
                "password": self._password
            }

            logger.info(f"正在登录增强搜索API: {url}")
            response = self._session.post(url, json=data, headers=headers, timeout=30)
            
            # 添加日志查看完整响应
            logger.info(f"登录响应状态码: {response.status_code}")
            logger.info(f"登录响应内容: {response.text}")
            
            response.raise_for_status()

            result = response.json()
            # 兼容多种token字段名
            token = result.get("access") or result.get("access_token") or result.get("token") or result.get("data", {}).get("access_token")
            if token:
                self._token = token
                # 设置token过期时间为1小时（提前60秒过期，避免边界问题）
                self._token_expiry = time.time() + 3600 - 60
                logger.info(f"增强搜索API登录成功，token有效期: 1小时")
                
                self._save_token_to_file()
                
                return True
            else:
                logger.error(f"增强搜索登录失败: 未找到token字段，完整响应: {result}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"增强搜索登录请求异常: {e}")
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
                    logger.info(f"已删除本地增强搜索token文件: {self._token_file}")
            except Exception as e:
                logger.error(f"删除增强搜索token文件失败: {e}")
            
            logger.info("增强搜索token已清除")

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
        self._base_url = 'https://10.4.158.43:18888'
        self._session = requests.Session()
        # 禁用SSL证书验证
        self._session.verify = False
    
    def search_documents(self, query: str, knowledge_base_ids: list = None, top_k: int = 5) -> Dict[str, Any]:
        """搜索文档"""
        try:
            url = f"{self._base_url}/api/enhanced_search/documents/multi/"
            auth_headers = enhanced_search_auth_service.get_auth_headers()
            headers = {
                **auth_headers,
                "Content-Type": "application/json"
            }
            
            # 记录请求头（不要记录完整token，只记录是否存在）
            logger.info(f"搜索请求 - Authorization头是否存在: {bool(auth_headers.get('Authorization'))}")
            
            payload = {
                "query": query,
                "knowledge_base_ids": knowledge_base_ids or [],
                "top_k": top_k
            }
            
            logger.info(f"正在调用增强搜索接口: {url}")
            response = self._session.post(url, json=payload, headers=headers, timeout=30)
            
            logger.info(f"搜索响应状态码: {response.status_code}")
            logger.info(f"搜索响应内容: {response.text}")
            
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"增强搜索接口返回成功")
            return result
                
        except requests.exceptions.RequestException as e:
            logger.error(f"增强搜索请求异常: {e}")
            return {"success": False, "error": str(e)}


enhanced_search_service = EnhancedSearchService()
