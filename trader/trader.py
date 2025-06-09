# -*- coding: utf-8 -*-
"""
交易模块

该模块提供了与XtQuant交易系统交互的功能，包括：
1. 交易回调处理（委托、成交、错误等）
2. 交易对象创建与初始化
3. 账户订阅与管理

主要组件：
- MyXtQuantTraderCallback: 处理交易回调的类
- create_trader: 创建交易对象的函数
"""

from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback
from xtquant.xttype import StockAccount
import random
from trader.utils import timestamp_to_datetime_string, parse_order_type, convert_to_current_date
from trader.anis import RED, GREEN, YELLOW, BLUE, RESET
from trader.logger import logger

# 存储已处理的错误订单ID，避免重复处理
error_orders = []


class MyXtQuantTraderCallback(XtQuantTraderCallback):
    """
    XtQuant交易回调处理类
    
    继承自XtQuantTraderCallback，用于处理交易过程中的各种回调事件，包括：
    - 连接断开事件
    - 委托信息推送
    - 成交信息推送
    - 委托错误处理
    - 撤单错误处理
    
    该类实现了所有必要的回调方法，并使用logger记录交易过程中的各种状态和错误信息。
    """
    def on_disconnected(self):
        """
        连接断开回调处理
        
        当与交易服务器的连接断开时被调用，输出连接断开信息
        
        返回:
            无返回值
        """
        print("connection lost")

    def on_stock_order(self, order):
        """
        委托信息推送回调处理
        
        当收到委托状态更新时被调用，根据委托状态记录不同级别的日志信息：
        - 状态码50：委托已提交，记录为info级别
        - 状态码53或54：委托已撤单，记录为warning级别
        
        参数:
            order: XtOrder对象，包含委托的详细信息，如股票代码、价格、数量等
        
        返回:
            无返回值
        """
        # 委托
        if order.order_status == 50:
            logger.info(
                f"{BLUE}【已委托】{RESET} {parse_order_type(order.order_type)} 代码:{order.stock_code} 名称:{order.order_remark} 委托价格:{order.price:.2f} 委托数量:{order.order_volume} 订单编号:{order.order_id} 委托时间:{timestamp_to_datetime_string(convert_to_current_date(order.order_time))}")
        elif order.order_status == 53 or order.order_status == 54:
            logger.warning(
                f"{YELLOW}【已撤单】{RESET} {parse_order_type(order.order_type)} 代码:{order.stock_code} 名称:{order.order_remark} 委托价格:{order.price:.2f} 委托数量:{order.order_volume} 订单编号:{order.order_id} 委托时间:{timestamp_to_datetime_string(convert_to_current_date(order.order_time))}")

    def on_stock_trade(self, trade):
        """
        成交信息推送回调处理
        
        当订单成交时被调用，记录成交详情，包括股票代码、名称、价格、数量等信息
        
        参数:
            trade: XtTrade对象，包含成交的详细信息，如股票代码、成交价格、成交数量等
        
        返回:
            无返回值
        """
        logger.info(
            f"{GREEN}【已成交】{RESET} {parse_order_type(trade.order_type)} 代码:{trade.stock_code} 名称:{trade.order_remark} 成交价格:{trade.traded_price:.2f} 成交数量:{trade.traded_volume} 成交编号:{trade.order_id} 成交时间:{timestamp_to_datetime_string(convert_to_current_date(trade.traded_time))}")

    def on_order_error(self, data):
        """
        委托错误回调处理
        
        当委托发生错误时被调用，记录错误信息并避免重复处理同一错误
        
        参数:
            data: 包含错误信息的数据对象，具有order_id和error_msg属性
        """
        if data.order_id in error_orders:
            return
        error_orders.append(data.order_id)
        logger.error(f"{RED}【委托失败】{RESET}错误信息:{data.error_msg.strip()}")

    def on_cancel_error(self, data):
        """
        撤单错误回调处理
        
        当撤单操作发生错误时被调用，记录错误信息并避免重复处理同一错误
        
        参数:
            data: 包含错误信息的数据对象，具有order_id和error_msg属性
        """
        if data.order_id in error_orders:
            return
        error_orders.append(data.order_id)
        logger.error(f"{RED}【撤单失败】{RESET}错误信息:{data.error_msg.strip()}")


def create_trader(account_id, mini_qmt_path):
    """
    创建并初始化交易对象
    
    该函数完成以下步骤：
    1. 创建随机会话ID
    2. 初始化XtQuantTrader对象
    3. 启动交易对象
    4. 连接交易服务器
    5. 创建并订阅账户
    6. 注册回调处理类
    
    参数:
        account_id (str): 交易账户ID，用于标识特定的交易账户
        mini_qmt_path (str): MiniQmt客户端的安装路径，用于连接交易服务器

    返回:
        tuple: 包含两个元素的元组
            - xt_trader (XtQuantTrader): 初始化完成的交易对象
            - account (StockAccount): 已订阅的账户对象
            
    异常:
        ValueError: 当连接MiniQMT失败时抛出，包含错误信息和参考文档链接
    """
    # 创建session_id
    session_id = int(random.randint(100000, 999999))
    # 创建交易对象
    xt_trader = XtQuantTrader(mini_qmt_path, session_id)
    # 启动交易对象
    xt_trader.start()
    # 连接客户端
    connect_result = xt_trader.connect()

    if connect_result == 0:
        logger.debug(f"{GREEN}【连接成功】{RESET} MiniQMT路径:{mini_qmt_path}")
    else:
        logger.error(f"{RED}【miniQMT连接失败】{RESET} 请检查")
        raise ValueError(f"【miniQMT连接失败】 请检查  参考文档【https://dict.thinktrader.net/nativeApi/question_function.html?id=c5Obtn#%E8%BF%9E%E6%8E%A5-xtquant-%E6%97%B6%E5%A4%B1%E8%B4%A5-%E8%BF%94%E5%9B%9E-1%E5%8F%8A%E8%A7%A3%E5%86%B3%E6%96%B9%E6%B3%95】")

    # 创建账号对象
    account = StockAccount(account_id)
    # 订阅账号
    xt_trader.subscribe(account)
    logger.debug(f"{GREEN}【订阅成功】{RESET} 账号ID:{account_id}")
    # 注册回调类
    xt_trader.register_callback(MyXtQuantTraderCallback())

    return xt_trader, account
