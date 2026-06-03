import logging
import os

def get_logger(name):
    """获取配置好的 logger"""
    logger = logging.getLogger(name)
    
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    level = getattr(logging, log_level, logging.INFO)
    logger.setLevel(level)
    
    return logger
