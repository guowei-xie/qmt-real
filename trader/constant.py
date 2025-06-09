# QMT持仓字段映射
QMT_POSITIONS_FIELD_MAPPING = {
    '账号类型': 'account_type',
    '资金账号': 'account_id',
    '股票代码': 'stock_code',
    '持仓数量': 'volume',
    '开仓价格': 'open_price',
    '可用数量': 'can_use_volume',
    '持仓市值': 'market_value',
    '冻结数量': 'frozen_volume',
    '在途股份': 'on_road_volume',
    '昨夜拥股': 'yesterday_volume',
    '成本价格': 'avg_price',
    '多空方向': 'direction',
}
# QMT账户字段映射
QMT_ASSET_FIELD_MAPPING = {
    '账号类型': 'account_type',
    '资金账号': 'account_id',
    '总资产': 'total_asset',
    '可用金额': 'cash',
    '冻结金额': 'frozen_cash',
    '持仓市值': 'market_value'
}
# QMT委托字段映射
QMT_ORDERS_FIELD_MAPPING = {
    '账号类型': 'account_type',
    '资金账号': 'account_id',
    '股票代码': 'stock_code',
    '订单编号': 'order_id',
    '柜台合同编号': 'order_sysid',
    '报单时间': 'order_time',
    '委托类型': 'order_type',
    '委托数量': 'order_volume',
    '报价类型': 'price_type',
    '委托价格': 'price',
    '成交数量': 'traded_volume',
    '成交均价': 'traded_price',
    '委托状态': 'order_status',
    '委托状态描述': 'status_msg',
    '策略名称': 'strategy_name',
    '委托备注': 'order_remark',
    '多空方向': 'direction',
    '交易操作': 'offset_flag'
}
# QMT成交字段映射
QMT_TRADES_FIELD_MAPPING = {
    '账号类型': 'account_type',
    '资金账号': 'account_id',
    '证券代码': 'stock_code',
    '委托类型': 'order_type',
    '成交编号': 'traded_id',
    '成交时间': 'traded_time',
    '成交均价': 'traded_price',
    '成交数量': 'traded_volume',
    '成交金额': 'traded_amount',
    '订单编号': 'order_id',
    '柜台合同编号': 'order_sysid',
    '策略名称': 'strategy_name',
    '委托备注': 'order_remark',
    '多空方向': 'direction',
    '交易操作': 'offset_flag'
}
