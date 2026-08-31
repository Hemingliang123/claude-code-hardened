# 模块职责拆解

## 1. 根目录关键文件

### `main.tsx`

职责：

- 主程序初始化
- 环境与安全设置
- 配置、模型、权限、插件、技能、MCP 的装配
- 交互式与非交互式模式切换
- 状态 store 初始化

适合在你想理解“程序从哪里真正开始跑”时优先阅读。

### `QueryEngine.ts`

职责：

- 统一处理 prompt 提交
- 组织系统提示词与消息历史
- 执行模型回合
- 触发工具调用
- 追踪权限拒绝、用量与中断状态

适合在你想理解“模型如何驱动工具与命令”时阅读。

### `Tool.ts`

职责：

- 定义工具上下文与结果协议
- 约束工具的调用方式
- 作为所有工具实现的公共接口层

### `commands.ts`

职责：

- 聚合内建命令、技能命令、插件命令、MCP 命令
- 做启用态过滤、可用性判断、缓存清理

### `tools.ts`

职责：

- 聚合基础工具
- 根据 feature flag/环境变量做工具裁剪
- 为模型提供最终工具清单

## 2. `entrypoints/`

该目录负责程序的早期分发与特殊入口。

### 主要职责

- 在加载大型模块前识别快速路径
- 支持特殊运行模式，如 MCP、bridge、daemon、runner 等
- 为不同入口设置统一的环境标记

### 代表文件

- `cli.tsx`: CLI 早期分流入口
- `init.ts`: 初始化相关入口逻辑
- `mcp.ts`: MCP 相关入口

## 3. `commands/`

该目录存放命令定义，是 slash command 行为的主要来源之一。

### 主要职责

- 定义命令名称、描述与执行行为
- 区分 prompt 型命令与 local 型命令
- 为交互式与非交互式模式提供命令入口

### 目录特征

文件命名基本按业务能力划分，例如：

- `review.ts`
- `security-review.ts`
- `commit.ts`
- `install.tsx`
- `statusline.tsx`
- `ultraplan.tsx`

这意味着命令模块是“按功能横向切片”的。

## 4. `components/`

该目录是终端 UI 组件层，数量很多，说明主工程并不是简单输出字符串，而是完整的终端应用。

### 主要职责

- 消息渲染
- 输入组件
- 状态条与对话框
- 任务列表
- MCP 管理面板
- 插件/设置/通知 UI

### 重要子域

- 与消息显示相关：`Message.tsx`、`Messages.tsx`、`MessageRow.tsx`
- 与输入交互相关：`TextInput.tsx`、`VimTextInput.tsx`
- 与 MCP 相关：`components/mcp/*`
- 与任务/状态相关：`TaskListV2.tsx`、`StatusLine.tsx`

## 5. `state/`

该目录负责全局状态建模、store 与 selector。

### 主要职责

- 定义 `AppState`
- 提供 store 创建与订阅
- 为 React 组件提供状态访问入口
- 处理状态变更回调

### 关键文件

- `AppStateStore.ts`: 状态模型与默认值
- `AppState.tsx`: Provider 与 hooks
- `store.ts`: store 抽象
- `selectors.ts`: 状态选择器

## 6. `services/`

该目录是服务层，承接跨模块复用的业务能力。

### 主要职责

- MCP 接入
- 限流与配额处理
- 通知与日志
- 语音能力
- VCR/录制回放
- 诊断与内部遥测

### 其中最重要的子域

#### `services/mcp/`

职责：

- 管理 MCP 连接生命周期
- 拉取远端工具、命令、资源
- 错误归集与状态同步
- 处理 channel permission 与 elicitation

#### 其他服务

- `voice.ts` / `voiceStreamSTT.ts`: 语音链路
- `notifier.ts`: 通知能力
- `vcr.ts`: 录制与回放
- `claudeAiLimits.ts`: 模型/配额相关逻辑

## 7. `remote/`

该目录负责“远程会话客户端”语义。

### 主要职责

- 与远程会话建立 WebSocket 链接
- 接收远端 SDK 消息
- 处理工具权限请求
- 向远端发消息

### 关键文件

- `RemoteSessionManager.ts`
- `SessionsWebSocket.ts`
- `sdkMessageAdapter.ts`

## 8. `server/`

该目录负责“本地直连服务端”语义，与 `remote/` 相对。

### 主要职责

- 创建 direct-connect session
- 管理本地 WebSocket 会话
- 转发消息与权限响应

### 关键文件

- `createDirectConnectSession.ts`
- `directConnectManager.ts`

## 9. `hooks/`

该目录存放前端/终端交互层的副作用逻辑。

### 主要职责

- 连接 REPL、IDE、remote session、SSH、任务系统
- 聚合工具与命令
- 管理用户输入、滚动、快捷键、超时、通知

### 特征

这类文件通常不是“业务核心算法”，但对于理解界面行为与事件流非常关键。

## 10. `context/`

该目录提供 React Context。

### 主要职责

- 通知共享
- mailbox
- modal/overlay
- voice
- fps/stats

它解决的是“跨组件共享运行时上下文”的问题。

## 11. `ink/`

该目录不是普通业务代码，而是终端 UI 渲染基础设施。

### 主要职责

- 终端节点与布局
- 事件分发
- 文本测量与换行
- 渲染与屏幕 diff
- 终端适配

这意味着主工程对终端界面控制比较深，并不完全依赖上层 UI 库默认行为。

## 12. `utils/`

该目录是项目中最宽泛的一层基础设施。

### 主要职责

- 配置读写
- 会话存储
- 路径与文件处理
- 权限与认证
- Git/Worktree
- 日志与调试
- 系统提示词与上下文构造
- shell、代理、环境变量、调度与 cron

### 阅读策略

不要试图一次性读完 `utils/`。建议按主题反查：

- 想找配置，看 `config.ts`、`settings/*`
- 想找权限，看 `permissions/*`
- 想找提示词，看 `systemPrompt.ts`
- 想找会话恢复，看 `session*` 相关文件

## 13. `skills/`

该目录负责技能注册与加载。

### 主要职责

- 加载 bundled skills
- 加载本地技能目录
- 与 MCP skill 生成逻辑协同

技能系统和命令系统紧密关联，但不是一回事：

- 命令面向用户显式调用
- 技能既可被用户触发，也可被模型在合适时机选择

## 14. `plugins/`

该目录处理内建插件与插件生态接入。

### 主要职责

- 注册内建插件
- 为运行时合并插件提供的命令、技能、MCP 能力

## 15. `tasks/`

该目录负责后台任务抽象。

### 主要职责

- 任务状态定义
- 本地主会话任务封装
- 任务停止与展示辅助

与 `AppState.tasks` 一起组成任务管理系统。

## 16. `types/`

该目录集中存放通用类型定义。

### 主要职责

- 命令类型
- 插件类型
- 权限类型
- Hook 类型
- 输入类型

这层是工程内的重要契约边界。

## 17. `chanlun_backtest/`

这是独立的 Python 子项目，职责边界比较清晰。

### 核心文件职责

- `download_data.py`: 下载 Binance 历史 K 线并保存为 parquet
- `chanlun_engine.py`: 缠论笔、中枢、背驰、买卖点引擎
- `smc_engine.py`: SMC 特征与结构引擎
- `duan_engine.py`: 线段构建
- `backtest.py`: 撮合与绩效统计
- `run_backtest.py`: 单周期回测脚本
- `run_backtest_multilevel.py`: 多级别联立回测脚本
- `test_smc_engine.py` / `test_duan_engine.py`: 合成数据测试

## 18. `.github/workflows/`

当前仓库中存在 GitHub Actions 工作流，但从已见内容看更像示例型 SLSA provenance 配置，而不是完整项目 CI。

因此：

- 可以把它看作供应链/元数据样例
- 不能把它当作主工程完整构建方式的权威来源

## 19. 模块边界总结

如果用一句话概括目录职责：

- `entrypoints/` 决定从哪里进
- `main.tsx` 决定怎么起
- `commands.ts` / `tools.ts` 决定能做什么
- `QueryEngine.ts` 决定如何执行
- `state/` 决定状态放哪里
- `components/` / `hooks/` / `ink/` 决定界面怎么表现
- `services/` / `remote/` / `server/` 决定怎样连外部系统
- `chanlun_backtest/` 是独立的 Python 研究子系统
