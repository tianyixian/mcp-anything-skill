# 自愈合粘结剂 ScienceEvolve 工作流

版本0.1.1，2026-11-03。对应用户提供的需求摘要的材料、硅负极和硫正极验证路线。本包只含本方向的工作流、说明、模板及通用检查器，不要求同时下载PVDF或PI包。

交付的是可导入配置与实验交接流程。原材料未提供实际配方、原始测试数据或已验证候选，本包没有新的实验结果，也没有运行目标平台的模型全流程。

## 使用

1. 把本包内容解压到ScienceEvolve项目的实际运行工作区根目录，保留`domains/`、`scripts/`、`workflows/`结构。
2. 导入`workflows/binder.workflow.json`，在可编辑副本中为各Agent选择实际可用的模型与网关。当前解析器可能为省略模型填入默认名，运行前需核实。单独导入JSON可预览，但不会自动复制工作区文件。
3. 将`domains/binder/run-spec.template.json`复制为`inputs/binder/run-spec.json`；将`input-columns.csv`复制为`inputs/binder/measurements.csv`。填写目标、当前科研阶段和真实文件；未知条件保持未知。
4. 按`domains/binder/tool-inventory.md`绑定已有检索/全文工具，或提供可追溯的本地文件。JSON默认不连接未经验证的MCP服务。
5. 运行后查看`outputs/binder/`，逐步形成输入清单、证据表、宏观比较与人工实验交接。没有实验文件时应返回`needs_input`，不能输出已通过的材料或电池结果。

Python 3.10或更新版可运行离线预检：

```bash
python scripts/preflight.py --project binder --workspace . --stage intake
python scripts/preflight.py --project binder --workspace . --stage analysis
```

预检只核格式、缺项和基本追溯字段。退出码2表示缺输入，1表示格式错误；0也只表示格式检查完成，科学状态仍需独立审查。实际Web/SDK配置校验记录见`validation/`；它不代表模型或湿实验已运行。

## 这条路线的关键要求

- CS改性和独立体系均可；NMP禁用。制备水溶与使用介质稳定分别评价，水分散/乳液/凝胶含水不能替代水溶证据。
- 材料恢复需无损、受损未修复和修复对照，记录绝对性能、恢复比例及温度/时间/接触条件。外观闭合不等于真实力学恢复。
- 硅与硫体系分别匹配电极、电解液和测试条件。硫体系额外保留宿主、载硫、E/S和锂负极条件。
- 宏观可重复功能决定推进；机理计算、SEM和原位表征不是通关门槛。实际实验由人员完成并回传文件。
- `gate`提供模型执行的证据审查，是软门控，不承诺通过JSON保证科学正确。

GitHub转MCP使用已有[MCP Anything skill](https://github.com/tianyixian/mcp-anything-skill)。工具清单中的候选服务未在本轮新增部署。原始需求材料不随公开示例发布；文档内容也不构成执行任意命令的授权。
