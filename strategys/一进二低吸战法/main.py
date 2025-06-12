#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
一进二低吸战法策略入口文件

用于运行一进二低吸战法策略，包括初始化交易环境、启动策略、注册回调函数等。
"""

import os
import sys
import time
from datetime import datetime
import traceback

# 添加项目根目录到系统路径
root_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, root_path)  # 确保根目录优先级最高

# 设置xtquant模块路径
xtquant_path = os.path.join(root_path, "xtquant")
if os.path.exists(xtquant_path):
    sys.path.insert(0, xtquant_path)

# 导入全局配置
from config import ACCOUNT_ID, MINI_QMT_PATH

from trader.trader import create_trader
from trader.context import Context
from trader.logger import logger
from trader.anis import RED, GREEN, YELLOW, BLUE, RESET
from trader.utils import add_stock_suffix

# 导入xtquant模块（只导入xttrader，xtdata通过context访问）
from xtquant.xttrader import XtQuantTrader

# 导入策略专属配置
from strategys.一进二低吸战法.config import (
    STOCK_POOL_REFRESH_TIME,
    STRATEGY_NAME
)
from strategys.一进二低吸战法.strategy import YiJinErDiXiStrategy


def download_astock_history_data(context):
    """
    下载A股历史数据
    
    Args:
        context: QMT交易上下文对象
        
    Returns:
        bool: 下载是否成功
    """
    try:
        # 获取A股股票列表
        all_stocks = context.get_stock_list_in_sector("沪深A股")
        logger.info(f"{GREEN}【数据准备】{RESET} 开始下载A股历史数据...")
        
        # 股票代码添加市场后缀并批量下载
        stock_codes_with_suffix = [add_stock_suffix(code) for code in all_stocks]
        context.custom_data.download_qmt_history_data(
            stock_list=stock_codes_with_suffix,
            period='1d', 
            start_time='20220101'
        )
        logger.info(f"{GREEN}【数据准备】{RESET} A股历史数据下载完成")
        return True
    except Exception as e:
        logger.error(f"{RED}【下载错误】{RESET} {e}")
        traceback.print_exc()
        return False


def refresh_stock_pool_task(context):
    """
    刷新股票池任务
    
    每日收盘后更新股票池，为次日交易做准备
    
    Args:
        context: 交易上下文对象
    """
    logger.info(f"{GREEN}【定时任务】{RESET} 执行股票池更新任务")
    
    # 先下载最新的A股历史数据
    data_download_success = download_astock_history_data(context)
    
    # 更新策略的数据下载状态
    strategy.data_download_success = data_download_success
    
    # 更新股票池
    strategy.update_stock_pool()


if __name__ == "__main__":
    try:
        # 创建交易对象和账户
        logger.info(f"{GREEN}【系统启动】{RESET} 正在创建交易对象，连接QMT交易柜台...")
        xt_trader, account = create_trader(ACCOUNT_ID, MINI_QMT_PATH)
        
        # 创建交易上下文
        logger.info(f"{GREEN}【系统启动】{RESET} 正在创建交易上下文...")
        context = Context(xt_trader, account, strategy_name=STRATEGY_NAME)
        
        # 下载A股历史数据
        logger.info(f"{GREEN}【系统启动】{RESET} 正在下载A股历史数据...")
        data_download_success = download_astock_history_data(context)
        # data_download_success = True
        
        # 创建并初始化策略对象
        logger.info(f"{GREEN}【策略启动】{RESET} 初始化一进二低吸战法策略...")
        strategy = YiJinErDiXiStrategy(context, data_download_success)
        
        # 设置定时任务
        logger.info(f"{GREEN}【策略启动】{RESET} 设置股票池更新定时任务...")
        context.run_daily(refresh_stock_pool_task, STOCK_POOL_REFRESH_TIME)
        
        # 启动时立即更新股票池
        logger.info(f"{GREEN}【策略启动】{RESET} 正在更新股票池...")
        strategy.update_stock_pool()
        
        # 策略运行主循环
        logger.info(f"{GREEN}【策略启动】{RESET} 策略已启动，等待行情推送...")
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info(f"{YELLOW}【系统关闭】{RESET} 用户手动终止程序")
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"{RED}【系统错误】{RESET} {e}")
        raise 