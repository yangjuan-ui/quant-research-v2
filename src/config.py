"""
config.py
集中管理全部可配置参数。所有其他模块必须从这里读取配置，
不允许在各模块内分散硬编码常量，便于审计和复现。
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


# ------------------------------------------------------------------
# 路径配置
# ------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = BASE_DIR / "results"
DB_PATH = DATA_DIR / "quant_research.db"
LOG_DIR = RESULTS_DIR / "logs"

# 数据快照目录（可复现性）：原始抓取结果与资产池快照按时间戳留档，
# 不覆盖历史版本，便于复现某次运行实际使用的数据。
SNAPSHOT_DIR = DATA_DIR / "snapshots"
SNAPSHOT_RAW_DIR = SNAPSHOT_DIR / "raw"
SNAPSHOT_UNIVERSE_DIR = SNAPSHOT_DIR / "universe"

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(SNAPSHOT_RAW_DIR, exist_ok=True)
os.makedirs(SNAPSHOT_UNIVERSE_DIR, exist_ok=True)


# ------------------------------------------------------------------
# 通用网络配置
# ------------------------------------------------------------------

# SEC EDGAR 要求请求必须带有可识别的 User-Agent（含联系方式）。
# 请在实际部署时，通过环境变量 SEC_USER_AGENT 覆盖为你自己的真实邮箱，
# 不要在公开仓库里保留无意义的占位邮箱用于生产用途。
SEC_USER_AGENT = os.environ.get(
    "SEC_USER_AGENT",
    "quant-research-project contact@example.com"
)

HTTP_TIMEOUT_SECONDS = 20
HTTP_MAX_RETRIES = 3
HTTP_BACKOFF_BASE_SECONDS = 2.0

# CoinGecko 免费接口限流：粗略控制在每分钟不超过这个次数
COINGECKO_MAX_CALLS_PER_MINUTE = 20

# SEC EDGAR 请求速率限制（官方建议不超过约10次/秒，这里取更保守的值）
SEC_MAX_CALLS_PER_SECOND = 4


# ------------------------------------------------------------------
# 加密货币模块配置
# ------------------------------------------------------------------

@dataclass
class CryptoConfig:
    exchange_id: str = "binance"
    quote_currency: str = "USDT"
    timeframe: str = "1d"
    default_symbols: List[str] = field(
        default_factory=lambda: ["BTC/USDT", "ETH/USDT"]
    )
    use_dynamic_top_n: bool = True   # True 时使用 CoinGecko 市值前 N（已确认需求：前50）
    top_n: int = 50
    start_date_utc: str = "2020-01-01T00:00:00Z"
    initial_capital_usdt: float = 10000.0
    fee_pct: float = 0.001        # 单边手续费，0.1%
    slippage_pct: float = 0.0005  # 单边滑点估算
    risk_per_trade_pct: float = 0.01    # 每笔交易风险占账户权益比例
    max_position_pct: float = 0.25      # 单资产最大名义仓位占账户权益比例
    allow_short: bool = False     # 不做空，仅现货多头
    # 流动性过滤：最近 liquidity_window_days 天的日均成交额（close*volume）
    # 低于此阈值（计价货币）的标的跳过并记录日志，避免低流动性标的让
    # 滑点模型严重失真。设为 0 表示关闭该过滤。
    min_avg_daily_quote_volume: float = 1_000_000.0
    liquidity_window_days: int = 30


CRYPTO_CONFIG = CryptoConfig()


# ------------------------------------------------------------------
# 美股模块配置
# ------------------------------------------------------------------

@dataclass
class USStockConfig:
    wikipedia_sp500_url: str = (
        "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    )
    top_n: int = 20
    start_date: str = "2020-01-01"
    initial_capital_usd: float = 10000.0
    fee_pct: float = 0.0           # 假设无佣金经纪商
    slippage_pct: float = 0.0005
    risk_per_trade_pct: float = 0.01
    max_position_pct: float = 0.25
    allow_short: bool = False


US_STOCK_CONFIG = USStockConfig()


# ------------------------------------------------------------------
# ARK 每日持仓模块配置
# ------------------------------------------------------------------

@dataclass
class ARKConfig:
    # ARK 官方 CSV 链接按基金代码配置化，链接结构若失效需人工更新此处
    # 并在 README 中说明如何核实最新官方地址。
    fund_csv_urls: dict = field(default_factory=lambda: {
        "ARKK": "https://assets.ark-funds.com/fund-documents/funds-etf-csv/ARK_INNOVATION_ETF_ARKK_HOLDINGS.csv",
        "ARKW": "https://assets.ark-funds.com/fund-documents/funds-etf-csv/ARK_NEXT_GENERATION_INTERNET_ETF_ARKW_HOLDINGS.csv",
        "ARKQ": "https://assets.ark-funds.com/fund-documents/funds-etf-csv/ARK_AUTONOMOUS_TECH._%26_ROBOTICS_ETF_ARKQ_HOLDINGS.csv",
        "ARKF": "https://assets.ark-funds.com/fund-documents/funds-etf-csv/ARK_FINTECH_INNOVATION_ETF_ARKF_HOLDINGS.csv",
        "ARKG": "https://assets.ark-funds.com/fund-documents/funds-etf-csv/ARK_GENOMIC_REVOLUTION_ETF_ARKG_HOLDINGS.csv",
        "ARKX": "https://assets.ark-funds.com/fund-documents/funds-etf-csv/ARK_SPACE_EXPLORATION_%26_INNOVATION_ETF_ARKX_HOLDINGS.csv",
    })


ARK_CONFIG = ARKConfig()


# ------------------------------------------------------------------
# SEC 13F 模块配置
# ------------------------------------------------------------------

@dataclass
class SEC13FConfig:
    # 默认列表为空。用户需自行从 SEC EDGAR 官方全文检索
    # (https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany)
    # 确认目标机构的真实 CIK 后手动填入，不得编造。
    target_ciks: dict = field(default_factory=lambda: {
        # 示例格式（已注释，默认不启用任何机构）：
        # "BERKSHIRE_HATHAWAY": "0001067983",
    })
    edgar_submissions_url_template: str = (
        "https://data.sec.gov/submissions/CIK{cik}.json"
    )
    edgar_full_text_search_url: str = (
        "https://www.sec.gov/cgi-bin/browse-edgar"
    )


SEC_13F_CONFIG = SEC13FConfig()


# ------------------------------------------------------------------
# 策略与指标配置
# ------------------------------------------------------------------

@dataclass
class StrategyConfig:
    ema_fast: int = 20
    ema_slow: int = 50
    atr_window: int = 14
    adx_window: int = 14
    rsi_window: int = 14
    bollinger_window: int = 20
    bollinger_std: float = 2.0

    adx_trend_threshold: float = 25.0

    atr_stop_loss_mult: float = 2.0
    atr_take_profit_mult: float = 3.0
    atr_trailing_stop_mult: float = 1.5

    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    rsi_exit_recovery: float = 50.0

    max_holding_days: int = 60  # 超时强制平仓的兜底天数，防止信号无限期悬挂

    # 海龟/Donchian 通道突破（趋势分支的备选入场，策略类型记为 'donchian'）：
    # 入场：趋势状态下收盘价突破此前 donchian_entry_period 根K线的最高价
    # （通道用 shift(1) 的历史窗口计算，不含当根K线，无未来函数）；
    # 退出：收盘价跌破此前 donchian_exit_period 根K线的最低价（通道退出），
    # 同时保留 ATR 止损/追踪止损作为风险兜底，无固定止盈（与海龟原规则一致）。
    donchian_enabled: bool = True
    donchian_entry_period: int = 20
    donchian_exit_period: int = 10


STRATEGY_CONFIG = StrategyConfig()


# ------------------------------------------------------------------
# 数据质量配置
# ------------------------------------------------------------------

@dataclass
class DataQualityConfig:
    enabled: bool = True
    # 单日涨跌幅绝对值超过该阈值记为异常波动告警（仅告警记录，不删数据）
    anomaly_return_threshold: float = 0.5
    # 标的历史K线少于该数量时跳过并记录日志：指标窗口（EMA50、ADX 的
    # Wilder 平滑稳定期等）需要足够长的预热数据，硬跑只会产生噪声信号。
    min_history_bars: int = 100
    # 美股相邻交易日间隔超过该天数（日历日）记为疑似缺口告警
    # （正常长周末+节假日一般不超过 4 天）
    stock_gap_warn_days: int = 5
    # 是否把每次运行的原始抓取结果按时间戳存档到 data/snapshots/raw/
    save_raw_snapshots: bool = True


DATA_QUALITY_CONFIG = DataQualityConfig()


# ------------------------------------------------------------------
# 双动量筛选配置（观察池二次筛选）
# ------------------------------------------------------------------

@dataclass
class MomentumConfig:
    # 双动量筛选：相对动量在观察池内排名 + 绝对动量过滤
    # （回看期收益 <= absolute_threshold 的标的不进入本次回测集合）。
    # 筛选只使用运行日之前已完成K线的数据，属于"运行时点"的观察池
    # 精选，与市值池本身一样存在时点选择属性，必须在报告中披露；
    # 它不改变单标的历史回测本身的无前视纪律。
    enabled: bool = True
    lookback_days: int = 252   # 约12个月交易日
    skip_days: int = 21        # 跳过最近约1个月（经典 12-1 动量口径）
    absolute_threshold: float = 0.0
    # 历史不足 lookback+skip 的标的无法计算动量：不因筛选被剔除，
    # 在筛选结果中标记为 insufficient_history 并保留在回测集合中。


MOMENTUM_CONFIG = MomentumConfig()

RISK_FREE_RATE_ANNUAL = 0.0  # Sharpe计算用的无风险利率假设，默认0，README需注明

# ------------------------------------------------------------------
# 运行时间说明（写入README的依据）
# ------------------------------------------------------------------
# GitHub Actions 定时运行固定设置为 UTC 13:00，不随美股夏令时调整，
# 实际对应的美东时间会在冬令时/夏令时之间有1小时差异。
SCHEDULED_RUN_UTC_HOUR = 13

