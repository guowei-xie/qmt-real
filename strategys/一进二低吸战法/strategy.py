#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
一进二低吸战法策略模块

实现一进二低吸战法的核心交易逻辑，包括：
1. 策略初始化
2. 股票池管理
3. 行情订阅
4. 买入信号判断
5. 卖出信号判断
6. 交易执行
7. 仓位风控管理
"""

import pandas as pd
import numpy as np
from datetime import datetime, time
import traceback
from collections import namedtuple

from trader.logger import logger
from trader.anis import RED, GREEN, YELLOW, BLUE, RESET
from trader.utils import is_trade_time, add_stock_suffix
from xtquant import xtdata

from strategys.一进二低吸战法.config import (
    BUY_AMOUNT, MAX_BUY_TIMES, MAX_INTRADAY_GAIN,
    MACDFS_SHORT, MACDFS_LONG, MACDFS_SIGNAL,
    STRATEGY_NAME, MAX_POSITION_RATIO, ENABLE_POSITION_CONTROL
)
from strategys.一进二低吸战法.indicator import (
    calculate_macdfs, is_green_bar_shrinking, is_red_bar_shrinking
)
from strategys.一进二低吸战法.stock_pool import filter_stock_pool

# 定义BarData数据结构
BarData = namedtuple('BarData', ['stock_code', 'time', 'open', 'high', 'low', 'close', 'volume', 'amount', 'pre_close'])


class YiJinErDiXiStrategy:
    """
    一进二低吸战法策略类
    
    实现一进二低吸战法的核心交易逻辑
    """
    
    def __init__(self, context, data_download_success=False):
        """
        初始化策略
        
        Args:
            context: QMT交易上下文对象
            data_download_success: 是否已成功下载A股历史数据
        """
        self.context = context
        # 不再直接导入xtdata模块，使用context提供的方法
        
        self.stock_pool = []  # 符合条件的股票池
        self.subscribed_stocks = []  # 已订阅行情的股票
        self.data_download_success = data_download_success  # 是否已成功下载A股历史数据
        self.last_minute = {}  # 记录每个股票最后处理的分钟时间
        
        # 交易记录
        self.stock_buy_times = {}  # 记录每只股票的买入次数，格式：{stock_code: count}
        self.stock_buy_prices = {}  # 记录每只股票当天的买入价格，格式：{stock_code: [price1, price2]}
        self.stock_sell_times = {}  # 记录每只股票的卖出次数，格式：{stock_code: count}
        
        # MACDFS计算用的价格缓存，格式：{stock_code: {date: [price1, price2, ...]}}
        self.price_cache = {}
        # MACDFS计算结果缓存，格式：{stock_code: {date: [macdfs1, macdfs2, ...]}}
        self.macdfs_cache = {}
        
        # 分时均价缓存，格式：{stock_code: {date: avg_price}}
        self.avg_price_cache = {}
        
        # 当日最高价缓存，格式：{stock_code: {date: high_price}}
        self.high_price_cache = {}
        
        # 涨停价缓存，格式：{stock_code: {date: limit_up_price}}
        self.limit_up_cache = {}
        
        # 是否为新的交易日
        self.current_date = datetime.now().strftime('%Y-%m-%d')
        
        logger.info(f"{GREEN}【策略初始化】{RESET} 一进二低吸战法策略初始化完成")
    
    def update_stock_pool(self):
        """
        更新股票池
        
        根据选股条件重新筛选股票池
        """
        try:
            # 筛选符合条件的股票
            self.stock_pool = filter_stock_pool(self.context, self.data_download_success)
            
            # 清空交易记录和缓存
            self._clear_cache()
            
            # 更新当前日期
            self.current_date = datetime.now().strftime('%Y-%m-%d')
            
            # 订阅股票行情
            self.subscribe_stock_quotes()
            
            logger.info(f"{GREEN}【股票池更新】{RESET} 共有 {len(self.stock_pool)} 只股票进入策略池")
            
        except Exception as e:
            logger.error(f"{RED}【股票池更新失败】{RESET} {e}")
            traceback.print_exc()
    
    def _clear_cache(self):
        """
        清空所有缓存和交易记录
        """
        self.stock_buy_times = {}
        self.stock_buy_prices = {}
        self.stock_sell_times = {}
        self.price_cache = {}
        self.macdfs_cache = {}
        self.avg_price_cache = {}
        self.high_price_cache = {}
        self.limit_up_cache = {}
    
    def subscribe_stock_quotes(self):
        """
        订阅股票行情
        
        订阅股票池中所有股票和已持仓股票的分钟级行情
        """
        try:
            # 取消之前的订阅
            if self.subscribed_stocks:
                # 遍历取消每个股票的订阅
                for stock in self.subscribed_stocks:
                    try:
                        # 使用context提供的方法取消订阅
                        self.context.unsubscribe_quote(stock)
                    except Exception as e:
                        logger.debug(f"{YELLOW}【取消订阅失败】{RESET} 股票:{stock} 错误:{e}")
                
                logger.debug(f"{BLUE}【取消订阅】{RESET} 已取消 {len(self.subscribed_stocks)} 只股票的行情订阅")
                self.subscribed_stocks = []
                self.last_minute = {}  # 清空最后处理时间记录
            
            # 获取持仓信息，将已持仓的股票也加入到订阅列表中
            position_stock_codes = []
            positions = self.context.get_positions()
            for position in positions:
                stock_code = position['证券代码']
                if stock_code not in self.stock_pool:
                    position_stock_codes.append(stock_code)
                    logger.debug(f"{GREEN}【持仓股票】{RESET} 股票:{stock_code} 持仓数量:{position['持仓数量']}")
            
            # 合并策略池和持仓股票
            subscribe_stocks = list(set(self.stock_pool + position_stock_codes))
            
            # 订阅股票行情
            if subscribe_stocks:
                # 定义行情回调函数
                def quote_callback(quote_data):
                    try:
                        if not quote_data:
                            return
                            
                        # 获取股票代码和K线数据
                        stock_code = list(quote_data.keys())[0]  # 单股订阅只有一个股票
                        bar_list = quote_data[stock_code]
                        
                        if not bar_list:  # 跳过空数据
                            return
                            
                        # 获取最新的K线数据
                        bar_data = bar_list[-1]
                        
                        # 转换时间戳为datetime对象
                        current_time = pd.to_datetime(bar_data['time'], unit='ms')
                        
                        # 获取当前分钟时间（去掉秒和微秒）
                        current_minute = current_time.replace(second=0, microsecond=0)
                        
                        # 如果是新的分钟，且该股票之前没有处理过这个分钟的数据
                        if stock_code not in self.last_minute or self.last_minute[stock_code] < current_minute:
                            self.last_minute[stock_code] = current_minute
                            
                            # 创建BarData对象并调用on_bar
                            bar_obj = BarData(
                                stock_code=stock_code,
                                time=current_time,
                                open=bar_data['open'],
                                high=bar_data['high'],
                                low=bar_data['low'],
                                close=bar_data['close'],
                                volume=bar_data['volume'],
                                amount=bar_data['amount'],
                                pre_close=bar_data.get('preClose', 0)  # 添加pre_close字段，可能在某些情况下需要
                            )
                            
                            # 调用on_bar处理K线数据
                            self.on_bar(bar_obj)
                        
                    except Exception as e:
                        logger.error(f"{RED}【行情处理错误】{RESET} 错误:{e}")
                        traceback.print_exc()
                
                # 遍历订阅每个股票的行情
                for stock in subscribe_stocks:
                    try:
                        # 使用context提供的方法订阅行情
                        self.context.subscribe_quote(stock, period='1m', callback=quote_callback)
                        logger.debug(f"{GREEN}【订阅成功】{RESET} 股票:{stock}")
                        self.subscribed_stocks.append(stock)
                    except Exception as e:
                        logger.error(f"{RED}【订阅失败】{RESET} 股票:{stock} 错误:{e}")
                
                logger.info(f"{GREEN}【行情订阅】{RESET} 已订阅 {len(self.subscribed_stocks)} 只股票的行情，包含策略池股票 {len(self.stock_pool)} 只，持仓非策略池股票 {len(position_stock_codes)} 只")
        except Exception as e:
            logger.error(f"{RED}【行情订阅错误】{RESET} 错误:{e}")
            traceback.print_exc()
    
    def on_bar(self, bar_data):
        """
        K线数据回调函数
        
        当收到分钟K线数据时调用，用于策略信号判断和交易执行
        
        Args:
            bar_data: K线数据
        """
        try:
            # 检查是否交易时间
            if not is_trade_time():
                return
                
            # 检查是否新的一天
            current_date = datetime.now().strftime('%Y-%m-%d')
            if current_date != self.current_date:
                logger.info(f"{GREEN}【新交易日】{RESET} 清空交易记录和缓存")
                # 清空交易记录和缓存
                self._clear_cache()
                self.current_date = current_date
            
            # 获取股票代码和时间
            stock_code = bar_data.stock_code
            bar_time = bar_data.time
            
            # 检查是否持有该股票
            position = self.context.get_position(stock_code)
            has_position = position and position['持仓数量'] > 0
            
            # 如果不在股票池中且没有持仓，则跳过处理
            if stock_code not in self.stock_pool and not has_position:
                return
                
            # 更新价格缓存
            self.update_price_cache(stock_code, bar_data)
            
            # 计算MACDFS指标
            self.calculate_stock_macdfs(stock_code)
            
            # 更新分时均价缓存
            self.update_avg_price_cache(stock_code, bar_data)
            
            # 更新当日最高价缓存
            self.update_high_price_cache(stock_code, bar_data)
            
            # 更新涨停价缓存
            self.update_limit_up_cache(stock_code)
            
            # 判断是否为开盘第一分钟
            is_first_minute = bar_time.hour == 9 and bar_time.minute == 31
            
            # 处理持仓股票的卖出信号
            if has_position:
                # 开盘第一分钟判断次日开盘卖出条件
                if is_first_minute:
                    self.check_next_day_open_sell_signal(stock_code, bar_data)
                
                # 检查是否涨停开板
                self.check_limit_up_break_sell_signal(stock_code, bar_data)
                
                # 检查卖出信号
                self.check_sell_signal(stock_code)
            
            # 处理股票池中的买入信号
            if stock_code in self.stock_pool and not has_position:
                self.check_buy_signal(stock_code, bar_data)
            
        except Exception as e:
            logger.error(f"{RED}【行情处理异常】{RESET} 股票:{stock_code} 错误:{e}")
            traceback.print_exc()
    
    def update_price_cache(self, stock_code, bar_data):
        """
        更新价格缓存
        
        将最新的分钟K线价格添加到缓存中
        
        Args:
            stock_code: 股票代码
            bar_data: K线数据
        """
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        # 初始化价格缓存
        self._ensure_cache_initialized(self.price_cache, stock_code, current_date, default=[])
        
        # 添加价格到缓存
        self.price_cache[stock_code][current_date].append(bar_data.close)
    
    def update_avg_price_cache(self, stock_code, bar_data):
        """
        更新分时均价缓存
        
        计算并缓存当前的分时均价
        
        Args:
            stock_code: 股票代码
            bar_data: K线数据
        """
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        # 初始化分时均价缓存
        self._ensure_cache_initialized(self.avg_price_cache, stock_code)
        
        # 计算分时均价 = 当日累计成交金额 ÷ 当日累计成交股数
        avg_price = bar_data.amount / bar_data.volume if bar_data.volume > 0 else 0
        
        # 缓存分时均价
        self.avg_price_cache[stock_code][current_date] = avg_price
    
    def update_high_price_cache(self, stock_code, bar_data):
        """
        更新当日最高价缓存
        
        记录当日的最高价格
        
        Args:
            stock_code: 股票代码
            bar_data: K线数据
        """
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        # 初始化最高价缓存
        self._ensure_cache_initialized(self.high_price_cache, stock_code)
        
        # 获取当前缓存的最高价
        current_high = self.high_price_cache[stock_code].get(current_date, 0)
        
        # 更新最高价
        if bar_data.high > current_high:
            self.high_price_cache[stock_code][current_date] = bar_data.high
    
    def update_limit_up_cache(self, stock_code):
        """
        更新涨停价缓存
        
        每只股票每天只获取一次涨停价信息并缓存
        
        Args:
            stock_code: 股票代码
        """
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        # 初始化涨停价缓存
        self._ensure_cache_initialized(self.limit_up_cache, stock_code)
        
        # 如果当日涨停价未缓存，则获取并缓存
        if current_date not in self.limit_up_cache[stock_code]:
            # 获取股票信息，包括涨停价
            stock_info = self.context.get_stock_info(stock_code)
            limit_up_price = stock_info['涨停价']
            
            # 缓存涨停价
            self.limit_up_cache[stock_code][current_date] = limit_up_price
            logger.debug(f"{BLUE}【涨停价缓存】{RESET} 股票:{stock_code} 涨停价:{limit_up_price:.2f}")
    
    def calculate_stock_macdfs(self, stock_code):
        """
        计算股票的MACDFS指标
        
        使用价格缓存计算MACDFS指标，确保每个交易日的MACDFS计算相对独立，
        从零轴开始计算，与行情软件保持一致。
        
        Args:
            stock_code: 股票代码
        """
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        # 初始化MACDFS缓存
        self._ensure_cache_initialized(self.macdfs_cache, stock_code, current_date, default=[])
        
        # 获取价格数据
        prices = self.price_cache[stock_code].get(current_date, [])
        
        if len(prices) >= 1:  # 至少需要1个价格点
            # 使用第一个价格作为开盘价
            open_price = prices[0]
            
            # 计算MACDFS，传递开盘价以便正确初始化
            prices_series = pd.Series(prices)
            macdfs_df = calculate_macdfs(
                prices_series, 
                fast_period=MACDFS_SHORT,
                slow_period=MACDFS_LONG,
                signal_period=MACDFS_SIGNAL,
                open_price=open_price  # 传递开盘价
            )
            
            # 缓存MACDFS值
            self.macdfs_cache[stock_code][current_date] = macdfs_df['MACDFS'].tolist()
    
    def check_buy_signal(self, stock_code, bar_data):
        """
        检查买入信号
        
        检查是否满足买入条件：
        1. MACDFS绿柱连续两根上缩
        2. 日内涨幅不超过9%
        3. 当前价格大于分时均价
        4. 价格保护机制
        5. 仓位管理机制
        
        Args:
            stock_code: 股票代码
            bar_data: K线数据
        """
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        # 检查买入次数是否已达上限
        buy_times = self.stock_buy_times.get(stock_code, 0)
        if buy_times >= MAX_BUY_TIMES:
            logger.debug(f"{BLUE}【买入次数已满】{RESET} 股票:{stock_code} 当前买入次数:{buy_times} 最大买入次数:{MAX_BUY_TIMES}")
            return
        
        # 获取MACDFS值
        macdfs_values = self.macdfs_cache[stock_code].get(current_date, [])
        
        # 检查MACDFS绿柱是否连续两根上缩
        if len(macdfs_values) < 3 or not is_green_bar_shrinking(macdfs_values):
            return
            
        logger.debug(f"{BLUE}【MACDFS绿柱上缩】{RESET} 股票:{stock_code} MACDFS值:{macdfs_values[-3:]}")
        
        # 获取当日最高价
        high_price = self.high_price_cache[stock_code].get(current_date, 0)
        
        # 检查当日涨幅是否超过限制
        prev_close = bar_data.pre_close
        intraday_gain = (high_price - prev_close) / prev_close if prev_close > 0 else 0
        if intraday_gain > MAX_INTRADAY_GAIN:
            logger.debug(f"{BLUE}【涨幅超限】{RESET} 股票:{stock_code} 日内最高涨幅:{intraday_gain:.2%} 超过{MAX_INTRADAY_GAIN:.2%}")
            return
        
        # 获取分时均价
        avg_price = self.avg_price_cache[stock_code].get(current_date, 0)
        
        # 检查当前价格是否大于分时均价
        current_price = bar_data.close
        if current_price <= avg_price:
            logger.debug(f"{BLUE}【价格低于均价】{RESET} 股票:{stock_code} 当前价格:{current_price:.2f} 分时均价:{avg_price:.2f}")
            return
            
        logger.debug(f"{BLUE}【价格高于均价】{RESET} 股票:{stock_code} 当前价格:{current_price:.2f} 分时均价:{avg_price:.2f}")
        
        # 价格保护机制：当天已有成交的情况下，新买入价格不能低于上一次买入价格
        if buy_times > 0:
            last_buy_price = self.stock_buy_prices[stock_code][-1]
            if current_price < last_buy_price:
                logger.debug(f"{BLUE}【价格保护】{RESET} 股票:{stock_code} 当前价格:{current_price:.2f} 上次买入价格:{last_buy_price:.2f}")
                return
            
            logger.debug(f"{BLUE}【价格保护通过】{RESET} 股票:{stock_code} 当前价格:{current_price:.2f} 上次买入价格:{last_buy_price:.2f}")
        
        # 执行买入
        self.execute_buy(stock_code, current_price)
    
    def check_sell_signal(self, stock_code):
        """
        检查卖出信号
        
        检查是否满足MACDFS指标卖出条件：
        当MACDFS红柱连续下缩2根时触发卖出
        
        Args:
            stock_code: 股票代码
        """
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        # 获取MACDFS值
        macdfs_values = self.macdfs_cache[stock_code].get(current_date, [])
        
        # 检查MACDFS红柱是否连续两根下缩
        if len(macdfs_values) < 3 or not is_red_bar_shrinking(macdfs_values):
            return
            
        # 获取最新价格
        latest_price = self.context.get_latest_price(stock_code)
        
        # 确保涨停价已缓存
        self.update_limit_up_cache(stock_code)
        limit_up_price = self.limit_up_cache[stock_code][current_date]
        
        # 判断是否涨停
        is_limit_up = (latest_price >= limit_up_price)
        
        # 涨停时不卖出
        if is_limit_up:
            logger.debug(f"{BLUE}【涨停不卖】{RESET} 股票:{stock_code} 当前价格:{latest_price:.2f} 涨停价:{limit_up_price:.2f}")
            return
            
        # 获取卖出次数
        sell_times = self.stock_sell_times.get(stock_code, 0)
        
        # 执行卖出
        if sell_times == 0:
            # 第一次触发，卖出1/2仓位
            self.execute_sell(stock_code, latest_price, 0.5)
        else:
            # 第二次及以后触发，卖出全部剩余仓位
            self.execute_sell(stock_code, latest_price, 1.0)
    
    def check_next_day_open_sell_signal(self, stock_code, bar_data):
        """
        检查次日开盘卖出条件
        
        如果次日开盘价低于昨日收盘价且第1分钟K线收阴，则清仓
        
        Args:
            stock_code: 股票代码
            bar_data: K线数据
        """
        # 获取昨日收盘价
        prev_close = bar_data.pre_close
        
        # 获取开盘价和第一分钟收盘价
        open_price = bar_data.open
        close_price = bar_data.close
        
        # 检查条件：开盘价低于昨日收盘价且第一分钟K线收阴
        if open_price < prev_close and close_price < open_price:
            logger.info(f"{YELLOW}【次日开盘卖出】{RESET} 股票:{stock_code} 开盘价:{open_price:.2f} 昨收价:{prev_close:.2f} 一分钟收阴")
            
            # 执行清仓
            self.execute_sell(stock_code, close_price, 1.0)
    
    def check_limit_up_break_sell_signal(self, stock_code, bar_data):
        """
        检查涨停开板卖出条件
        
        如果上一分钟为涨停，但当前已低于涨停价（即开板），则立即全仓卖出
        无论是开盘就涨停后开板，还是盘中涨停后开板，都会触发卖出信号
        
        Args:
            stock_code: 股票代码
            bar_data: K线数据
        """
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        # 获取价格缓存
        prices = self.price_cache[stock_code].get(current_date, [])
        if len(prices) < 2:
            return
            
        # 获取前一分钟价格和当前价格
        prev_price = prices[-2]
        current_price = prices[-1]
        
        # 从缓存获取涨停价
        limit_up_price = self.limit_up_cache[stock_code][current_date]
        
        # 判断前一分钟是否涨停
        is_prev_limit_up = (prev_price >= limit_up_price)
        
        # 判断当前价格是否低于涨停价（开板）
        is_break_limit_up = (current_price < limit_up_price)
        
        # 检查条件：前一分钟涨停且当前价格低于涨停价（即开板）
        if is_prev_limit_up and is_break_limit_up:
            logger.info(f"{YELLOW}【涨停开板卖出】{RESET} 股票:{stock_code} 前一分钟价格:{prev_price:.2f} 当前价格:{current_price:.2f} 涨停价:{limit_up_price:.2f}")
            
            # 执行清仓，使用限价委托
            self.execute_sell(stock_code, current_price, 1.0, use_limit_price=True)
    
    def execute_buy(self, stock_code, price):
        """
        执行买入操作
        
        Args:
            stock_code: 股票代码
            price: 参考价格，实际使用市价委托
        """
        try:
            # 检查可用资金
            asset = self.context.get_asset()
            available_cash = asset['可用金额']
            total_asset = asset['总资产']
            
            if available_cash < BUY_AMOUNT:
                logger.warning(f"{YELLOW}【资金不足】{RESET} 可用资金:{available_cash:.2f} 小于买入金额:{BUY_AMOUNT:.2f}")
                return False
            
            # 检查整体仓位是否已达到最大限制
            if ENABLE_POSITION_CONTROL:
                # 计算当前总持仓市值
                positions = self.context.get_positions()
                total_position_value = sum([p['最新市值'] for p in positions]) if positions else 0
                
                # 计算当前仓位比例
                current_position_ratio = total_position_value / total_asset if total_asset > 0 else 0
                
                # 预估本次买入后的仓位比例
                estimated_new_position_ratio = (total_position_value + BUY_AMOUNT) / total_asset if total_asset > 0 else 0
                
                # 如果预估仓位超过设定的最大仓位比例，则不执行买入
                if estimated_new_position_ratio > MAX_POSITION_RATIO:
                    logger.warning(f"{YELLOW}【仓位超限】{RESET} 股票:{stock_code} 当前仓位比例:{current_position_ratio:.2%} 本次买入后预估仓位比例:{estimated_new_position_ratio:.2%} 超过最大限制:{MAX_POSITION_RATIO:.2%}")
                    return False
                
                logger.debug(f"{BLUE}【仓位检查】{RESET} 股票:{stock_code} 当前仓位比例:{current_position_ratio:.2%} 买入后预估仓位比例:{estimated_new_position_ratio:.2%} 最大限制:{MAX_POSITION_RATIO:.2%}")
                
            # 获取股票名称
            stock_name = self.context.get_security_name(stock_code)
            
            # 记录买入次数
            if stock_code not in self.stock_buy_times:
                self.stock_buy_times[stock_code] = 0
                self.stock_buy_prices[stock_code] = []
                
            self.stock_buy_times[stock_code] += 1
            self.stock_buy_prices[stock_code].append(price)
            
            # 记录买入备注
            buy_times = self.stock_buy_times[stock_code]
            remark = f"{STRATEGY_NAME}-买入{buy_times}"
            
            # 执行买入，使用市价委托（价格参数设为0）
            order_result = self.context.order_value(
                security=stock_code,
                value=BUY_AMOUNT,
                price=0,  # 使用0表示市价委托
                strategy_name=STRATEGY_NAME,
                remark=remark
            )
            
            if order_result and order_result.get('订单编号'):
                logger.info(f"{GREEN}【买入信号】{RESET} 股票:{stock_code} 名称:{stock_name} 参考价格:{price:.2f} 金额:{BUY_AMOUNT:.2f} 次数:{buy_times} 委托方式:市价 订单编号:{order_result.get('订单编号')}")
                return True
            else:
                logger.warning(f"{YELLOW}【买入失败】{RESET} 股票:{stock_code} 名称:{stock_name} 参考价格:{price:.2f} 金额:{BUY_AMOUNT:.2f} 委托方式:市价 返回结果:{order_result}")
                return False
            
        except Exception as e:
            logger.error(f"{RED}【买入失败】{RESET} 股票:{stock_code} 错误:{e}")
            traceback.print_exc()
            return False
    
    def execute_sell(self, stock_code, price, ratio=1.0, use_limit_price=False):
        """
        执行卖出操作
        
        Args:
            stock_code: 股票代码
            price: 参考价格，实际使用市价委托
            ratio: 卖出比例，默认为1.0（全部卖出）
            use_limit_price: 是否使用限价委托，默认为False表示使用市价委托
            
        Returns:
            bool: 卖出是否成功
        """
        try:
            # 检查持仓
            position = self.context.get_position(stock_code)
            if not position or position['可用数量'] <= 0:
                logger.debug(f"{BLUE}【无可用持仓】{RESET} 股票:{stock_code}")
                return False
                
            # 计算卖出数量
            available_shares = position['可用数量']
            sell_shares = int(available_shares * ratio)
            
            if sell_shares <= 0:
                logger.debug(f"{BLUE}【卖出数量为0】{RESET} 股票:{stock_code} 可用数量:{available_shares} 比例:{ratio:.2%}")
                return False
                
            # 获取股票名称
            stock_name = self.context.get_security_name(stock_code)
            
            # 记录卖出次数
            if stock_code not in self.stock_sell_times:
                self.stock_sell_times[stock_code] = 0
                
            self.stock_sell_times[stock_code] += 1
            
            # 记录卖出备注
            sell_times = self.stock_sell_times[stock_code]
            remark = f"{STRATEGY_NAME}-卖出{sell_times}"
            
            # 根据参数决定是使用限价委托还是市价委托
            if use_limit_price:
                # 使用限价委托，设置为当前价格略低一点（降低0.2%），提高成交概率
                # 炸板时通常股价会快速下跌，设置稍低的价格有助于成交
                limit_price = price * 0.99  # 当前价格的99%
                price_type = "限价"
            else:
                # 使用市价委托
                limit_price = 0
                price_type = "市价"
            
            # 执行卖出
            order_result = self.context.order(
                security=stock_code,
                amount=-sell_shares,
                price=limit_price,
                strategy_name=STRATEGY_NAME,
                remark=remark
            )
            
            if order_result and order_result.get('订单编号'):
                logger.info(f"{YELLOW}【卖出信号】{RESET} 股票:{stock_code} 名称:{stock_name} 参考价格:{price:.2f} 委托价格:{limit_price if limit_price > 0 else '市价'} 数量:{sell_shares} 比例:{ratio:.2%} 次数:{sell_times} 委托方式:{price_type} 订单编号:{order_result.get('订单编号')}")
                return True
            else:
                logger.warning(f"{YELLOW}【卖出失败】{RESET} 股票:{stock_code} 名称:{stock_name} 参考价格:{price:.2f} 委托价格:{limit_price if limit_price > 0 else '市价'} 数量:{sell_shares} 委托方式:{price_type} 返回结果:{order_result}")
                return False
            
        except Exception as e:
            logger.error(f"{RED}【卖出失败】{RESET} 股票:{stock_code} 错误:{e}")
            traceback.print_exc()
            return False
    
    def _ensure_cache_initialized(self, cache_dict, stock_code, date=None, default=None):
        """
        确保缓存已初始化
        
        Args:
            cache_dict: 缓存字典
            stock_code: 股票代码
            date: 日期，默认为None
            default: 默认值，默认为None
        """
        if stock_code not in cache_dict:
            cache_dict[stock_code] = {}
        
        if date is not None and date not in cache_dict[stock_code]:
            if default is None:
                default = {}
            cache_dict[stock_code][date] = default if not isinstance(default, list) else [] 