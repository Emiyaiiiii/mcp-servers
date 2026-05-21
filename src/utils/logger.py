import json
import logging
import os
import sys
from datetime import datetime

class JSONFormatter(logging.Formatter):
    """JSON 格式的日志格式化器"""
    
    def format(self, record):
        log_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_record, ensure_ascii=False)

def get_logger(name):
    """获取配置好的 logger"""
    logger = logging.getLogger(name)
    
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    level = getattr(logging, log_level, logging.INFO)
    logger.setLevel(level)
    
    # 避免重复添加处理器
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
    
    return logger