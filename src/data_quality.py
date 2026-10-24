"""
data_quality.py
OHLCV 数据质量校验层。

设计原则：
- 只做"检测与记录"，不擅自修改、填充或删除数据（重复时间戳已在抓取层
  去重）。缺口保留原样，指标层自然产生 NaN 并被信号层跳过；
  用前值硬填补缺失K线等于伪造数据，本项目明确不做。
- 每个标的输出一行校验报告（dict），由 main.py 汇总保存为 CSV，
  并把关键问题写入运行日志，使数据问题可见、可追溯，而不是静默喂给
  回测引擎后变成无法解释的结果偏差。
"""

import pandas as pd

from src.config import DATA_QUALITY_CONFIG
from src.common import get_logger

logger = get_logger("data_quality")


def validate_ohlcv(df: pd.DataFrame, symbol: str, market: str, cfg=None) -> dict:
    """
    对单个标的的 OHLCV DataFrame 做质量校验。
    df 需包含列：datetime, open, high, low, close, volume（按时间升序）。

    返回报告 dict，字段包括：
      symbol, market, num_rows, start_date, end_date,
      duplicate_timestamps, non_monotonic_timestamps,
      ohlc_logic_violations, nonpositive_price_rows, negative_volume_rows,
      zero_volume_rows, extreme_move_rows, max_abs_daily_return_pct,
      gap_events, last_bar_may_be_incomplete, issue_count

    issue_count 为上述问题计数的汇总（不含 zero_volume 与
    last_bar_may_be_incomplete 这类提示性标记）。
    """
    cfg = cfg or DATA_QUALITY_CONFIG
    report = {
        "symbol": symbol,
        "market": market,
        "num_rows": 0,
        "start_date": None,
        "end_date": None,
        "duplicate_timestamps": 0,
        "non_monotonic_timestamps": False,
        "ohlc_logic_violations": 0,
        "nonpositive_price_rows": 0,
        "negative_volume_rows": 0,
        "zero_volume_rows": 0,
        "extreme_move_rows": 0,
        "max_abs_daily_return_pct": None,
        "gap_events": 0,
        "last_bar_may_be_incomplete": False,
        "issue_count": 0,
    }

    if df is None or len(df) == 0:
        report["issue_count"] = 1
        logger.warning(f"[{market}] {symbol} 数据为空，无法校验。")
        return report

    d = df.sort_values("datetime").reset_index(drop=True)
    report["num_rows"] = len(d)
    report["start_date"] = str(d["datetime"].iloc[0])
    report["end_date"] = str(d["datetime"].iloc[-1])

    # --- 时间戳：重复与单调性 ---
    report["duplicate_timestamps"] = int(d["datetime"].duplicated().sum())
    report["non_monotonic_timestamps"] = bool(
        not d["datetime"].is_monotonic_increasing
    )

    # --- OHLC 逻辑：high 应 >= max(open, close)，low 应 <= min(open, close)，
    #     且 high >= low ---
    oc_max = d[["open", "close"]].max(axis=1)
    oc_min = d[["open", "close"]].min(axis=1)
    violations = (
        (d["high"] < d["low"])
        | (d["high"] < oc_max)
        | (d["low"] > oc_min)
    )
    report["ohlc_logic_violations"] = int(violations.sum())

    # --- 价格/成交量合法性 ---
    report["nonpositive_price_rows"] = int(
        ((d["open"] <= 0) | (d["high"] <= 0) | (d["low"] <= 0) | (d["close"] <= 0)).sum()
    )
    report["negative_volume_rows"] = int((d["volume"] < 0).sum())
    report["zero_volume_rows"] = int((d["volume"] == 0).sum())

    # --- 异常波动：单日涨跌幅绝对值超过阈值（仅告警，可能是拆股/真实
    #     极端行情/数据错误，需人工判断，不自动删除） ---
    daily_ret = d["close"].pct_change()
    extreme = daily_ret.abs() > cfg.anomaly_return_threshold
    report["extreme_move_rows"] = int(extreme.sum())
    if daily_ret.notna().any():
        report["max_abs_daily_return_pct"] = float(daily_ret.abs().max() * 100.0)

    # --- 缺口：相邻K线的时间间隔异常 ---
    ts = pd.to_datetime(d["datetime"], utc=True)
    deltas_days = ts.diff().dt.total_seconds() / 86400.0
    if market == "crypto":
        # 加密货币 24/7 交易，日线间隔应恒为 1 天，>1 天即数据缺口
        report["gap_events"] = int((deltas_days > 1.5).sum())
    else:
        # 美股只在交易日有数据，正常周末间隔 3 天、长假 4 天；
        # 超过 stock_gap_warn_days 才记为疑似缺口（可能停牌或数据缺失）
        report["gap_events"] = int((deltas_days > cfg.stock_gap_warn_days).sum())

    # --- 最后一根K线可能尚未收盘（仅提示：抓取发生在当日盘中/币圈当日
    #     未结束时，最后一根日线是未完成K线，其收盘价不可靠） ---
    try:
        last_date = ts.iloc[-1].date()
        today_utc = pd.Timestamp.now(tz="UTC").date()
        report["last_bar_may_be_incomplete"] = bool(last_date >= today_utc)
    except Exception:
        pass

    issue_count = (
        report["duplicate_timestamps"]
        + (1 if report["non_monotonic_timestamps"] else 0)
        + report["ohlc_logic_violations"]
        + report["nonpositive_price_rows"]
        + report["negative_volume_rows"]
        + report["extreme_move_rows"]
        + report["gap_events"]
    )
    report["issue_count"] = int(issue_count)

    if issue_count > 0:
        logger.warning(
            f"[{market}] {symbol} 数据质量告警: 问题计数={issue_count} "
            f"(OHLC逻辑错误={report['ohlc_logic_violations']}, "
            f"异常波动={report['extreme_move_rows']}, "
            f"缺口={report['gap_events']}, "
            f"重复时间戳={report['duplicate_timestamps']}, "
            f"非正价格={report['nonpositive_price_rows']})；"
            f"数据未被修改，问题已记录在案。"
        )
    if report["zero_volume_rows"] > 0:
        logger.warning(
            f"[{market}] {symbol} 有 {report['zero_volume_rows']} 根零成交量K线，"
            f"可能为停牌/极低流动性，仅记录不处理。"
        )

    return report


def validate_market_data(ohlcv_data: dict, market: str, cfg=None) -> pd.DataFrame:
    """对一个市场的全部标的逐一校验，返回报告 DataFrame（一行一个标的）。"""
    rows = [
        validate_ohlcv(df, symbol, market, cfg=cfg)
        for symbol, df in ohlcv_data.items()
    ]
    return pd.DataFrame(rows)
