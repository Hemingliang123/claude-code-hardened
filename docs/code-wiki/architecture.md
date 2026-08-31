# 主体架构说明

本文件聚焦仓库主干代码，即根目录下的 TypeScript/Bun CLI/TUI 智能代理应用，不覆盖 `chanlun_backtest/` 子项目。

## 1. 系统定位

从根目录 `README.md` 和源码结构来看，主应用是一套终端形态的智能代理框架，核心能力包括：

- CLI 启动与参数分流。
- 基于 React/Ink 的终端交互界面。
- 命令系统与工具系统的统一装配。
- Query 循环、工具调用、上下文压缩与任务预算控制。
- MCP、插件、技能、远程会话、bridge、后台任务等扩展能力。

它不是一个单纯的命令行包装器，而是一个“交互层 + 状态层 + 推理编排层 + 扩展层”组合而成的完整代理运行时。

## 2. 启动链路

主启动链路可概括为：

`entrypoints/cli.tsx -> main.tsx -> commands/tools/app state 初始化 -> REPL 或 headless QueryEngine -> query 循环 -> tool/task/remote/bridge 执行`

### 2.1 轻量入口：`entrypoints/cli.tsx`

`entrypoints/cli.tsx` 是 bootstrap 入口，负责在尽量少加载模块的前提下处理“快速路径”。

关键职责：

- 处理 `--version` 这类零依赖快速输出。
- 根据不同参数分流到 daemon、remote-control、bridge、background session 等模式。
- 对某些能力使用 `feature('...')` 做条件分支，说明构建系统支持特性裁剪。
- 在非快速路径下再动态导入完整主程序。

这里可以把它理解为“前台分诊台”：先判断是不是简单需求，如果不是，再把请求交给完整应用。

### 2.2 主入口：`main.tsx`

`main.tsx` 是完整主程序入口，也是主应用依赖最密集的装配层。

它承担的职责包括：

- 初始化配置、认证、策略限制、遥测与环境状态。
- 拉取命令、工具、MCP、插件、技能、agent 定义等运行时资源。
- 初始化应用状态 `AppState`。
- 根据运行模式决定进入 REPL、恢复会话、远程会话、assistant、SSH、direct connect 等路径。

从 import 面可以看出，`main.tsx` 不是“业务逻辑密集层”，而是“系统装配中心”。

## 3. 架构分层

### 3.1 入口与装配层

核心文件：

- `entrypoints/cli.tsx`
- `main.tsx`
- `entrypoints/init.ts`
- `setup.ts`
- `replLauncher.tsx`

职责：

- 建立运行环境。
- 初始化配置与全局状态。
- 选择执行模式。
- 启动 TUI 或 headless 模式。

### 3.2 UI 与交互层

核心目录：

- `components/`
- `screens/`
- `context/`
- `hooks/`
- `ink/`
- `keybindings/`

其中：

- `screens/REPL.tsx` 是主交互屏幕，负责把消息流、命令输入、工具执行、权限弹窗、远程状态、任务列表等拼接成一个工作台。
- `components/App.tsx` 是顶层 UI 外壳，主要负责 Provider 组合。
- `ink/` 看起来是本项目自带的终端渲染实现或深度定制层，而不仅仅是简单使用第三方组件。
- `hooks/` 承载大量“运行态编排逻辑”，并不只是传统意义上的纯 UI hook。

这一层的特点是：终端 UI、状态同步、工具权限、消息队列、远程会话高度耦合，`REPL.tsx` 因而成为非常重要的阅读入口。

### 3.3 状态层

核心文件：

- `state/store.ts`
- `state/AppStateStore.ts`
- `state/AppState.tsx`
- `state/selectors.ts`
- `state/onChangeAppState.ts`

关键特点：

- `state/store.ts` 提供通用 `createStore<T>()`。
- `state/AppStateStore.ts` 定义了超大 `AppState` 结构。
- `AppState` 不仅保存 UI 状态，还承载任务、MCP、插件、权限、bridge、remote、文件历史、通知、elicitation、session hook 等全局运行态数据。

这说明项目使用的是“集中式全局会话状态”模式，而不是按功能域拆分成多个完全独立的 store。

## 4. 核心模块职责

### 4.1 命令系统

核心文件：

- `commands.ts`
- `commands/`

命令系统的设计要点：

- `commands.ts` 中的 `COMMANDS()` 汇总内建命令。
- `getCommands(cwd)` 会把内建命令、动态发现的技能、插件命令、工作流命令合并成最终可用命令集。
- 命令可带 availability / enabled 判定，因此命令可用性取决于当前认证态、配置态和 feature gate。

适用场景：

- 新增 slash command。
- 排查命令为什么没出现在当前会话里。
- 理解技能、插件、动态命令如何进入命令池。

### 4.2 工具系统

核心文件：

- `Tool.ts`
- `tools.ts`
- `tools/`

设计要点：

- `Tool.ts` 定义工具的核心抽象，包括 `ToolUseContext`、工具调用返回结构、工具匹配与查找等基础能力。
- `ToolUseContext` 很重要，它把命令、工具、MCP 客户端、AppState、文件缓存、权限与交互能力都聚合到一起，相当于工具执行时的“运行容器”。
- `tools.ts` 中的 `getAllBaseTools()` 负责注册基础工具集合，包括 Agent、Bash、Glob/Grep、Read/Edit/Write、Web、Todo、Skill、Plan、Task、MCP 资源等。
- `getTools(permissionContext)` 则根据权限上下文和运行模式裁剪可见工具。

适用场景：

- 新增或修改工具。
- 理解某个工具为什么能被模型看到。
- 排查权限规则如何影响工具暴露。

### 4.3 Query 与 Agent 编排

核心文件：

- `QueryEngine.ts`
- `query.ts`
- `query/`
- `tasks/`
- `Task.ts`

设计要点：

- `QueryEngine` 是会话级编排器，持有消息、读文件状态、权限拒绝记录、usage 统计等跨轮状态。
- `QueryEngineConfig` 把 `cwd`、`tools`、`commands`、`mcpClients`、`agents`、`getAppState/setAppState`、预算参数等关键依赖统一注入。
- `submitMessage()` 是 headless/SDK 入口，会组装 system prompt、用户上下文、权限包装器，再调用底层 `query()`。
- `query.ts` 中的 `query()` 与 `queryLoop()` 负责真正的循环执行，包括模型请求、工具执行、compact、task budget、skill discovery prefetch、memory prefetch 等。

这部分是主应用的“引擎室”，如果你要理解代理如何思考、如何用工具、如何持续多轮运行，应从这里进入。

### 4.4 远程、Bridge 与会话协同

核心目录：

- `remote/`
- `bridge/`
- `server/`
- `tasks/`

职责拆分大致如下：

- `remote/` 负责远程会话与消息适配。
- `server/` 提供 direct connect 相关会话能力。
- `bridge/` 支持 remote-control / bridge 模式，负责工作轮询、会话拉起、鉴权与消息传输。
- `tasks/` 统一抽象本地、远程、后台、teammate 等任务。

如果把主应用看作一个“单用户代理工作台”，这些目录就是它扩展成“多会话、多节点、远程协同系统”的关键部件。

### 4.5 插件、技能与 MCP

核心目录：

- `plugins/`
- `skills/`
- `services/`

观察到的模式：

- 技能和插件并不是命令系统之外的旁路，而是会回流到命令池和工具上下文中。
- `main.tsx` 会初始化 bundled plugins 和 bundled skills。
- `services/` 下承担大量运行时基础设施，包括 API、analytics、MCP、policy、LSP、notifier 等。

因此，这一层更适合被理解为“平台扩展层”，而不是若干零散 helper。

## 5. 关键类与函数索引

以下符号值得优先熟悉。

### 5.1 启动与会话

- `entrypoints/cli.tsx::main`
  - CLI bootstrap，优先处理快速路径与特殊模式分流。
- `main.tsx::main`
  - 完整程序入口和系统装配中心。
- `replLauncher.tsx::launchRepl`
  - 把 `<App>` 与 `<REPL>` 真正挂载到终端界面。

### 5.2 命令与工具

- `commands.ts::COMMANDS`
  - 内建命令表。
- `commands.ts::getCommands`
  - 汇总技能、插件、工作流命令与内建命令。
- `tools.ts::getAllBaseTools`
  - 基础工具注册中心。
- `tools.ts::getTools`
  - 基于权限与运行模式过滤工具。
- `Tool.ts::ToolUseContext`
  - 工具运行上下文总入口。
- `Tool.ts::Tool`
  - 工具接口抽象。

### 5.3 Query 引擎

- `QueryEngine.ts::QueryEngine`
  - 会话级查询引擎。
- `QueryEngine.ts::submitMessage`
  - 单轮用户输入的编排入口。
- `query.ts::query`
  - 对外暴露的生成器接口。
- `query.ts::queryLoop`
  - 实际循环执行逻辑。

### 5.4 UI 与状态

- `components/App.tsx`
  - 顶层 Provider 外壳。
- `screens/REPL.tsx`
  - 主工作台与消息交互中心。
- `state/AppStateStore.ts::AppState`
  - 全局应用状态定义。
- `state/AppStateStore.ts::getDefaultAppState`
  - 初始状态构造函数。

## 6. 目录职责速查

- `assistant/`
  - assistant 模式相关代码。
- `bridge/`
  - remote-control / bridge 模式与协议处理。
- `buddy/`
  - companion / buddy 相关交互能力。
- `commands/`
  - 各类 slash command 实现。
- `components/`
  - 可复用 UI 组件。
- `constants/`
  - 常量、系统提示、产品配置。
- `context/`
  - React context。
- `entrypoints/`
  - 各入口文件。
- `hooks/`
  - 运行态 hook 与编排逻辑。
- `ink/`
  - 终端渲染基础层。
- `keybindings/`
  - 键位绑定与解析。
- `plugins/`
  - 内建插件装配入口。
- `query/`
  - query 相关子模块。
- `remote/`
  - 远程会话管理。
- `screens/`
  - 页面级视图。
- `server/`
  - direct connect 等服务端风格会话能力。
- `services/`
  - API、analytics、MCP、notifier 等基础服务。
- `skills/`
  - 技能装配与加载。
- `state/`
  - 全局状态与 selector。
- `tasks/`
  - 任务抽象与后台会话。
- `tools/`
  - 工具实现。
- `types/`
  - 类型定义。
- `utils/`
  - 各种底层基础设施与帮助模块。

## 7. 依赖关系主链

对阅读最有帮助的依赖主链如下：

### 7.1 启动主链

`entrypoints/cli.tsx -> main.tsx -> getCommands/getTools -> launchRepl 或 QueryEngine`

### 7.2 交互主链

`REPL.tsx -> query.ts -> Tool.ts/tools.ts -> tools/* -> services/* 或 tasks/*`

### 7.3 状态主链

`state/store.ts -> AppStateStore.ts -> App.tsx / REPL.tsx / QueryEngine.ts`

### 7.4 扩展主链

`skills/* + plugins/* + services/mcp/* -> commands.ts / ToolUseContext`

### 7.5 远程主链

`bridge/* 或 remote/* -> 消息适配 -> REPL 消息流 / 后台任务状态`

## 8. 阅读顺序建议

如果你要快速理解主应用，建议按这个顺序读：

1. `README.md`
2. `entrypoints/cli.tsx`
3. `main.tsx`
4. `commands.ts`
5. `tools.ts`
6. `Tool.ts`
7. `QueryEngine.ts`
8. `query.ts`
9. `screens/REPL.tsx`
10. 与目标功能相关的 `services/`、`tasks/`、`tools/` 子目录

## 9. 当前已知边界

- 当前仓库缺少标准前端/Node 项目的构建元数据，因此无法仅依据仓库文件确认主应用的统一构建命令。
- 从源码可见 Bun 特性与大量 `src/...`、`.js` 后缀导入、feature gate 使用模式，说明它原本来自一个完整工程，但当前快照并不完整。
- 因此，本文件适合用于架构理解与改动定位，不适合直接当作“可执行构建说明”使用；构建与验证信息请以 `development-and-validation.md` 中“可确认/未知”边界为准。
