# -*- coding: utf-8 -*-
"""
数据获取模块

该模块提供了QMT量化交易平台的数据获取和处理功能，包括：
1. QMT历史数据下载和查询
2. QMT全推行情数据获取

主要依赖：
- xtquant: QMT量化交易平台API
- pandas: 数据处理
"""

from trader.utils import *
from tqdm import tqdm
from xtquant import xtdata
from trader.logger import logger
from trader.anis import RED, GREEN, YELLOW, BLUE, RESET
import pandas as pd

class CustomData:
    """
    自定义数据获取类
    
    提供QMT量化交易平台的数据获取功能，包括：
    - QMT历史数据下载和查询
    - QMT全推行情数据获取
    
    该类提供统一的接口进行QMT数据获取和处理。
    """
    
    def __init__(self):
        """
        初始化数据获取类
        
        在初始化时下载板块数据，确保在使用相关功能前数据已经准备好。
        """
        try:
            logger.info(f"{GREEN}【初始化数据】{RESET} 开始下载板块分类信息")
            # 下载板块分类信息
            self.download_sector_data()
            logger.info(f"{GREEN}【初始化数据】{RESET} 板块分类信息下载完成")
        except Exception as e:
            logger.error(f"{YELLOW}【初始化数据失败】{RESET} {e}")
            logger.info(f"{YELLOW}【初始化数据】{RESET} 将在使用时尝试重新下载板块数据")

    def download_qmt_history_data(self, stock_list=None, period='1d'):
        """
        使用QMT下载指定股票代码的历史数据

        通过QMT的API增量下载指定股票的历史数据，支持不同周期的数据下载。
        下载的数据将保存在QMT的本地数据库中，可以通过get_qmt_daily_data等函数查询。

        参数:
            stock_list (list): 股票代码列表，如['000001', '600000']
            period (str): 数据周期，默认为'1d'（日线），可选值包括：
                - '1m': 1分钟线
                - '5m': 5分钟线
                - '15m': 15分钟线
                - '30m': 30分钟线
                - '1h': 1小时线
                - '1d': 日线
                - '1w': 周线
                - '1mon': 月线

        返回:
            无直接返回值，数据下载到本地数据库
        """
        logger.debug(f"{GREEN}【数据下载】{RESET} {len(stock_list)}只")
        # 使用tqdm创建进度条，显示下载进度
        for code in tqdm(stock_list, desc=f"{GREEN}下载历史数据{RESET}", ncols=100, colour="green"):
            xtdata.download_history_data(code, period=period, incrementally=True)


    def get_qmt_daily_data(self, stock_list=['000001.SZ'], period='1d', start_time='', end_time='', count=100, is_download=True):
        """
        使用QMT获取指定股票代码的历史数据

        从QMT本地数据库获取指定股票的历史数据，支持不同周期和时间范围的查询。
        可选择是否在查询前先下载最新数据。

        参数:
            stock_list (list): 股票代码列表，默认为['000001.SZ']
            period (str): 数据周期，默认为'1d'（日线）
            start_time (str): 起始时间，格式为'YYYY-MM-DD'或'YYYY-MM-DD HH:MM:SS'
            end_time (str): 结束时间，格式为'YYYY-MM-DD'或'YYYY-MM-DD HH:MM:SS'
            count (int): 数据条数，默认为100条
                - 当指定了start_time和end_time时，以end_time为基准向前取count条
                - 当未指定start_time和end_time时，取最新的count条数据
            is_download (bool): 是否在查询前下载最新数据，默认为True

        返回:
            pd.DataFrame: 包含股票历史数据的DataFrame，如果获取失败则返回空DataFrame
            
        异常:
            Exception: 当数据获取失败时捕获异常并记录日志
        """
        try:
            if is_download:
                self.download_qmt_history_data(add_stock_suffix(stock_list), period)
            df = xtdata.get_market_data_ex(field_list=[], stock_list=add_stock_suffix(stock_list), period=period,
                                                  start_time=start_time, end_time=end_time, count=count,
                                                  dividend_type='none', fill_data=True)
            return df
        except Exception as e:
            logger.error(f"{YELLOW}【数据获取失败】{RESET} {e}")
            return pd.DataFrame()

    def get_qmt_full_tick(self, stock_list=['000001.SZ']):
        """
        使用QMT获取指定股票代码的全推行情数据

        获取指定股票的实时全推行情数据，包括最新价、买卖盘、成交量等信息。

        参数:
            stock_list (list): 股票代码列表，默认为['000001.SZ']

        返回:
            pd.DataFrame: 包含股票全推行情数据的DataFrame，如果获取失败则返回空DataFrame
            
        异常:
            Exception: 当数据获取失败时捕获异常并记录日志
        """
        try:
            code_list = []
            for code in stock_list:
                code_list.append(add_stock_suffix(code))
            df = xtdata.get_full_tick(code_list)
            return df
        except Exception as e:
            logger.error(f"{YELLOW}【数据获取失败】{RESET} {e}")
            return pd.DataFrame()
            
    def download_sector_data(self):
        """
        下载板块分类信息数据
        
        在获取板块成份股之前，需要先下载板块分类信息数据。
        该函数调用QMT的API下载最新的板块分类信息。
        
        返回:
            bool: 下载成功返回True，失败返回False
        """
        try:
            logger.info(f"{GREEN}【下载板块数据】{RESET} 开始下载板块分类信息")
            # 调用QMT的API下载板块分类信息
            xtdata.download_sector_data()
            logger.info(f"{GREEN}【下载板块数据】{RESET} 板块分类信息下载完成")
            return True
        except Exception as e:
            logger.error(f"{YELLOW}【下载板块数据失败】{RESET} {e}")
            return False
    
    def get_stock_list_in_sector(self, sector_name):
        """
        获取板块成份股列表
        
        通过QMT的API获取指定板块的成份股列表，支持客户端左侧板块列表中任意的板块，包括自定义板块。
        
        参数:
            sector_name (str): 板块名称，如'沪深A股'、'上证50'等
            
        返回:
            list: 板块成份股代码列表
            
        异常:
            Exception: 当数据获取失败时捕获异常并记录日志
        """
        try:
            stock_list = xtdata.get_stock_list_in_sector(sector_name)
            return stock_list
        except Exception as e:
            logger.error(f"{YELLOW}【获取板块成份股失败】{RESET} {sector_name}: {e}")
            return []
    
    def get_stock_info(self, stock_code):
        """
        获取股票基本信息
        
        参数:
            stock_code (str): 股票代码
            
        返回:
            dict: 股票基本信息，包含股票名称、停牌状态、总市值等
        """
        try:
            # 添加市场后缀
            stock_code_with_suffix = add_stock_suffix(stock_code)
            
            # 获取股票详细信息
            detail = xtdata.get_instrument_detail(stock_code_with_suffix)
            if detail is None:
                return None
                
            # 构建返回结果
            result = {
                '股票名称': detail.get('InstrumentName', ''),
                '停牌状态': 0 if detail.get('IsTrading', True) else 1,
                '总市值': detail.get('TotalVolume', 0) * detail.get('PreClose', 0)
            }
            
            return result
        except Exception as e:
            logger.error(f"获取股票信息失败: {e}")
            return None

# 创建 CustomData 实例供其他模块导入
custom_data = CustomData()
