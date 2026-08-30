# TRAE Agent / Claude Code Leak - Code Wiki

## 1. 文档范围

本 Wiki 基于当前工作区源码生成，目标是帮助读者快速理解这个仓库的整体结构、运行方式与核心执行链路。

需要先说明两点事实：

1. 根目录 `README.md` 明确写明：当前仓库是 **Claude Code 源码泄露版本**，仅额外加入了说明性 README，源码本体“未修改”。因此，仓库名是 `trae-agent`，但代码主体实际上对应 Claude Code 的主工程。
2. 当前工作区 **缺少** `package.json`、`bunfig.toml`、`tsconfig*.json` 等标准构建清单文件。因此，本文档中“依赖”与“运行方式”部分只能依据源码 import、注释与内联命令进行归纳，凡无法直接证实的内容都会明确标注为“未知”或“推断”。

---

## 2. 项目一句话概述

这是一个以 **TypeScript + Bun + React/Ink TUI** 为核心的 AI 编码代理系统，支持：

- 交互式命令行会话
- 模型回合循环与工具调用
- 本地与远程会话
- MCP 能力暴露与 MCP 客户端集成
- 插件、技能、工作流扩展
- 权限控制、沙箱、后台任务与多代理协作

从职责上看，它不是一个普通 CLI 工具，而是一个完整的“**Agent Runtime + TUI Shell + Extensibility Platform**”。

---

## 3. 仓库结构总览

### 3.1 顶层判断

当前工作区包含两个性质不同的部分：

- **主工程**：根目录下的大量 TypeScript/TSX 代码，属于 Agent 主程序
- **独立子项目**：`chanlun_backtest/`，是一个 Python 回测研究项目，不属于主 Agent 的运行主链路

因此，分析主仓库时应优先聚焦根目录主工程，把 `chanlun_backtest/` 视作并列子目录。

### 3.2 主要目录职责

| 目录 / 文件 | 角色 | 说明 |
| --- | --- | --- |
| `entrypoints/` | 启动入口层 | 提供 CLI、MCP 等入口 |
| `main.tsx` | 主装配器 | 初始化环境、配置、插件、命令、工具、会话并拉起 UI |
| `screens/` | 屏幕级 UI | 主要是 REPL、恢复会话、诊断等主界面 |
| `components/` | 组件层 | 各类 TUI 组件、消息、弹窗、状态条、Diff 展示 |
| `hooks/` | 逻辑与副作用层 | 远程会话、插件管理、IDE 集成、任务与交互逻辑 |
| `state/` | 应用状态层 | 自定义 store 与 AppState 注入 |
| `commands/` + `commands.ts` | 命令体系 | Slash commands、插件命令、技能命令、工作流命令 |
| `tools/` + `tools.ts` | 工具体系 | 模型可调用工具注册、过滤与拼装 |
| `QueryEngine.ts` | 会话引擎 | SDK/会话级封装，一次 turn 的高层总控 |
| `query.ts` | 查询循环 | 真正的模型循环、上下文压缩、工具执行与流式处理 |
| `bridge/` | 远程控制桥接 | remote-control / bridge 模式主链路 |
| `remote/` | 远程会话层 | 远程会话 WebSocket 订阅与权限回传 |
| `services/` | 基础服务层 | API、MCP、策略、语音、限流、通知等 |
| `skills/` | 技能系统 | 从技能目录与 MCP 构建可调用技能 |
| `plugins/` | 插件系统 | 内建插件与外部插件接入 |
| `utils/` | 通用底座层 | auth、config、git、prompt、session、sandbox 等横切能力 |
| `chanlun_backtest/` | 独立 Python 子项目 | 数字货币缠论/SMC 回测，不在主 Agent 运行链路中 |

---

## 4. 总体架构

### 4.1 分层架构

可以把主工程理解为以下纵向结构：

```text
CLI / MCP 入口层
    ->
主装配层（main.tsx）
    ->
TUI / 状态层（React + Ink + AppState）
    ->
命令 / 技能 / 插件 / 工具编排层
    ->
QueryEngine / queryLoop 执行内核
    ->
模型 API / MCP / Remote / Sandbox / Session 基础设施
    ->
通用工具与运行时底座（utils）
```

### 4.2 架构特点

- **中心化装配**：`main.tsx`、`commands.ts`、`tools.ts`、`QueryEngine.ts` 都是总控文件
- **执行内核清晰**：`QueryEngine.ts` 负责“会话级封装”，`query.ts` 负责“单轮执行循环”
- **强扩展性**：命令、技能、插件、工作流、MCP 工具都可插入主链路
- **多运行模式**：交互 REPL、headless、MCP server、remote-control、daemon、后台 session 都共用同一套核心
- **横切关注点很多**：权限、预算、压缩、Telemetry、会话恢复、文件缓存、策略限制持续贯穿全链路

---

## 5. 启动与入口体系

### 5.1 CLI 主入口

主 CLI 入口是 `entrypoints/cli.tsx`。

它的职责不是直接启动完整程序，而是先做 **fast-path 分流**：

- `--version`
- `--dump-system-prompt`
- `--claude-in-chrome-mcp`
- `--chrome-native-host`
- `remote-control` / `rc` / `remote` / `sync` / `bridge`
- `daemon`
- `ps` / `logs` / `attach` / `kill`
- `environment-runner`
- `self-hosted-runner`

如果以上特殊路径都不命中，才会动态导入 `main.js` 并执行完整 CLI 主流程。

### 5.2 主程序入口

完整程序入口是 `main.tsx` 导出的 `main()`。

它承担的职责非常重，属于全局启动编排器，主要包括：

- 初始化配置与环境变量
- 初始化遥测、策略限制、远程设置
- 初始化内建插件与内建技能
- 计算模型、权限模式、会话状态
- 加载命令、MCP、插件、agents
- 恢复历史会话或创建新会话
- 启动 Ink root，并挂载 `App -> REPL`

### 5.3 REPL 挂载链路

交互式会话的 UI 装配链路如下：

```text
entrypoints/cli.tsx
    ->
main.tsx: main()
    ->
launchRepl()
    ->
App
    ->
REPL
```

其中：

- `replLauncher.tsx` 负责动态导入 `App` 与 `REPL`
- `components/App.tsx` 负责注入 `FpsMetricsProvider`、`StatsProvider`、`AppStateProvider`
- `screens/REPL.tsx` 是核心交互界面

### 5.4 MCP 入口

`entrypoints/mcp.ts` 提供独立的 MCP server 入口：

- 基于 `@modelcontextprotocol/sdk`
- 使用 `StdioServerTransport`
- 暴露当前内建工具集合
- 为每次 MCP tool call 构造最小化 `ToolUseContext`

这说明该程序不仅能“消费 MCP”，还能把自己包装成一个可被外部调用的 MCP Server。

### 5.5 Remote / Bridge 入口

远程相关运行模式主要分两类：

1. **bridge / remote-control 模式**
   - 入口在 `entrypoints/cli.tsx`
   - 主逻辑在 `bridge/bridgeMain.ts`
   - 用途是把本地机器作为远程桥接环境

2. **remote session viewer / remote session interaction**
   - UI 侧通过 `useRemoteSession()`
   - 管理器为 `remote/RemoteSessionManager.ts`
   - 底层 WebSocket 连接为 `remote/SessionsWebSocket.ts`

---

## 6. 关键执行流程

### 6.1 交互式会话主流程

用户输入进入系统后的主链路可以概括为：

```text
用户输入
    ->
REPL 采集输入
    ->
QueryEngine.submitMessage()
    ->
构建 system prompt / user context / system context
    ->
query()
    ->
queryLoop()
    ->
模型流式输出 / tool_use
    ->
工具执行
    ->
工具结果回写为消息
    ->
继续下一轮 queryLoop
    ->
得到最终 assistant 输出
```

### 6.2 QueryEngine 的职责

`QueryEngine` 是“**每个会话一个实例**”的高层会话引擎，负责：

- 保存对话级消息状态
- 管理读取缓存、累计 usage、权限拒绝记录
- 组装系统提示
- 构建 `ProcessUserInputContext`
- 处理用户输入与 slash commands
- 把完整参数交给 `query()` 进入底层执行循环

一句话概括：**`QueryEngine` 负责“组织一次 turn”，`query.ts` 负责“执行一次 turn”。**

### 6.3 queryLoop 的职责

`queryLoop()` 是系统最核心的执行内核之一，负责：

- 维护每次 turn 的循环状态
- 预算跟踪与 task budget 管理
- 记忆预取与技能预取
- 工具结果预算裁剪
- snip / microcompact / autocompact / context collapse
- 发起模型请求并流式读取响应
- 在模型返回 tool_use 时触发工具执行
- 把工具输出继续回灌到消息流

可以把它理解成一个“**模型回合状态机**”。

### 6.4 工具调用流程

工具层的执行关系如下：

```text
tools.ts:getAllBaseTools()
    ->
tools.ts:getTools(permissionContext)
    ->
tools.ts:assembleToolPool(permissionContext, mcpTools)
    ->
QueryEngine / REPL 持有最终工具池
    ->
queryLoop 遇到 tool_use
    ->
调用具体 Tool 实现
```

内建工具覆盖范围很广，包括：

- Agent
- Task / Todo
- Bash / PowerShell
- 文件读写与编辑
- Glob / Grep
- WebFetch / WebSearch
- Skill
- AskUserQuestion
- MCP 资源读取
- Workflow / Monitor / Schedule

工具系统同时支持：

- 权限过滤
- deny 规则裁剪
- REPL 模式屏蔽原始工具
- 与 MCP 工具池合并

### 6.5 命令、技能、插件装配流程

命令系统的装配顺序大致为：

```text
bundled skills
    +
builtin plugin skills
    +
skills dir commands
    +
workflow commands
    +
plugin commands
    +
plugin skills
    +
built-in commands
    ->
getCommands()
```

`getCommands()` 还会额外插入 **dynamic skills**，并按：

- availability
- isEnabled()
- 去重

进行最终整理。

这意味着“命令体系”实际上是多个来源的统一抽象层，而不是仅靠 `commands/` 目录里的静态命令。

### 6.6 插件加载流程

插件加载主入口是 `hooks/useManagePlugins.ts`。

该 Hook 在挂载时会：

- `loadAllPlugins()`
- 检测并卸载被下架插件
- 读取 flagged plugins 并推送通知
- 加载插件命令、插件 agents、插件 hooks
- 加载插件 MCP server 配置
- 加载插件 LSP server 配置
- 合并错误并写回 `AppState.plugins`

因此它不是一个“只负责列插件”的轻量 Hook，而是插件生命周期的总控协调器。

### 6.7 技能加载流程

技能系统的核心在 `skills/loadSkillsDir.ts`：

- 解析技能 frontmatter
- 生成 `Command` 抽象
- 处理 allowed-tools、模型、effort、hooks、agent 等元数据
- 支持从 `/skills/<name>/SKILL.md` 目录格式加载
- 支持动态技能目录发现与条件技能激活

技能最终也被映射为命令，因此“技能”本质上是：

**用 Markdown + frontmatter 定义的、可被模型和用户共同调用的 Prompt Command。**

### 6.8 远程会话流程

远程会话管理器 `RemoteSessionManager` 的职责包括：

- 建立 WebSocket 订阅
- 接收远端消息
- 处理权限请求与取消
- 通过 HTTP POST 发送用户消息
- 回传权限决策
- 发送 interrupt

链路如下：

```text
useRemoteSession()
    ->
RemoteSessionManager.connect()
    ->
SessionsWebSocket.connect()
    ->
接收 SDKMessage / control_request / control_cancel_request
    ->
本地 UI 渲染与权限响应
```

---

## 7. 状态管理设计

### 7.1 Store 基础实现

项目没有使用 Redux / Zustand 作为主状态容器，而是自己实现了最小 Store：

- `state/store.ts:createStore()`

这个 Store 只提供三件事：

- `getState()`
- `setState(updater)`
- `subscribe(listener)`

因此它更像一个轻量级外部状态容器，再通过 React context 暴露给组件树。

### 7.2 AppState 的地位

`state/AppStateStore.ts` 中的 `AppState` 是全局运行态总模型，信息量非常大，覆盖：

- settings
- 当前模型
- 工具权限上下文
- remote / bridge 状态
- 任务池
- MCP clients / tools / commands / resources
- plugins 状态与错误
- fileHistory / attribution
- notifications / elicitation
- thinking 开关
- session hooks
- REPL VM context
- team / standalone agent context

结论：**AppState 是 UI 层和交互层的单一事实来源。**

### 7.3 Provider 注入关系

`components/App.tsx` 的注入顺序为：

```text
FpsMetricsProvider
    ->
StatsProvider
    ->
AppStateProvider
    ->
children(REPL 等)
```

这说明 UI 侧依赖的核心上下文主要有三类：

- 渲染性能指标
- 统计信息
- 全局应用状态

---

## 8. 核心模块职责详解

### 8.1 `main.tsx`

角色：**应用总装配器**

主要职责：

- 承接 CLI 完整启动路径
- 初始化配置与用户态
- 装配模型、命令、工具、agents、MCP、插件
- 设置 render 上下文与 REPL 初始状态
- 处理恢复会话、远程会话、worktree、teleport 等复杂启动场景

如果只能读一个文件来理解系统启动，这个文件优先级最高。

### 8.2 `commands.ts`

角色：**命令系统总注册表**

主要职责：

- 定义内建命令清单
- 读取技能、插件、workflow 命令
- 根据 availability / feature flag / 用户状态过滤命令
- 合并动态技能
- 为 SkillTool 提供可被模型调用的 prompt 型命令列表

### 8.3 `tools.ts`

角色：**工具池总装配器**

主要职责：

- 定义内建工具全集
- 根据权限上下文裁剪工具
- 处理 simple mode / REPL mode / coordinator mode 的工具可见性
- 合并 MCP 工具
- 统一作为系统提示和执行时的工具源

### 8.4 `Tool.ts`

角色：**工具接口契约层**

它定义了工具的共性抽象，如：

- `call`
- `description` / `prompt`
- `checkPermissions`
- `validateInput`
- `render`
- `progress`

同时也定义了工具运行依赖的 `ToolUseContext` 与权限相关上下文。

因此，`Tool.ts` 是整套“模型工具协议”的接口核心。

### 8.5 `QueryEngine.ts`

角色：**会话级总控引擎**

关键职责：

- 持有会话消息
- 记录 usage 与 permission denials
- 组装 system prompt 与上下文
- 构建 `ProcessUserInputContext`
- 调用底层 `query()`
- 支撑 SDK / headless 模式

它是“应用层”与“模型执行层”之间的桥梁。

### 8.6 `query.ts`

角色：**模型执行循环内核**

关键职责：

- 每轮请求前处理上下文
- 控制 compact / snip / collapse
- 跟踪 query chain
- 处理工具调用与续轮
- 产生流式事件与最终终止结果

如果把整个项目当作一个 Agent runtime，`query.ts` 是最接近“发动机”的位置。

### 8.7 `hooks/useManagePlugins.ts`

角色：**插件生命周期总协调器**

关键职责：

- 首次加载所有插件
- 收集插件错误
- 初始化 plugin commands / agents / hooks / MCP / LSP
- 把插件状态同步到 `AppState`

### 8.8 `skills/loadSkillsDir.ts`

角色：**技能编译器**

关键职责：

- 解析技能 frontmatter
- 把 Markdown 技能编译成 `Command`
- 处理变量替换与 shell prompt 执行
- 支持条件技能、动态技能目录与多来源加载

这套设计把“技能”转成统一命令抽象，使模型、UI 与系统提示都能复用相同的数据结构。

### 8.9 `remote/RemoteSessionManager.ts`

角色：**远程会话控制器**

关键职责：

- 维护 WebSocket 连接
- 接收与分发远端消息
- 处理权限请求 / 取消 / 响应
- 发送远端用户消息
- 中断、断开与重连

### 8.10 `entrypoints/mcp.ts`

角色：**MCP Server 适配层**

关键职责：

- 将现有内建工具导出为 MCP Tools
- 为 MCP 调用构造运行时上下文
- 实现 `list tools` 与 `call tool`

这说明系统架构里“内部工具协议”和“MCP 对外协议”之间有一层明确适配。

---

## 9. 关键类与函数索引

以下是理解主工程时最值得优先阅读的类与函数。

### 9.1 启动与装配

| 符号 | 文件 | 作用 |
| --- | --- | --- |
| `main()` | `entrypoints/cli.tsx` | CLI bootstrap，做 fast-path 分流 |
| `main()` | `main.tsx` | 完整主程序入口 |
| `launchRepl()` | `replLauncher.tsx` | 动态挂载 `App + REPL` |
| `App()` | `components/App.tsx` | 注入 AppState / Stats / FPS 上下文 |
| `startMCPServer()` | `entrypoints/mcp.ts` | 以 stdio 启动 MCP server |

### 9.2 状态管理

| 符号 | 文件 | 作用 |
| --- | --- | --- |
| `AppState` | `state/AppStateStore.ts` | 全局状态总模型 |
| `getDefaultAppState()` | `state/AppStateStore.ts` | 构造默认状态 |
| `createStore()` | `state/store.ts` | 最小状态容器实现 |
| `AppStateProvider` | `state/AppState.tsx` | 把 store 注入 React 树 |

### 9.3 查询与执行

| 符号 | 文件 | 作用 |
| --- | --- | --- |
| `QueryEngine` | `QueryEngine.ts` | 每个会话一个实例的会话引擎 |
| `submitMessage()` | `QueryEngine.ts` | 一次用户 turn 的高层总控 |
| `ask()` | `QueryEngine.ts` | 单次调用封装 |
| `query()` | `query.ts` | 对外暴露的查询生成器 |
| `queryLoop()` | `query.ts` | 真正的模型循环状态机 |

### 9.4 工具与命令

| 符号 | 文件 | 作用 |
| --- | --- | --- |
| `getAllBaseTools()` | `tools.ts` | 内建工具全集 |
| `getTools()` | `tools.ts` | 按权限与模式筛选内建工具 |
| `assembleToolPool()` | `tools.ts` | 合并 built-in tools 与 MCP tools |
| `COMMANDS()` | `commands.ts` | 内建命令注册表 |
| `getCommands()` | `commands.ts` | 组合全部命令来源 |
| `getSkillToolCommands()` | `commands.ts` | 返回模型可调用的 prompt 命令 |

### 9.5 插件与技能

| 符号 | 文件 | 作用 |
| --- | --- | --- |
| `useManagePlugins()` | `hooks/useManagePlugins.ts` | 插件生命周期管理 |
| `parseSkillFrontmatterFields()` | `skills/loadSkillsDir.ts` | 解析技能 frontmatter |
| `createSkillCommand()` | `skills/loadSkillsDir.ts` | 把技能转为统一命令对象 |
| `getSkillDirCommands()` | `skills/loadSkillsDir.ts` | 加载技能目录 |

### 9.6 远程

| 符号 | 文件 | 作用 |
| --- | --- | --- |
| `RemoteSessionManager` | `remote/RemoteSessionManager.ts` | 远程会话管理器 |
| `createRemoteSessionConfig()` | `remote/RemoteSessionManager.ts` | 远程配置构造器 |

---

## 10. 模块依赖关系

### 10.1 核心依赖骨架

主链路的内部依赖关系可以简化为：

```text
entrypoints/cli.tsx
    -> main.tsx
        -> commands.ts
        -> tools.ts
        -> state/*
        -> hooks/*
        -> replLauncher.tsx
            -> components/App.tsx
            -> screens/REPL.tsx
                -> QueryEngine.ts / query.ts / Tool.ts / AppState
```

### 10.2 命令与技能的关系

```text
commands.ts
    -> skills/loadSkillsDir.ts
    -> plugins/*
    -> workflow command builder
    -> built-in commands
```

结论：命令层是扩展系统的汇总边界。

### 10.3 工具与 MCP 的关系

```text
tools.ts
    -> built-in tools
    -> permission filtering
    -> MCP tools
    -> final merged tool pool
```

结论：工具层是模型能力暴露的统一边界。

### 10.4 QueryEngine 与上下游的关系

```text
REPL / SDK caller
    -> QueryEngine
        -> ToolUseContext
        -> commands
        -> tools
        -> mcpClients
        -> AppState
        -> query.ts
```

结论：`QueryEngine` 依赖范围很广，是核心胶水层。

### 10.5 Remote 与会话层关系

```text
useRemoteSession()
    -> RemoteSessionManager
        -> SessionsWebSocket
        -> sendEventToRemoteSession()
```

---

## 11. 外部依赖与技术栈

### 11.1 已能直接从源码确认的技术栈

根据 import 与入口代码，可直接确认以下技术要素：

- **Bun**
  - 存在 `import { feature } from 'bun:bundle'`
  - 说明构建与特性裁剪依赖 Bun

- **TypeScript / TSX**
  - 主工程大量使用 `.ts` / `.tsx`

- **React**
  - UI 组件与 hooks 大量依赖 `react`

- **Ink 风格 TUI**
  - 存在自定义 `ink/` 目录与 `Root` 渲染路径
  - 说明这是终端 UI，而非浏览器 Web UI

- **Commander**
  - `main.tsx` 使用 `@commander-js/extra-typings`

- **Model Context Protocol SDK**
  - `entrypoints/mcp.ts` 使用 `@modelcontextprotocol/sdk`

- **Zod**
  - 存在 `zod/v4` 与 JSON schema 转换逻辑

- **Lodash-es**
  - 广泛使用 `lodash-es`

- **Chalk**
  - CLI/TUI 输出着色

### 11.2 从 import 观察到的代表性外部库

以下库在源码中可见，但由于缺少 `package.json`，这里只能视为“观察到被使用”，不能保证版本与完整清单：

- `react`
- `@commander-js/extra-typings`
- `@modelcontextprotocol/sdk`
- `zod/v4`
- `lodash-es`
- `chalk`
- `chokidar`
- `execa`
- `figures`
- `ignore`
- `usehooks-ts`
- `wrap-ansi`

### 11.3 依赖关系的注意事项

由于仓库缺少构建清单，以下内容目前都是未知：

- 完整依赖列表
- 精确版本号
- 脚本名与 build pipeline
- monorepo / workspace 配置是否被裁剪

因此，本文只给出“代码层可见依赖”，不把它误写成可直接安装的依赖清单。

---

## 12. 运行方式

### 12.1 已证实的事实

从源码可直接确认：

- 项目使用 Bun 特性裁剪与构建相关能力
- 内部某些工作流明确提到了：
  - `bun run watch`
  - `bun run start`

### 12.2 当前无法直接证实的部分

由于缺少 `package.json`：

- 无法确认 `bun run start` 的脚本定义
- 无法确认最终可执行命令的完整格式
- 无法确认开发态与发布态的构建命令
- 无法确认需要哪些环境变量和本地配置文件

### 12.3 基于源码的合理推断

如果这是一个完整未裁剪仓库，主工程很可能采用如下运行形态：

1. 使用 Bun 构建或直接运行入口
2. 默认入口为 `entrypoints/cli.tsx`
3. 交互模式由 `main.tsx -> launchRepl() -> App + REPL` 驱动
4. MCP 模式由 `entrypoints/mcp.ts` 单独启动
5. 远程模式由 `entrypoints/cli.tsx` 分流到 `bridgeMain()`

但需要强调：**上述只是结构性推断，不等于当前工作区已可直接运行。**

### 12.4 面向源码阅读者的建议运行验证顺序

如果后续有人补全清单文件并尝试恢复运行环境，建议按以下顺序验证：

1. 验证 Bun 环境
2. 确认入口是否指向 `entrypoints/cli.tsx`
3. 验证最小 CLI 启动
4. 再验证 REPL 模式
5. 最后验证 MCP / remote-control / daemon 等特殊模式

---

## 13. 独立子项目：`chanlun_backtest/`

`chanlun_backtest/` 不是主 Agent 的一个模块，而是一个独立 Python 研究项目。

它的职责是：

- 下载 Binance 历史数据
- 实现缠论、SMC、线段等量化逻辑
- 执行回测
- 输出统计与验证结果

它有自己独立的 README、Python 脚本与复现方式，不与主 TypeScript Agent 运行链路直接耦合。

因此在阅读仓库时应明确区分：

- **主工程**：AI coding agent runtime
- **子项目**：量化回测研究代码

---

## 14. 阅读顺序建议

如果目标是快速理解主工程，建议按下面顺序阅读：

1. `README.md`
2. `entrypoints/cli.tsx`
3. `main.tsx`
4. `commands.ts`
5. `tools.ts`
6. `Tool.ts`
7. `QueryEngine.ts`
8. `query.ts`
9. `state/AppStateStore.ts`
10. `hooks/useManagePlugins.ts`
11. `skills/loadSkillsDir.ts`
12. `remote/RemoteSessionManager.ts`
13. `entrypoints/mcp.ts`

如果目标是理解“扩展系统”，优先看：

- `commands.ts`
- `hooks/useManagePlugins.ts`
- `skills/loadSkillsDir.ts`
- `tools.ts`

如果目标是理解“Agent 如何真正执行一轮请求”，优先看：

- `QueryEngine.ts`
- `query.ts`
- `Tool.ts`

---

## 15. 关键结论

### 15.1 这个仓库本质上是什么

它本质上不是一个简单命令行包装器，而是一套完整的 AI Agent 平台运行时，包含：

- 会话引擎
- 工具框架
- 命令框架
- 技能框架
- 插件框架
- TUI 交互界面
- MCP 对接能力
- 远程控制与后台会话能力

### 15.2 哪些文件最核心

如果只选最关键的 6 个文件：

- `entrypoints/cli.tsx`
- `main.tsx`
- `commands.ts`
- `tools.ts`
- `QueryEngine.ts`
- `query.ts`

### 15.3 当前仓库状态对分析的影响

由于缺少标准构建清单，本文档能完整回答：

- 架构如何分层
- 模块职责是什么
- 关键类与函数有哪些
- 内部依赖关系如何组织
- 程序入口和主要运行模式是什么

但不能完全回答：

- 最终可执行构建命令是什么
- 精确依赖版本是什么
- 当前工作区能否直接成功运行

这些部分属于“待补环境信息”而非“代码不可理解”。

