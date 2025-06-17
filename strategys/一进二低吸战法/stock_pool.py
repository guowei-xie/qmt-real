#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
股票选股模块

实现一进二低吸战法的选股逻辑，筛选出符合条件的股票池
"""

import pandas as pd
from datetime import datetime, time

# 导入配置参数
from strategys.一进二低吸战法.config import (
    EXCLUDE_ONE_WORD_BOARD, FIRST_LIMIT_UP_DAYS, NEW_HIGH_DAYS, 
    MAX_MARKET_VALUE, MAIN_BOARD_ONLY, EXCLUDE_ST, EXCLUDE_SUSPENDED
)
from trader.logger import logger
from trader.anis import RED, GREEN, YELLOW, BLUE, RESET
from trader.utils import add_stock_suffix


def is_one_word_board(daily_data):
    """判断是否为一字板"""
    price_equal = daily_data['open'] == daily_data['close']
    volume_shrink = daily_data['volume'] < (daily_data['vol_prev'] * 0.2) if 'vol_prev' in daily_data else False
    return price_equal or volume_shrink


def is_main_board_stock(stock_code):
    """判断是否为主板股票"""
    if '.' in stock_code:
        stock_code = stock_code.split('.')[0]
    return stock_code.startswith('60') or stock_code.startswith('00')


def is_st_stock(stock_name):
    """判断是否为ST股票"""
    return 'ST' in stock_name or '*ST' in stock_name


def filter_stock_pool(context, batch_download_success=True):
    """
    根据选股条件筛选股票池
    
    选股条件包括：
    1. 昨天涨停但排除一字板
    2. 近3个交易日内的首次涨停
    3. 昨天收盘价是近30个交易日的最高价
    4. 主板股票、排除ST股和停牌股
    5. 公司总市值上限为150亿元
    """
    # 获取沪深A股股票列表
    all_stocks = context.get_stock_list_in_sector("沪深A股")
    selected_stocks = []
    
    # 开始筛选股票
    logger.info(f"{GREEN}【选股开始】{RESET} 正在筛选符合一进二低吸战法条件的股票...")
    
    # 遍历所有股票
    for stock_code in all_stocks:
        try:
            # 获取股票基本信息并进行初步筛选
            stock_info = context.get_stock_info(stock_code)
            if not stock_info:
                continue
                
            stock_name = stock_info['股票名称']
            
            # 基本条件筛选（条件4和5）
            if (EXCLUDE_SUSPENDED and stock_info['停牌状态'] == 1) or \
               (EXCLUDE_ST and is_st_stock(stock_name)) or \
               (MAIN_BOARD_ONLY and not is_main_board_stock(stock_code)) or \
               (stock_info['总市值'] / 100000000 > MAX_MARKET_VALUE):
                continue
                
            # 获取涨停价
            up_stop_price = stock_info['涨停价']
                
            # 获取历史日线数据
            daily_data_dict = context.get_qmt_daily_data(
                stock_list=[stock_code], 
                period='1d', 
                count=NEW_HIGH_DAYS + 2,
                is_download=not batch_download_success
            )
            
            daily_data = daily_data_dict[stock_code]
            if daily_data.empty or len(daily_data) < 2:
                continue
                
            # 确保数据按日期升序排列
            daily_data = daily_data.sort_index()
            
            # 数据预处理：计算涨跌幅和前一天成交量
            daily_data['pre_close'] = daily_data['close'].shift(1)
            daily_data['pct_change'] = (daily_data['close'] - daily_data['pre_close']) / daily_data['pre_close']
            daily_data['vol_prev'] = daily_data['volume'].shift(1)
            
            # 获取最后一个交易日的数据（无论是否在交易时段）
            yesterday_data = daily_data.iloc[-1]
            yesterday_date = daily_data.index[-1]
            
            # 条件1：判断是否涨停
            # 优先使用涨停价判断，涨停价无效时使用涨幅判断
            is_limit_up = False
            if up_stop_price > 0 and False:
                is_limit_up = abs(yesterday_data['close'] - up_stop_price) < 0.01
            else:
                is_limit_up = yesterday_data['pct_change'] >= 0.095
                
            # 排除非涨停或一字板
            if not is_limit_up or (EXCLUDE_ONE_WORD_BOARD and is_one_word_board(yesterday_data)):
                continue
                
            # 条件2：近3个交易日内的首次涨停
            recent_end_idx = len(daily_data)
            recent_start_idx = max(0, recent_end_idx - FIRST_LIMIT_UP_DAYS)
            recent_data = daily_data.iloc[recent_start_idx:recent_end_idx]
            
            # 计算涨停次数 - 需要使用涨幅判断，因为涨停价是变化的
            # 最后一天已经是涨停了，所以初始计数为1
            limit_up_count = 1
            
            # 检查前面的日期是否也有涨停
            for i in range(recent_start_idx, recent_end_idx - 1):  # 不包括最后一天，因为已经知道最后一天涨停
                current_row = daily_data.iloc[i]
                # 使用涨幅判断涨停，一般认为9.5%以上就是涨停
                if current_row['pct_change'] >= 0.095:
                    limit_up_count += 1
            
            # 排除非首次涨停（即排除连续涨停的情况）
            if limit_up_count > 1:
                continue
                
            # 条件3：最后一个交易日收盘价是近30个交易日的最高价
            high_end_idx = len(daily_data)
            high_start_idx = max(0, high_end_idx - NEW_HIGH_DAYS)
            high_data = daily_data.iloc[high_start_idx:high_end_idx]
            
            if yesterday_data['close'] < high_data['close'].max():
                continue
                
            # 所有条件都满足，将股票添加到选股结果中
            selected_stocks.append(stock_code)
            logger.info(f"{GREEN}【选股结果】{RESET} 股票代码:{stock_code} 股票名称:{stock_name} 日期:{yesterday_date}")
                
        except Exception as e:
            logger.error(f"筛选股票 {stock_code} 时出错: {e}")
    
    logger.info(f"{GREEN}【选股完成】{RESET} 共筛选出 {len(selected_stocks)} 只符合条件的股票")
    return selected_stocks 