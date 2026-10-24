"""
momentum_screen.py
双动量筛选（Dual Momentum）：观察池二次筛选层。

方法（公开框架，Gary Antonacci《Dual Momentum Investing》；
动量效应学术出处 Jegadeesh & Titman, 1993）：
- 相对动量：同一观察池内，按回看期收益对全部标的排名，强者靠前。
- 绝对动量：回看期收益 <= 阈值（默认 0）的标的判定为"趋势向下"，
  不进入本次回测集合，避免在系统性下跌中仍然满池回测多头策略。
- 回看口径采用经典 12-1 形式：lookback_days=252、skip_days=21，
  即用 [t-273, t-21] 区间的收益，跳过最近约 1 个月，
  避开短期均值回归噪声。

时点纪律（重要披露）：
- 筛选只使用"运行日之前已获取的最后一根已完成K线"及更早的数据，
  计算本身无未来函数；但筛选结果是"运行时点"的观察池精选，
  与市值前 N 池一样具有时点选择属性：它决定的是"本次运行回测哪些
  标的"，不能被解读为历史任意时点的无偏选择。筛选全过程（每个标的
  的动量值、排名、是否通过、数据是否充足）都会完整输出留档，
  被筛掉的标的同样记录，不隐藏。

数据不足处理：
- 历史长度不足 lookback+skip 的标的无法计算动量，标记
  insufficient_history 并保留在回测集合中（其数据长度门槛已由
  数据质量层的 min_history_bars 单独把关），不因筛选被误杀。
"""

import pandas as pd

from src.config import MOMENTUM_CONFIG
from src.common import get_logger

logger = get_logger("momentum_screen")


def compute_momentum_return(close: pd.Series, lookback_days: int, skip_days: int):
    """
    计算单个标的的动量收益：close[-1-skip] / close[-1-skip-lookback] - 1。
    数据不足（len <= lookback+skip）时返回 None。
    只使用序列尾部已完成K线，不涉及未来数据。
    """
    n = len(close)
    if n <= lookback_days + skip_days:
        return None
    end_idx = n - 1 - skip_days
    start_idx = end_idx - lookback_days
    if start_idx < 0:
        return None
    start_price = close.iloc[start_idx]
    end_price = close.iloc[end_idx]
    if start_price is None or pd.isna(start_price) or start_price <= 0:
        return None
    if end_price is None or pd.isna(end_price):
        return None
    return float(end_price / start_price - 1.0)


def compute_dual_momentum_screen(ohlcv_data: dict, cfg=None) -> pd.DataFrame:
    """
    对一个市场的全部标的计算双动量筛选。
    返回 DataFrame，列：
      symbol, as_of_date, momentum_return, absolute_momentum_pass,
      momentum_rank, screened_in, screen_status
    screen_status 取值：'pass' / 'absolute_momentum_fail' /
    'insufficient_history'。
    """
    cfg = cfg or MOMENTUM_CONFIG
    rows = []
    for symbol, df in ohlcv_data.items():
        mom = compute_momentum_return(
            df["close"], cfg.lookback_days, cfg.skip_days
        )
        as_of = str(df["datetime"].iloc[-1]) if len(df) > 0 else None
        if mom is None:
            rows.append({
                "symbol": symbol,
                "as_of_date": as_of,
                "momentum_return": None,
                "absolute_momentum_pass": None,
                "momentum_rank": None,
                "screened_in": True,
                "screen_status": "insufficient_history",
            })
        else:
            passed = mom > cfg.absolute_threshold
            rows.append({
                "symbol": symbol,
                "as_of_date": as_of,
                "momentum_return": mom,
                "absolute_momentum_pass": passed,
                "momentum_rank": None,
                "screened_in": bool(passed),
                "screen_status": "pass" if passed else "absolute_momentum_fail",
            })

    screen_df = pd.DataFrame(rows)
    if len(screen_df) > 0:
        ranked = screen_df.dropna(subset=["momentum_return"]).sort_values(
            "momentum_return", ascending=False
        )
        for rank, idx in enumerate(ranked.index, start=1):
            screen_df.loc[idx, "momentum_rank"] = rank

    n_in = int(screen_df["screened_in"].sum()) if len(screen_df) > 0 else 0
    logger.info(
        f"双动量筛选完成：共 {len(screen_df)} 个标的，{n_in} 个进入回测集合，"
        f"{len(screen_df) - n_in} 个被绝对动量过滤 "
        f"(lookback={cfg.lookback_days}, skip={cfg.skip_days}, "
        f"threshold={cfg.absolute_threshold})。"
    )
    return screen_df


def apply_momentum_screen(ohlcv_data: dict, screen_df: pd.DataFrame) -> dict:
    """按筛选结果过滤回测数据字典，只保留 screened_in 的标的。"""
    if screen_df is None or len(screen_df) == 0:
        return dict(ohlcv_data)
    keep = set(screen_df.loc[screen_df["screened_in"], "symbol"])
    return {s: df for s, df in ohlcv_data.items() if s in keep}
