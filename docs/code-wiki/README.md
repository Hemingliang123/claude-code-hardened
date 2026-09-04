# Code Wiki

本套文档基于当前工作区 `/workspace` 的实际源码生成，而不是基于仓库名称做推断。

需要先说明一个重要事实：

- 当前根目录 `README.md` 明确写的是 `Claude Code - Source Leak`。
- 因此，虽然你的输入是 `https://github.com/bytedance/trae-agent`，但我这套 Wiki 实际分析对象是当前工作区中的源码快照。
- 文档中的结论均以当前文件内容为准；对缺失的构建清单、锁文件、官方安装脚本等内容，统一标注为“未知”。

## 文档索引

1. [01-项目总览](./01-%E9%A1%B9%E7%9B%AE%E6%80%BB%E8%A7%88.md)
2. [02-主系统架构](./02-%E4%B8%BB%E7%B3%BB%E7%BB%9F%E6%9E%B6%E6%9E%84.md)
3. [03-核心模块详解](./03-%E6%A0%B8%E5%BF%83%E6%A8%A1%E5%9D%97%E8%AF%A6%E8%A7%A3.md)
4. [04-运行与依赖](./04-%E8%BF%90%E8%A1%8C%E4%B8%8E%E4%BE%9D%E8%B5%96.md)
5. [05-chanlun_backtest-子项目](./05-chanlun_backtest-%E5%AD%90%E9%A1%B9%E7%9B%AE.md)

## 建议阅读顺序

1. 先看“项目总览”，快速建立整体认知。
2. 再看“主系统架构”，理解主执行链和扩展点。
3. 再看“核心模块详解”，定位关键目录、类与函数。
4. 然后看“运行与依赖”，确认可运行范围与缺失项。
5. 最后看 `chanlun_backtest` 子项目，理解仓库中的独立 Python 项目。

## 核心结论

- 该仓库主体是一个大型 TypeScript CLI/TUI 智能代理系统。
- 入口链路是 `entrypoints/cli.tsx -> main.tsx -> run() -> REPL / QueryEngine / query()`。
- 系统核心由命令系统、工具系统、查询引擎、状态管理、桥接远控、MCP 与插件机制构成。
- 仓库中同时包含一个独立的 Python 量化回测子项目 `chanlun_backtest/`，与主 TypeScript 系统基本解耦。
- 当前源码快照缺少 `package.json`、锁文件、`tsconfig` 等清单，导致精确构建方式只能部分还原，不能伪造补齐。
