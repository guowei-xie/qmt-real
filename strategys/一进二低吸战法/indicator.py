#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MACDFS指标计算模块

用于计算分时MACD指标（MACDFS），专门用于一进二低吸战法的技术指标计算。
"""

import pandas as pd
import numpy as np


def calculate_ema_with_init(prices, period, init_value=None):
    """
    计算指数移动平均线(EMA)，支持自定义初始值
    
    Args:
        prices (pandas.Series): 价格序列数据
        period (int): EMA计算周期
        init_value (float, optional): EMA初始值，默认为None表示使用第一个价格
        
    Returns:
        pandas.Series: 计算得到的EMA序列
    """
    if len(prices) == 0:
        return pd.Series([])
    
    # 初始化EMA序列
    ema_values = np.zeros(len(prices))
    
    # 第一个值设为初始值或第一个价格
    ema_values[0] = init_value if init_value is not None else prices.iloc[0]
    
    # EMA计算参数
    multiplier = 2.0 / (period + 1)
    
    # 计算剩余的EMA值
    for i in range(1, len(prices)):
        ema_values[i] = (prices.iloc[i] - ema_values[i-1]) * multiplier + ema_values[i-1]
    
    return pd.Series(ema_values, index=prices.index)


def calculate_macdfs(prices, fast_period=12, slow_period=26, signal_period=9, open_price=None):
    """
    计算分时MACD指标(MACDFS)
    
    MACDFS与传统日线MACD的最大区别在于，它从当日开盘后的第一分钟就开始计算，
    而不需要等待足够的历史数据。开盘第一分钟的EMA初始值设为开盘价。
    
    Args:
        prices (pandas.Series): 价格序列数据（分钟级别收盘价）
        fast_period (int): 快线周期，默认为12
        slow_period (int): 慢线周期，默认为26
        signal_period (int): 信号线周期，默认为9
        open_price (float, optional): 开盘价，用于初始化EMA值，默认为None表示使用第一个价格
        
    Returns:
        pandas.DataFrame: 包含DIF、DEA和MACDFS三列的DataFrame
    """
    if len(prices) == 0:
        return pd.DataFrame(columns=['DIF', 'DEA', 'MACDFS'])
    
    # 如果未提供开盘价，使用第一个价格作为开盘价
    if open_price is None:
        open_price = prices.iloc[0]
    
    # 计算快线EMA，开盘第一分钟初始值设为开盘价
    fast_ema = calculate_ema_with_init(prices, fast_period, open_price)
    
    # 计算慢线EMA，开盘第一分钟初始值设为开盘价
    slow_ema = calculate_ema_with_init(prices, slow_period, open_price)
    
    # 计算DIF (MACD Line)
    dif = fast_ema - slow_ema
    
    # 计算DEA (MACD Signal Line)，第一个值初始化为0
    dea = calculate_ema_with_init(dif, signal_period, 0)
    
    # 计算MACDFS柱状线 (MACD Histogram)
    macdfs = 2 * (dif - dea)
    
    # 组合结果
    result = pd.DataFrame({
        'DIF': dif,
        'DEA': dea,
        'MACDFS': macdfs
    })
    
    return result


def is_green_bar_shrinking(macdfs_values):
    """
    判断MACDFS绿柱是否连续两根上缩
    
    Args:
        macdfs_values (list): 最近的MACDFS值列表，至少需要3个值
        
    Returns:
        bool: 如果绿柱连续两根上缩则返回True，否则返回False
    """
    if len(macdfs_values) < 3:
        return False
    
    # 获取最近的三个MACDFS值
    v1, v2, v3 = macdfs_values[-3], macdfs_values[-2], macdfs_values[-1]
    
    # 判断是否为绿柱（MACDFS值为负）
    if v1 >= 0 or v2 >= 0 or v3 >= 0:
        return False
    
    # 判断是否连续上缩（绝对值变小）
    if abs(v2) < abs(v1) and abs(v3) < abs(v2):
        return True
    
    return False


def is_red_bar_shrinking(macdfs_values):
    """
    判断MACDFS红柱是否连续两根下缩
    
    Args:
        macdfs_values (list): 最近的MACDFS值列表，至少需要3个值
        
    Returns:
        bool: 如果红柱连续两根下缩则返回True，否则返回False
    """
    if len(macdfs_values) < 3:
        return False
    
    # 获取最近的三个MACDFS值
    v1, v2, v3 = macdfs_values[-3], macdfs_values[-2], macdfs_values[-1]
    
    # 判断是否为红柱（MACDFS值为正）
    if v1 <= 0 or v2 <= 0 or v3 <= 0:
        return False
    
    # 判断是否连续下缩
    if v2 < v1 and v3 < v2:
        return True
    
    return False 