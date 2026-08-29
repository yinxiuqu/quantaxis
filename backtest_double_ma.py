# -*- coding: utf-8 -*-
"""
双均线策略回测（QUANTAXIS QIFI 账户体系）
=========================================
标的 : 平安银行 000001（A股）
周期 : 2023-01-01 ~ 2024-12-31 日线（数据自动入库 MongoDB）
策略 : MA5 上穿 MA20 → 次日开盘全仓买入；MA5 下穿 MA20 → 次日开盘清仓
账户 : QIFI_Account，初始资金 100,000 元（离线模式，不写数据库）
基准 : 同期买入持有
运行 : python backtest_double_ma.py
"""
import warnings
warnings.filterwarnings('ignore')

import pandas as pd
import matplotlib
matplotlib.use('Agg')  # 无界面环境
import matplotlib.pyplot as plt

import QUANTAXIS as QA
from QUANTAXIS.QIFI.QifiAccount import QIFI_Account, ORDER_DIRECTION
from QUANTAXIS.QAUtil import DATABASE

CODE = '000001'
START, END = '2023-01-01', '2024-12-31'
INIT_CASH = 100000
FAST, SLOW = 5, 20


def load_data():
    """优先从 MongoDB 读，无数据则从通达信拉取并入库"""
    df = QA.QA_fetch_stock_day(code=CODE, start=START, end=END, format='pd')
    if df is None or len(df) == 0:
        print(f'[数据] MongoDB 无数据，从通达信拉取 {START}~{END} ...')
        df = QA.QA_fetch_get_stock_day(package='tdx', code=CODE,
                                       start=START, end=END, if_fq='00')
        DATABASE.stock_day.insert_many(df.to_dict('records'))
        df = QA.QA_fetch_stock_day(code=CODE, start=START, end=END, format='pd')
    return df.sort_index()


def main():
    # ========== 1. 数据 ==========
    df = load_data()
    print(f'[数据] {CODE} 共 {len(df)} 个交易日 ({df.index[0].date()} ~ {df.index[-1].date()})')

    # ========== 2. 指标与信号 ==========
    close = df['close']
    ma_fast = close.rolling(FAST).mean()
    ma_slow = close.rolling(SLOW).mean()
    above = (ma_fast > ma_slow).astype(int)      # 1=金叉区(持多) 0=死叉区(空仓)
    # 信号在次日开盘执行，避免未来函数

    # ========== 3. 回测 ==========
    acc = QIFI_Account(username='double_ma', password='test', model='BACKTEST',
                       init_cash=INIT_CASH, nodatabase=True)
    acc.initial()
    print(f'[账户] 初始资金 {INIT_CASH:,} 元，开始回测...')

    pending = None              # 待执行指令: 'BUY' / 'SELL'
    trades = []                 # 成交记录
    eq_curve, bh_curve = [], []
    hold_shares = 0
    buyhold_shares = 0
    first_close = None

    for i, (dt, bar) in enumerate(df.iterrows()):
        date_str = str(dt)[:10]

        # ① 开盘：执行昨日信号（用当日开盘价成交）
        if pending == 'SELL':
            pos = acc.get_position(CODE)
            if pos.volume_long > 0:
                order = acc.send_order(CODE, pos.volume_long, bar['open'],
                                       ORDER_DIRECTION.SELL, datetime=date_str)
                if order:
                    acc.make_deal(order)
                    trades.append({'date': date_str, 'type': '卖出',
                                   'price': bar['open'], 'amount': order['volume'],
                                   'equity': acc.balance})
        elif pending == 'BUY':
            avail = acc.available
            amount = int(avail / (bar['open'] * 100)) * 100      # A股整手=100股
            if amount >= 100:
                order = acc.send_order(CODE, amount, bar['open'],
                                       ORDER_DIRECTION.BUY, datetime=date_str)
                if order:
                    acc.make_deal(order)
                    trades.append({'date': date_str, 'type': '买入',
                                   'price': bar['open'], 'amount': order['volume'],
                                   'equity': acc.balance})
        pending = None

        # ② 收盘：更新持仓市值
        acc.on_price_change(CODE, bar['close'])

        # ③ 收盘后计算今日信号（次日执行）
        if i >= SLOW and above.iloc[i] != above.iloc[i - 1]:
            pending = 'BUY' if above.iloc[i] == 1 else 'SELL'

        # ④ 每日结算 + 记录净值
        acc.settle()
        eq_curve.append({'date': dt, 'equity': acc.balance})

        # ⑤ 基准：买入持有（首个交易日按收盘价全仓买入）
        if first_close is None:
            first_close = bar['close']
            buyhold_shares = int(INIT_CASH / (first_close * 100)) * 100
        bh_equity = buyhold_shares * bar['close'] + (INIT_CASH - buyhold_shares * first_close)
        bh_curve.append({'date': dt, 'equity': bh_equity})

    eq = pd.DataFrame(eq_curve).set_index('date')
    bh = pd.DataFrame(bh_curve).set_index('date')

    # ========== 4. 绩效统计 ==========
    final_equity = eq['equity'].iloc[-1]
    total_ret = final_equity / INIT_CASH - 1
    days = len(eq)
    annual_ret = (final_equity / INIT_CASH) ** (252 / days) - 1

    def max_drawdown(series):
        peak = series.cummax()
        return ((series - peak) / peak).min()

    mdd = max_drawdown(eq['equity'])
    bh_ret = bh['equity'].iloc[-1] / INIT_CASH - 1
    bh_mdd = max_drawdown(bh['equity'])

    buys = [t for t in trades if t['type'] == '买入']
    sells = [t for t in trades if t['type'] == '卖出']
    # 胜率：按买卖配对（简化：按每笔卖出相对最近买入的价格差）
    wins = 0
    for s in sells:
        prior_buys = [b for b in buys if b['date'] < s['date']]
        if prior_buys:
            b = prior_buys[-1]
            if s['price'] > b['price']:
                wins += 1
    win_rate = wins / len(sells) if sells else 0

    print('\n' + '=' * 52)
    print('  双均线策略回测结果 (000001 平安银行, 2023~2024)')
    print('=' * 52)
    print(f'  初始资金        : {INIT_CASH:,} 元')
    print(f'  最终权益        : {final_equity:,.2f} 元')
    print(f'  策略总收益率    : {total_ret * 100:.2f}%   (年化 {annual_ret * 100:.2f}%)')
    print(f'  策略最大回撤    : {mdd * 100:.2f}%')
    print(f'  买入持有收益率  : {bh_ret * 100:.2f}%   (最大回撤 {bh_mdd * 100:.2f}%)')
    print(f'  超额收益        : {(total_ret - bh_ret) * 100:.2f}%')
    print(f'  交易次数        : {len(trades)}  (买 {len(buys)} / 卖 {len(sells)})')
    print(f'  卖出胜率        : {win_rate * 100:.1f}%')
    print('=' * 52)

    # ========== 5. 画图 ==========
    plt.rcParams['font.sans-serif'] = ['Noto Sans CJK SC', 'WenQuanYi Micro Hei',
                                       'WenQuanYi Zen Hei', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(eq.index, eq['equity'] / INIT_CASH, label='双均线策略', linewidth=2, color='#d62728')
    ax.plot(bh.index, bh['equity'] / INIT_CASH, label='买入持有基准', linewidth=1.5, color='#1f77b4', alpha=0.8)

    for t in trades:
        color = '#d62728' if t['type'] == '买入' else '#2ca02c'
        ax.scatter(pd.Timestamp(t['date']), t['equity'] / INIT_CASH,
                   marker='^' if t['type'] == '买入' else 'v', color=color, s=40, zorder=5)

    ax.axhline(1.0, color='gray', linestyle='--', linewidth=0.8)
    ax.set_title(f'双均线策略回测净值曲线 (MA{FAST}/MA{SLOW} · {CODE} · {START}~{END})')
    ax.set_xlabel('日期')
    ax.set_ylabel('净值 (初始=1.0)')
    ax.legend(loc='best')
    ax.grid(alpha=0.3)
    fig.tight_layout()
    out_png = f'/home/yinxiuqu/quantaxis/backtest_double_ma_{CODE}.png'
    fig.savefig(out_png, dpi=130)
    print(f'[图表] 已保存: {out_png}')


if __name__ == '__main__':
    main()
