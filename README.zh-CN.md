# MCP Anything Skill

**给 Agent 一个软件项目，让它完成 MCP 接入，并拿出确实能用的证据。**

[English](README.md) · [安装说明](docs/skill-install.md) · [轻量示例](examples/sqlite) · [验证记录](docs/skill-validation.md)

很多软件有命令行或 Python 接口，但 Agent 无法直接把它们当成可靠的工具使用。MCP Anything 是一套给编程 Agent 使用的 skill：读取真实接口，挑选有用的功能，编写 MCP 适配器，安装运行，最后通过实际调用检查结果。

它支持从 GitHub、本地仓库、命令行程序、库、数据库或 API 文档开始。使用你已有的编程 Agent，不需要额外购买生成服务或配置另一套模型 API Key。目标软件自身的依赖和访问权限仍然需要准备；“Anything”不代表任何仓库都能一键转换。

## 怎么用

将本仓库的 `skills/mcp-anything` 文件夹复制到 Agent 的 skills 目录：Codex 通常是 `~/.codex/skills/`，Claude Code 通常是 `~/.claude/skills/`。新开会话后，直接说明目标软件和你要做的事。Windows、ZIP 安装命令见[安装说明](docs/skill-install.md)。

例如：

> 使用 $mcp-anything，把这个 GitHub 仓库接成 MCP。我需要它的文件检查和格式转换功能。请安装适配器，跑一个真实小例子，给出客户端配置和简短使用说明。

> 使用 $mcp-anything，把本地 SQLite 数据库接成只读 MCP，支持查看表、字段和少量数据；用示例数据验证，不要改动原数据库。

> 使用 $mcp-anything，把这个 API 的搜索功能接成 MCP，密钥通过环境变量传入，并验证一次实际请求。

## 会交付什么

- 能实际调用的适配器，参数类型、单位、范围和输出字段清楚。
- 安装步骤与 MCP 客户端配置。
- 给 Agent 看的使用指南：准确的输入格式、短例子、失败时如何处理。
- 实际测试结果，以及哪些功能完成、哪些条件尚未验证。

如果已有维护良好的 MCP 能满足需求，会优先使用。需要新开发时，Agent 选择稳定接口并实现，而不是把所有内部函数直接暴露出去。长任务采用“提交 → 查询 → 取结果”，并处理取消与断开连接。

自带脚本可以检查本地仓库、生成起始项目、通过真实 MCP 连接检查工具。起始项目会明确返回 `adapter_ready: false`；真正实现并验证目标功能之后，才算转换完成。当前没有自动把 OpenAPI、GraphQL 或 gRPC 整体翻译成 MCP 的生成器。

## 两个例子

| 示例 | 能做什么 | 适合谁 |
| --- | --- | --- |
| [SQLite](examples/sqlite) | 只读查看表、字段和受限行数的数据 | 想快速试用、不想安装大型软件的人 |
| [LAMMPS](adapters/lammps/README.zh-CN.md) | 分子动力学小算例、任务查询、取消和结果文件 | 需要接入科研计算或其他长任务的人 |

LAMMPS 已保留 Windows、Linux、stdio 和平台 HTTP 的真实验证记录。小算例证明工具链可以工作，不代表材料性质或聚合物 Tg 已完成科学验证。共享服务也没有按用户隔离任务。Skill 版本为 **0.3.0**，LAMMPS 适配器保持 **0.2.0**。

## 与同名项目的关系

参考了 [gabrielekarra/mcp-anything](https://github.com/gabrielekarra/mcp-anything) 的任务描述、功能选择和 Agent 使用指南思路。该项目现在也有 skill/plugin，因此不能用“它不是 skill”来区分。我们侧重让已有编程 Agent 完成软件接入，并以真实调用、明确边界和可复现交付检验结果。详细比较见[相关工作](docs/related-work.md)。

原创代码和文档采用 MIT 许可。LAMMPS 等上游软件保留各自许可，并单独安装。开发与打包命令见[英文说明](README.md#develop-and-package)。
