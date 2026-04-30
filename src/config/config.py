import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.yaml"

def load_config():
    """加载 YAML 配置"""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {
        "reservoirs": []
    }

config_data = load_config()

class Config:
    """配置类"""

    def __init__(self, data):
        self._data = data

    @property
    def reservoirs(self):
        return self._data.get("reservoirs", [])

config = Config(config_data)
