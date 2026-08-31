# Code Wiki

本目录是对当前仓库源码的结构化解读，目标是帮助阅读者快速理解：

- 仓库整体组成与技术栈
- 主 TypeScript/Bun CLI 工程的架构与执行链路
- 主要目录与模块职责
- 关键类与函数的职责边界
- Python 子项目 `chanlun_backtest/` 的算法与运行流程
- 当前仓库已确认的运行方式、依赖与已知未知项

## 适用范围

本 Wiki 基于当前工作区中的真实文件内容编写，重点覆盖两部分：

1. 根目录下的 Bun/TypeScript/TSX CLI/TUI 工程
2. 子目录 `chanlun_backtest/` 下的 Python 回测工程

## 关键结论

- 仓库是一个混合工程，而不是单一应用。
- 主工程是一个 AI Coding Agent 风格的 CLI/TUI 应用，核心由命令系统、查询引擎、工具系统、MCP 集成、远程会话与终端 UI 组成。
- `chanlun_backtest/` 是一个相对独立的 Python 量化回测子项目，围绕缠论、SMC 与线段结构递归做因果式回测。
- 当前检出内容中未发现主 TypeScript 工程常见的 `package.json`、`tsconfig.json`、`Dockerfile`、`Makefile` 等构建清单，因此主工程的标准安装/构建命令无法从仓库内权威确认。

## 文档导航

- `01-repository-overview.md`: 仓库总览、技术栈、目录结构与整体关系
- `02-main-cli-architecture.md`: 主 CLI/TUI 工程的启动流程、主执行链路与状态模型
- `03-module-responsibilities.md`: 按目录拆解的模块职责说明
- `04-key-classes-and-functions.md`: 关键类、函数与核心接口说明
- `05-dependencies-and-runtime.md`: 依赖关系、运行方式、测试与 CI 现状
- `06-chanlun-backtest.md`: Python 子项目的算法结构、脚本职责与数据流

## 阅读建议

如果你第一次接触这个仓库，推荐按下面顺序阅读：

1. 先看 `01-repository-overview.md`
2. 再看 `02-main-cli-architecture.md`
3. 想定位具体代码时看 `03-module-responsibilities.md` 和 `04-key-classes-and-functions.md`
4. 只关注 Python 回测部分时，直接看 `06-chanlun-backtest.md`

## 已知未知项

以下内容在当前仓库中无法被权威确认，因此本 Wiki 不做臆测：

- 主 TypeScript 工程的官方安装命令
- 主 TypeScript 工程的标准构建流程
- 主 TypeScript 工程的正式测试入口
- 根仓库对外发布时使用的完整 CI/CD 流水线

这些未知项会在对应章节中明确标注。
