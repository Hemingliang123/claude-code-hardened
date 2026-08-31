# 依赖关系与运行方式

## 1. 依赖关系概览

本仓库的依赖关系要分成两部分看：

1. 主 TypeScript/Bun 工程
2. `chanlun_backtest/` Python 子项目

## 2. 主 TypeScript/Bun 工程依赖

### 2.1 已从源码直接确认的依赖

以下依赖可直接从 import 语句确认：

- `bun:bundle`
- `@commander-js/extra-typings`
- `react`
- `chalk`
- `lodash-es`
- `@modelcontextprotocol/sdk`

此外还可以确认它依赖大量本地模块，例如：

- `services/mcp/*`
- `utils/*`
- `state/*`
- `components/*`
- `tools/*`

### 2.2 依赖结构

主工程可以粗略表示为：

```text
entrypoints/main
  -> commands.ts
  -> tools.ts
  -> QueryEngine.ts
  -> Tool.ts
  -> state/*
  -> services/*
  -> remote/* / server/*
  -> components/* / hooks/* / ink/*
```

### 2.3 依赖边界特征

- `commands.ts` 依赖命令、技能、插件与工作流来源
- `tools.ts` 依赖所有可注册工具实现
- `QueryEngine.ts` 同时依赖状态、提示词、权限、工具与消息模型
- `services/mcp/*` 依赖 MCP SDK 与本地状态系统
- `components/*` 依赖 `state/`、`context/` 与 `hooks/`

这说明主工程是一个高度模块化但耦合面广的会话型应用。

## 3. Python 子项目依赖

### 3.1 明确依赖

`chanlun_backtest/requirements.txt` 中声明了：

- `czsc`
- `pandas`
- `numpy`
- `pyarrow`
- `requests`

### 3.2 依赖用途

- `czsc`: 缠论笔构建与 `RawBar`/`Direction` 等核心数据结构
- `pandas`: 数据读取、处理与指标计算
- `numpy`: 数值运算
- `pyarrow`: parquet 读写支持
- `requests`: 下载 Binance 历史数据

## 4. 运行方式

## 4.1 主工程运行方式

### 已确认事实

从源码可以确认主工程存在以下运行形态：

- 交互式 CLI/TUI
- 非交互式 print/headless
- bridge/remote-control
- daemon
- direct-connect
- assistant/remote viewer

### 当前无法权威确认的内容

当前仓库内未发现：

- `package.json`
- `tsconfig.json`
- `Dockerfile`
- `Makefile`
- `pnpm-lock.yaml` / `bun.lockb`

因此无法仅凭当前仓库给出“官方正确”的主工程安装与启动命令。

换句话说：

- 能确认“它是什么”
- 也能确认“它大概如何分模式运行”
- 但不能确认“外部使用者应怎样一键安装和启动它”

这是当前仓库材料的客观边界。

## 4.2 Python 子项目运行方式

Python 子项目的运行方式是明确的。

### 安装依赖

```bash
pip install -r /workspace/chanlun_backtest/requirements.txt
```

或按 README 中的显式依赖安装：

```bash
pip install czsc pandas numpy pyarrow requests
```

### 下载数据

```bash
python /workspace/chanlun_backtest/download_data.py PEPEUSDT 2025-06 2026-05
python /workspace/chanlun_backtest/download_data.py ORDIUSDT 2025-06 2026-05
python /workspace/chanlun_backtest/download_data.py ZECUSDT 2025-06 2026-05
```

### 运行单周期回测

```bash
python /workspace/chanlun_backtest/run_backtest.py --symbol PEPEUSDT --freqs 1m 5m 30m --fee 0.001
```

### 运行多级别联立回测

```bash
python /workspace/chanlun_backtest/run_backtest_multilevel.py --symbol PEPEUSDT --fee 0.001
```

### 运行测试脚本

```bash
python /workspace/chanlun_backtest/test_smc_engine.py
python /workspace/chanlun_backtest/test_duan_engine.py
```

## 5. 数据与产物关系

### 输入数据

Python 子项目的数据输入位于：

- `chanlun_backtest/data/`

数据格式：

- parquet

来源：

- Binance 公共历史数据集

### 输出产物

输出一般位于：

- `chanlun_backtest/results/`

常见产物：

- 交易明细 csv
- 汇总 json
- 若干分析型 Markdown 文档

## 6. 测试情况

### 主工程

当前仓库中未明确发现主 TypeScript 工程的标准测试入口或通用测试清单文件，因此该部分测试体系状态未知。

### Python 子项目

已明确存在的测试/验证脚本包括：

- `test_smc_engine.py`
- `test_duan_engine.py`
- `validate_basic_logic.py`
- `validate_beichi_alternatives.py`
- `validate_beichi_zhongshu_anchored.py`

其中前两者更像直接执行型测试脚本，后几者更偏研究性验证脚本。

## 7. CI 与工作流现状

当前仓库中存在 `.github/workflows/`，已确认至少有一个工作流文件。

### 已确认结论

- 工作流存在
- 内容更接近 SLSA provenance 示例
- 它不是主工程完整构建管线的充分证据

### 因此不应做出的推论

以下结论目前都不能直接下：

- 主工程已经具备完整 CI
- 主工程通过该工作流完成构建与测试
- 该工作流就是对外发布的正式流水线

## 8. 运行风险与边界说明

### 主工程

由于缺少构建清单，直接尝试运行主 TypeScript 工程存在以下不确定性：

- 依赖版本未知
- feature flag 默认值未知
- 是否需要特定内部环境未知
- 是否依赖未提交文件未知

### Python 子项目

Python 子项目的运行路径相对明确，但仍有两个前提：

- 需要先准备历史数据
- `czsc` 环境必须安装成功

## 9. 一句话总结

就“可运行性”而言：

- 主工程更像“可研究源码，但当前仓库不足以权威复原标准构建流程”
- `chanlun_backtest/` 更像“可直接安装依赖并执行的独立回测工程”
