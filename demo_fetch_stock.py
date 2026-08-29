# -*- coding: utf-8 -*-
"""
QUANTAXIS 实战示例1：数据获取 + 指标计算
获取平安银行(000001)日线 → 计算MA20 → 保存到MongoDB
运行: python demo_fetch_stock.py
"""
import QUANTAXIS as QA
from QUANTAXIS.QAIndicator.indicators import QA_indicator_MA

print("=" * 50)
print("示例1: 从通达信获取平安银行日线数据")
print("=" * 50)

# 1. 从通达信数据源拉取（自动入库 MongoDB）
df = QA.QA_fetch_get_stock_day(
    package='tdx',       # 数据源: 'tdx'通达信 / 'tushare' / 'baostock'
    code='000001',
    start='2024-01-01',
    end='2024-12-31',
    if_fq='00',        # '00'不复权（通达信实时源不支持复权）/ '01'前复权(tushare)
)
print(f"获取到 {len(df)} 条日线数据")
print(df.head(3))

# 2. 构造 QA 数据结构
data = QA.QA_DataStruct_Stock_day(df)
print(f"\n数据结构: {len(data)} 个交易日, 列: {list(data.data.columns)}")

# 3. 计算 MA20 指标
ma20 = QA_indicator_MA(data, 20)
print(f"\nMA20 最后5个值:\n{ma20.tail(5)}")

# 4. 简单统计: 收盘价在 MA20 上方的天数
above = int((data.close > ma20['MA20']).sum())
print(f"\n2024年收盘价在 MA20 之上的天数: {above} / {len(data)}")

# 5. 手动入库 MongoDB + 从 MongoDB 回读（QUANTAXIS 2.x 中拉取与入库分离）
from QUANTAXIS.QAUtil import DATABASE

# 5.1 入库（stock_day 集合；df 自带 date 列，直接转记录）
docs = df.to_dict('records')
DATABASE.stock_day.insert_many(docs)
print(f"\n已入库 MongoDB stock_day: {len(docs)} 条")

# 5.2 从 MongoDB 查询（推荐路径：数据只拉一次，之后全部走本地库）
df_db = QA.QA_fetch_stock_day(
    code='000001',
    start='2024-01-01',
    end='2024-12-31',
    format='pd',
)
print(f"从 MongoDB 回读: {len(df_db)} 条, 列: {list(df_db.columns)}")
print(df_db.head(2))
