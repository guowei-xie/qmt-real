# -*- coding: utf-8 -*-
"""
交易上下文模块

该模块提供了交易上下文环境，封装了QMT交易接口和数据接口，提供了统一的交易和数据查询接口。

主要功能包括：
1. 账户资产和持仓查询 - 获取账户总资产、持仓市值、可用资金等信息
2. 订单管理 - 支持多种下单方式（按数量、按金额、按仓位）和撤单操作
3. 行情数据获取 - 获取证券最新价格、名称等信息
4. 定时任务设置 - 支持定时和定期执行策略逻辑

该模块是策略实现的核心组件，为策略提供了完整的QMT交易和数据环境。
"""

from xtquant import xtdata
from xtquant import xtconstant

from trader.constant import QMT_POSITIONS_FIELD_MAPPING, QMT_ASSET_FIELD_MAPPING, QMT_ORDERS_FIELD_MAPPING, \
    QMT_TRADES_FIELD_MAPPING
from trader.data import custom_data
from trader.utils import add_stock_suffix, calculate_shares
from trader.logger import logger
from trader.anis import RED, GREEN, YELLOW, BLUE, RESET

import pandas as pd

# 设置pandas显示选项，不省略行和列
pd.set_option('display.max_rows', None)  # 显示所有行
pd.set_option('display.max_columns', None)  # 显示所有列
pd.set_option('display.width', None)  # 自动调整列宽
pd.set_option('display.max_colwidth', None)  # 显示完整的列内容


class Context:
    """
    交易上下文类，提供统一的交易和数据查询接口。
    
    该类封装了QMT交易接口，提供了统一的交易和数据查询方法。
    主要功能包括：
    1. 账户资产和持仓查询 - 获取账户总资产、持仓市值、可用资金等信息
    2. 订单管理 - 支持多种下单方式（按数量、按金额、按仓位）和撤单操作
    3. 行情数据获取 - 获取证券最新价格、名称等信息
    4. 定时任务设置 - 支持定时和定期执行策略逻辑
    
    通过属性委托机制（__getattr__），可以直接访问底层数据接口的方法，无需关心具体实现细节。
    这使得策略代码可以更加简洁和直观。
    """
    
    def __getattr__(self, name):
        """
        属性委托方法，按优先级顺序查找属性。
        
        当访问context对象不存在的属性时，会按照优先级顺序在各个数据对象中查找该属性。
        优先级顺序为：xtdata > xt_trader > custom_data
        
        参数:
            name (str): 要访问的属性名
            
        返回:
            属性值或方法引用
            
        异常:
            AttributeError: 当所有数据对象中都不存在该属性时抛出
        """
        # 定义一个数据对象的列表，按优先级顺序排列
        data_objects = [xtdata, self.xt_trader, self.custom_data]
        for obj in data_objects:
            if hasattr(obj, name):
                return getattr(obj, name)
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
    
    def __init__(self, xt_trader, account, mode=0, strategy_name=''):
        """
        初始化交易上下文对象。
        
        参数:
            xt_trader: QMT交易接口对象
            account (str): 交易账户
            mode (int): 交易模式，0表示实盘，1表示模拟盘
            strategy_name (str): 策略名称，用于标识订单来源
        """
        self.tasks = []  # 定时任务列表
        self.xt_trader = xt_trader  # QMT交易接口
        xtdata.enable_hello = False  # 禁用QMT数据接口的hello消息
        self.custom_data = custom_data  # 自定义数据接口
        self.qmt_account = account  # 交易账户
        self.strategy_name = strategy_name  # 策略名称
        self.is_simulate = mode == 1  # 是否为模拟盘

    def run_time(self, func, period):
        """
        设置定时任务，以指定的周期重复执行。

        参数:
            func (callable): 回调函数，将在指定周期被调用
            period (str): 周期字符串，例如 "5nSecond"（5秒）、"1nMinute"（1分钟）
            
        返回:
            None
            
        示例:
            # 每5秒执行一次update函数
            context.run_time(update, "5nSecond")
        """
        self.tasks.append({
            "func": func,
            "period": period,
            "type": "time"
        })

    def run_daily(self, func, time):
        """
        设置定时任务，以指定的时间每天执行。

        参数:
            func (callable): 回调函数，将在指定时间被调用
            time (str): 执行时间字符串，格式为"HH:MM:SS"，例如 "09:30:00"（每天上午9点30分执行）
            
        返回:
            None
            
        示例:
            # 每天开盘时执行open_market函数
            context.run_daily(open_market, "09:30:00")
        """
        self.tasks.append({
            "func": func,
            "period": time,
            "type":"daily"
        })

    def get_positions(self):
        """
        查询并返回账户的持仓信息。
        
        返回:
            pd.DataFrame: 包含账户持仓信息的 DataFrame。
        """
        positions = self.xt_trader.query_stock_positions(self.qmt_account)
        if not positions:
            return pd.DataFrame(columns=QMT_POSITIONS_FIELD_MAPPING.keys())
        df = pd.DataFrame([
            {key: getattr(p, value) for key, value in QMT_POSITIONS_FIELD_MAPPING.items()}
            for p in positions
        ])
        return df

    def get_position(self, security='000001.SZ'):
        """
        查询并返回指定股票代码的持仓信息。
    
        参数:
            security (str): 股票代码，默认为 '000001.SZ'
    
        返回:
            dict: 包含指定股票持仓信息的字典。如果未找到该股票的持仓信息，则返回 None。
        """
        positions = self.get_positions()
        if positions.empty:
            return None
        position = positions[positions['股票代码'] == add_stock_suffix(security)]
        return position.to_dict(orient='records')[0] if not position.empty else None

    def get_security_percent(self, security='000001.SZ'):
        """
        查询并返回指定标的的仓位。

        参数:
            security (str): 股票代码，默认为 '000001.SZ'

        返回:
            float: 指定标的的仓位，没查到则返回None。
        """
        position = self.get_position(security)
        if position is not None:
            asset = self.get_asset()
            market_value = position['持仓市值']
            total_asset = asset['总资产']
            percent = round(market_value / total_asset, 4)
            return percent
        return None

    def get_security_available(self, security='000001.SZ'):
        """
        查询并返回指定标的的可用数量。

        参数:
            security (str): 股票代码，默认为 '000001.SZ'

        返回:
            float: 指定标的的可用数量，没查到则返回None。
        """
        position = self.get_position(security)
        if position is not None:
            return position['可用数量']
        return None

    def get_asset(self):
        """
        查询并返回账户的资产信息。

        返回:
            dict: 包含账户资产信息的字典。
        """
        asset_info = self.xt_trader.query_stock_asset(self.qmt_account)
        return {display_name: getattr(asset_info, qmt_field.lower())
                for display_name, qmt_field in QMT_ASSET_FIELD_MAPPING.items()
                }

    def get_total_asset(self):
        """
        查询并返回账户的总资产。

        返回:
            float: 账户的总资产。
        """
        return self.get_asset()['总资产']

    def get_total_market_value(self):
        """
        查询并返回账户的持仓市值。

        返回:
            float: 账户的持仓市值。
        """
        return self.get_asset()['持仓市值']

    def get_total_percent(self):
        """
        查询并返回账户的持仓仓位。

        返回:
            float: 账户的持仓仓位。
        """
        total_asset = self.get_total_asset()
        total_market_value = self.get_total_market_value()
        if total_asset > 0:
            percent = total_market_value / total_asset
            return round(percent, 4)
        return 0

    def get_total_cash(self):
        """
        查询并返回账户的可用余额。

        返回:
            float: 账户的可用余额。
        """
        return self.get_asset()['可用金额']

    def get_orders(self, cancelable_only=False):
        """
        查询并返回指定账户的股票委托订单信息。

        参数:
            cancelable_only (bool): 仅查询可撤委托

        返回:
            pd.DataFrame: 包含委托订单信息的 DataFrame
        """
        orders = self.xt_trader.query_stock_orders(self.qmt_account, cancelable_only)
        if not orders:
            return pd.DataFrame(columns=QMT_ORDERS_FIELD_MAPPING.keys())
        df = pd.DataFrame([
            {key: getattr(order, value) for key, value in QMT_ORDERS_FIELD_MAPPING.items()}
            for order in orders
        ])
        return df

    def get_order_no(self, remark=None, order_id=None, cancelable_only=False):
        """
        根据 order_remark 或 order_id 查询订单。

        参数:
            remark (str): 订单备注。
            order_id (str): 订单编号。
            cancelable_only (bool): 仅查询可撤委托

        返回:
            pd.DataFrame: 包含符合条件的订单信息的 DataFrame；如果未找到，则返回空 DataFrame。
        """
        all_orders = self.get_orders(cancelable_only)
        if all_orders.empty or (remark is None and order_id is None):
            return pd.DataFrame()

        # 筛选符合条件的订单
        filtered_orders = all_orders[
            (all_orders['委托备注'] == remark) |
            (all_orders['订单编号'] == order_id)
            ]

        return filtered_orders

    def get_trades(self):
        """
        查询并返回指定账户的股票成交订单信息。

        返回:
            pd.DataFrame: 包含成交订单信息的 DataFrame
        """
        trades = self.xt_trader.query_stock_trades(self.qmt_account)
        if not trades:
            return pd.DataFrame(columns=QMT_TRADES_FIELD_MAPPING.keys())
        df = pd.DataFrame([
            {key: getattr(p, value) for key, value in QMT_TRADES_FIELD_MAPPING.items()}
            for p in trades
        ])
        return df

    def get_trades_no(self, remark=None, order_id=None):
        """
        根据 order_remark 或 order_id 查询成交信息。

        参数:
            remark (str): 订单备注。
            order_id (str): 订单编号。

        返回:
            pd.DataFrame: 包含符合条件的订单信息的 DataFrame；如果未找到，则返回空 DataFrame。
        """
        all_orders = self.get_trades()
        if all_orders.empty or (remark is None and order_id is None):
            return pd.DataFrame()
        filtered_orders = all_orders[
            (all_orders['委托备注'] == remark) |
            (all_orders['订单编号'] == order_id)
            ]
        return filtered_orders

    def order_check(self, security='000001.SZ', side=xtconstant.STOCK_BUY, amount=100, price=0):
        """
        订单校验，买单校验可用余额，卖单校验可用数量。

        参数:
            security (str): 股票代码，默认为 '000001.SZ'。
            side (int): 交易方向，买入或者卖出。
            amount (int): 交易数量，正数表示买入，负数表示卖出。
            price (float): 交易价格，0 表示市价单，非 0 表示限价单。

        返回:
            bool: 是否校验通过。
        """
        if side == xtconstant.STOCK_BUY:
            if price == 0:
                price = self.get_latest_price(security=security)
            total_amount = round(price * amount, 2)
            total_cash = self.get_total_cash()
            result_flag = total_cash >= total_amount
            if not result_flag:
                logger.warning(
                    f"{YELLOW}【校验失败】{RESET}  标的：{security}  方向：[买入]  可用余额：{total_cash}  买入金额：{total_amount}")
            return result_flag

        if side == xtconstant.STOCK_SELL:
            available_amount = self.get_security_available(security=security)
            available_amount = 0 if available_amount is None else available_amount
            result_flag = available_amount >= amount
            if not result_flag:
                logger.warning(
                    f"{YELLOW}【校验失败】{RESET}  标的：{security}  方向：[卖出]  可用数量：{available_amount}  卖出数量：{amount}")
            return result_flag

    def order(self, security='000001.SZ', amount=100, price=0, strategy_name='', remark=''):
        """
        买卖标的。调用成功后, 您将可以调用[orders]取得所有未完成的交易,
        也可以调用[cancel_order]取消交易。

        参数:
            security (str): 股票代码，默认为 '000001.SZ'。
            amount (int): 交易数量，正数表示买入，负数表示卖出。
            price (float): 交易价格，0 表示市价单，非 0 表示限价单。
            strategy_name (str): 策略名称，用于记录订单来源。
            remark (str): 备注信息，用于记录订单的额外说明。

        返回:
            str: 订单 ID。如果下单失败或条件不满足，则返回 None。
        """
        if amount == 0:
            logger.warning(
                f"{YELLOW}【数据校验】{RESET} 标的：{security}  方向：[{'买入' if amount > 0 else '卖出'}]  交易数量：{amount} 交易价格：{ price if price > 0 else '市价'}")
            return None
        if not self.is_simulate:
            logger.info(
                f"{GREEN}【模拟订单】{RESET} 标的：{security}  方向：[{'买入' if amount > 0 else '卖出'}]  交易数量：{amount}  交易价格：{ price if price > 0 else '市价'}")
        side = xtconstant.STOCK_BUY if amount > 0 else xtconstant.STOCK_SELL
        amount = abs(amount)
        price_type = xtconstant.FIX_PRICE if price > 0 else xtconstant.LATEST_PRICE
        strategy_name = self.strategy_name if strategy_name == '' else strategy_name
        # 检查订单是否有效，如果是模拟盘则直接下单，如果是实盘则需要先校验
        if not self.is_simulate and not self.order_check(security=security, side=side, amount=amount, price=price):
            return None
            
        # 执行下单操作
        order_id = self.xt_trader.order_stock(self.qmt_account, add_stock_suffix(security), side, amount,
                                              price_type, price,
                                              strategy_name,
                                              remark)
        return order_id

        return None

    def order_target(self, security='000001.SZ', amount=100, price=0, strategy_name='', remark=''):
        """
        买卖标的, 使最终标的的数量达到指定的amount。
        注意使用此接口下单时若指定的标的有未完成的订单，
        则先前未完成的订单将会被取消。
        
        参数:
            security (str): 股票代码，默认为 '000001.SZ'。
            amount (int): 目标持仓数量。
            price (float): 交易价格，0 表示市价单，非 0 表示限价单。
            strategy_name (str): 策略名称，用于记录订单来源。
            remark (str): 备注信息，用于记录订单的额外说明。

        返回:
            str: 如果需要调整持仓，返回下单生成的订单 ID；如果无需调整，则返回 None。
        """
        position = self.get_position(security=security)
        if position is not None:
            current_amount = position['持仓数量']
            amount = amount - current_amount
        self.cancel_security_order(security=security)
        order_id = self.order(security, amount, price, strategy_name, remark)
        return order_id

    def order_value(self, security='000001.SZ', value=None, price=0, strategy_name='', remark=''):
        """
        买卖价值为value的标的。

        参数:
            security (str): 股票代码，默认为 '000001.SZ'。
            value (float): 股票价值，value = 最新价 * 手数 * 保证金率（股票为1） * 乘数（股票为100）。
            price (float): 交易价格，0 表示市价单，非 0 表示限价单。
            strategy_name (str): 策略名称，用于记录订单来源。
            remark (str): 备注信息，用于记录订单的额外说明。

        返回:
            str: 如果需要调整持仓，返回下单生成的订单 ID；如果无需调整，则返回 None。
        """
        current_price = price
        if price == 0:
            current_price = self.get_latest_price(security)
        # 计算股票数量
        amount = calculate_shares(value, current_price)
        order_id = self.order(security, amount, price, strategy_name, remark)
        return order_id

    def order_target_value(self, security='000001.SZ', value=None, price=0, strategy_name='', remark=''):
        """
        买卖目标价值为value的标的。

        参数:
            security (str): 股票代码，默认为 '000001.SZ'。
            value (float): 股票价值，value = 最新价 * 手数 * 保证金率（股票为1） * 乘数（股票为100）。
            price (float): 交易价格，0 表示市价单，非 0 表示限价单。
            strategy_name (str): 策略名称，用于记录订单来源。
            remark (str): 备注信息，用于记录订单的额外说明。

        返回:
            str: 如果需要调整持仓，返回下单生成的订单 ID；如果无需调整，则返回 None。
        """
        if price == 0:
            price = self.get_latest_price(security)
        position = self.get_position(security=security)
        if position is not None:
            market_value = position['持仓市值']
            value = value - market_value
        # 计算股票数量
        amount = calculate_shares(value, price)
        self.cancel_security_order(security=security)
        order_id = self.order(security, amount, price, strategy_name, remark)
        return order_id

    def order_position(self, security='000001.SZ', percent=None, price=0, strategy_name='', remark=''):
        """
        买卖仓位为position的标的。

        参数:
            security (str): 股票代码，默认为 '000001.SZ'。
            percent (float): 股票仓位，基数为1，买入20%就传0.2，卖出20%就传-0.2。
            price (float): 交易价格，0 表示市价单，非 0 表示限价单。
            strategy_name (str): 策略名称，用于记录订单来源。
            remark (str): 备注信息，用于记录订单的额外说明。

        返回:
            str: 如果需要调整持仓，返回下单生成的订单 ID；如果无需调整，则返回 None。
        """
        if percent is None:
            logger.warning(f"{YELLOW}【数据校验】{RESET} {security} 交易仓位：{percent}")
            return None
        total_asset = self.get_total_asset()
        value = percent * total_asset
        order_id = self.order_value(security, value, price, strategy_name, remark)
        return order_id

    def order_target_position(self, security='000001.SZ', percent=None, price=0, strategy_name='', remark=''):
        """
        买卖目标仓位为position的标的。

        参数:
            security (str): 股票代码，默认为 '000001.SZ'。
            percent (float): 股票仓位，基数为1，买入20%就传0.2，卖出20%就传-0.2。
            price (float): 交易价格，0 表示市价单，非 0 表示限价单。
            strategy_name (str): 策略名称，用于记录订单来源。
            remark (str): 备注信息，用于记录订单的额外说明。

        返回:
            str: 如果需要调整持仓，返回下单生成的订单 ID；如果无需调整，则返回 None。
        """
        if percent is None:
            logger.warning(f"{YELLOW}【数据校验】{RESET} {security} 目标仓位：{percent}")
            return None
        current_position = self.get_security_percent(security=security)
        # 如果目标仓位和当前仓位的差距小于2%，则不进行调整
        # if current_position is not None and abs(current_position - percent) < 0.02:
        #     return None
        total_asset = self.get_total_asset()
        if current_position is not None:
            percent = percent - current_position
        value = percent * total_asset
        self.cancel_security_order(security=security)
        order_id = self.order_value(security, value, price, strategy_name, remark)
        return order_id

    def cancel_order(self, order_id=None):
        """
        根据订单编号对委托进行撤单操作。
        
        参数:
            order_id (str): 同步下单接口返回的订单编号，对于期货来说，是order结构中的order_sysid字段
            
        返回:
            int或None: 撤单结果代码
                0: 成功发出撤单指令
                -1: 撤单失败
                None: 订单编号为None
        """
        if order_id is not None:
            # 执行撤单操作，不需要区分是否为模拟盘
            cancel_result = self.xt_trader.cancel_order_stock(self.qmt_account, order_id)
            return cancel_result
        return None

    def cancel_all_order(self):
        """
        撤销当前账户的所有可撤销订单。
        
        该方法会查询当前账户的所有可撤销订单，并逐一发送撤单指令。
        适用于需要快速清空所有挂单的场景，如市场剧烈波动时的风险控制。
        
        参数:
            无
            
        返回:
            list: 撤单结果代码列表，每个元素为一个撤单结果代码：
                0: 成功发出撤单指令
                -1: 撤单失败
                
        示例:
            # 撤销所有挂单
            cancel_results = context.cancel_all_order()
            print(f"撤单结果: {cancel_results}")
        """
        cancel_result = []
        orders = self.get_orders(cancelable_only=True)
        for index, row in orders.iterrows():
            order_id = row['订单编号']
            if order_id is not None:
                result = self.xt_trader.cancel_order_stock(self.qmt_account, order_id)
                cancel_result.append(result)
        return cancel_result

    def cancel_security_order(self, security='000001.SZ'):
        """
        撤销指定标的的所有可撤销订单。
        
        该方法会查询当前账户的所有可撤销订单，筛选出指定标的的订单，并逐一发送撤单指令。
        适用于需要调整某只股票策略时，快速撤销该股票的所有挂单。
        
        参数:
            security (str): 股票代码，默认为 '000001.SZ'，支持带后缀(如'000001.SZ')和不带后缀(如'000001')的格式
            
        返回:
            list: 撤单结果代码列表，每个元素为一个撤单结果代码：
                0: 成功发出撤单指令
                -1: 撤单失败
                
        示例:
            # 撤销平安银行的所有挂单
            cancel_results = context.cancel_security_order('000001')
            # 或者使用带后缀的代码
            cancel_results = context.cancel_security_order('000001.SZ')
        """
        cancel_result = []
        orders = self.get_orders(cancelable_only=True)
        for index, row in orders.iterrows():
            order_id = row['订单编号']
            stock_code = row['股票代码']
            if order_id is not None and (security == stock_code or add_stock_suffix(security) == stock_code):
                result = self.xt_trader.cancel_order_stock(self.qmt_account, order_id)
                cancel_result.append(result)
        return cancel_result

    def get_latest_price(self, security='000001.SZ'):
        """
        获取指定标的的最新市场价格。
        
        该方法通过QMT接口获取指定证券的最新成交价格。如果交易接口未初始化，则返回0。
        该价格通常用于市价单下单或者计算持仓市值。
        
        参数:
            security (str): 股票代码，例如 '000001.SZ'或'000001'，支持不带后缀的格式，函数内部会自动添加后缀
            
        返回:
            float: 标的的最新价格，如果交易接口未初始化则返回0
            
        示例:
            # 获取平安银行的最新价格
            price = context.get_latest_price('000001')
            print(f"平安银行最新价: {price}")
        """
        if self.xt_trader is None:
            return 0
        security = add_stock_suffix(security)
        # 使用xtdata.get_full_tick获取最新价格
        try:
            tick_data = xtdata.get_full_tick([security])
            if security in tick_data and 'lastPrice' in tick_data[security]:
                return tick_data[security]['lastPrice']
            return 0
        except Exception as e:
            logger.error(f"获取最新价格失败: {e}")
            return 0

    def get_security_name(self, security='000001.SZ'):
        """
        获取指定标的的证券名称。
        
        该方法通过QMT接口获取指定证券代码对应的证券名称。如果交易接口未初始化，则返回空字符串。
        通常用于日志记录或界面显示，提高可读性。
        
        参数:
            security (str): 股票代码，例如 '000001.SZ'或'000001'，支持不带后缀的格式，函数内部会自动添加后缀
            
        返回:
            str: 标的的证券名称，如果交易接口未初始化则返回空字符串
            
        示例:
            # 获取平安银行的证券名称
            name = context.get_security_name('000001')
            print(f"证券名称: {name}")  # 输出: 证券名称: 平安银行
        """
        if self.xt_trader is None:
            return ''
        security = add_stock_suffix(security)
        # 使用xtdata.get_instrument_detail获取股票名称
        instrument_detail = self.get_instrument_detail(security)
        if instrument_detail is not None and 'InstrumentName' in instrument_detail:
            return instrument_detail['InstrumentName']
        return ''
