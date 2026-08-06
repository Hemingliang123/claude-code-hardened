# 神话项目 (Myth Project) 仓库 Code Wiki

## 1. 项目整体架构 (Overall Architecture)

该仓库 (`15053801818liang-dot/-`) 是一个包含多个独立子项目和实验性模块的综合体。核心子项目包括符号推理智能体、金融量化技术分析内核、多语言（C++/Go/Python）分布式任务调度系统，以及 iOS LLM 客户端脚手架等。

主要包含以下核心版块：
- **盘古 (Pangu)**: 主权可控的纯 Python 符号推理智能体引擎。
- **缠论 (Chanlun)**: 零外部依赖的量化技术分析内核。
- **Scheduler (多语言调度系统)**: 包括 C++ 版本 (`distributed-scheduler`)、Go 版本 (`go-scheduler`) 和 Python 版本 (`scheduler`)。
- **LLM 调度集成 (`llm-scheduler-integration`)**: C++ 调度器与大语言模型 (Claude) 的结合层。
- **YBLLMStreamSystem**: iOS 平台 LLM 流式对话系统脚手架。

---

## 2. 主要模块职责 (Main Modules)

### 2.1 盘古 (Pangu) - 符号推理引擎
**职责**：提供完全本地化、零依赖的符号推理智能体，结合 16 种认知架构、4D 持久记忆和自动技能学习，提供一致性证明和用户主权保护。
**特点**：单文件纯 Python 标准库实现，零外部 API 依赖，内置 MCP 协议桥接 (`--mcp` 模式)。支持从事实和规则库中进行显式/隐式逻辑推理，包含后台“梦境反思”进化机制。

### 2.2 缠论 (Chanlun) - 金融量化技术分析内核
**职责**：从原始 K 线数据出发，自动逐级识别缠论结构，生成交易信号（流程：K线包含处理 → 分型 → 笔 → 中枢 → MACD背驰 → 买卖点）。
**特点**：纯 Python 实现，零外部依赖。提供新笔 (`StrokeStandard.NEW`) 和老笔严笔 (`StrokeStandard.OLD`) 标准支持，适合作为高扩展性的量化交易底层。

### 2.3 分布式任务调度器 (Schedulers)
该仓库包含三个不同层面的调度器实现：
- **C++ 分布式调度器 (`distributed-scheduler`)**：单机多线程任务调度 Hub，基于 ZeroMQ ROUTER/DEALER，提供 WAL 崩溃恢复和 O(1) 空闲 Worker 查找效率，最高支持约 50k tasks/s 吞吐。
- **Go DAG 调度器 (`cmd/go-scheduler/`)**：DAG（有向无环图）工作流调度引擎。通过 JSON stdin/stdout 驱动执行 Python 任务脚本 (`tasks/` 目录下)，常用于执行缠论回测流水线。
- **Python 调度器 (`scheduler/`)**：基于无锁共享内存 (lock-free MPMC) 和 etcd 的 Leader 选举任务队列，用于多进程高并发数据消费。

### 2.4 LLM 调度集成 (`llm-scheduler-integration`)
**职责**：将 C++ 分布式调度器与 Python LLM worker 集成。利用调度器的崩溃安全和 WAL 特性，处理海量 LLM Prompt 推理分发（基于 Anthropic Claude API），保障任务不丢失且能够负载均衡。

### 2.5 YBLLMStreamSystem
**职责**：一个具备良好架构（Core, Parsing, Agent, Cognition, UI）边界的 iOS LLM 流式输出脚手架，采用 Objective-C 和 Swift 混编，为 iOS 开发者提供接入 LLM 推理的 App 骨架。

---

## 3. 关键类与函数说明 (Key Classes & Functions)

### 3.1 盘古 (Pangu)
- **`SuperBrainAgent`**: 主控入口类。负责整合认知引擎、记忆、仲裁器等，并管理感知-决策-执行循环 (`perceive()`, `decide()`, `act()`)。
- **`KB` (知识库)**: 提供事实和规则管理，核心方法 `query_best_with_trace()` 实现带启发式评分和深度限制的合一回溯推理引擎。
- **`CognitiveEngine`**: 实现了 16 种认知架构（如 CoT, ToT, ReAct, Socratic 等），并统一记录 `think_log` 轨迹。
- **`Arbiter` (仲裁器)**: 负责根据查询目标特征（如谓词名前缀、变量数量）自动选择最优的推理方法。
- **`BoneGuard`**: 安全层，基于正则匹配和硬编码白名单，执行身份不可侵犯保护和指令拦截。
- **`DreamEngine`**: 后台梦境引擎守护线程，定期生成重构和归纳候选规则，存入待确认队列供用户审核生效。

### 3.2 缠论 (Chanlun)
- **`analyze(bars)`**: 门面函数，串起整条分析流水线。
- **`kline.py`**: 执行 K 线包含处理（向上/向下合并逻辑）。
- **`fractal.py` / `stroke.py` / `pivot.py`**: 分别实现顶底分型、笔构建（交替+假分型回退）、中枢识别（重叠与延伸）。
- **`signals.py`**: 负责执行背驰判定及一/二/三类买卖点生成。

### 3.3 调度器核心 (Schedulers)
- **C++ Hub (分布式调度器)**: 
  - `has_idle()` / `find_and_mark_idle()`: 通过 `unordered_set` 实现 O(1) 复杂度的空闲 Worker 查找。
  - IO 线程 & 调度线程: 采用 ZeroMQ 消息轮询 (`poll`)、JSON 帧解析以及 Write-Ahead Log (`wal_write`) 保障事务。
- **Go Scheduler**: `JSONExecutor` 接口负责管理通过 stdin/stdout 与 Python worker (`tasks/` 目录中的脚本) 的通信。
- **Python LLM Worker**: `llm_worker.py` 通过 ZeroMQ DEALER 连接到 Hub 接收 prompt，调用 `anthropic` SDK 执行大模型推理后回传 `TASK_DONE`。

---

## 4. 依赖关系 (Dependencies)

- **盘古 (Pangu) & 缠论 (Chanlun)**: 主打 **零外部依赖 (Zero Dependency)**，完全基于 Python 3.8+ 标准库运行。
- **C++ 分布式调度器**: (Linux 环境) 依赖 `libzmq3-dev`, `cppzmq-dev`, `nlohmann-json3-dev`，使用 `cmake` 编译。
- **Go 调度器**: 依赖 Go 1.22+ 编译器，需要运行环境中存在 `python3` 命令以调用子脚本。
- **Python 调度器**: 依赖 `etcd3` (注意 protobuf 需 `<3.21`), `prometheus-client`, `psutil` (`requirements.txt`)，以及底层的 `libatomic.so.1`。
- **LLM 调度集成**: 依赖 `anthropic`, `pyzmq` (详见 `llm-scheduler-integration/requirements.txt`)。

---

## 5. 项目运行方式 (How to Run)

> **注**：在当前仓库环境中，推荐使用 `python3`，不要使用 `python`。部分依赖需安装到用户目录 (`pip install --break-system-packages`)。

### 5.1 运行盘古 (Pangu)
盘古支持直接作为交互式 REPL 运行（测试代码请直接通过 `python3 test_pangu_xxx.py` 运行，请勿使用 pytest 收集）：
```bash
cd 盘古
python3 pangu_v0.12.0.py
```
*(MCP 桥接模式可附加 `--mcp` 参数运行)*

### 5.2 运行缠论分析 (Chanlun)
自带命令行演示场景（下降通道底背驰 → 第一类买点等）：
```bash
python3 -m chanlun.demo
```
运行单元测试：
```bash
python3 chanlun/test_chanlun.py
# 或 python3 -m pytest chanlun/test_chanlun.py
```

### 5.3 运行 Go 调度器进行回测
生成测试数据并通过 Go 引擎执行 Python 任务流水线：
```bash
python3 scripts/generate_btc_csv.py
WORKSPACE_DIR=workspace go run ./cmd/go-scheduler/
```
*(运行后会在 `workspace/reports/` 目录下生成 markdown 报告)*

### 5.4 运行 C++ 分布式调度器与 LLM Worker
1. **编译 C++ Hub**:
```bash
cd distributed-scheduler
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
```
2. **启动调度 Hub**:
```bash
./build/hub --port 5555
```
3. **运行 LLM Worker**（演示模式免 API Key，直接返回 Mock 数据）：
```bash
cd llm-scheduler-integration
./run_demo.sh --mock
```
*(真实环境请配置 `export ANTHROPIC_API_KEY=sk-...` 后去掉 `--mock` 参数)*