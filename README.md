# QMT量化交易策略框架

这是一个基于国金QMT交易终端的量化交易策略框架，用于实现A股市场的自动化交易策略。目前已实现"一进二低吸"战法策略，支持个性化配置和自动化运行。

## 项目特点

- 基于国金QMT交易终端API开发
- 支持实时行情数据获取和分析
- 提供完整的交易环境和回调函数框架
- 实现模块化设计，易于扩展新策略
- 内置详细日志记录功能
- 支持定时任务和自动化股票池更新

## 系统架构

```
qmt-real/
├── config.py                # 全局配置文件
├── requirements.txt         # 项目依赖
├── trader/                  # 交易核心模块
│   ├── context.py           # 交易上下文
│   ├── trader.py            # 交易接口封装
│   ├── data.py              # 数据处理模块
│   ├── utils.py             # 工具函数
│   ├── logger.py            # 日志模块
│   ├── constant.py          # 常量定义
│   └── anis.py              # 终端颜色支持
├── strategys/               # 策略模块目录
│   └── 一进二低吸战法/      # 一进二低吸战法策略
│       ├── main.py          # 策略入口
│       ├── strategy.py      # 策略核心逻辑
│       ├── config.py        # 策略参数配置
│       ├── indicator.py     # 技术指标计算
│       └── stock_pool.py    # 股票池管理
└── xtquant/                 # QMT接口库(本地依赖)
```

## 安装指南

### 前置条件

- 安装并登录国金QMT交易终端
- Python 3.8或更高版本
- Windows操作系统

### 安装步骤

1. 克隆代码仓库到本地：
```bash
git clone <仓库地址> qmt-real
cd qmt-real
```

2. 创建并激活虚拟环境：
```bash
python -m venv .venv
.venv\Scripts\activate
```

3. 安装依赖包：
```bash
pip install -r requirements.txt
```

4. 复制并修改配置文件：
```bash
cp config.example.py config.py
```
   然后编辑`config.py`文件，填入您的QMT账号和安装路径。

## 使用方法

### 配置策略

1. 修改根目录下的`config.py`文件，配置QMT账号和安装路径：
```python
ACCOUNT_ID = "你的QMT资金账号"  # 资金账号
MINI_QMT_PATH = "D:\国金QMT交易端模拟\userdata_mini"  # QMT客户端安装路径
```

2. 根据需要修改策略专属配置（`strategys/一进二低吸战法/config.py`）。

### 启动策略

确保QMT交易终端已登录，然后运行：

```bash
python strategys/一进二低吸战法/main.py
```

### 策略说明

目前项目实现了"一进二低吸战法"策略，该策略主要针对涨停后的低吸机会，通过MACD指标的变化来捕捉买入和卖出时机。详细说明请参考 [一进二低吸战法说明文档](strategys/一进二低吸战法/README.md)。

## 开发新策略

如需开发新策略，建议按照以下步骤进行：

1. 在`strategys`目录下创建新的策略文件夹
2. 参考现有策略的结构，创建对应的`main.py`、`strategy.py`、`config.py`等文件
3. 实现策略的选股、交易信号生成和风控逻辑
4. 通过继承并重写基类方法来实现自定义功能

## 项目依赖

- pandas, numpy: 数据处理和分析
- pytdx, baostock: 市场数据获取
- requests: HTTP请求支持
- tqdm: 进度条显示
- python-dateutil, pytz: 日期时间处理
- xtquant: QMT交易API (本地依赖)

## 注意事项

- 策略运行时需保持QMT交易终端登录状态
- 建议在模拟盘测试策略后再应用于实盘交易
- 请遵守证券市场交易规则和交易所相关规定
- 量化交易存在风险，请根据自身风险承受能力进行配置 