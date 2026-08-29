# -*- coding: utf-8 -*-
"""
QUANTAXIS 安装验证脚本
运行: python test_installation.py
"""
import sys
print(f"Python版本: {sys.version}")

# 1. 导入 QUANTAXIS
import QUANTAXIS as QA
print(f"QUANTAXIS版本: {QA.__version__}")

# 2. 核心模块导入
from QUANTAXIS import (
    QA_fetch_get_stock_day,
    QA_DataStruct_Stock_day,
    QIFI_Account,
)
print("✅ 核心模块导入成功")

# 3. MongoDB 连接检查
from QUANTAXIS.QAUtil import DATABASE
try:
    DATABASE.stock_day.find_one()
    print("✅ MongoDB连接成功")
except Exception as e:
    print(f"⚠️  MongoDB连接失败: {e}")
