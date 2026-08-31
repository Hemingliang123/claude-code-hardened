# `chanlun_backtest` 子项目说明

本文件聚焦 `chanlun_backtest/` 目录。它是一个与主 TypeScript CLI 基本解耦的 Python 子项目，用于对“阿娇版缠论”与相关变体规则进行因果式量化回测、对比实验与逻辑验证。

## 1. 项目目标

根据子目录 `README.md`，该项目的目标不是做通用交易平台，而是围绕以下问题展开研究：

- 用严格因果式、无未来函数的方式实现缠论核心规则。
- 在多个数字货币与多个时间尺度上做真实回测。
- 验证单周期、多级别联立、SMC 组合等策略变体。
- 通过随机基线、逻辑审查与专门验证脚本，对核心理论进行独立检验。

它本质上是一个“研究型回测目录”，不是一个长期服务进程。

## 2. 目录结构

从源码与 `README.md` 可以整理出以下分层：

- 数据获取
  - `download_data.py`
- 缠论核心引擎
  - `chanlun_engine.py`
- SMC 与结构扩展
  - `smc_engine.py`
  - `duan_engine.py`
- 回测与绩效统计
  - `backtest.py`
  - `random_baseline.py`
- 驱动脚本
  - `run_backtest.py`
  - `run_backtest_multilevel.py`
  - `run_smc_backtest.py`
  - `run_chan_smc_confluence.py`
  - `run_duan_confluence.py`
  - `run_chan_random_baseline.py`
- 逻辑验证脚本
  - `validate_basic_logic.py`
  - `validate_beichi_alternatives.py`
  - `validate_beichi_zhongshu_anchored.py`
- 合成测试
  - `test_smc_engine.py`
  - `test_duan_engine.py`
- 研究结论文档
  - `RESULTS.md`
  - `COMPARISON.md`
  - `LOGIC_ANALYSIS.md`
  - `SMC_ANALYSIS.md`
  - `BASIC_LOGIC_VALIDATION.md`
  - `DUAN_CONFLUENCE.md`

## 3. 核心数据流

最重要的数据流如下：

`download_data.py -> parquet 数据 -> load_bars() -> ChanEngine / 其他引擎 -> 信号点 -> run_backtest() -> evaluate_trades() -> results/*.csv + *_summary.json`

如果是多级别联立或扩展验证，则会在“引擎产出信号”之前或之后插入额外的结构时间线、过滤逻辑或统计检验模块。

## 4. 关键类与函数

### 4.1 数据读取与基础指标

位于 `chanlun_engine.py` 的关键函数：

- `load_bars(parquet_path, symbol, freq_key)`
  - 从 parquet 读取 K 线数据，转为 `czsc.RawBar` 列表。
- `compute_macd(closes, fast=12, slow=26, signal=9)`
  - 基于历史收盘价因果式计算 MACD 序列。

它们是所有后续分析的输入基础。

### 4.2 结构与信号建模

`chanlun_engine.py` 中最关键的类型：

- `ZhongShu`
  - 表示走势中枢，包含中枢高低边界及所覆盖的笔区间。
- `TrendTimeline`
  - 用已确认的大级别笔构造方向时间线，为小级别信号提供“顺大级别方向而为”的过滤能力。
- `BSPoint`
  - 表示一类、二类、三类买卖点的统一结构。
- `ChanEngine`
  - 缠论核心引擎，负责 MACD 预处理、笔级力度计算、中枢构建、背驰与买卖点检测，以及整段数据的因果式遍历。

`ChanEngine` 内特别值得关注的方法：

- `_bi_price_power(bi)`
  - 自定义笔力度度量，避免直接使用库内可能不适配超低价币种的实现。
- `_bi_macd_area(bi)`
  - 计算与笔方向一致的 MACD 柱面积。
- `build_zhongshu_list(bi_list)`
  - 从笔序列构造中枢序列。
- `detect_signals(bi_list)`
  - 基于当前已确认笔序列识别买卖点。
- `run(...)`
  - 主执行循环，输出信号点、执行时机与运行时自证结果。

其中，`run()` 是最适合整体理解算法的入口，因为它把“数据遍历、因果验证、信号产出”串了起来。

### 4.3 回测撮合与统计

`backtest.py` 中的关键元素：

- `Trade`
  - 单笔交易记录，保存方向、开平仓时间、价格、原因与收益率。
- `run_backtest(bars, points, exec_bar_ids, fee_rate=0.001)`
  - 按信号执行撮合，采用“下一根 K 线开盘价成交”的因果式规则。
- `evaluate_trades(trades)`
  - 统计交易笔数、胜率、盈亏比、累计收益率、最大回撤等指标。
- `trades_to_df(trades)`
  - 把交易结果转为 DataFrame 以便导出。

这一层与信号层是分离的，因此后续替换信号引擎或增加策略对照相对容易。

### 4.4 驱动脚本

`run_backtest.py` 是最直接的入口脚本，其职责包括：

- 解析参数。
- 组织输入输出目录。
- 读取 parquet 数据。
- 运行 `ChanEngine.run(...)`。
- 若运行时自证发现安全冗余不足，则自动增大 `safety_margin` 重跑。
- 调用 `run_backtest()` 与 `evaluate_trades()`。
- 导出 CSV 和 JSON 汇总结果。

这个脚本最能代表该子项目的标准使用方式。

## 5. 设计特点

### 5.1 因果式约束是第一原则

从 `README.md` 与代码注释可以看出，该子项目极其强调“无未来函数”：

- 笔的构建交给 `czsc` 的增量更新算法。
- 信号执行价取“确认后下一根 K 线开盘价”。
- `ChanEngine.run()` 内部会对安全冗余进行运行时自证，而不是只做一次性假设。

这意味着：该项目的首要优化目标不是速度或接口美观，而是研究结论的时序合法性。

### 5.2 信号层与回测层解耦

信号识别主要在 `chanlun_engine.py`、`smc_engine.py`、`duan_engine.py`；
撮合与收益统计集中在 `backtest.py`；
而各种实验只是在驱动脚本中改变“信号来源”和“过滤条件”。

这是一种很适合研究目录的组织方式，因为：

- 可以复用相同撮合逻辑做横向对照。
- 可以把争议集中在信号规则而不是回测框架上。
- 新实验通常只需新增脚本，而不用改底层公共组件。

### 5.3 文档与实验脚本并重

该子项目不仅提供代码，还配套了较完整的研究报告型文档。对于理解项目意图，阅读这些 Markdown 往往与读代码同等重要，因为很多规则口径、修正原因和统计结论只存在于文档里。

## 6. 依赖关系

高层依赖关系如下：

- `run_backtest.py`
  - 依赖 `chanlun_engine.py`、`backtest.py`
- `run_backtest_multilevel.py`
  - 依赖 `chanlun_engine.py`，并额外使用多级别过滤逻辑
- `run_smc_backtest.py`
  - 依赖 `smc_engine.py`、`backtest.py`
- `run_chan_smc_confluence.py`
  - 组合使用缠论与 SMC 信号
- `run_duan_confluence.py`
  - 依赖 `duan_engine.py` 进行结构递归级别实验

底层公共依赖主要是：

- `pandas`
- `numpy`
- `pyarrow`
- `requests`
- `czsc`

其中 `czsc` 是缠论笔构建的关键第三方依赖。

## 7. 运行与测试

子项目 `README.md` 提供了明确的安装与运行命令：

### 7.1 安装依赖

```bash
pip install czsc pandas numpy pyarrow requests
```

或者根据现有 `requirements.txt` 安装：

```bash
pip install -r requirements.txt
```

### 7.2 下载数据

```bash
python download_data.py PEPEUSDT 2025-06 2026-05
python download_data.py ORDIUSDT 2025-06 2026-05
python download_data.py ZECUSDT 2025-06 2026-05
```

### 7.3 单周期回测

```bash
python run_backtest.py --symbol PEPEUSDT --freqs 1m 5m 30m --fee 0.001
```

### 7.4 多级别联立回测

```bash
python run_backtest_multilevel.py --symbol PEPEUSDT --fee 0.001
```

### 7.5 脚本式测试

仓库中未看到统一的 `pytest` 配置，但存在可直接运行的测试脚本：

```bash
python test_smc_engine.py
python test_duan_engine.py
```

## 8. 适合从哪里开始修改

根据目标不同，建议入口如下：

- 想调整买卖点规则：从 `chanlun_engine.py` 开始。
- 想改成交或绩效统计：从 `backtest.py` 开始。
- 想新增实验：参考 `run_*.py` 脚本新建一个驱动文件。
- 想验证某个理论口径：优先看 `validate_*.py` 与对应分析文档。
- 想理解“当前结果为何如此”：先读 `LOGIC_ANALYSIS.md` 和 `BASIC_LOGIC_VALIDATION.md`。

## 9. 已知边界

- `data/` 与 `results/` 是运行时目录，当前仓库未必包含完整数据文件。
- 该子项目强调研究可复现，不代表其收益曲线可直接视为实盘策略表现。
- 文档中多次强调“当前版本不含止损/仓位管理”，因此结果解释必须结合这一前提。
