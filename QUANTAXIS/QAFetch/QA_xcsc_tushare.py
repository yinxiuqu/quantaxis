# coding: utf-8
#
# xcsc_tushare(湘财证券量化版)数据源适配
# ======================================
# 仿照 QATushare.py 的全部数据获取方法, 客户端换成湘财 xcsc_tushare。
#
# 湘财与标准 tushare pro 的差异(实测):
#   - pro_api 需要 env/server 参数: xcts.pro_api(env='prd', token=..., server='http://116.128.206.39:7172')
#   - daily 字段不同: ts_code, trade_date, open, high, low, close, pre_close,
#     change, pct_chg, volume, amount, adj_pre_close~adj_close(累计复权价),
#     adj_factor(累计因子), avg_price, trade_status —— 无 vol/turnover_rate 等
#   - pro_bar 不可用(服务端拒绝), 日线直接调 pro.daily
#   - adj_* 是累计(后复权风格)价 = close × adj_factor;
#     前复权价 = adj_* / 该股最近交易日的 adj_factor
#   - 免费接口无分笔成交(tick), 老 tushare HTTP 接口(get_today_all 等)不适用
#
# 日期时间格式: 两个方向的转换(与 QATushare / QA_util_* 一致)
#   QA → 湘财: datetime/'YYYY-MM-DD'/'YYYYMMDD' → 湘财参数 'YYYYMMDD'  (见 _qa_date_to_xcsc)
#   湘财 → QA: trade_date 'YYYYMMDD' → date_stamp(cover_time) /
#              date 索引(pd.to_datetime format='%Y%m%d') / date 字符串(QA_util_date_int2str)
#
# ⚠️ token 不写在代码里: 从环境变量 XCSC_TOKEN 或
#    ~/.quantaxis/setting/config.ini [XCSC] 段读取(token/server/env)。
#
import configparser
import os
import time

import pandas as pd

import xcsc_tushare as xcts

from QUANTAXIS.QAUtil import (
    QA_util_date_int2str,
    QA_util_date_stamp,
    QA_util_to_json_from_pandas,
)

_CONFIG_PATH = os.path.expanduser('~/.quantaxis/setting/config.ini')


# ============ 配置 / 客户端 ============

def _load_xcsc_config():
    """读取湘财配置: 环境变量优先, 其次 ~/.quantaxis/setting/config.ini [XCSC]"""
    cfg = configparser.ConfigParser()
    cfg.read(_CONFIG_PATH)
    get = lambda key, fallback=None: os.environ.get(
        'XCSC_' + key.upper()) or cfg.get('XCSC', key, fallback=fallback)
    return {
        'token': get('token'),
        'server': get('server', 'http://116.128.206.39:7172'),
        'env': get('env', 'prd'),
    }


def set_token(token=None):
    """写入/读取湘财 token(存 ~/.quantaxis/setting/config.ini [XCSC])"""
    cfg = configparser.ConfigParser()
    cfg.read(_CONFIG_PATH)
    if token is not None:
        if not cfg.has_section('XCSC'):
            cfg.add_section('XCSC')
        cfg.set('XCSC', 'token', token)
        with open(_CONFIG_PATH, 'w') as f:
            cfg.write(f)
        print('xcsc token 已写入 %s' % _CONFIG_PATH)
    else:
        token = _load_xcsc_config()['token']
        if token is None:
            print('请设置湘财 token: 环境变量 XCSC_TOKEN 或 set_token(token)')
        return token


def get_pro():
    """获取湘财 pro 客户端(失败打印提示并返回 None)"""
    try:
        conf = _load_xcsc_config()
        if not conf['token']:
            print('请设置湘财 token: 环境变量 XCSC_TOKEN 或 ~/.quantaxis/setting/config.ini [XCSC] token')
            return None
        return xcts.pro_api(env=conf['env'], token=conf['token'],
                            server=conf['server'])
    except Exception as e:
        print('xcsc_tushare pro_api 初始化失败: %s' % e)
        return None


# ============ 代码 / 日期格式转换 ============

def _to_ts_code(code):
    """6位代码 -> 湘财 ts_code(000001 -> 000001.SZ / 600000 -> 600000.SH)"""
    code = str(code)
    if '.' in code:  # 已是 ts_code
        return code
    return code + ('.SH' if code.startswith('6') else '.SZ')


def _qa_date_to_xcsc(date):
    """QA 日期 → 湘财参数 'YYYYMMDD'
    兼容输入: datetime/Timestamp/'2026-09-02'/'20260902'/20260902(int)/''/None
    """
    if date is None or str(date) == '':
        return ''
    return str(pd.Timestamp(str(date)).strftime('%Y%m%d'))


def cover_time(date):
    """'20260902'(湘财/tushare 格式) → float 时间戳(与 QATushare.cover_time 一致)"""
    datestr = str(date)[0:8]
    return time.mktime(time.strptime(datestr, '%Y%m%d'))


def _get_subscription_type(if_fq):
    """复权参数归一: '01'/'qfq'->'qfq', '02'/'hfq'->'hfq', '00'/'bfq'->None"""
    if str(if_fq) in ['qfq', '01']:
        return 'qfq'
    elif str(if_fq) in ['hfq', '02']:
        return 'hfq'
    elif str(if_fq) in ['bfq', '00']:
        return None
    return 'qfq'


# ============ 数据获取方法(镜像 QATushare, 全部用湘财 pro 接口) ============

def QA_fetch_get_stock_day(name, start='', end='', if_fq='qfq', type_='pd'):
    """湘财日线(核心方法, 仿 QATushare.QA_fetch_get_stock_day)

    复权口径: '00'/'bfq' 不复权 | '02'/'hfq' 后复权(累计) | '01'/'qfq' 前复权
    返回 DataFrame(date 索引, 含 date 字符串/code/date_stamp/fqtype) 或 json。
    """
    ts_code = _to_ts_code(name)
    start_x = _qa_date_to_xcsc(start)  # QA → 湘财
    end_x = _qa_date_to_xcsc(end)

    def _fetch():
        pro = get_pro()
        if pro is None:
            return None
        df = pro.daily(ts_code=ts_code, start_date=start_x, end_date=end_x)
        time.sleep(0.02)  # 节奏控制
        return df

    data = _fetch()
    if data is None or len(data) == 0:
        return pd.DataFrame() if type_ in ['pd', 'pandas'] else []

    data = data.sort_values('trade_date').reset_index(drop=True)

    # 复权列选择: 湘财 adj_* 为累计价(后复权); qfq 需除以最新因子
    fq = str(if_fq)
    if fq in ['00', 'bfq']:
        pass  # 用原始 open/high/low/close
    else:
        if fq in ['02', 'hfq']:
            cols = {'open': 'adj_open', 'high': 'adj_high',
                    'low': 'adj_low', 'close': 'adj_close'}
        elif fq in ['01', 'qfq']:
            # 前复权 = 累计价 / 该股最近交易日的累计因子
            # 若查询区间未覆盖最新交易日, 需单独查一次最新因子
            latest_factor = float(data['adj_factor'].iloc[-1])
            if end_x < _qa_date_to_xcsc(pd.Timestamp.today()):
                try:
                    pro = get_pro()
                    latest = pro.daily(ts_code=ts_code, start_date='19900101',
                                       end_date=_qa_date_to_xcsc(pd.Timestamp.today()))
                    if latest is not None and len(latest):
                        latest_factor = float(latest['adj_factor'].iloc[-1])
                except Exception:
                    pass
            cols = {'open': 'adj_open', 'high': 'adj_high',
                    'low': 'adj_low', 'close': 'adj_close'}
            for c in cols.values():
                data[c] = data[c].astype(float) / latest_factor
        else:
            raise ValueError('wrong fq flag: %s' % if_fq)
        for k, v in cols.items():
            data[k] = data[v]

    # 湘财 → QA: trade_date('YYYYMMDD') → date_stamp / date / code
    data = data.rename(columns={'trade_date': 'date'})
    data['date_stamp'] = data['date'].apply(lambda x: cover_time(x))
    data['code'] = data['ts_code'].apply(lambda x: str(x)[0:6])
    data['fqtype'] = if_fq

    if type_ in ['json']:
        data['date'] = data['date'].astype(str)
        return QA_util_to_json_from_pandas(data)

    data['date'] = pd.to_datetime(data['date'].astype(str),
                                  format='%Y%m%d', utc=False)
    data = data.set_index('date', drop=False)
    data['date'] = data['date'].apply(
        lambda x: QA_util_date_int2str(int(x.strftime('%Y%m%d'))))
    return data


def QA_fetch_get_stock_adj(code, end=''):
    """复权因子(湘财 adj_factor)

    end 给定时返回该日因子; 否则返回全历史因子。
    """
    pro = get_pro()
    if pro is None:
        return pd.DataFrame()
    end_x = _qa_date_to_xcsc(end)
    if end_x:
        adj = pro.adj_factor(ts_code=_to_ts_code(code), trade_date=end_x)
    else:
        adj = pro.adj_factor(ts_code=_to_ts_code(code),
                             start_date='19900101',
                             end_date=_qa_date_to_xcsc(pd.Timestamp.today()))
    return adj


def QA_fetch_stock_basic():
    """全市场股票列表(湘财 stock_basic 字段更全: 含上市板/退市日期等)"""
    pro = get_pro()
    if pro is None:
        return pd.DataFrame()
    df = pro.stock_basic(exchange='', list_status='L')
    if df is None or len(df) == 0:
        return pd.DataFrame()
    df['code'] = df['ts_code'].apply(lambda x: str(x)[0:6])
    return df


def QA_fetch_get_stock_realtime():
    """全市场当日行情快照(替代老接口 get_today_all)

    湘财无实时接口, 用 pro.daily(trade_date=最新交易日) 收盘后全市场数据。
    返回 json(与 QATushare 输出一致)。
    """
    pro = get_pro()
    if pro is None:
        return []
    today = pd.Timestamp.today()
    data = None
    for back in range(10):  # 向前找最近交易日(处理节假日/盘中)
        day = (today - pd.Timedelta(days=back)).strftime('%Y%m%d')
        try:
            data = pro.daily(trade_date=day)
        except Exception:
            data = None
        if data is not None and len(data):
            break
        time.sleep(0.02)
    if data is None or len(data) == 0:
        return []
    return QA_util_to_json_from_pandas(data)


def QA_fetch_get_stock_info(name):
    """股票基本资料(替代老接口 get_stock_basics)

    name='' 返回全市场; 否则返回单只(按 6 位代码或 ts_code 过滤)。
    """
    df = QA_fetch_stock_basic()
    if df is None or len(df) == 0:
        return None
    if name == '':
        return df
    code = str(name)
    if '.' in code:
        hit = df[df['ts_code'] == code]
    else:
        hit = df[df['code'] == code[0:6]]
    return hit if len(hit) else None


def QA_fetch_get_stock_tick(name, date):
    """分笔成交 —— 湘财免费接口不支持"""
    raise NotImplementedError(
        '湘财 xcsc_tushare 免费接口无分笔成交(tick)数据; '
        '如需 tick 请用 tdx 数据源 QA_fetch_get_stock_tick')


def QA_fetch_get_stock_list():
    """全部股票 ts_code 列表(基于 stock_basic)"""
    df = QA_fetch_stock_basic()
    return list(df.ts_code)


def QA_fetch_get_stock_time_to_market():
    """上市日期 Series(替代老接口 get_stock_basics 的 timeToMarket)

    基于湘财 stock_basic.list_date, index=ts_code, 值 'YYYY-MM-DD'。
    """
    df = QA_fetch_stock_basic()
    if df is None or len(df) == 0:
        return pd.Series()
    s = df.set_index('ts_code')['list_date'].dropna()
    return s.apply(lambda x: QA_util_date_int2str(int(str(x)[0:8])))


def QA_fetch_get_trade_date(end, exchange):
    """交易日历(湘财 trade_cal), 输出与 QATushare 兼容的 message 列表

    Arguments:
        end {str} -- 截止日期('YYYY-MM-DD' 或 'YYYYMMDD')
        exchange {str} -- 交易所('SSE'/'SZSE')
    """
    pro = get_pro()
    if pro is None:
        return []
    end_x = _qa_date_to_xcsc(end)
    # 湘财 trade_cal 单次返回有行数上限, 按年分段拉取再拼接
    parts = []
    start_year = 1990
    end_year = int(end_x[0:4])
    for year in range(start_year, end_year + 1):
        s = '%d0101' % year
        e = '%d1231' % year
        if year == end_year:
            e = end_x
        try:
            p = pro.trade_cal(exchange=exchange, start_date=s, end_date=e)
            if p is not None and len(p):
                parts.append(p)
        except Exception:
            pass
        time.sleep(0.02)
    if not parts:
        return []
    df = pd.concat(parts, ignore_index=True)
    df = df[df['is_open'] > 0].sort_values('cal_date').reset_index(drop=True)
    message = []
    for i in range(len(df)):
        date = QA_util_date_int2str(int(str(df['cal_date'].iloc[i])[0:8]))
        message.append({
            'date': date,
            'num': i + 1,
            'exchangeName': exchange,
            'date_stamp': QA_util_date_stamp(date),
        })
    return message


def QA_fetch_get_lhb(date):
    """龙虎榜(湘财 top_list, 替代老接口 ts.top_list)"""
    pro = get_pro()
    if pro is None:
        return pd.DataFrame()
    return pro.top_list(trade_date=_qa_date_to_xcsc(date))


def QA_fetch_get_stock_money(code, start='', end=''):
    """个股资金流向(湘财 moneyflow)

    Arguments:
        code {str} -- 6位代码或 ts_code
        start/end {str} -- 区间(QA 日期格式)
    """
    pro = get_pro()
    if pro is None:
        return pd.DataFrame()
    return pro.moneyflow(ts_code=_to_ts_code(code),
                         start_date=_qa_date_to_xcsc(start),
                         end_date=_qa_date_to_xcsc(end))


def QA_fetch_get_stock_block():
    """板块数据 —— 湘财免费接口无成分/板块接口

    中证500成分可改用 baostock: QUANTAXIS.QAFetch.QABaostock 或
    save_tdx 中已修复的 baostock 方案。
    """
    raise NotImplementedError(
        '湘财 xcsc_tushare 免费接口无板块/成分数据; '
        '中证500成分可用 baostock query_zz500_stocks()')


# test
if __name__ == '__main__':
    df = QA_fetch_get_stock_day('000001', '2026-08-28', '2026-09-02', if_fq='00')
    print(df.tail(3))
