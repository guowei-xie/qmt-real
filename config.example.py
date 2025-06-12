#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
全局配置文件

包含所有策略共用的全局配置参数，如账户信息、路径配置等
"""

# 账户配置
ACCOUNT_ID = "你的QMT资金账号"  # 资金账号
MINI_QMT_PATH = "D:\国金QMT交易端模拟\userdata_mini"  # miniQMT客户端安装路径

# 日志配置
LOG_LEVEL = "INFO"  # 日志级别，可选值：DEBUG, INFO, WARNING, ERROR, CRITICAL

# 其他全局配置
DEFAULT_ORDER_TIMEOUT = 60  # 默认订单超时时间（秒） 