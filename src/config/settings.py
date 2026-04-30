import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    MCP_SERVER_NAME = os.getenv('MCP_SERVER_NAME', 'FloodControlMCP')

    SCENE_WS_BASE_URL = os.getenv('SCENE_WS_BASE_URL', 'ws://localhost:8889')
    SCENE_WS_TIMEOUT = int(os.getenv('SCENE_WS_TIMEOUT', '30'))
    SCENE_IDLE_TIMEOUT = int(os.getenv('SCENE_IDLE_TIMEOUT', '60'))

    DATA_API_BASE_URL = os.getenv('DATA_API_BASE_URL', 'http://wt.hxyai.cn/fx')
    DATA_API_ACCESS_KEY = os.getenv('DATA_API_ACCESSKEY', 'yhllm')
    DATA_API_SECRETKEY = os.getenv('DATA_API_SECRETKEY', '5f75d154f9cc50ad0ad8790d0a7f5301')
    DATA_API_MOCK_ENABLED = os.getenv('DATA_API_MOCK_ENABLED', 'true').lower() == 'true'

    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

settings = Settings()
