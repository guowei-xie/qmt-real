# -*- coding: utf-8 -*-
"""
日志模块

该模块提供了日志记录功能，支持控制台输出、文件写入和WebHook推送
"""

import logging
import requests
import os
import re
from datetime import date

# 标准日志格式，包含时间戳
formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

# WebHook推送日志格式，时间戳和消息内容分行显示
push_formatter = logging.Formatter('[%(asctime)s]\n%(message)s', datefmt='%Y-%m-%d %H:%M:%S')


class RemoveAnsiEscapeCodes(logging.Filter):
    """
    日志过滤器，用于移除日志消息中的ANSI转义码
    
    ANSI转义码通常用于控制台输出的颜色和格式，但在文件日志中会显示为乱码，
    该过滤器可以确保日志文件中的内容清晰可读。
    """
    def filter(self, record):
        """
        过滤日志记录，移除ANSI转义码
        
        Args:
            record: 日志记录对象
            
        Returns:
            bool: 始终返回True，表示保留该日志记录
        """
        record.msg = re.sub(r'\033\[[0-9;]*m', '', str(record.msg))
        return True


def create_logger():
    """
    创建并配置日志记录器
    
    创建一个日志记录器，配置控制台输出和文件输出。
    日志文件按日期命名，存放在logs目录下。
    
    Returns:
        logging.Logger: 配置好的日志记录器对象
    """
    logger = logging.getLogger('log')
    logger.setLevel(logging.DEBUG)  # 设置日志级别为DEBUG

    # 添加控制台处理器
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # 创建日志文件夹（如果不存在）
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # 创建文件处理器，并将日志写入文件
    # 文件名格式为YYYY-MM-DD.log
    file_handler = logging.FileHandler(f"{log_dir}/{date.today().strftime('%Y-%m-%d')}.log", encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(RemoveAnsiEscapeCodes())  # 添加ANSI转义码过滤器
    logger.addHandler(file_handler)

    return logger


class WebHookHandler(logging.Handler):
    """
    WebHook日志处理器
    
    将日志消息通过HTTP POST请求发送到指定的WebHook URL。
    主要用于将重要日志推送到企业微信、钉钉等平台。
    """
    def __init__(self, webhook_url):
        """
        初始化WebHook处理器
        
        Args:
            webhook_url: WebHook的URL地址
        """
        super().__init__()
        self.webhook_url = webhook_url

    def emit(self, record):
        """
        发送日志记录到WebHook
        
        将日志记录格式化后，通过HTTP POST请求发送到WebHook URL。
        使用企业微信/钉钉等平台支持的消息格式。
        
        Args:
            record: 日志记录对象
        """
        log_entry = self.format(record)
        payload = {
            "msgtype": "text",
            "text": {
                "content": log_entry
            }
        }
        try:
            response = requests.post(self.webhook_url, json=payload)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Failed to send log to WeChat: {e}")


def add_webhook_handler(webhook_url):
    """
    添加WebHook日志处理器到全局日志记录器
    
    如果提供了有效的webhook_url，则创建一个WebHook处理器并添加到全局日志记录器。
    WebHook处理器的日志级别设置为INFO，只有INFO及以上级别的日志会被推送。
    
    Args:
        webhook_url: WebHook的URL地址，如果为None则不添加处理器
    """
    if webhook_url is not None:
        # 创建WebHook处理器，并将日志发送到WebHook
        webhook_handler = WebHookHandler(webhook_url)
        webhook_handler.setLevel(logging.INFO)  # 只推送INFO及以上级别的日志
        webhook_handler.setFormatter(push_formatter)
        webhook_handler.addFilter(RemoveAnsiEscapeCodes())  # 添加ANSI转义码过滤器
        logger.addHandler(webhook_handler)


# 创建全局日志记录器实例
logger = create_logger()
