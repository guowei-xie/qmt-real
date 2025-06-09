# -*- coding: utf-8 -*-
"""
一进二低吸战法策略运行入口

该模块是一进二低吸战法量化交易策略的运行入口，主要功能包括：
1. 初始化交易环境 - 连接QMT交易接口，设置账户信息
2. 加载策略 - 初始化策略对象，选择符合条件的股票
3. 设置定时任务 - 定时执行策略逻辑，处理行情数据并生成交易信号
4. 执行交易 - 根据交易信号执行买入或卖出操作

使用方法：
直接运行该脚本即可启动策略，策略将在每个交易日的交易时段内运行。
"""

import os
import sys
import time
from datetime import datetime
import configparser

# 添加项目根目录到系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback
from trader.trader import MyXtQuantTraderCallback, create_trader
from trader.context import Context
from trader.logger import logger
from trader.anis import RED, GREEN, YELLOW, BLUE, RESET
from trader.utils import is_trade_time

# 导入策略模块
from strategys.一进二低吸战法.strategy import TradingStrategy

# 读取策略配置文件
strategy_config = configparser.ConfigParser()
strategy_config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')
strategy_config.read(strategy_config_path, encoding='utf-8')

# 读取全局配置文件
global_config = configparser.ConfigParser()
global_config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'config.ini')
global_config.read(global_config_path, encoding='utf-8')

# 策略名称
STRATEGY_NAME = strategy_config.get('strategy', 'name')

# QMT账户配置（从全局配置文件读取）
ACCOUNT_ID = global_config.get('account', 'account_id', fallback="").strip('"')  # 使用全局配置，如果不存在则使用空字符串，并去除引号
MINI_QMT_PATH = global_config.get('path', 'mini_qmt_path', fallback="").strip('"')  # 使用全局配置，如果不存在则使用空字符串，并去除引号

# 全局变量
context = None
trading_strategy = None


def initialize():
    """
    初始化函数，连接交易接口并初始化策略
    """
    global context, trading_strategy
    
    logger.info(f"{GREEN}【策略启动】{RESET} {STRATEGY_NAME}")
    
    try:
        # 使用封装好的函数创建交易对象和账户
        xt_trader, account = create_trader(ACCOUNT_ID, MINI_QMT_PATH)
        
        # 创建交易上下文
        context = Context(xt_trader, account, mode=0, strategy_name=STRATEGY_NAME)
        
        # 创建交易策略
        trading_strategy = TradingStrategy(context)
        
        # 初始化策略
        trading_strategy.initialize()
        
        # 设置定时任务
        context.run_time(update, "1nMinute")
        
        logger.info(f"{GREEN}【初始化完成】{RESET} {STRATEGY_NAME}")
        return True
    except Exception as e:
        logger.error(f"{RED}【初始化失败】{RESET} {e}")
        return False


def update():
    """
    定时更新函数，每分钟执行一次
    """
    # 检查是否为交易时间
    if not is_trade_time():
        return
    
    # 获取选中的股票列表（涨停股票池）
    selected_stocks = trading_strategy.selected_stocks
    
    # 获取当前持仓股票列表
    positions = context.get_positions()
    position_stocks = []
    if not positions.empty:
        position_stocks = positions['股票代码'].tolist()
    
    # 合并股票列表（去重）
    all_stocks = list(set(selected_stocks + position_stocks))
    if not all_stocks:
        return
    
    # 处理每只股票
    for stock in all_stocks:
        try:
            # 获取分钟数据
            minute_data = trading_strategy.get_minute_data(stock)
            if minute_data.empty:
                continue
            
            # 处理分钟数据，获取交易信号
            # 优化逻辑：已持仓票只判断卖出信号，涨停池的票只判断买入信号
            position = trading_strategy.context.get_position(stock)
            
            if position is not None and position['持仓数量'] > 0:
                # 对于已持仓的股票，只判断卖出信号
                signal = trading_strategy.check_sell_condition(stock, minute_data, None)
                logger.info(f"{BLUE}【信号检测】{RESET} {stock} 已持仓，只检查卖出条件")
            elif stock in selected_stocks:
                # 对于在涨停池中且未持仓的股票，只判断买入信号
                signal = trading_strategy.check_buy_condition(stock, minute_data, None)
                logger.info(f"{BLUE}【信号检测】{RESET} {stock} 在涨停池中且未持仓，只检查买入条件")
            else:
                # 对于既不在持仓中也不在涨停池中的股票，不处理
                signal = {'signal': 'none'}
                logger.debug(f"{BLUE}【信号检测】{RESET} {stock} 既不在持仓中也不在涨停池中，跳过处理")
            
            # 执行交易
            if signal['signal'] != 'none':
                trading_strategy.execute_trade(stock, signal)
        
        except Exception as e:
            logger.error(f"{RED}【处理错误】{RESET} {stock}: {e}")



def main():
    """
    主函数
    """
    # 初始化
    if not initialize():
        logger.error(f"{RED}【初始化失败】{RESET} 程序退出")
        return
    
    # 主循环
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info(f"{YELLOW}【程序退出】{RESET} 用户中断")
    except Exception as e:
        logger.error(f"{RED}【程序异常】{RESET} {e}")


if __name__ == "__main__":
    main()