# QUANTAXIS 学习指南（本机实战版）

> 本文档基于本机（/home/yinxiuqu）实际安装验证过程编写，涵盖项目分析、安装步骤、核心用法与学习路径。
> 更新时间：2026-08-26 | 版本：2.1.0-alpha2（官方 master）

---

## 一、QUANTAXIS 是什么？

**QUANTAXIS** 是一个国产开源的**量化金融策略框架**，由 yutiansut（罗元）发起，2016 年开源至今，GitHub 上约 6k+ stars。它定位为"股票/期货/自定义市场 数据/回测/模拟/交易/可视化 纯本地一站式解决方案"。

### 核心特点

| 特点 | 说明 |
|------|------|
| 🆓 免费开源 | MIT 协议，代码全开放，无商业收费 |
| 🗄️ 数据本地化 | 以 **MongoDB** 为核心存储，数据全部落本地，支持增量更新 |
| 🌐 多市场 | A股、期货、期权、港股、美股、数字货币、自定义市场 |
| 📡 多数据源 | 通达信(TDX)、Tushare、同花顺、东方财富、万得（需自行配置） |
| 📊 模块化 | 11 大模块，数据、回测、因子、账户、调度各司其职 |
| ⚡ 高性能 | Rust 账户引擎(QARS2) 100x 加速、零拷贝数据传输(QADataSwap) |
| 🧪 学术友好 | 内置 QAFactor 因子研究套件（alphalens/pyfolio 生态） |

### 与其他框架的定位差异

| 框架 | 定位 | 语言 | 特点 |
|------|------|------|------|
| **QUANTAXIS** | 一站式全流程 | Python | 数据+回测+模拟+因子+Web，本地化 |
| vn.py (vnpy) | 实盘交易为主 | Python | 对接 CTP 等柜台，实盘强 |
| Backtrader | 纯回测 | Python | 轻量回测，数据要自己接 |
| Qlib | 机器学习量化 | Python | 微软出品，AI 选股研究 |
| Zipline | 回测 | Python | Quantopian 遗产，A股支持弱 |

**一句话**：QUANTAXIS 的强项是**数据管道 + 全流程闭环**——从行情采集入库，到策略回测，到模拟交易，到 Web 可视化，一条龙且全部本地可控。

---

## 二、核心架构（11 大模块）

```
                        ┌─────────────────────────────────┐
                        │        QAWebServer (Web中台)     │
                        │        QASchedule (任务调度)      │
                        └──────────────┬──────────────────┘
                                       │
┌──────────────┐    ┌──────────────────┼──────────────────┐
│  QASU/QAFetch │───▶│                 QAStrategy          │
│  (数据采集存储) │    │              (策略回测/实盘)         │
└──────┬───────┘    └──────────┬──────────────────────────┘
       │                       │
       ▼                       ▼
┌──────────────────────────────────────────────────────┐
│                MongoDB (数据仓库)                       │
│  股票日线/分钟线/期货/Tick/财务/因子/账户/交易记录          │
└──────────────────────────────────────────────────────┘
       ▲                       ▲
       │                       │
┌──────┴───────┐    ┌──────────┴──────────┐
│  QAData      │    │  QIFI / QAMarket    │
│  (数据结构)   │    │  (统一账户体系)      │
│  QAIndicator │    │  QAFactor (因子)    │
│  (指标计算)   │    │                     │
│  QAEngine    │    │  QAPubSub (消息总线) │
│  (并发引擎)   │    │                     │
└──────────────┘    └─────────────────────┘
```

### 模块逐一解析

| 模块 | 全名 | 职责 | 类比 |
|------|------|------|------|
| **QASU** | QUANTAXIS Save Unit | 数据采集入库的"调度单元"，负责把数据源的数据落库 | 数据管道 |
| **QAFetch** | QUANTAXIS Fetch | 统一数据获取 API：从 MongoDB 或数据源直接拉数据 | 数据读取层 |
| **QAUtil** | QUANTAXIS Util | 工具库：交易日历、交易时间、复权处理、市场识别、DataFrame 转换 | 瑞士军刀 |
| **QAData** | QUANTAXIS Data | 多标的多市场数据结构，回测/实时的内存数据库 | 数据容器 |
| **QAIndicator** | QUANTAXIS Indicator | 指标计算：MA/EMA/MACD/KDJ/BOLL 等，支持自定义与全市场批量 | 指标库 |
| **QAStrategy** | QUANTAXIS Strategy | CTA/套利回测引擎，事件驱动策略框架 | 回测引擎 |
| **QIFI** | QUANTAXIS IFI | 统一账户体系（含 QIFIAccount 账户、QAPosition 仓位管理） | 账户系统 |
| **QAMarket** | QUANTAXIS Market | 市场预制：期货/股票/数字货币的 tick、保证金、手续费模型 | 市场模型 |
| **QAFactor** | QUANTAXIS Factor | 因子研究套件：单因子入库、因子测试、因子合并 | 因子实验室 |
| **QAEngine** | QUANTAXIS Engine | 线程/进程基类、异步计算、分布式计算 agent | 并发框架 |
| **QAPubSub** | QUANTAXIS PubSub | 基于 MQ 的消息队列，任务分发、订单流 | 消息总线 |
| **QAWebServer** | QUANTAXIS WebServer | tornado 的 Web 服务套件 | Web 中台 |

### 关键设计理念

1. **一切皆 DataFrame**：核心数据统一用 pandas DataFrame，上手门槛低
2. **数据与逻辑分离**：采集(QASU) → 存储(MongoDB) → 读取(QAFetch) → 计算(QAData/QAIndicator) → 决策(QAStrategy) → 账户(QIFI)
3. **QIFI 统一账户**：一套账户代码逻辑同时用于回测、模拟、实盘，避免"回测赚钱实盘亏钱"的代码漂移
4. **纯本地优先**：不依赖云端，数据主权在自己手里

---

## 三、本机安装实录

### 3.1 本机环境

| 项目 | 状态 |
|------|------|
| 操作系统 | Linux（Deepin，Ubuntu 系） |
| Python | anaconda3（base 3.8.8），新建专用环境 **qa**（Python 3.11.16） |
| MongoDB | ✅ 已安装并运行（mongod.service，systemd 托管，端口 27017） |
| QUANTAXIS 源码 | ~/quantaxis（已更新到官方 master，2025 年最新） |
| 数据源 | pytdx（通达信，免费）；tushare（需 token） |

> ⚠️ 注意：QUANTAXIS 2.x **要求 Python ≥ 3.9**，base 环境的 3.8.8 不满足，所以创建了独立 conda 环境。

### 3.2 安装步骤（本机已完成，供其他机器参考）

```bash
# 1. 准备 Python 3.9+ 环境（conda 示例）
conda create -n qa python=3.11 -y
conda activate qa

# 2. 安装 MongoDB（Debian/Ubuntu 系）
sudo systemctl status mongod    # 检查是否已运行

# 3. 克隆源码（或 pip install quantaxis，但 PyPI 上稳定版停留在 1.10.19，
#    建议用源码装最新 2.x）
git clone https://github.com/QUANTAXIS/QUANTAXIS.git
cd QUANTAXIS
pip install -e .                # 开发模式安装，改源码即生效

# 4. Rust 组件（本机实测全打通 ✅）
#    ✅ qars（Rust账户引擎 QARS）从源码编译安装：
#       仓库是 yutiansut/qa-rs（不是 qars2/qars3，PyPI 上没有）
git clone https://github.com/yutiansut/qa-rs.git
cd qa-rs
pip install setuptools-rust
#    需要 Rust nightly-2025-01-15（rust-toolchain.toml 指定）+ 系统 OpenSSL 头文件
#    （本机用 conda 环境的 OpenSSL：export OPENSSL_DIR=~/anaconda3/envs/qa）
#    构建隔离环境缺 setuptools_rust，需 --no-build-isolation；装 orjson/empyrical
pip install --no-build-isolation .
#    因 QUANTAXIS 桥接层写死 from qars3 import ...，需建 qars3 shim：
echo "from qars import QA_QIFIAccount" > site-packages/qars3.py
#    ✅ qadataswap（零拷贝传输）也需从源码编译：
git clone https://github.com/yutiansut/qadataswap.git
cd qadataswap/src/python
pip install pybind11 cmake
#    需先修复 2 处兼容问题（见下方"本机实测修复"），然后：
pip install --no-build-isolation .
```

> 💡 国内网络提示（本机实测）：
> - 清华 pypi/anaconda 镜像 **2026 年已失效（403/超时）**，本机已改用 **阿里云镜像**：`https://mirrors.aliyun.com/pypi/simple/`（写入 `~/.config/pip/pip.conf`）
> - conda 源已从清华改回官方（`~/.condarc`，备份为 `~/.condarc.bak_*`）
> - PyPI 上稳定版 quantaxis 停在 1.10.19（2021 年），**强烈建议源码安装最新 2.x**
> - Rust 工具链用字节跳动镜像安装：`RUSTUP_DIST_SERVER=https://rsproxy.cn sh rustup-init.sh -y`；cargo 源配 `~/.cargo/config.toml`（rsproxy-sparse）
> - ⚠️ 老 CPU 机器装 polars 会崩（需要 avx2/fma/bmi2 指令集），改用 `pip install "polars[rtcompat]"`

### 3.3 关键目录约定

| 路径 | 作用 |
|------|------|
| `~/.quantaxis/setting/config.ini` | MongoDB 连接配置（`[MONGODB] uri = mongodb://localhost:27017`） |
| `~/.quantaxis/log` | 运行日志 |
| `~/.quantaxis/strategy` | 策略存放目录 |
| MongoDB 数据库 `stock_day` / `stock_min` 等 | QA 系列集合（数据落库后按 `QA_` 前缀库名存放） |

---

## 四、快速上手（核心 API 速查）

### 4.1 数据获取（QAFetch）

```python
import QUANTAXIS as QA

# ① 从 MongoDB 查询已入库数据（推荐，最快）
df = QA.QA_fetch_stock_day(code='000001', start='2024-01-01', end='2024-12-31', format='pd')

# ② 从数据源实时拉取（2.x 中【拉取与入库分离】，需要 package 参数）
df = QA.QA_fetch_get_stock_day(
    package='tdx',       # 数据源: 'tdx'通达信 / 'tushare' / 'baostock'
    code='000001', start='2024-01-01', end='2024-12-31',
    if_fq='00'           # '00'不复权 '01'前复权（注: tdx 实时源不支持复权）
)

# ③ 手动入库 MongoDB（拉取后自行决定是否存库）
from QUANTAXIS.QAUtil import DATABASE
DATABASE.stock_day.insert_many(df.to_dict('records'))

# ④ 股票列表 / 全市场某日
stocks = QA.QA_fetch_stock_list()              # 全部股票列表
day_all = QA.QA_fetch_stock_full(date='2024-10-25')

# ⑤ 期货 / 分钟线
df_f = QA.QA_fetch_get_future_day(package='tdx', code='IF2512', start='2024-01-01', end='2024-01-31')
df_m = QA.QA_fetch_get_stock_min(package='tdx', code='000001', start='2024-10-01 09:30:00', end='2024-10-25 15:00:00', level='5min')
```

### 4.2 数据结构（QAData）

```python
data = QA.QA_DataStruct_Stock_day(df)   # 包一层，获得高级能力
data.data                              # 内部 DataFrame
data.close                             # 收盘价序列（2.x 是属性，不是 get_close()）
len(data)                              # 交易日数量
```

### 4.3 指标计算（QAIndicator）

```python
# 注意: 2.x 中指标模块路径是 QAIndicator.indicators（不是老的 QT_Indicator）
from QUANTAXIS.QAIndicator.indicators import QA_indicator_MA, QA_indicator_MACD

ma20 = QA_indicator_MA(data, 20)      # 20日均线（返回 DataFrame，列名 MA20）
macd = QA_indicator_MACD(data)        # 添加MACD三个指标值：DIF，DEA和MACD 
```

### 4.4 回测（QAStrategy，QIFI 账户）

```python
from QUANTAXIS.QIFI import QIFI_Account
from QUANTAXIS.QAFetch import QA_fetch_get_stock_day

# 建账户（10万本金模拟炒股）
account = QIFI_Account(username='demo', password='demo',
                       model='stock', init_cash=100000)

# 策略循环：每天根据信号买卖
for date in trading_dates:
    account.receive_quotation(data_slice)     # 喂行情
    if signal == 'buy':
        account.send_order(code='000001', price=..., amount=100,
                           towards=QA.ORDER_DIRECTION.BUY)
    account.settle()                          # 结算
```

### 4.5 常用 CLI 命令

```bash
quantaxis        # 交互式命令入口（查看帮助）
qawebserver      # 启动 Web 服务
qarun            # 运行策略
```

---

## 五、完整示例：跑通一只股票

```python
"""最小可用示例：获取平安银行日线 → 计算MA20 → 入库 → 回读
完整可运行脚本: ~/quantaxis/demo_fetch_stock.py（本机已实测通过）
"""
import QUANTAXIS as QA
from QUANTAXIS.QAIndicator.indicators import QA_indicator_MA

# 1. 拉数据（通达信源；注意 2.x 必须带 package 参数）
df = QA.QA_fetch_get_stock_day(package='tdx', code='000001',
                               start='2024-01-01', end='2024-12-31', if_fq='00')
print(f"获取到 {len(df)} 条日线")

# 2. 构造数据结构 + 算指标
data = QA.QA_DataStruct_Stock_day(df)
ma20 = QA_indicator_MA(data, 20)

# 3. 简单策略统计：收盘价在 MA20 之上的天数
above = (data.close > ma20['MA20']).sum()
print(f"MA20 上方天数: {above} / {len(data)}")

# 4. 入库 + 从 MongoDB 回读（拉取与入库分离，回读走 QA_fetch_stock_day）
from QUANTAXIS.QAUtil import DATABASE
DATABASE.stock_day.insert_many(df.to_dict('records'))
df_db = QA.QA_fetch_stock_day(code='000001', start='2024-01-01', end='2024-12-31', format='pd')
print(f"从 MongoDB 回读: {len(df_db)} 条")
```

**本机实测输出**：242 条日线 / MA20 上方 124 天 / MongoDB 回读 242 条 ✅

> ⚠️ 本机实测修复了 2 处 pandas 2.x 兼容 bug（源码 `~/quantaxis/QUANTAXIS/QAData/base_datastruct.py`）：
> 1. `self.data.index.remove_unused_levels()` 在普通 Index 上不存在 → 加 `isinstance(x, pd.MultiIndex)` 判断
> 2. `index` property 中同样的调用 → 同样修复

---

## 六、学习路径建议（从入门到进阶）

### 阶段一：跑通（1-2 天）
- [x] 安装环境（已完成 ✅）
- [ ] 运行上面「完整示例」拿到第一份数据
- [ ] 用 pandas/matplotlib 画一张 K 线图（`data.plot()` 或自行绘图）
- [ ] 阅读官方 quickstart：`~/quantaxis/doc/getting-started/quickstart.md`

### 阶段二：数据工程（2-3 天）
- [ ] 批量下载全市场日线：`QA_fetch_get_stock_day` 循环或 QASU 批量任务
- [ ] 理解 MongoDB 集合结构：`mongosh` 查看 `stock_day`、`stock_list`
- [ ] 配置 tushare token（`QA_fetch_get_stock_day(package='tushare')`）
- [ ] 学会增量更新（避免全量重复下载）

### 阶段三：策略与回测（1 周）
- [ ] 阅读官方回测文档：`~/quantaxis/doc/user-guide/backtesting.md`
- [ ] 实现双均线策略回测（MA5 上穿 MA20 买入，下穿卖出）
- [ ] 学会 QIFI 账户的资金/持仓/盈亏查询
- [ ] 复现官方 examples：`~/quantaxis/examples/qifiaccountexample.py`

### 阶段四：进阶（长期）
- [x] QADataSwap（零拷贝传输）✅ 本机已编译启用（版本 0.1.0，Pandas↔Polars↔Arrow）
- [x] **QARS Rust 账户引擎 ✅ 已编译启用**（qars 0.0.13，源码 yutiansut/qa-rs + qars3 shim，has_qars_support=True）
- [ ] QAFactor 因子研究：单因子入库、IC 分析（结合 alphalens）
- [ ] QAEngine 并发：全市场扫描
- [ ] QAWebServer + QASchedule：构建自己的量化中台
- [ ] QARS2 账户引擎：⚠️ 不可装（qars3 包不存在于 PyPI/GitHub，官方文档夸大）
- [ ] 阅读 QABook（官方 PDF 文档）：https://github.com/QUANTAXIS/QUANTAXIS/releases/download/latest/quantaxis.pdf

### 阶段五：实盘对接（谨慎！）
- [ ] 模拟盘跑通 1-3 个月再考虑
- [ ] 了解 QAMarket 市场预制与手续费模型
- [ ] 风险控制：仓位管理（QAPosition）、止损止盈

---

## 七、资源导航

| 资源 | 地址 |
|------|------|
| 官方 GitHub | https://github.com/QUANTAXIS/QUANTAXIS |
| 作者仓库 | https://github.com/yutiansut/quantaxis |
| 官方文档（本地） | `~/quantaxis/doc/`（38 篇 md，含安装/快速入门/回测/实盘/FAQ） |
| QABook PDF | https://github.com/QUANTAXIS/QUANTAXIS/releases/download/latest/quantaxis.pdf |
| 本机示例代码 | `~/quantaxis/examples/` |
| 官方论坛 | https://forum.quantaxis.cn |
| QQ 群 | 563280068 |
| 本机旧策略（vnpy 风格，可参考） | `~/strategies/` |

---

## 八、常见坑（FAQ）

| 问题 | 解决方案 |
|------|----------|
| `ImportError: No module named 'QUANTAXIS'` | 确认激活了 qa 环境：`conda activate qa` |
| MongoDB 连接失败 | `sudo systemctl start mongod`；检查 `~/.quantaxis/setting/config.ini` |
| `AttributeError: remove_unused_levels` | pandas 2.x 兼容 bug，已修复（见第五章） |
| `QA_fetch_get_stock_day() missing package` | 2.x API 必须显式传 `package='tdx'/'tushare'` |
| `No module named 'QUANTAXIS.QT_Indicator'` | 2.x 指标路径为 `QUANTAXIS.QAIndicator.indicators` |
| 通达信源返回 None（复权） | tdx 实时源不支持复权，用 `if_fq='00'`；复权请用 tushare |
| 清华 pip/conda 镜像报 403 | 已换阿里云/官方源（见第三章） |
| 数据拉取后 MongoDB 没数据 | 2.x 拉取与入库分离，需手动 `insert_many` 或走 QASU |
| 首次下载全市场很慢 | 用 QASU 批量 + 增量更新，先只下需要的股票 |

---

*本文档随学习进度持续更新。祝你量化愉快！📈*
