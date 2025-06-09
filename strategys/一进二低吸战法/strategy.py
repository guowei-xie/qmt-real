# -*- coding: utf-8 -*-
"""
一进二低吸战法策略模块

该模块实现了一进二低吸战法量化交易策略的核心功能，包括：
1. 股票选择条件 - 筛选符合条件的交易标的
2. MACDFS指标计算 - 基于分时数据计算特殊的MACD指标
3. 买入条件判断 - 根据MACDFS绿柱上缩等条件判断买入时机
4. 卖出条件判断 - 根据MACDFS红柱下缩等条件判断卖出时机

该策略主要针对涨停后的低吸机会，通过MACD指标的变化来捕捉买入和卖出时机。
"""

import os
import configparser
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from trader.logger import logger
from trader.anis import RED, GREEN, YELLOW, BLUE, RESET
from trader.utils import add_stock_suffix, remove_stock_suffix

# 读取配置文件
config = configparser.ConfigParser()
config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')
config.read(config_path, encoding='utf-8')

# 策略参数
MAIN_BOARD = config.getint('selection', 'main_board')
EXCLUDE_ST = config.getint('selection', 'exclude_st')
MAX_MARKET_CAP = config.getfloat('selection', 'max_market_cap')
RECENT_DAYS = config.getint('selection', 'recent_days')
NEW_HIGH_DAYS = config.getint('selection', 'new_high_days')

BUY_AMOUNT = config.getfloat('trading', 'buy_amount')
MAX_BUY_TIMES = config.getint('trading', 'max_buy_times')
MAX_INTRADAY_GAIN = config.getfloat('trading', 'max_intraday_gain')

SHORT_PERIOD = config.getint('indicator', 'short_period')
LONG_PERIOD = config.getint('indicator', 'long_period')
SIGNAL_PERIOD = config.getint('indicator', 'signal_period')


class StockSelector:
    """
    股票选择器类
    
    根据策略条件筛选符合要求的股票，主要筛选条件包括：
    1. 昨天涨停的股票（排除一字板）
    2. 近期首次涨停
    3. 价格创新高
    4. 基本面限制（主板、非ST、市值上限）
    """
    
    def __init__(self, context):
        """
        初始化股票选择器
        
        参数:
            context: 交易上下文对象
        """
        self.context = context
        self.selected_stocks = []
    
    def select_stocks(self):
        """
        选择符合条件的股票
        
        返回:
            list: 符合条件的股票代码列表
        """
        # 获取A股股票列表
        stock_list = self.get_a_stocks()
        
        # 筛选符合条件的股票
        selected_stocks = []
        for stock in stock_list:
            if self.check_stock_condition(stock):
                selected_stocks.append(stock)
        
        self.selected_stocks = selected_stocks
        logger.info(f"{GREEN}【选股结果】{RESET} 符合条件的股票数量: {len(selected_stocks)}")
        return selected_stocks
    
    def get_a_stocks(self):
        """
        获取A股股票列表
        
        返回:
            list: A股股票代码列表
        """
        # 使用QMT接口获取A股股票列表
        stock_list = self.context.get_stock_list_in_sector('沪深A股')
        return stock_list
    
    def check_stock_condition(self, stock):
        """
        检查股票是否符合选股条件
        
        参数:
            stock (str): 股票代码
            
        返回:
            bool: 是否符合条件
        """
        try:
            # 获取股票基本信息
            stock_info = self.context.get_stock_info(stock)
            if stock_info is None:
                return False
            
            # 检查是否为主板股票
            if MAIN_BOARD and not (stock.startswith('00') or stock.startswith('60')):
                return False
            
            # 检查是否为ST股票
            if EXCLUDE_ST and ('ST' in stock_info['股票名称'] or '*' in stock_info['股票名称']):
                return False
            
            # 检查是否停牌
            if stock_info['停牌状态'] == 1:
                return False
            
            # 检查市值上限
            if stock_info['总市值'] > MAX_MARKET_CAP * 100000000:  # 转换为亿元
                return False
            
            # 获取历史数据
            df = self.context.custom_data.get_qmt_daily_data(
                stock_list=[stock], 
                period='1d', 
                count=NEW_HIGH_DAYS + 1,
                is_download = True
            )
            
            if df.empty:
                return False
            
            # 检查昨天是否涨停
            yesterday_data = df.iloc[1]  # 索引0是今天的数据，索引1是昨天的数据
            if not self.is_limit_up(yesterday_data):
                return False
            
            # 检查是否为一字板
            if yesterday_data['open'] == yesterday_data['close'] or yesterday_data['volume'] < yesterday_data['volume'].mean() * 0.3:
                return False
            
            # 检查是否为近期首次涨停
            recent_data = df.iloc[1:RECENT_DAYS+1]  # 最近N天的数据（不包括今天）
            limit_up_days = [self.is_limit_up(day) for _, day in recent_data.iterrows()]
            if sum(limit_up_days) > 1 or limit_up_days[0] == False:
                return False
            
            # 检查昨天收盘价是否为近期新高
            price_data = df.iloc[1:NEW_HIGH_DAYS+1]  # 最近N天的数据（不包括今天）
            if yesterday_data['close'] < price_data['close'].max():
                return False
            
            return True
        
        except Exception as e:
            logger.error(f"{RED}【选股错误】{RESET} {stock}: {e}")
            return False
    
    def is_limit_up(self, day_data):
        """
        判断是否涨停
        
        参数:
            day_data (Series): 日线数据
            
        返回:
            bool: 是否涨停
        """
        # 涨停幅度通常为10%，科创板、创业板为20%
        limit_pct = 0.1
        if day_data.name.startswith('68') or day_data.name.startswith('30'):
            limit_pct = 0.2
        
        # 计算涨幅
        prev_close = day_data['pre_close']
        current_close = day_data['close']
        pct_change = (current_close - prev_close) / prev_close
        
        # 判断是否涨停（允许有0.2%的误差）
        return pct_change >= limit_pct - 0.002


class MAFSIndicator:
    """
    MACDFS指标计算类
    
    计算基于分时数据的MACD指标（MACDFS），特点是：
    1. 从当日开盘后第一分钟就开始计算
    2. 开盘第一分钟的EMA初始值设为开盘价
    3. 每个交易日的计算相对独立
    """
    
    def __init__(self, short_period=SHORT_PERIOD, long_period=LONG_PERIOD, signal_period=SIGNAL_PERIOD):
        """
        初始化MACDFS指标计算器
        
        参数:
            short_period (int): 短期EMA周期，默认为12
            long_period (int): 长期EMA周期，默认为26
            signal_period (int): 信号线EMA周期，默认为9
        """
        self.short_period = short_period
        self.long_period = long_period
        self.signal_period = signal_period
        
        # 当日数据缓存
        self.today_data = {}
    
    def calculate(self, stock, minute_data):
        """
        计算MACDFS指标
        
        参数:
            stock (str): 股票代码
            minute_data (DataFrame): 分钟级别的行情数据
            
        返回:
            DataFrame: 包含MACDFS指标的DataFrame
        """
        if minute_data.empty:
            return pd.DataFrame()
        
        # 确保数据按时间排序
        df = minute_data.sort_index()
        
        # 获取当前交易日
        current_date = df.index[0].strftime('%Y-%m-%d')
        
        # 如果是新的交易日，重置缓存
        if stock not in self.today_data or self.today_data[stock]['date'] != current_date:
            # 初始化EMA值为开盘价
            open_price = df.iloc[0]['open']
            self.today_data[stock] = {
                'date': current_date,
                'short_ema': open_price,
                'long_ema': open_price,
                'dif': 0,
                'dea': 0,
                'macd': 0,
                'history': []
            }
        
        # 计算MACDFS指标
        result = []
        for idx, row in df.iterrows():
            price = row['close']
            
            # 计算EMA
            short_ema = self._calculate_ema(price, self.today_data[stock]['short_ema'], self.short_period)
            long_ema = self._calculate_ema(price, self.today_data[stock]['long_ema'], self.long_period)
            
            # 计算DIF
            dif = short_ema - long_ema
            
            # 计算DEA
            dea = self._calculate_ema(dif, self.today_data[stock]['dea'], self.signal_period)
            
            # 计算MACD
            macd = 2 * (dif - dea)
            
            # 更新缓存
            self.today_data[stock]['short_ema'] = short_ema
            self.today_data[stock]['long_ema'] = long_ema
            self.today_data[stock]['dif'] = dif
            self.today_data[stock]['dea'] = dea
            self.today_data[stock]['macd'] = macd
            
            # 添加到结果
            result.append({
                'time': idx,
                'price': price,
                'short_ema': short_ema,
                'long_ema': long_ema,
                'dif': dif,
                'dea': dea,
                'macd': macd
            })
            
            # 添加到历史记录
            self.today_data[stock]['history'].append({
                'time': idx,
                'price': price,
                'macd': macd
            })
        
        return pd.DataFrame(result)
    
    def _calculate_ema(self, current, previous, period):
        """
        计算EMA值
        
        参数:
            current (float): 当前价格
            previous (float): 前一个EMA值
            period (int): EMA周期
            
        返回:
            float: 计算得到的EMA值
        """
        alpha = 2 / (period + 1)
        return current * alpha + previous * (1 - alpha)
    
    def is_green_bar_shrinking(self, stock, count=2):
        """
        判断MACDFS绿柱是否连续上缩
        
        参数:
            stock (str): 股票代码
            count (int): 连续上缩的根数，默认为2
            
        返回:
            bool: 是否连续上缩
        """
        if stock not in self.today_data or len(self.today_data[stock]['history']) < count + 1:
            return False
        
        # 获取最近的MACD值
        recent_macd = [item['macd'] for item in self.today_data[stock]['history'][-count-1:]]
        
        # 判断是否为绿柱
        if recent_macd[-1] >= 0:
            return False
        
        # 判断是否连续上缩（绿柱变短）
        for i in range(1, count + 1):
            if recent_macd[-i] <= recent_macd[-i-1]:
                return False
        
        return True
    
    def is_red_bar_shrinking(self, stock, count=2):
        """
        判断MACDFS红柱是否连续下缩
        
        参数:
            stock (str): 股票代码
            count (int): 连续下缩的根数，默认为2
            
        返回:
            bool: 是否连续下缩
        """
        if stock not in self.today_data or len(self.today_data[stock]['history']) < count + 1:
            return False
        
        # 获取最近的MACD值
        recent_macd = [item['macd'] for item in self.today_data[stock]['history'][-count-1:]]
        
        # 判断是否为红柱
        if recent_macd[-1] <= 0:
            return False
        
        # 判断是否连续下缩（红柱变短）
        for i in range(1, count + 1):
            if recent_macd[-i] >= recent_macd[-i-1]:
                return False
        
        return True


class TradingStrategy:
    """
    交易策略类
    
    实现一进二低吸战法的买入和卖出逻辑，包括：
    1. 买入条件判断 - MACDFS绿柱上缩、价格高于分时均价等
    2. 卖出条件判断 - MACDFS红柱下缩、次日开盘条件等
    3. 交易记录管理 - 记录每只股票的买入次数和买入价格
    """
    
    def __init__(self, context):
        """
        初始化交易策略
        
        参数:
            context: 交易上下文对象
        """
        self.context = context
        self.macd_indicator = MAFSIndicator()
        self.stock_selector = StockSelector(context)
        
        # 交易记录
        self.trade_records = {}
        
        # 初始化选股
        self.selected_stocks = []
    
    def initialize(self):
        """
        初始化策略，选择符合条件的股票
        """
        self.selected_stocks = self.stock_selector.select_stocks()
        logger.info(f"{GREEN}【策略初始化】{RESET} 选股完成，共选出 {len(self.selected_stocks)} 只股票")
    
    def process_minute_data(self, stock, minute_data):
        """
        处理分钟数据，计算指标并判断买卖条件
        
        参数:
            stock (str): 股票代码
            minute_data (DataFrame): 分钟级别的行情数据
            
        返回:
            dict: 交易信号，包含买入或卖出信号
        """
        # 计算MACDFS指标
        macd_data = self.macd_indicator.calculate(stock, minute_data)
        if macd_data.empty:
            return {'signal': 'none'}
        
        # 获取当前持仓
        position = self.context.get_position(stock)
        
        # 如果有持仓，判断卖出条件
        if position is not None and position['持仓数量'] > 0:
            return self.check_sell_condition(stock, minute_data, macd_data)
        
        # 如果是选中的股票，判断买入条件
        if stock in self.selected_stocks:
            return self.check_buy_condition(stock, minute_data, macd_data)
        
        return {'signal': 'none'}
    
    def check_buy_condition(self, stock, minute_data, macd_data):
        """
        检查买入条件
        
        参数:
            stock (str): 股票代码
            minute_data (DataFrame): 分钟级别的行情数据
            macd_data (DataFrame): MACDFS指标数据
            
        返回:
            dict: 买入信号
        """
        # 初始化交易记录
        if stock not in self.trade_records:
            self.trade_records[stock] = {
                'buy_times': 0,
                'buy_prices': []
            }
        
        # 检查买入次数是否达到上限
        if self.trade_records[stock]['buy_times'] >= MAX_BUY_TIMES:
            return {'signal': 'none'}
        
        # 检查股票是否在昨日已持仓
        # 获取持仓情况
        position = self.context.get_position(stock)
        if position is not None and position['持仓数量'] > 0:
            # 检查可用数量是否等于持仓数量
            # 如果可用数量小于持仓数量，说明有部分股票是今日买入的（T+1交易规则导致不可卖出）
            # 如果可用数量等于持仓数量，说明是昨日或更早买入的，不允许再次买入
            if position['可用数量'] == position['持仓数量']:
                logger.info(f"{YELLOW}【买入限制】{RESET} {stock} 为昨日或更早持仓，不允许买入")
                return {'signal': 'none'}
        
        # 检查MACDFS绿柱是否连续上缩
        if not self.macd_indicator.is_green_bar_shrinking(stock):
            return {'signal': 'none'}
        
        # 获取当前价格和最高价
        current_price = minute_data.iloc[-1]['close']
        high_price = minute_data['high'].max()
        open_price = minute_data.iloc[0]['open']
        
        # 检查日内涨幅是否超过限制
        if (high_price - open_price) / open_price > MAX_INTRADAY_GAIN / 100:
            return {'signal': 'none'}
        
        # 计算分时均价
        amount = (minute_data['close'] * minute_data['volume']).sum()
        volume = minute_data['volume'].sum()
        avg_price = amount / volume if volume > 0 else 0
        
        # 检查当前价格是否高于分时均价
        if current_price <= avg_price:
            return {'signal': 'none'}
        
        # 价格保护机制：如果已经有成交，新的买入价格不能低于上一次买入价格
        if self.trade_records[stock]['buy_times'] > 0 and current_price < self.trade_records[stock]['buy_prices'][-1]:
            return {'signal': 'none'}
        
        # 更新交易记录
        self.trade_records[stock]['buy_times'] += 1
        self.trade_records[stock]['buy_prices'].append(current_price)
        
        # 返回买入信号
        return {
            'signal': 'buy',
            'price': current_price,
            'amount': BUY_AMOUNT
        }
    
    def check_sell_condition(self, stock, minute_data, macd_data):
        """
        检查卖出条件
        
        参数:
            stock (str): 股票代码
            minute_data (DataFrame): 分钟级别的行情数据
            macd_data (DataFrame): MACDFS指标数据，可能为None
            
        返回:
            dict: 卖出信号
        """
        # 获取当前持仓
        position = self.context.get_position(stock)
        if position is None or position['持仓数量'] <= 0:
            return {'signal': 'none'}
            
        # 检查是否有可用数量
        if position['可用数量'] <= 0:
            logger.info(f"{YELLOW}【卖出限制】{RESET} {stock} 没有可用数量，不能卖出")
            return {'signal': 'none'}
        
        # 检查是否为开盘第一分钟
        now = datetime.now()
        market_open = datetime(now.year, now.month, now.day, 9, 30)
        if now.hour == 9 and now.minute == 30:
            # 获取昨日收盘价
            daily_data = self.context.custom_data.get_qmt_daily_data(
                stock_list=[stock], 
                period='1d', 
                count=2
            )
            if not daily_data.empty:
                yesterday_close = daily_data.iloc[1]['close']
                today_open = minute_data.iloc[0]['open']
                first_minute_close = minute_data.iloc[0]['close']
                
                # 次日开盘价低于昨日收盘价且第一分钟K线收阴
                if today_open < yesterday_close and first_minute_close < today_open:
                    return {
                        'signal': 'sell',
                        'price': 0,  # 市价单
                        'percent': 1.0  # 清仓
                    }
        
        # 如果macd_data为None，需要先计算
        if macd_data is None:
            macd_data = self.macd_indicator.calculate(stock, minute_data)
            if macd_data.empty:
                return {'signal': 'none'}
        
        # 检查MACDFS红柱是否连续下缩
        if self.macd_indicator.is_red_bar_shrinking(stock):
            # 初始化交易记录
            if stock not in self.trade_records:
                self.trade_records[stock] = {
                    'sell_times': 0
                }
            elif 'sell_times' not in self.trade_records[stock]:
                self.trade_records[stock]['sell_times'] = 0
            
            # 第一次触发卖出一半仓位
            if self.trade_records[stock]['sell_times'] == 0:
                self.trade_records[stock]['sell_times'] += 1
                
                return {
                    'signal': 'sell',
                    'price': 0,  # 市价单
                    'percent': 0.5  # 卖出一半
                }
            # 第二次触发卖出剩余仓位
            elif self.trade_records[stock]['sell_times'] == 1:
                self.trade_records[stock]['sell_times'] += 1
                
                return {
                    'signal': 'sell',
                    'price': 0,  # 市价单
                    'percent': 1.0  # 清仓
                }
        
        return {'signal': 'none'}
    
    def get_minute_data(self, stock):
        """
        获取股票的分钟级别数据
        
        参数:
            stock (str): 股票代码
            
        返回:
            DataFrame: 分钟级别的行情数据
        """
        # 获取当前日期
        now = datetime.now()
        today = now.strftime('%Y-%m-%d')
        
        # 获取分钟数据
        minute_data = self.context.custom_data.get_qmt_daily_data(
            stock_list=[stock], 
            period='1m', 
            start_time=f'{today} 09:30:00',
            end_time=f'{today} {now.strftime("%H:%M:%S")}',
            is_download=True
        )
        
        return minute_data
    
    def execute_trade(self, stock, signal):
        """
        执行交易
        
        参数:
            stock (str): 股票代码
            signal (dict): 交易信号
            
        返回:
            str: 订单ID或None
        """
        if signal['signal'] == 'buy':
            # 执行买入
            order_id = self.context.order_value(
                security=stock,
                value=signal['amount'],
                price=signal['price'],
                strategy_name='一进二低吸战法',
                remark=f'MACDFS绿柱上缩买入'
            )
            if order_id:
                logger.info(f"{GREEN}【买入信号】{RESET} {stock} 价格: {signal['price']} 金额: {signal['amount']}")
            return order_id
        
        elif signal['signal'] == 'sell':
            # 获取持仓
            position = self.context.get_position(stock)
            if position is None:
                return None
            
            # 计算卖出数量
            sell_amount = int(position['持仓数量'] * signal['percent'])
            if sell_amount <= 0:
                return None
            
            # 执行卖出
            order_id = self.context.order(
                security=stock,
                amount=-sell_amount,  # 负数表示卖出
                price=signal['price'],
                strategy_name='一进二低吸战法',
                remark=f'MACDFS红柱下缩卖出'
            )
            if order_id:
                logger.info(f"{RED}【卖出信号】{RESET} {stock} 价格: {signal['price']} 数量: {sell_amount}")
            return order_id
        
        return None