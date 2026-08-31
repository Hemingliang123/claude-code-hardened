# 关键类与函数说明

本章只覆盖对理解仓库最关键的符号，不追求“全量 API 手册”。

## 1. 主工程关键符号

### 1.1 `QueryEngine`

位置：`/workspace/QueryEngine.ts`

角色：

- 主工程的查询执行核心
- 负责把用户 prompt 变成完整的一次模型回合

核心职责：

- 构造系统提示词
- 整合工具、命令、MCP、技能与状态
- 追踪权限拒绝
- 维护消息历史
- 以流式方式输出 SDK 消息

最重要的方法：

- `submitMessage(prompt, options)`
  - 作用：执行一个完整回合
  - 输入：prompt、UUID、Meta 标记等
  - 输出：`AsyncGenerator<SDKMessage>`

适合理解的问题：

- 模型为什么能看到这些工具
- 工具调用结果如何并入消息流
- headless 模式怎样执行一次请求

### 1.2 `ask()`

位置：`/workspace/QueryEngine.ts`

角色：

- `QueryEngine` 的一次性包装器

作用：

- 创建临时 `QueryEngine`
- 转发参数
- 执行单次查询

适合理解的问题：

- SDK/print 模式如何复用主引擎

### 1.3 `ToolUseContext`

位置：`/workspace/Tool.ts`

角色：

- 工具执行时的统一上下文对象

为什么重要：

- 它定义了工具“在会话中拥有什么能力”
- 也是工具与状态系统、权限系统、MCP、消息上下文之间的桥梁

关键字段：

- `options`: 当前模型、工具、命令、MCP 等运行选项
- `getAppState()` / `setAppState()`: 读写全局状态
- `abortController`: 中断控制
- `messages`: 当前消息历史
- `requestPrompt`: 交互式提示能力
- `handleElicitation`: 远端或协议层补充输入能力

### 1.4 `Tool`

位置：`/workspace/Tool.ts`

角色：

- 所有工具实现必须遵守的接口协议

作用：

- 统一工具名称、别名、输入 schema、执行逻辑、进度与结果格式

意义：

- 让 Bash、Read、Edit、Web、MCP、任务类工具都能被同一套引擎调用

### 1.5 `getCommands(cwd)`

位置：`/workspace/commands.ts`

角色：

- 当前运行目录下可用命令的汇总入口

职责：

- 合并内建命令
- 合并技能目录命令
- 合并插件命令
- 合并工作流命令
- 合并动态技能
- 做过滤与去重

阅读价值：

- 这是理解“为什么你在当前会话里能看到这些命令”的关键入口

### 1.6 `getAllBaseTools()`

位置：`/workspace/tools.ts`

角色：

- 主工程工具清单的基础来源

职责：

- 列出理论可用的所有基础工具
- 按 feature flag 和环境条件做裁剪

阅读价值：

- 这是理解“模型理论上拥有哪些工具”的最佳入口

### 1.7 `AppState`

位置：`/workspace/state/AppStateStore.ts`

角色：

- 会话级全局状态模型

核心内容：

- 设置
- 权限上下文
- 任务
- MCP
- 插件
- 远程连接
- 通知
- TODO
- 文件历史

阅读价值：

- 这是理解整个终端应用状态面最关键的定义文件

### 1.8 `AppStateProvider`

位置：`/workspace/state/AppState.tsx`

角色：

- 将 `AppState` 注入 React 组件树

辅助函数：

- `useAppState()`
- `useSetAppState()`
- `useAppStateStore()`

### 1.9 `useManageMCPConnections()`

位置：`/workspace/services/mcp/useManageMCPConnections.ts`

角色：

- MCP 连接生命周期管理 Hook

核心职责：

- 初始化 MCP 客户端
- 处理 tools/commands/resources 拉取
- 处理连接状态变化
- 做重连与错误去重
- 将远端能力同步进 `AppState`

阅读价值：

- 这是理解 MCP 如何并入本地能力平面的关键位置

### 1.10 `RemoteSessionManager`

位置：`/workspace/remote/RemoteSessionManager.ts`

角色：

- 远程会话客户端控制器

核心职责：

- 建立 WebSocket 连接
- 接收 SDK 消息
- 处理权限请求与取消
- 将用户消息发送到远端会话

关键方法：

- `connect()`
- `sendMessage()`
- `respondToPermissionRequest()`

阅读价值：

- 这是理解 viewer/remote assistant 能力的重要入口

## 2. Python 子项目关键符号

### 2.1 `load_bars(parquet_path, symbol, freq_key)`

位置：`/workspace/chanlun_backtest/chanlun_engine.py`

角色：

- 将 parquet 行情转换为 `czsc.RawBar` 列表

意义：

- 它是所有回测脚本进入算法层之前的统一数据适配器

### 2.2 `compute_macd(closes, fast, slow, signal)`

位置：`/workspace/chanlun_backtest/chanlun_engine.py`

角色：

- 纯因果 MACD 计算函数

用途：

- 为缠论背驰判断提供力度度量

### 2.3 `ZhongShu`

位置：`/workspace/chanlun_backtest/chanlun_engine.py`

角色：

- 中枢数据结构

字段含义：

- `bis`: 构成中枢的笔序列
- `zg`: 中枢上沿
- `zd`: 中枢下沿
- `start_idx` / `end_idx`: 在笔序列中的边界

### 2.4 `TrendTimeline`

位置：`/workspace/chanlun_backtest/chanlun_engine.py`

角色：

- 大级别笔方向时间线

用途：

- 服务多级别联立过滤

关键方法：

- `direction_at(dt)`: 查询给定时刻对应的大级别方向
- `allows(point)`: 判断某个买卖点是否符合大级别方向过滤

### 2.5 `BSPoint`

位置：`/workspace/chanlun_backtest/chanlun_engine.py`

角色：

- 缠论买卖点统一数据结构

关键字段：

- `kind`: 一买/二买/三买/一卖/二卖/三卖
- `side`: `buy` 或 `sell`
- `dt`
- `price`
- `bar_id`

### 2.6 `ChanEngine`

位置：`/workspace/chanlun_backtest/chanlun_engine.py`

角色：

- 缠论核心引擎

核心职责：

- 维护 MACD 序列
- 构建中枢
- 检测一二三类买卖点
- 做“无未来函数”运行时自证

关键方法：

- `_bi_price_power()`: 计算笔的价格力度
- `_bi_macd_area()`: 计算笔覆盖区间的 MACD 面积
- `build_zhongshu_list()`: 从笔序列构造中枢列表
- `detect_signals()`: 从已确认笔中检测买卖点
- `run()`: 因果式逐步运行并输出信号、执行时点和验证统计

为什么重要：

- 它几乎是整个回测子项目最关键的算法核心

### 2.7 `Trade`

位置：`/workspace/chanlun_backtest/backtest.py`

角色：

- 一笔交易的数据结构

关键字段：

- 开平仓时间与价格
- 开平仓原因
- 多空方向
- 扣费后收益率

### 2.8 `run_backtest(bars, points, exec_bar_ids, fee_rate)`

位置：`/workspace/chanlun_backtest/backtest.py`

角色：

- 信号撮合引擎

核心规则：

- 信号在 `exec_bar_id` 被发现
- 真实成交价使用下一根 K 线开盘价
- 始终只持有一个方向仓位
- 遇到反向信号先平仓再反手

### 2.9 `evaluate_trades(trades)`

位置：`/workspace/chanlun_backtest/backtest.py`

角色：

- 绩效统计函数

输出指标：

- 交易笔数
- 胜率
- 平均盈利/亏损
- 盈亏比
- 累计收益率
- 最大回撤
- 多头/空头分组统计

### 2.10 `main()` in `run_backtest.py`

位置：`/workspace/chanlun_backtest/run_backtest.py`

角色：

- 单周期回测主脚本入口

职责：

- 解析参数
- 加载 parquet 数据
- 调用 `ChanEngine.run()`
- 在自证失败时自动调大 `safety_margin`
- 调用回测与统计函数
- 持久化 csv 与 json 结果

### 2.11 `SMCPoint`

位置：`/workspace/chanlun_backtest/smc_engine.py`

角色：

- SMC 信号统一数据结构

接口设计特点：

- 与 `BSPoint` 对齐，便于复用同一套回测函数

### 2.12 `SMCEngine`

位置：`/workspace/chanlun_backtest/smc_engine.py`

角色：

- SMC 特征提取与结构识别引擎

核心职责：

- 检测 FVG 与订单块
- 检测摆点
- 检测 BOS/CHoCH
- 显式记录信号最早可观察 bar_id

关键方法：

- `_build_frame()`
- `_detect_fvg_and_ob()`
- `_detect_structure()`
- `run()`

### 2.13 `Duan`

位置：`/workspace/chanlun_backtest/duan_engine.py`

角色：

- 线段数据结构

字段：

- `bis`
- `direction`

派生属性：

- `fx_a`
- `fx_b`
- `high`
- `low`

### 2.14 `build_duan_list(bi_list)`

位置：`/workspace/chanlun_backtest/duan_engine.py`

角色：

- 基于笔序列构建线段列表

用途：

- 为“小转大”与结构递归级别分析提供基础结构

### 2.15 `download_symbol_interval(symbol, interval, start, end, out_dir)`

位置：`/workspace/chanlun_backtest/download_data.py`

角色：

- 从 Binance 公共数据集下载指定标的与周期的历史数据并保存为 parquet

阅读价值：

- 这是数据准备流程的主入口

## 3. 关键接口之间的关系

可以把这些关键符号关系理解成两条主链。

### 3.1 主工程主链

```text
entrypoints/cli.tsx
  -> main.tsx
  -> getCommands()
  -> getAllBaseTools()
  -> QueryEngine.submitMessage()
  -> Tool / MCP / RemoteSessionManager
  -> AppState 更新
  -> UI 渲染
```

### 3.2 Python 子项目主链

```text
download_data.py
  -> load_bars()
  -> ChanEngine.run() / SMCEngine.run() / build_duan_list()
  -> run_backtest()
  -> evaluate_trades()
  -> csv/json/markdown 结果
```

## 4. 阅读优先级建议

如果你时间有限，优先读以下符号：

### 主工程

- `QueryEngine`
- `ToolUseContext`
- `getCommands()`
- `getAllBaseTools()`
- `AppState`
- `useManageMCPConnections()`
- `RemoteSessionManager`

### Python 子项目

- `ChanEngine`
- `run_backtest()`
- `evaluate_trades()`
- `SMCEngine`
- `build_duan_list()`
