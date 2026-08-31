# 主 CLI 架构

## 1. 架构目标

主工程本质上是一个可在终端中运行的 AI Agent 容器，负责把“用户输入”转成“模型回合 + 工具执行 + 状态更新 + 终端渲染”的完整闭环。

它同时支持：

- 交互式 REPL/TUI
- 非交互式 headless/print 模式
- MCP 工具与资源接入
- 远程会话与 direct-connect
- bridge/remote-control 风格的远控能力

## 2. 启动分层

### 2.1 早期入口：`entrypoints/cli.tsx`

`entrypoints/cli.tsx` 的职责不是承载完整业务，而是做“尽早分流”：

- 处理 `--version` 等零依赖快速路径
- 处理 `--dump-system-prompt` 等专用路径
- 处理 `remote-control`、`daemon`、后台任务、模板命令等模式
- 在普通情况下，延迟加载主程序 `main.tsx`

这样做的目的，是把高频、轻量、只读场景与完整主程序初始化隔离开，减少启动时无谓开销。

### 2.2 主入口：`main.tsx`

`main.tsx` 负责真正把程序拉起。它覆盖的事情很多，但可以归纳成 5 类：

1. 安全与环境初始化
2. 配置、认证、插件、技能、MCP 初始化
3. 命令与工具集装配
4. 交互式或非交互式状态创建
5. 进入渲染循环或 headless 查询执行

`initializeEntrypoint()` 会根据当前模式将入口标记为 `cli`、`sdk-cli`、`mcp` 或 GitHub Action 等不同形态。

## 3. 命令系统

### 3.1 汇聚入口：`commands.ts`

`commands.ts` 是命令注册中心，职责包括：

- 注册内建命令
- 载入技能目录命令
- 载入插件命令
- 载入工作流命令
- 做可用性过滤与去重
- 将“动态技能”插入命令列表

`COMMANDS()` 中汇总了大量内建命令，例如：

- `review`
- `securityReview`
- `mcp`
- `plugin`
- `stats`
- `plan`
- `tasks`

`getCommands(cwd)` 则是在运行期返回当前用户可见、可用的命令列表。

### 3.2 命令来源

主工程的命令不是单一来源，而是多路合并：

- 内建命令
- 本地技能目录命令
- 插件技能命令
- Bundled Skills
- Workflow 命令
- MCP 提供的技能命令

这意味着命令系统本质上是一个“统一命令目录”，而不是简单的静态数组。

## 4. 工具系统

### 4.1 总契约：`Tool.ts`

`Tool.ts` 定义了工具系统的核心抽象：

- `ToolUseContext`
- `ToolResult`
- `Tool`
- `toolMatchesName()`
- `findToolByName()`

`ToolUseContext` 体现了这个项目的设计重点：工具调用并不是纯函数，而是带着完整会话上下文运行，包括：

- 当前命令与工具集
- AppState 读写能力
- MCP 连接
- 中断控制
- 文件读取缓存
- 技能发现信息
- 对话消息上下文
- 权限与提示接口

换句话说，工具在这里是“会话内可组合执行单元”，不是单纯的 shell wrapper。

### 4.2 工具注册：`tools.ts`

`tools.ts` 是工具清单的真实来源。`getAllBaseTools()` 返回当前环境中理论可用的所有基础工具，例如：

- `AgentTool`
- `BashTool`
- `FileReadTool`
- `FileEditTool`
- `FileWriteTool`
- `GlobTool`
- `GrepTool`
- `WebFetchTool`
- `WebSearchTool`
- `TodoWriteTool`
- `AskUserQuestionTool`
- `SkillTool`

此外还有一些通过 feature flag 或环境变量控制的工具，例如：

- `WebBrowserTool`
- `WorkflowTool`
- `LSPTool`
- `TungstenTool`
- `RemoteTriggerTool`

因此工具系统具备明显的“按能力开关裁剪”特征。

## 5. 查询执行核心

### 5.1 `QueryEngine`

`QueryEngine.ts` 是主工程最核心的业务编排器。

其职责包括：

- 接收用户 prompt
- 构造系统提示词
- 结合命令、工具、MCP、技能与状态形成执行上下文
- 处理工具权限拒绝与回合预算
- 以流式方式产出 SDK 消息

`submitMessage()` 是核心执行入口，负责完成一个完整回合。

### 5.2 `ask()` 包装器

`ask()` 是面向“单次调用”的轻量封装，它创建 `QueryEngine`，再把 prompt 交给 `submitMessage()`。

这表明项目内部对“交互式会话”和“单次非交互式执行”采用的是同一套引擎，只是在上层包装与状态来源上有所区别。

## 6. 状态模型

### 6.1 状态中心：`state/AppStateStore.ts`

`AppState` 很大，说明这是一个会话型终端应用，而不是简单命令行工具。

状态中至少包含以下核心域：

- 设置与模型配置
- 命令输出与界面选择状态
- 工具权限上下文
- 远程连接状态
- bridge 状态
- 任务状态
- MCP 客户端、工具、命令与资源
- 插件启用状态与错误
- 通知、elicitation、todo、文件历史、归因信息

这也解释了为什么工具上下文必须带 `getAppState()` / `setAppState()`。

### 6.2 UI 接入：`components/App.tsx`

`components/App.tsx` 是顶层包装器，负责将以下上下文接入组件树：

- `AppStateProvider`
- `StatsProvider`
- `FpsMetricsProvider`

因此 UI 结构大致是：

```text
App
  -> AppStateProvider
  -> StatsProvider
  -> FpsMetricsProvider
  -> 具体界面组件
```

## 7. 交互式与非交互式分叉

### 7.1 交互式模式

交互式模式更偏传统 TUI：

- 使用 React + `ink/` 渲染终端界面
- 通过 hooks 与 context 组织事件、副作用与状态
- 支持光标、输入框、任务面板、MCP 设置、远程状态等 UI 元素

### 7.2 非交互式模式

在 `main.tsx` 的 `--print` 分支中，程序会：

- 创建一个 headless 版本的 `AppState`
- 初始化 `headlessStore`
- 为非交互模式过滤命令集
- 在后台逐步接入 MCP
- 继续复用相同的 QueryEngine 和工具系统

这说明 headless 不是另一个程序，而是同一运行时的“无界面外壳”。

## 8. MCP 与远程能力

### 8.1 MCP

MCP 子系统由 `services/mcp/` 主导，关键点是：

- 按配置初始化客户端
- 拉取远端的 tools、commands、resources
- 维护重连与错误状态
- 将远端能力并入本地 `AppState`

`useManageMCPConnections()` 体现了这一点。

### 8.2 远程会话

`remote/RemoteSessionManager.ts` 负责远程会话客户端逻辑：

- 通过 WebSocket 订阅远端会话
- 接收 SDK 消息
- 处理权限请求与取消
- 通过 HTTP 向远端发送消息

它把“会话 UI”与“远端执行环境”解耦了。

## 9. 架构特征总结

主工程体现出几个很鲜明的设计特征：

- 强入口分流：尽量把快速路径从完整主程序中摘出来
- 单引擎复用：交互式与非交互式共用 QueryEngine
- 状态中心化：大量运行时状态统一放入 AppState
- 工具优先：工具系统是模型执行的第一等公民
- 能力可插拔：命令、工具、技能、插件、MCP 都能动态合流
- 协议层丰富：本地、远端、MCP、bridge 多协议共存

## 10. 一句话理解

如果把主工程看成一个系统，它最准确的描述是：

“一个以 `QueryEngine` 为执行核心、以 `Tool`/MCP 为能力边界、以 `AppState` 为会话状态中心、以 React/Ink 为终端交互壳的 AI Agent CLI 平台。”
