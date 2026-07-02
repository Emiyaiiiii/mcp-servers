import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

class Settings:
    MCP_SERVER_NAME = os.getenv('MCP_SERVER_NAME', 'FloodControlMCP')

    SCENE_WS_BASE_URL = os.getenv('SCENE_WS_BASE_URL', 'ws://localhost:8889')
    SCENE_WS_TIMEOUT = int(os.getenv('SCENE_WS_TIMEOUT', '30'))
    SCENE_IDLE_TIMEOUT = int(os.getenv('SCENE_IDLE_TIMEOUT', '60'))

    DATA_API_BASE_URL = os.getenv('DATA_API_BASE_URL', 'http://wt.hxyai.cn/fx')
    DATA_API_ACCESS_KEY = os.getenv('DATA_API_ACCESSKEY', 'yhllm')
    DATA_API_SECRETKEY = os.getenv('DATA_API_SECRETKEY', '5f75d154f9cc50ad0ad8790d0a7f5301')
    DATA_API_MOCK_ENABLED = os.getenv('DATA_API_MOCK_ENABLED', 'true').lower() == 'true'

    KNOWLEDGE_BASE_API_URL = os.getenv('KNOWLEDGE_BASE_API_URL', 'http://10.4.158.35:9621/query/data')

    DISPATCH_API_BC_URL = os.getenv('DISPATCH_API_BC_URL', 'http://localhost:22811/bc')
    DISPATCH_API_SW_URL = os.getenv('DISPATCH_API_SW_URL', 'http://localhost:22811/sw')

    XINANJIANG_API_BASE_URL = os.getenv('XINANJIANG_API_BASE_URL', 'http://gateway.yrihr.com')

    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

settings = Settings()
