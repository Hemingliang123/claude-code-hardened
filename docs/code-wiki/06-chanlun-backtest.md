# `chanlun_backtest` 子项目解读

## 1. 项目目标

`chanlun_backtest/` 是一个围绕缠论与相关结构化交易信号做“真实历史回测”的 Python 子项目。

它的特点不是追求策略工程化，而是强调：

- 规则显式化
- 过程可复现
- 因果式、无未来函数
- 可对照、可验证、可写出研究结论

## 2. 子项目目录结构

```text
chanlun_backtest/
├── download_data.py
├── chanlun_engine.py
├── smc_engine.py
├── duan_engine.py
├── backtest.py
├── run_backtest.py
├── run_backtest_multilevel.py
├── run_smc_backtest.py
├── run_chan_smc_confluence.py
├── run_duan_confluence.py
├── random_baseline.py
├── test_smc_engine.py
├── test_duan_engine.py
├── validate_basic_logic.py
├── validate_beichi_alternatives.py
├── validate_beichi_zhongshu_anchored.py
├── README.md
├── RESULTS.md
├── COMPARISON.md
├── LOGIC_ANALYSIS.md
├── SMC_ANALYSIS.md
├── BASIC_LOGIC_VALIDATION.md
└── DUAN_CONFLUENCE.md
```

## 3. 整体数据流

该项目的数据流非常清晰：

```text
download_data.py
  -> 生成 parquet 行情文件
  -> load_bars()
  -> ChanEngine / SMCEngine / build_duan_list()
  -> 产生信号 points + exec_bar_ids
  -> backtest.run_backtest()
  -> evaluate_trades()
  -> 输出 csv / json / Markdown 结论
```

## 4. 数据准备层

### `download_data.py`

职责：

- 从 Binance 官方公开数据集下载历史 K 线
- 支持按币种、周期、时间区间拉取
- 统一保存为 parquet

关键函数：

- `month_range()`: 生成月份区间
- `download_month()`: 下载单月 zip 并解析为 DataFrame
- `download_symbol_interval()`: 拉取整个区间并写入 parquet

输出结果：

- `data/<symbol>-<interval>-<start>_to_<end>.parquet`

## 5. 缠论信号层

### `chanlun_engine.py`

这是项目中最核心的算法文件。

### 核心思想

- 笔的构建交给 `czsc`
- 中枢、背驰、三类买卖点由本项目自行实现
- 所有判断都只使用当前及之前数据
- 对“未来函数”风险进行运行时自证

### 核心数据结构

- `ZhongShu`: 中枢
- `TrendTimeline`: 多级别方向时间线
- `BSPoint`: 买卖点信号
- `ChanEngine`: 缠论引擎

### 关键逻辑

#### `build_zhongshu_list()`

作用：

- 从笔序列中构建中枢列表

逻辑：

- 连续三笔存在重叠则形成中枢候选
- 后续笔只要继续与中枢区间重叠就延伸
- 出现完全不重叠的离开笔时结束该中枢

#### `detect_signals()`

作用：

- 在已确认笔序列上检测一二三类买卖点

覆盖逻辑：

- 一类买卖点：围绕中枢的进入笔与离开笔做背驰比较
- 二类买卖点：严格锚定在真实一类信号之后
- 三类买卖点：中枢离开后回抽不回中枢

该函数中有大量注释解释“以前实现错在哪里、现在为什么这么修”。

#### `run()`

作用：

- 逐步推进 K 线
- 在轮询点上取“已绝对确认”的笔
- 触发信号检测
- 记录每个信号最早可观察到的 `exec_bar_id`
- 进行未来函数自证

### 为什么 `run()` 很关键

项目最重要的可信度来源就在这里：

- 不直接使用 `c.bi_list` 的尾部延伸笔
- 通过 `safety_margin` 丢弃最新若干笔
- 对历史已确认笔做指纹比对
- 一旦发现“原以为确认、实际上后来又变了”的笔，立即报错重跑

这让子项目不仅“声称无未来函数”，而是把这个约束写进了运行流程。

## 6. 回测与统计层

### `backtest.py`

该文件解决的是“把信号变成交易”的问题。

### `run_backtest()`

职责：

- 根据 `points + exec_bar_ids` 做撮合
- 采用下一根 K 线开盘价成交
- 保持单仓位方向
- 在反向信号时平仓并反手

### `evaluate_trades()`

职责：

- 对成交结果做统计

输出指标包括：

- 胜率
- 平均盈利/亏损
- 盈亏比
- 累计收益率
- 最大回撤
- 多空拆分统计

## 7. 回测脚本层

### `run_backtest.py`

职责：

- 跑单周期回测
- 自动处理 `safety_margin` 不足时的重试
- 输出每个周期的 csv 与汇总 json

### `run_backtest_multilevel.py`

职责：

- 跑多级别联立回测

通常含义是：

- 大级别定方向
- 小级别找买卖点

### 其他运行脚本

- `run_smc_backtest.py`: SMC 单独回测
- `run_chan_smc_confluence.py`: 缠论与 SMC 组合测试
- `run_duan_confluence.py`: 固定时钟级别与结构递归级别对照
- `run_chan_random_baseline.py`: 随机基线对照

## 8. SMC 子系统

### `smc_engine.py`

该文件不是简单照搬外部 SMC 实现，而是带有“审查后重写”的背景。

### 解决的问题

文件顶部已经明确指出它修复了几类典型问题：

- 分块计算导致滚动窗口跨 chunk 错误
- `shift(-2)` 带来的未来函数风险
- 订单块定义逻辑矛盾
- BOS/CHoCH 缺失

### 核心能力

- FVG 检测
- 订单块检测
- 摆点检测
- BOS/CHoCH 检测
- 因果式 `bar_id` 标注

### 关键设计亮点

- `SMCPoint` 接口与 `BSPoint` 对齐
- 因而可以直接复用 `backtest.run_backtest()`

这是一种很好的“信号层与回测层解耦”设计。

## 9. 线段与结构递归子系统

### `duan_engine.py`

这个模块服务于“小转大”问题，也就是：

- 大级别是否一定要靠固定时钟重采样得到
- 还是可以从同一份低级别结构中递归推导出来

### 核心数据结构

- `Duan`

### 核心函数

- `_merge_char_seq()`: 特征序列包含处理
- `build_duan_list()`: 从笔序列构造线段列表

### 方法学意义

这部分不是普通指标计算，而是在检验：

- 固定时钟级别
- 结构递归级别

二者对策略结果的影响差异。

## 10. 测试与验证层

### 明确测试文件

- `test_smc_engine.py`
- `test_duan_engine.py`

### 验证文件

- `validate_basic_logic.py`
- `validate_beichi_alternatives.py`
- `validate_beichi_zhongshu_anchored.py`

这些文件共同构成了项目“研究型验证”的一部分。

它们的意义不只是防回归，更是在检验策略逻辑本身是否成立。

## 11. 文档层

子项目附带了多份专题文档：

- `RESULTS.md`
- `COMPARISON.md`
- `LOGIC_ANALYSIS.md`
- `SMC_ANALYSIS.md`
- `BASIC_LOGIC_VALIDATION.md`
- `DUAN_CONFLUENCE.md`

这些文档不是 API 说明，而是研究结论与方法论说明。

## 12. 子项目的设计特点

从工程视角看，这个子项目有几个鲜明特征：

- 强调因果性而非策略包装
- 把“未来函数风险”当成一等问题处理
- 将信号识别与回测撮合分层
- 允许不同信号引擎复用同一回测框架
- 附带大量研究文档作为解释层

## 13. 一句话总结

`chanlun_backtest/` 可以理解为：

“一个以因果式信号识别为核心、以统一回测接口为执行层、以统计验证与研究文档为解释层的量化研究工程。”
