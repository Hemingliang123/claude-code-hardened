# 开发、运行与验证说明

本文件只记录当前仓库中“可以从现有文件明确确认”的开发与验证信息；无法从仓库内容确认的部分会明确写为“未知”。

## 1. 仓库现状判定

### 1.1 已确认

- 根目录存在大量 TypeScript/TSX 源码，主体是 CLI/TUI 智能代理应用。
- 根目录同时存在 `chanlun_backtest/` Python 子项目。
- 根目录 `README.md` 将仓库描述为源码快照。
- `.github/workflows/` 中仅有一个 SLSA provenance 相关工作流。

### 1.2 未确认

以下文件在当前仓库中未发现：

- `package.json`
- `tsconfig.json`
- `bunfig.toml`
- `pyproject.toml`
- `Cargo.toml`
- `go.mod`
- `Makefile`

因此以下信息无法从当前仓库直接确认：

- 主 TypeScript CLI 的统一 bootstrap 命令。
- 主 TypeScript CLI 的构建命令。
- 主 TypeScript CLI 的测试命令。
- 主 TypeScript CLI 的 lint / format 命令。
- 主 TypeScript CLI 的运行时版本要求。

结论：当前仓库适合做架构研究和源码阅读，但并不具备完整的主应用工程元数据。

## 2. 根目录结构速查

根目录下与理解项目最相关的路径如下：

- `README.md`
  - 仓库背景说明。
- `entrypoints/`
  - CLI 与 MCP 入口。
- `main.tsx`
  - 主程序装配入口。
- `commands.ts`
  - 命令装配。
- `tools.ts`
  - 工具装配。
- `Tool.ts`
  - 工具抽象。
- `QueryEngine.ts`
  - 会话级 Query 引擎。
- `query.ts`
  - Query 循环。
- `screens/REPL.tsx`
  - 主交互界面。
- `state/`
  - 全局状态。
- `services/`
  - API、MCP、analytics 等基础服务。
- `chanlun_backtest/`
  - 独立 Python 子项目。

## 3. 已发现的脚本与入口

### 3.1 主 TypeScript/Bun 代码

已确认存在入口文件：

- `entrypoints/cli.tsx`
- `main.tsx`
- `entrypoints/mcp.ts`

但由于缺少工程元数据，当前不能直接从仓库中确认如何把这些源文件打包或运行。

### 3.2 Python 子项目

已确认可直接运行的脚本：

- `download_data.py`
- `run_backtest.py`
- `run_backtest_multilevel.py`
- `run_smc_backtest.py`
- `run_chan_smc_confluence.py`
- `run_duan_confluence.py`
- `run_chan_random_baseline.py`
- `validate_basic_logic.py`
- `validate_beichi_alternatives.py`
- `validate_beichi_zhongshu_anchored.py`
- `test_smc_engine.py`
- `test_duan_engine.py`

这些脚本都属于“直接用 `python xxx.py` 执行”的风格，而不是通过统一任务运行器调度。

## 4. 可确认的安装与运行方式

本节仅针对 `chanlun_backtest/`。

### 4.1 安装依赖

`README.md` 给出了显式安装命令：

```bash
pip install czsc pandas numpy pyarrow requests
```

同时，由于目录内存在 `requirements.txt`，也可使用：

```bash
pip install -r requirements.txt
```

### 4.2 下载历史数据

```bash
python download_data.py PEPEUSDT 2025-06 2026-05
python download_data.py ORDIUSDT 2025-06 2026-05
python download_data.py ZECUSDT 2025-06 2026-05
```

说明：

- 这些命令会为后续回测准备 parquet 数据。
- `README.md` 说明数据目录为 `data/`，且该目录不一定被提交到仓库。

### 4.3 运行单周期回测

```bash
python run_backtest.py --symbol PEPEUSDT --freqs 1m 5m 30m --fee 0.001
```

运行逻辑：

- 加载指定币种与周期的数据。
- 用 `ChanEngine.run(...)` 生成信号。
- 若运行时因果性自证失败，则自动提高 `safety_margin` 并重跑。
- 调用回测模块输出结果。
- 将交易明细写入 `results/*.csv`，将汇总写入 `*_summary.json`。

### 4.4 运行多级别联立回测

```bash
python run_backtest_multilevel.py --symbol PEPEUSDT --fee 0.001
```

### 4.5 运行脚本式测试

```bash
python test_smc_engine.py
python test_duan_engine.py
```

说明：

- 当前未发现 `pytest.ini`、`pyproject.toml` 或 `tox.ini` 等统一测试配置。
- 因此更可靠的说法是“存在可直接执行的测试脚本”，而不是“项目标准测试框架是 pytest”。

## 5. GitHub Actions 现状

已发现唯一工作流：

- `.github/workflows/generator-generic-ossf-slsa3-publish.yml`

该工作流的实际行为：

- 在 `workflow_dispatch` 或 `release.created` 时触发。
- 通过 `echo "artifact1"`、`echo "artifact2"` 生成示例产物。
- 计算产物摘要后调用 SLSA generator 生成 provenance。

这说明：

- 它更像供应链证明示例工作流，而不是主应用真实 CI。
- 当前仓库并未暴露出完整的代码构建、测试、lint 流水线配置。

## 6. 对修改者最有用的工作方式

### 6.1 研究主 TypeScript 应用时

建议按下列顺序理解代码：

1. `README.md`
2. `entrypoints/cli.tsx`
3. `main.tsx`
4. `commands.ts`
5. `tools.ts`
6. `Tool.ts`
7. `QueryEngine.ts`
8. `query.ts`
9. `screens/REPL.tsx`

这样可以减少在大仓库里盲目搜索的成本。

### 6.2 修改 Python 子项目时

建议流程：

1. 先安装依赖。
2. 准备 `data/` 下的 parquet 数据。
3. 从最贴近目标的 `run_*.py` 或 `validate_*.py` 脚本切入。
4. 若改动影响信号逻辑，至少重新运行对应脚本式测试。
5. 若改动影响回测规则，重新生成结果并核对 `results/` 输出结构是否保持兼容。

## 7. 适合作为 Copilot / AI Agent 上下文的关键信息

如果后续要把这些内容浓缩成自定义指令文件，可优先保留以下要点：

- 该仓库由两部分组成：主 TypeScript CLI/TUI 代理应用 + `chanlun_backtest/` Python 研究子项目。
- 主应用入口链是 `entrypoints/cli.tsx -> main.tsx -> commands/tools/query/REPL`。
- 主应用当前缺少标准工程元数据，因此不要臆造 build/test/lint 命令。
- `chanlun_backtest/` 才是当前仓库里唯一具备明确安装和运行说明的子项目。
- `.github/workflows/` 中的现有工作流不是主业务 CI。

## 8. 当前文档的使用边界

- 本文件适合做“事实底册”和“AI 上下文源”。
- 本文件不应被解读为主 TypeScript CLI 已经可以在当前仓库中直接构建成功。
- 若未来补充了 `package.json` 或其他工程清单，需优先回填本文件中的“未确认”项。
