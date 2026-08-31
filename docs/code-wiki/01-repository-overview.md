# 仓库总览

## 1. 仓库定位

当前仓库并不是一个单体应用，而是由两个相对独立但同仓存放的工程组成：

1. 根目录主工程：Bun/TypeScript/TSX 编写的 AI Coding Agent CLI/TUI
2. 子项目 `chanlun_backtest/`：Python 编写的缠论与 SMC 回测工程

根目录 `README.md` 将仓库描述为 Claude Code 源码泄露版本，说明其主要用途偏“源码研究”而不是标准交付发布。

## 2. 技术栈

### 主工程

- 运行时与构建特征：Bun，源码直接使用 `bun:bundle`
- 语言：TypeScript / TSX
- CLI 框架：`@commander-js/extra-typings`
- UI：React + 自定义终端渲染层 `ink/`
- 工具与协议：MCP、插件系统、技能系统、远程会话、桥接模式

### 子工程 `chanlun_backtest/`

- 语言：Python
- 核心依赖：`czsc`、`pandas`、`numpy`、`pyarrow`、`requests`
- 用途：历史行情下载、缠论/SMC/线段结构分析、信号回测、统计验证

## 3. 顶层目录结构

下面只列与理解架构最相关的目录：

```text
/workspace
├── entrypoints/           # CLI 早期入口与特殊模式分发
├── commands/              # Slash Command 与命令定义
├── components/            # React/终端 UI 组件
├── state/                 # 全局状态模型与 store
├── services/              # MCP、通知、限流、语音等服务层
├── remote/                # 远程会话客户端
├── server/                # 本地 direct-connect 服务端
├── hooks/                 # UI 与会话副作用逻辑
├── utils/                 # 基础设施与通用能力
├── tools/                 # 各类模型可调用工具实现
├── skills/                # 技能加载与注册
├── chanlun_backtest/      # 独立 Python 回测工程
├── main.tsx               # 主程序入口
├── QueryEngine.ts         # 查询执行核心
├── Tool.ts                # 工具系统总契约
├── commands.ts            # 命令汇聚与过滤中心
└── tools.ts               # 工具注册中心
```

## 4. 主工程的整体关系

主工程大致可以拆成 6 层：

1. 入口层：`entrypoints/cli.tsx`、`main.tsx`
2. 命令与工具注册层：`commands.ts`、`tools.ts`
3. 查询执行层：`QueryEngine.ts`
4. 协议与集成层：`services/mcp/`、`remote/`、`server/`
5. 状态管理层：`state/`
6. 展示与交互层：`components/`、`hooks/`、`context/`、`ink/`

## 5. 主执行链路

简化后的主执行链路如下：

```text
entrypoints/cli.tsx
  -> main.tsx
  -> 初始化配置 / 插件 / 技能 / MCP / 状态
  -> commands.ts 获取命令
  -> tools.ts 获取工具
  -> QueryEngine 提交用户输入
  -> Tool / MCP / Slash Command / 远程会话
  -> AppState 更新
  -> components + ink 渲染输出
```

其中：

- `entrypoints/cli.tsx` 负责尽可能多的快速分流，减少不必要模块加载
- `main.tsx` 负责真正初始化交互式或非交互式运行环境
- `QueryEngine.ts` 是模型回合执行的核心编排器
- `Tool.ts` 与 `tools.ts` 定义“模型能调用什么、如何调用”

## 6. 子项目 `chanlun_backtest/` 的整体关系

Python 子项目的执行链路更清晰，属于脚本型分析工程：

```text
download_data.py
  -> 生成 parquet 历史行情
  -> load_bars()
  -> ChanEngine / SMCEngine / build_duan_list()
  -> run_backtest()
  -> evaluate_trades()
  -> 输出 csv / json / markdown 分析结论
```

该项目强调“因果式、无未来函数”这一约束，很多实现细节都围绕这个目标展开。

## 7. 当前仓库的边界判断

基于当前实际文件，可以明确判断：

- 主 TypeScript 工程源码较完整，具备清晰的入口、状态、工具与协议分层
- 但主工程缺少常见构建清单，因此“完整发布工程”状态无法从当前仓库单独确认
- Python 子项目则更接近一个可直接执行的独立研究工程，README、依赖、脚本入口都比较完整

## 8. 推荐关注点

如果你的目标是快速理解主工程，请优先关注：

- `entrypoints/cli.tsx`
- `main.tsx`
- `commands.ts`
- `tools.ts`
- `QueryEngine.ts`
- `Tool.ts`
- `state/AppStateStore.ts`

如果你的目标是理解回测逻辑，请优先关注：

- `chanlun_backtest/README.md`
- `chanlun_backtest/chanlun_engine.py`
- `chanlun_backtest/backtest.py`
- `chanlun_backtest/run_backtest.py`
- `chanlun_backtest/smc_engine.py`
- `chanlun_backtest/duan_engine.py`
