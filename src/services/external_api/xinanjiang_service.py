import requests
import time
from typing import Optional, Dict, Any
from src.config.settings import settings
from src.utils.logger import get_logger
from src.services.external_api.base_auth_service import BaseTokenAuthService

logger = get_logger(__name__)


class XinanjiangAuthService(BaseTokenAuthService):
    """新安江模型API认证服务，管理token的获取和刷新"""

    def __init__(self):
        super().__init__(name="新安江模型API", token_filename=".xinanjiang_token.json")

    def init_from_settings(self):
        self._base_url = settings.XINANJIANG_API_BASE_URL
        self._app_key = settings.XINANJIANG_APP_KEY
        self._app_secret = settings.XINANJIANG_APP_SECRET

    def _login(self) -> Dict[str, Any]:
        """登录获取token"""
        url = f"{self._base_url}/sys/sysApplication/getAppToken"
        headers = {"Content-Type": "application/json"}
        data = {
            "appKey": self._app_key,
            "appSecret": self._app_secret
        }

        logger.info(f"正在登录新安江模型API: {url}")
        response = self._session.post(url, json=data, headers=headers, timeout=30)
        response.raise_for_status()

        result = response.json()
        if result.get("success") and result.get("code") == 200:
            token_info = result.get("result", {})
            token = token_info.get("token")
            expire_seconds = int(token_info.get("expire", 28800))
            expiry = time.time() + expire_seconds - 60
            logger.info(f"新安江模型API登录成功，token有效期: {expire_seconds}秒")
            return {"token": token, "expiry": expiry}
        else:
            raise Exception(f"新安江模型登录失败: {result.get('message', '未知错误')}")

    def get_auth_headers(self) -> dict:
        """获取包含认证信息的请求头"""
        token = self.get_token()
        if token:
            return {
                "X-Access-Token": token,
                "Login-Type": "3"
            }
        return {}


xinanjiang_auth_service = XinanjiangAuthService()


class XinanjiangModelService:
    """新安江模型服务"""

    def __init__(self):
        self._base_url = settings.XINANJIANG_API_BASE_URL
        self._session = requests.Session()

    def write_service_nc_file(self, control_params: Dict[str, Any], rainfall_data: Dict[str, Any], etp_data: Dict[str, Any]) -> Dict[str, Any]:
        """写入NC文件（传入参数）"""
        try:
            url = f"{self._base_url}/szrs-model/model/slbModelServiceArgo/writeServiceNcFile"
            headers = {
                **xinanjiang_auth_service.get_auth_headers(),
                "Content-Type": "application/json"
            }

            payload = [
                control_params,
                rainfall_data,
                etp_data
            ]

            logger.info(f"正在写入新安江模型NC文件: {url}")
            response = self._session.post(url, json=payload, headers=headers, timeout=60)
            response.raise_for_status()

            result = response.json()
            if result.get("success") and result.get("code") == 200:
                logger.info("新安江模型NC文件写入成功")
                return result
            else:
                logger.error(f"写入NC文件失败: {result.get('message', '未知错误')}")
                return result

        except requests.exceptions.RequestException as e:
            logger.error(f"写入NC文件请求异常: {e}")
            return {"success": False, "message": str(e), "code": 500}

    def call_model(self, control_file_path: str, em_file_path: str, p_file_path: str) -> Dict[str, Any]:
        """调用模型"""
        try:
            url = f"{self._base_url}/szrs-model/model/slbModelServiceVcJob/stdSvc/yrihr-xaj/"
            headers = {
                **xinanjiang_auth_service.get_auth_headers(),
                "Content-Type": "application/json"
            }

            payload = {
                "callBackUrl": "",
                "key": "",
                "data": [
                    {
                        "key": "control",
                        "keyDescribe": "控制参数",
                        "value": control_file_path
                    },
                    {
                        "key": "em",
                        "keyDescribe": "蒸散发数据",
                        "value": em_file_path
                    },
                    {
                        "key": "p",
                        "keyDescribe": "等时段降雨数据",
                        "value": p_file_path
                    }
                ]
            }

            logger.info(f"正在调用新安江模型: {url}")
            response = self._session.post(url, json=payload, headers=headers, timeout=60)
            response.raise_for_status()

            result = response.json()
            if result.get("success") and result.get("code") == 200:
                inc_key = result.get("result", {}).get("incKey")
                logger.info(f"新安江模型调用成功，任务ID: {inc_key}")
                return result
            else:
                logger.error(f"模型调用失败: {result.get('message', '未知错误')}")
                return result

        except requests.exceptions.RequestException as e:
            logger.error(f"模型调用请求异常: {e}")
            return {"success": False, "message": str(e), "code": 500}

    def get_service_instance(self, inc_key: str) -> Dict[str, Any]:
        """轮询查看结果"""
        try:
            url = f"{self._base_url}/szrs-model/model/slbModelServiceArgo/getServiceInstance"
            headers = {
                **xinanjiang_auth_service.get_auth_headers()
            }
            params = {"incKey": inc_key}

            logger.info(f"正在查询新安江模型任务状态: {inc_key}")
            response = self._session.get(url, params=params, headers=headers, timeout=30)
            response.raise_for_status()

            result = response.json()
            if result.get("success") and result.get("code") == 200:
                status = result.get("result", {}).get("status")
                message = result.get("result", {}).get("message")
                logger.info(f"任务状态: {status}, 消息: {message}")
                return result
            else:
                logger.error(f"查询任务状态失败: {result.get('message', '未知错误')}")
                return result

        except requests.exceptions.RequestException as e:
            logger.error(f"查询任务状态请求异常: {e}")
            return {"success": False, "message": str(e), "code": 500}

    def nc_to_json(self, file_path: str) -> Dict[str, Any]:
        """NC文件解析"""
        try:
            url = f"{self._base_url}/szrs-model/model/slbModelCores/ncToJson"
            headers = {
                **xinanjiang_auth_service.get_auth_headers(),
                "Content-Type": "application/json"
            }

            payload = {"filePath": file_path}

            logger.info(f"正在解析NC文件: {file_path}")
            response = self._session.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()

            result = response.json()
            if result.get("success") and result.get("code") == 200:
                logger.info("NC文件解析成功")
                return result
            else:
                logger.error(f"NC文件解析失败: {result.get('message', '未知错误')}")
                return result

        except requests.exceptions.RequestException as e:
            logger.error(f"NC文件解析请求异常: {e}")
            return {"success": False, "message": str(e), "code": 500}


xinanjiang_model_service = XinanjiangModelService()