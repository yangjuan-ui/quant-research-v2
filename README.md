# quant-research-v2

量化研究与历史回测系统（加密货币 + 美股）。每日由 GitHub Actions 在 **UTC 13:00** 自动运行（多伦多时间夏令时 09:00 / 冬令时 08:00），也可在 Actions 页面手动触发。

> 本项目是研究与回测软件：**不连接券商/交易所账户、不自动下单、不承诺盈利。** 所有数据来自公开免费接口，可能存在延迟、限流或格式变化。

## 做什么

1. **资产池构建**
   - 加密货币：CoinGecko 当前市值前 50 → 映射 Binance USDT 交易对 → ccxt 拉取 2020-01-01 以来日线。
   - 美股：Wikipedia 当前 S&P 500 成分股 → yfinance 当前市值排序取前 20 → yfinance 历史日线。
2. **策略回测（单币/单股独立回测，每标的独立 10,000 初始资金假设）**
   - ADX(14) ≥ 25 为趋势状态：EMA20 > EMA50 且收盘 > EMA20 时做多；ATR 止损（2×）、止盈（3×）、追踪止损（1.5×）。
   - ADX < 25 为震荡状态：RSI(14) < 30 且收盘低于布林下轨时做多；触及布林中轨或 RSI 恢复至 50 退出，ATR 止损兜底。
   - 最大持仓 60 根K线兜底退出；仅做多，不做空。
3. **观察池参考层（不参与回测）**
   - ARK 六只主动 ETF 每日持仓（来源标签 `ark_daily`）。
   - SEC 13F 季度持仓（来源标签 `13f_quarterly_reference`）：默认机构列表为空，需自行在 `src/config.py` 的 `SEC13FConfig.target_ciks` 填入经 SEC EDGAR 核实的真实 CIK；持仓 CUSIP 不做代码映射（标记 `UNMAPPED`，因无免费权威映射源，不冒充已确认代码）。13F 只能使用申报日（filing_date）之后的数据，`filter_usable_as_of_date()` 强制这一纪律。
4. **产出**：SQLite 数据库 `data/quant_research.db`（runs / market_data_metadata / watchlist_members / trades / metrics 五张表）+ `results/` 目录下的 CSV/JSON（资产池快照、逐标的权益曲线、交易记录、指标汇总、运行汇总）。

## 回测纪律

- 信号只用已完成K线收盘后确认，**下一根K线开盘价成交**，不使用未来数据。
- 同一根K线同时触及止盈与止损时，**止损优先**（保守假设）。
- 手续费（加密 0.1%/边，美股假设 0）与滑点（0.05%/边）在进出场均计入。
- 仓位按 ATR 止损距离定风险：单笔风险 1% 权益，单标的名义仓位上限 25% 权益。
- 胜率**从不单独报告**：始终与平均盈利/亏损、盈亏比、期望值、最大回撤一起给出；未平仓交易不计入已实现绩效。
- Sharpe 计算的无风险利率假设为 0（见 `src/config.py` 的 `RISK_FREE_RATE_ANNUAL`）。

## 已知限制（重要）

- **幸存者偏差**：加密前 50 与 S&P 500 成分股均为"当前"名单，无法还原历史时点的真实名单与排名；当前市值不代表历史市值。结果应视为方法演示与研究参考，不是无偏的历史业绩证明。
- 单资产独立回测**不是组合回测**：把各标的权益曲线相加/平均不代表统一账户的组合绩效。
- 免费数据源（CoinGecko/ccxt/yfinance/ARK/SEC）均可能限流、延迟或变更格式；单标的失败会被记录并跳过，不中断整体运行。
- SEC 要求请求带可识别的 User-Agent：部署时请通过环境变量 `SEC_USER_AGENT` 或仓库 Secret 设置为你自己的真实联系邮箱，不要长期使用代码中的占位值。

## 本地运行

```bash
pip install -r requirements.txt
python main.py
```

退出码：核心流程全部失败才返回非零；部分标的/数据源失败记为 `partial_failure` 并保留已完成产出，退出码为 0。每次运行的详细日志在 `results/logs/`。

## 定时运行

`.github/workflows/daily_run.yml`：每日 UTC 13:00 + 手动触发；运行后自动把更新后的 `data/*.db` 提交回仓库。需要在仓库 Settings → Actions → General 中把 Workflow permissions 设为 **Read and write**。
