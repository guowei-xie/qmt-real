# -*- coding: utf-8 -*-
"""
工具函数模块

该模块提供了一系列工具函数，用于处理股票代码、交易时间判断、数据读写和行情数据获取等功能。
主要包括：
1. JSON数据读写
2. 股票代码格式转换
3. 交易时间判断
4. 行情数据连接
5. 其他辅助功能
"""

from pytdx.config import hosts
from xtquant import xtconstant
from datetime import datetime
from trader.logger import logger
from trader.anis import RED, GREEN, YELLOW, BLUE, RESET
import random
from pytdx.hq import TdxHq_API
import baostock as bs

import json
import os
import pandas as pd


def write_json(data, file_path):
    """
    将 Python 对象或 Pandas DataFrame 写入 JSON 文件

    参数:
    data: 要写入的 Python 对象 (字典、列表等) 或 Pandas DataFrame
    file_path: 要写入的 JSON 文件的全路径

    返回:
    None
    """
    try:
        # 确保目录存在
        dir_path = os.path.dirname(file_path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path)

        # 如果数据是 Pandas DataFrame，使用 to_json 方法
        if isinstance(data, pd.DataFrame):
            data.to_json(file_path, orient='records', force_ascii=False, indent=4, date_format='iso')
        else:
            # 使用 json 模块写入字典或列表
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

        print(f"数据已成功写入 JSON 文件: {file_path}")
    except Exception as e:
        print(f"写入 JSON 文件失败: {e}")
        raise


def read_json(file_path):
    """
    从 JSON 文件中读取数据

    参数:
    file_path: 要读取的 JSON 文件路径

    返回:
    读取的 Python 对象 (字典、列表等)
    """
    try:
        # 获取调用方脚本所在的目录
        caller_dir = os.path.dirname(os.path.realpath(__file__))
        absolute_file_path = os.path.join(caller_dir, file_path)

        with open(absolute_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        print(f"文件未找到: {file_path}")
        return None
    except json.JSONDecodeError as e:
        print(f"JSON 解码错误: {e}")
        return None
    except Exception as e:
        print(f"读取 JSON 文件失败: {e}")
        return None

def calculate_shares(total_amount, price):
    """
    根据总金额和标的（股票）价格计算可交易的股数，确保股数是 100 的倍数。

    参数:
    total_amount (float): 总金额
    price (float): 标的价格（每股价格）

    返回:
    int: 可交易的股数（100 的倍数）
    """
    if total_amount is None or price is None:
        return 0
    if total_amount == 0 or price == 0:
        return 0
    max_shares = total_amount // price
    shares = (max_shares // 100) * 100
    return int(shares)


def add_stock_suffix_akshare(stock_code):
    """
    为给定的股票代码添加相应的AKShare格式后缀
    
    根据股票代码的前缀判断其所属交易所，并添加对应的后缀格式：
    - 深交所股票：sz开头，如sz000001
    - 上交所股票：sh开头，如sh600000
    - 北交所股票：bj开头，如bj430047
    
    参数:
        stock_code (str): 6位数字的股票代码，如'000001'、'600000'
        
    返回:
        str: 添加后缀的股票代码，如'sz000001'、'sh600000'
        
    异常:
        ValueError: 当股票代码不是6位数字时抛出
    """
    # 检查股票代码是否已经有后缀
    if "." in stock_code:
        return stock_code

    # 检查股票代码是否为6位数字
    if len(stock_code) != 6 or not stock_code.isdigit():
        raise ValueError("股票代码必须是6位数字")

    # 根据股票代码的前缀添加相应的后缀
    if stock_code.startswith("00") or stock_code.startswith("30") or stock_code.startswith(
            "15") or stock_code.startswith("16") or stock_code.startswith("18") or stock_code.startswith("12"):
        return f"sz{stock_code}"  # 深圳证券交易所（包括部分可转债）
    elif stock_code.startswith("60") or stock_code.startswith("68") or stock_code.startswith("11") or stock_code.startswith("13") or stock_code.startswith("11"):
        return f"sh{stock_code}"  # 上海证券交易所（包括部分可转债）
    elif stock_code.startswith("83") or stock_code.startswith("43") or stock_code.startswith("87"):
        return f"bj{stock_code}"  # 北京证券交易所

    return f"{stock_code}.SH"  # 默认上海证券交易所


def add_stock_suffix(codes):
    """
    为给定的股票代码或股票代码列表添加相应的标准后缀
    
    根据股票代码的前缀判断其所属交易所，并添加对应的后缀格式：
    - 深交所股票：.SZ后缀，如000001.SZ
    - 上交所股票：.SH后缀，如600000.SH
    - 北交所股票：.BJ后缀，如430047.BJ
    
    参数:
        codes (str或list): 单个股票代码或股票代码列表
        
    返回:
        str或list: 添加后缀的股票代码或股票代码列表
        
    异常:
        ValueError: 当股票代码不是6位数字时抛出
    """
    # 如果输入是列表，遍历列表中的每个股票代码并添加后缀
    if isinstance(codes, list):
        return [add_stock_suffix(code) for code in codes]

    # 检查股票代码是否已经有后缀
    if "." in codes:
        return codes

    # 检查股票代码是否为6位数字
    if len(codes) != 6 or not codes.isdigit():
        raise ValueError("股票代码必须是6位数字")

    # 根据股票代码的前缀添加相应的后缀
    if codes.startswith("00") or codes.startswith("30") or codes.startswith(
            "15") or codes.startswith("16") or codes.startswith(
        "18") or codes.startswith("12"):
        return f"{codes}.SZ"  # 深圳证券交易所（包括部分可转债）
    elif codes.startswith("60") or codes.startswith("68") or codes.startswith(
            "11") or codes.startswith("13") or codes.startswith("11"):
        return f"{codes}.SH"  # 上海证券交易所（包括部分可转债）
    elif codes.startswith("83") or codes.startswith("43") or codes.startswith("87"):
        return f"{codes}.BJ"  # 北京证券交易所

    return f"{codes}.SH"  # 默认上海证券交易所


def remove_stock_suffix(codes):
    """
    去除股票代码中的市场后缀
    
    将带有市场后缀的股票代码转换为纯6位数字代码，支持处理单个股票代码或股票代码列表。
    可处理的格式包括：
    - 000001.SZ、600000.SH、430047.BJ 等标准格式
    - sz000001、sh600000、bj430047 等AKShare格式
    
    参数:
        codes (str或list): 单个股票代码或股票代码列表
        
    返回:
        str或list: 去除后缀的6位数字股票代码或股票代码列表
        
    异常:
        ValueError: 当股票代码格式不正确时抛出
    """
    # 如果输入是列表，遍历列表中的每个股票代码并去除后缀
    if isinstance(codes, list):
        return [remove_stock_suffix(code) for code in codes]

    # 检查股票代码是否包含市场后缀
    if len(codes) == 6 and codes.isdigit():
        # 如果股票代码已经是6位数字，直接返回
        return codes

    # 检查股票代码是否包含市场后缀（长度至少为 9 位）
    if len(codes) < 9:
        raise ValueError("股票代码格式不正确，应包含市场后缀或为6位数字")

    # 去除市场后缀，只保留前 6 位
    stock_code = codes[:6]

    # 检查去除后缀后的股票代码是否为6位数字
    if not stock_code.isdigit():
        raise ValueError("去除后缀后的股票代码必须是6位数字")

    return stock_code

def get_szzs_stock_code(self):
    """
    获取上证指数代码
    
    返回:
        str: 上证指数代码 '000001.SH'
    """
    return '000001.SH'


def get_szcz_stock_code(self):
    """
    获取深证成指代码
    
    返回:
        str: 深证成指代码 '399001.SZ'
    """
    return '399001.SZ'


def get_cybz_stock_code(self):
    """
    获取创业板指代码
    
    返回:
        str: 创业板指代码 '399006.SZ'
    """
    return '399006.SZ'


def get_stock_market(stock_code):
    """
    根据股票代码获取其对应的市场代码。
    市场代码 0 表示深圳证券交易所，1 表示上海证券交易所。

    参数:
    stock_code (str): 股票代码，例如 '000001' 或 '600000'

    返回:
    int: 市场代码，0 表示深圳，1 表示上海
    """
    # 根据股票代码的前缀判断市场
    if stock_code.startswith("00") or stock_code.startswith("30") or stock_code.startswith(
            "15") or stock_code.startswith("16") or stock_code.startswith("18") or stock_code.startswith("12"):
        return 0  # 深圳证券交易所
    elif stock_code.startswith("60") or stock_code.startswith("68") or stock_code.startswith("11"):
        return 1  # 上海证券交易所
    elif stock_code.startswith("83") or stock_code.startswith("43"):
        raise ValueError("北京证券交易所的股票代码暂不支持")  # 北京证券交易所暂不支持


def timestamp_to_datetime_string(timestamp):
    """
    将时间戳转换为时间字符串
    
    将秒级时间戳转换为格式化的日期时间字符串
    
    参数:
        timestamp (float): 时间戳（秒级）
        
    返回:
        str: 格式化的时间字符串，格式为 'YYYY-MM-DD HH:MM:SS'
    """
    dt_object = datetime.fromtimestamp(timestamp)
    time_string = dt_object.strftime('%Y-%m-%d %H:%M:%S')
    return time_string


def parse_order_type(order_type):
    """
    解析订单类型，并返回带颜色标记的文本
    
    将数字订单类型转换为带颜色的文本表示：
    - 买入订单显示为红色
    - 卖出订单显示为绿色
    
    参数:
        order_type (int): 订单类型常量，来自xtconstant模块
        
    返回:
        str: 带颜色标记的订单类型文本
    """
    if order_type == xtconstant.STOCK_BUY:
        return f"{RED}买入{RESET}"
    elif order_type == xtconstant.STOCK_SELL:
        return f"{GREEN}卖出{RESET}"


def convert_to_current_date(timestamp):
    """
    将给定时间戳的时间部分与当前日期组合，生成新的时间戳
    
    保留原时间戳的时分秒部分，但将日期更改为当前日期
    
    参数:
        timestamp (float): 输入的时间戳（秒级）
        
    返回:
        float: 组合后的新时间戳（秒级）
    """
    # 将时间戳转换为 datetime 对象
    dt = datetime.fromtimestamp(timestamp)

    # 获取当前日期
    current_date = datetime.now().date()

    # 创建一个新的 datetime 对象，使用当前日期和原始时间戳的时间部分
    new_dt = datetime.combine(current_date, dt.time())

    return new_dt.timestamp()


def is_trade_time():
    """
    校验当前是否为A股交易时间
    
    判断当前时间是否在A股交易时段内，包括：
    1. 开盘集合竞价 (9:15-9:25)
    2. 早盘连续竞价 (9:30-11:30)
    3. 午盘连续竞价 (13:00-14:57)
    4. 收盘集合竞价 (14:57-15:00)
    5. 科创板和创业板盘后交易 (15:05-15:30)
    
    注意：该函数仅检查时间，不考虑节假日因素
    
    返回:
        bool: 如果当前时间在交易时段内返回True，否则返回False
    """
    now = datetime.now()
    current_time = now.time()
    weekday = now.weekday()  # 0-4 是周一到周五

    # 检查是否为交易日（周一至周五，非节假日）
    if weekday >= 5:  # 周六、周日
        return False  

    # 定义交易时段
    trading_periods = [
        {"name": "开盘集合竞价", "start": "09:15:00", "end": "09:25:00", "can_cancel": True},
        {"name": "早盘连续竞价", "start": "09:30:00", "end": "11:30:00", "can_cancel": True},
        {"name": "午间休市", "start": "11:30:00", "end": "13:00:00", "can_cancel": False},
        {"name": "午盘连续竞价", "start": "13:00:00", "end": "14:57:00", "can_cancel": True},
        {"name": "收盘集合竞价", "start": "14:57:00", "end": "15:00:00", "can_cancel": False},
    ]

    # 科创板和创业板的盘后交易（15:05-15:30）
    kechuang_cyb_period = {"name": "科创/创业板盘后交易", "start": "15:05:00", "end": "15:30:00", "can_cancel": False}

    # 检查当前是否在交易时段
    for period in trading_periods:
        start_time = datetime.strptime(period["start"], "%H:%M:%S").time()
        end_time = datetime.strptime(period["end"], "%H:%M:%S").time()
        if start_time <= current_time <= end_time:
            return True

    # 检查是否在科创/创业板盘后交易时段
    kechuang_start = datetime.strptime(kechuang_cyb_period["start"], "%H:%M:%S").time()
    kechuang_end = datetime.strptime(kechuang_cyb_period["end"], "%H:%M:%S").time()
    if kechuang_start <= current_time <= kechuang_end:
        return True

    # 不在任何交易时段
    return False


# def pytdx_connect(retry_times=3):
#     """
#     初始化 TDX 配置并连接 TDX 行情服务器，支持重试机制。

#     参数:
#     retry_times (int): 重试次数，默认为3次。

#     返回:
#     TdxHq_API: 连接成功的 TdxHq_API 对象，或 None 如果连接失败。
#     """
#     # 初始化 TDX 配置
#     df = pd.DataFrame(hosts.hq_hosts)
#     df.columns = ['name', 'ip', 'port']
#     name_list = df['name'].tolist()
#     ip_list = df['ip'].tolist()
#     port_list = df['port'].tolist()

#     # 设置默认服务器
#     default_name = '招商证券深圳行情'
#     default_ip = '124.71.187.122'
#     default_port = 7709

#     # 初始化 TdxHq_API 对象
#     api = TdxHq_API()
#     connected = False

#     try:
#         api.connect(ip=default_ip, port=default_port, time_out=21600)
#         connected = True
#         logger.info(f"{GREEN}【通达信数据】{RESET} 连接成功")
#         return api
#     except Exception as e:
#         pass

#     # 如果默认连接失败，尝试随机连接其他服务器
#     for _ in range(retry_times):
#         try:
#             n = len(name_list)
#             if n == 0:
#                 break  # 没有可用服务器，退出循环
#             random_index = random.randint(0, n - 1)
#             random_ip = ip_list[random_index]
#             random_port = port_list[random_index]
#             api.connect(ip=random_ip, port=random_port)
#             connected = True
#             return api
#         except Exception as e:
#             return None

#     if not connected:
#         return None


# def baostock_login():
#     """
#     初始化 BaoStock 并登录
    
#     BaoStock是一个免费、开源的证券数据平台，提供完整、准确、快速的历史证券数据API接口。
#     该函数执行BaoStock的登录操作，并记录登录结果。
    
#     返回:
#         bs: 已登录的BaoStock对象，可用于后续数据查询
#     """
#     lg = bs.login()
#     logger.info(f"{GREEN}【BaoStock数据】{RESET} {lg.error_msg}")
#     return bs
