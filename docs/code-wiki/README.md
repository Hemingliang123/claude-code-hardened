# Code Wiki

本目录是针对当前仓库生成的结构化代码 Wiki，目标是帮助第一次接触该仓库的开发者或 AI 助手快速回答四个问题：

1. 这个仓库整体在做什么。
2. 主体代码的启动链路和模块边界是什么。
3. `chanlun_backtest/` 这个 Python 子项目如何运行、测试与扩展。
4. 当前仓库里哪些构建/校验信息是明确存在的，哪些仍然未知。

## 仓库一句话总结

该仓库主体是一个基于 TypeScript + React/Ink + Bun 特性构建的 CLI/TUI 智能代理源码快照，核心能力包括命令系统、工具系统、Query/Agent 编排、MCP 集成、权限控制、远程会话与任务管理；同时仓库中还包含一个相对独立的 Python 量化研究子项目 `chanlun_backtest/`。

根目录的 `README.md` 将该仓库描述为 Claude Code 的源码泄漏快照，且明确说明除 `README.md` 外未额外增删改主代码。Wiki 中关于仓库背景的描述均以该说明为准。

## 文档导航

- `architecture.md`
  - 主 TypeScript/Bun CLI 应用的架构分层、启动链路、关键模块职责、关键类与函数入口。
- `chanlun-backtest.md`
  - Python 子项目的目标、目录结构、数据流、关键类与函数、运行方式与已知边界。
- `development-and-validation.md`
  - 仓库结构清单、已发现的工作流与脚本入口、可确认的运行/测试方法、当前无法确认的构建信息。

## 阅读建议

- 如果你要修改主 CLI/TUI 代码：先看 `architecture.md`，再结合目标目录深入源码。
- 如果你要运行或研究量化回测部分：直接看 `chanlun-backtest.md` 和 `development-and-validation.md`。
- 如果你要为 Copilot、AI Agent 或新成员提供仓库上下文：优先引用本目录三份文档中的“模块职责”“关键入口”“运行与验证”章节。

## 关键事实

- 仓库根目录未发现标准的 `package.json`、`tsconfig.json`、`pyproject.toml`、`go.mod`、`Cargo.toml` 或 `Makefile`。
- 因此，主 TypeScript CLI 的统一构建、测试、lint 命令在当前仓库快照中是未知的，不能臆造。
- 唯一具有明确安装与运行说明的是 `chanlun_backtest/`，其依赖和命令由子目录内 `README.md` 与 `requirements.txt` 给出。
- `.github/workflows/` 中仅发现一个 SLSA provenance 示例工作流，不构成该仓库主业务代码的真实 CI 构建链路。

## 维护建议

- 未来若仓库补充了构建清单或测试配置，应优先更新 `development-and-validation.md`。
- 如果新增主应用的模块级设计文档，建议从 `architecture.md` 的“目录职责”与“调用主链”两节增量维护，而不是重写整份 Wiki。
