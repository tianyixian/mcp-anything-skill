# MCP Anything Skill

**给 Agent 软件名称、安装路径或网址，说明要做什么，让它完成 MCP 接入并验证结果。**

[English](README.md) · [安装说明](docs/skill-install.md) · [轻量示例](examples/sqlite) · [验证记录](docs/skill-validation.md)

MCP Anything 是一套给编程 Agent 使用的 skill：找到目标软件，选择可用接口，编写 MCP 适配器，安装运行，最后检查真实结果。无需先提供 GitHub 仓库；已安装的程序、桌面应用和网页也可以作为起点。

优先复用现成 MCP、API、命令行、库、插件或桌面自动化接口，再按任务需要选择浏览器或桌面界面操作。遇到无源码或接口不清楚的软件，可以按需调用 [REA](https://github.com/morluto/rea) 辅助分析。REA 是可选工具，不是必装依赖。

使用你已有的编程 Agent，不需要另一套模型 API Key。目标软件仍需自身的依赖和访问权限。“Anything”表示入口不局限于仓库，每项功能仍须具体实现和验证。[支持范围与证据](docs/software-support.md)

## 怎么用

将本仓库的 `skills/mcp-anything` 文件夹复制到 Agent 的 skills 目录：Codex 通常是 `~/.codex/skills/`，Claude Code 通常是 `~/.claude/skills/`。新开会话后，直接说明目标软件和你要做的事。Windows、ZIP 安装命令见[安装说明](docs/skill-install.md)。

例如：

> 使用 $mcp-anything，把这台电脑上的 FFmpeg 接成 MCP。我需要查看音频信息和把 WAV 转成 FLAC，请实际转换并验证音频样本。

> 使用 $mcp-anything，把 Microsoft Excel 接成 MCP。我需要创建测试工作簿、读取单元格并另存修改结果。使用已安装的 Excel 并检查保存结果。

> 使用 $mcp-anything，把这个笔记网页接成 MCP，支持查看和创建笔记。使用专用浏览器会话，创建后刷新并确认内容已保存。

GitHub、本地仓库、数据库和 API 文档仍然可用。请说明需要哪些功能；软件名称本身不代表它的全部功能都已支持。

## 会交付什么

- 能实际调用的适配器，参数类型、单位、范围和输出字段清楚。
- 安装步骤与 MCP 客户端配置。
- 给 Agent 看的使用指南：准确的输入格式、短例子、失败时如何处理。
- 实际测试结果，以及哪些功能完成、哪些条件尚未验证。

如果已有维护良好的 MCP 能满足需求，会优先使用。需要新开发时，Agent 选择稳定接口并实现。界面操作也要封装为具体业务功能，并检查操作后的状态；长任务继续采用提交、查询、取结果和取消流程。

新增的软件发现脚本可以查找程序名称、检查安装目录或判断网址入口，不启动目标程序、不请求网页。它只给出待验证的候选路线，不把“找到软件”当成“已经接通”。名称查找覆盖 PATH 和 Windows 的 App Paths 注册信息，无法定位或存在多个结果时需要补充路径或选择。

```sh
python skills/mcp-anything/scripts/discover_target.py ffmpeg --task "查看并转换音频"
python skills/mcp-anything/scripts/discover_target.py "Microsoft Excel" --task "读取单元格并另存修改结果"
python skills/mcp-anything/scripts/discover_target.py https://example.com/app --kind url
```

发现报告可能含本机安装路径，分享前应检查。原有仓库检查、起始项目和真实 MCP 检查脚本仍可使用。脚手架明确返回 `adapter_ready: false`，完成实际运行验证后才算接入成功。

## 可运行的例子

| 示例 | 能做什么 | 适合谁 |
| --- | --- | --- |
| [FFmpeg](examples/ffmpeg) | 音频信息、WAV 转新 FLAC 文件 | 本地命令行软件接入 |
| [Excel](examples/excel) | 新建/读取工作簿、另存修改结果 | Windows 已安装桌面软件的自动化接口 |
| [网页笔记](examples/browser) | 通过真实浏览器查看、创建笔记 | 网页操作接入；当前验收对象是本地演示网页 |
| [SQLite](examples/sqlite) | 只读查看表、字段和受限行数的数据 | 想快速试用、不想安装大型软件的人 |
| [LAMMPS](adapters/lammps/README.zh-CN.md) | 分子动力学小算例、任务查询、取消和结果文件 | 需要接入科研计算或其他长任务的人 |

这些例子只证明列出的具体功能。REA 从录制数据导出的环境也不等于已接通原软件，需要另行验证真实执行。各案例依赖与验收情况见[支持范围](docs/software-support.md)。

Skill 版本为 **0.4.1**，LAMMPS 适配器保持 **0.2.0**。LAMMPS 历史 Windows/Linux 和平台 HTTP 验证记录继续保留；小算例不代表材料性质或聚合物 Tg 已完成科学验证，共享服务也没有按用户隔离任务。

新版按用户要求的每项操作判断完成：读取模型成功，不能代替求解成功。[操作验收工具](skills/mcp-anything/references/operation-acceptance.md)核对调用记录、文件哈希和结果断言；[wheel 检查工具](skills/mcp-anything/references/verification.md)核对打包代码与源码。MCP 协议检查器已在独立环境实测 SDK 1.30.0 和 2.3.0，避免把客户端版本差异当成软件故障。

## 与同名项目的关系

参考了 [gabrielekarra/mcp-anything](https://github.com/gabrielekarra/mcp-anything) 的任务描述、功能选择和 Agent 使用指南思路。该项目现在也有 skill/plugin，因此不能用“它不是 skill”来区分。我们侧重让已有编程 Agent 完成软件接入，并以真实调用、明确边界和可复现交付检验结果。详细比较见[相关工作](docs/related-work.md)。

本项目独立开发，按需调用 REA，没有分叉或复制它的源码。原创代码和文档采用 MIT 许可。目标软件和分析工具单独安装，保留各自许可，见[依赖说明](docs/software-dependencies.md)。开发与打包命令见[英文说明](README.md#develop-and-package)。
