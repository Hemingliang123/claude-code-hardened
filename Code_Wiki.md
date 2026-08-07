# Code Wiki: Claude Code 泄露源码及阿娇版缠论回测项目

本文档旨在结构化地分析和总结当前工作区内（`/workspace`）的代码仓库。该仓库主体为 Anthropic 的 AI 编程智能体 **Claude Code** 的完整泄露源码（基于 TypeScript/Bun/React Ink）。同时，工作区内包含一个独立的高质量 Python 量化回测子项目——**阿娇版缠论（数字货币真实胜率回测）**。

考虑到提问使用的是中文，且“缠论”项目拥有极高的定制化分析价值，本 Wiki 将分为两个主要部分：首先详细解析**阿娇版缠论回测项目**，其次概述 **Claude Code 核心源码架构**。

---

## 第一部分：阿娇版缠论（数字货币真实胜率回测）

该子项目位于 `/workspace/chanlun_backtest/` 目录下，采用严格的因果式（无未来函数）逻辑实现了缠中说禅体系中最核心的规则（笔、中枢、背驰、三类买卖点），并集成了 SMC (Smart Money Concepts) 策略框架。

### 1. 项目整体架构
* **数据层 (Data Layer)**：从 Binance 官方获取并清洗 K 线数据。
* **计算与引擎层 (Engine Layer)**：
  * **缠论核心 (`chanlun_engine.py`)**：依赖 Rust 编写的 `czsc` 库流式增量计算“笔”，在 Python 端无未来函数地构建中枢、判断背驰并生成买卖点。
  * **线段引擎 (`duan_engine.py`)**：基于特征序列法构建线段，用于实现缠论的“小转大”级别递归。
  * **SMC引擎 (`smc_engine.py`)**：实现了 FVG（失衡区）、订单块（OB）、结构突破（BOS）等概念，并修复了市面上常见 SMC 代码的未来函数缺陷。
* **回测与验证层 (Backtest & Validation Layer)**：
  * 包含信号撮合系统（`backtest.py`）、多级别联立运行逻辑，以及针对逻辑漏洞进行深入检验的脚本（例如随机基线蒙特卡洛检验）。

### 2. 主要模块职责
* **`download_data.py`**：免 API Key 从 Binance 公开数据源下载历史 K 线（支持 PEPEUSDT、ORDIUSDT、ZECUSDT 等）。
* **`chanlun_engine.py`**：核心策略逻辑，定义了中枢（`ZhongShu`）、多级别联立的趋势时间线（`TrendTimeline`）以及买卖点生成规则。
* **`backtest.py`**：回测引擎，负责将生成的买卖点（`BSPoint`）信号转化为实际的交易记录（`Trade`），并严格控制执行价格为“信号确认的下一根K线开盘价”，以彻底杜绝未来函数。包含完整的绩效统计逻辑（胜率、盈亏比、回撤等）。
* **`validate_basic_logic.py` & `random_baseline.py`**：基础逻辑验证器，剥离买卖点，单独对中枢自洽性、背驰反转等进行统计学显著性检验（如蒙特卡洛对比）。

### 3. 关键类与函数说明
* **`ChanEngine` (在 `chanlun_engine.py`)**
  * **核心职责**：管理 K 线流，计算 MACD，维护因果性笔列表，并执行核心缠论算法。
  * **关键方法**：
    * `_bi_price_power()`: 计算笔的价格力度，基于相对百分比，适配如 PEPE 等极低面值的币种。
    * `build_zhongshu_list()`: 基于笔序列（`bi_list`）增量构建 `ZhongShu`。
    * `detect_signals()`: 结合进入笔、离开笔以及 MACD 面积计算背驰并产出买卖点信号。
* **`TrendTimeline`**
  * **核心职责**：用于多级别联立，根据大级别确定的笔方向过滤小级别的交易信号。
  * **关键方法**：`allows(point)`，判定某一时间点产生的买卖点信号是否顺应当前大级别趋势。
* **`run_backtest(bars, points, exec_bar_ids, fee_rate)` (在 `backtest.py`)**
  * **核心职责**：将产生的信号结合真实 K 线进行撮合成交。
  * **运作机制**：保证成交价格为 `exec_bar_id + 1` 的开盘价，且单边持有（开多必先平空）。

### 4. 依赖关系
此 Python 项目主要依赖于数据科学栈及量化包：
* `czsc`: 高性能缠论笔计算引擎（底层含 Rust 优化）。
* `pandas` & `numpy`: K 线数据处理、MACD 计算和绩效指标矢量化计算。
* `pyarrow`: 读取 parquet 格式数据。
* `requests`: Binance 数据下载支持。

### 5. 项目运行方式
1. **环境准备**：
   ```bash
   pip install czsc pandas numpy pyarrow requests
   ```
2. **下载数据**：
   ```bash
   python chanlun_backtest/download_data.py PEPEUSDT 2025-06 2026-05
   ```
3. **执行回测**（单周期或多级别联立）：
   ```bash
   python chanlun_backtest/run_backtest.py --symbol PEPEUSDT --freqs 1m 5m 30m --fee 0.001
   python chanlun_backtest/run_backtest_multilevel.py --symbol PEPEUSDT --fee 0.001
   ```

---

## 第二部分：Claude Code (Anthropic 智能体泄露源码)

这是 Anthropic 推出的第一方 AI 编码智能体（Claude Code）的完整 TypeScript 实现。

### 1. 项目整体架构
* **启动与运行时 (Entrypoints)**：`entrypoints/cli.tsx` 及 `main.tsx` 是系统核心入口。提供普通交互 CLI、系统 Prompt 导出、无头环境运行等不同启动模式。
* **核心引擎 (Coordinator & Engine)**：
  * `QueryEngine.ts`：系统大脑，负责对话会话状态、管理 Context、发送提示给大模型并解析结构化输出（Tools calling）。
  * `services/api/claude.js` 等：直接与 Anthropic 官方 API（Claude 3.5 Sonnet / 3.7 Sonnet 等）通信的适配层。
* **交互前端 (UI/Ink)**：基于 React Ink（`ink/` 和 `components/` 目录）构建富交互终端界面。包含各种弹窗、流式日志渲染、Markdown 显示等。
* **工具集 (Tools Ecosystem)**：位于 `tools/` 目录，封装了大量供大模型使用的操作工具，是智能体“手脚”的实现。

### 2. 主要模块职责
* **`tools/` 模块**：
  * **`AgentTool`**: 能够生成子智能体（Sub-agent）并分发多步骤任务。
  * **`BashTool` / `PowerShellTool`**: 执行系统命令。
  * **`FileEditTool` / `FileReadTool` / `GlobTool`**: 操作代码仓库文件系统。
  * **`MCPTool`**: 与 MCP (Model Context Protocol) 资源交互的标准化接口。
* **`services/mcp/`**：Model Context Protocol 的客户端与服务端实现，允许 Claude Code 连接并使用外部工具或资源服务器。
* **`utils/permissions/`**：安全与权限控制模块，用于拦截敏感的 Bash 命令、控制文件读写权限等。

### 3. 关键类与函数说明
* **`QueryEngine` (在 `QueryEngine.ts`)**
  * **核心职责**：拥有并管理当前对话生命周期和查询引擎。
  * **功能**：处理每一次的用户输入 `submitMessage()`，携带完整的 `Tools`、`Commands`、`mcpClients`，与大语言模型（LLM）进行交互并处理流式返回结果。
* **`Tool` 接口 (在 `Tool.ts`)**
  * 定义了所有的工具契约，包括 `userFacingName`、输入 JSON Schema，以及最重要的 `call()` 方法。

### 4. 依赖关系
* **运行环境**：Node.js / Bun。
* **核心依赖**：
  * `@commander-js/extra-typings`: 命令行参数解析。
  * `ink` / `react`: 终端 UI 渲染引擎。
  * `@anthropic-ai/sdk`: 官方 API 通信 SDK。
  * `zod`: Schema 验证与数据结构防腐层。

### 5. 项目运行方式
该仓库是构建打包前的源码层，通常需要通过 `bun` 或 `npm` 安装依赖后启动。开发入口如下：
```bash
# 启动标准 CLI 模式
bun run src/entrypoints/cli.tsx
# 或执行内置功能例如查看版本
bun run src/entrypoints/cli.tsx --version
```
> 注：由于此为泄露源码仓库，可能缺乏原版项目的部分构建配置（如根目录的 `package.json`），具体运行可能需补充缺失的配置。
