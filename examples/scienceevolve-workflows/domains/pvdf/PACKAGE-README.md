# PVDF湿纺 ScienceEvolve 工作流

独立交付包 0.1.1，2026-11-03。

本包用于核查PVDF湿纺与后拉伸的文献、原始数据和旧模型，再形成有设备及性能约束的下一轮实验交接单。交付内容是工作流、领域Skill、输入模板和预检脚本；未附真实PVDF数据，未重训模型、制样或控制仪器。

## 文件入口

| 文件 | 用途 |
|---|---|
| `workflows/pvdf.workflow.json` | 导入ScienceEvolve的流程配置 |
| `domains/pvdf/SKILL.md` | 样品证据、测量口径、分析与人工交接要求 |
| `domains/pvdf/run-spec.template.json` | 目标、资料、设备、SOP、预算和判据模板 |
| `domains/pvdf/input-columns.csv` | 空数据表头，保留来源、样品、批次与测量关系 |
| `domains/pvdf/tool-inventory.md` | 本方向需要的外部工具和不需MCP的工作 |
| `domains/pvdf/NOTES.md` | 字段含义、输入缺口及原需求行号 |
| `validation/official-sdk-validation.json` | 当前公开工作流的官方SDK校验记录和SHA256 |

## 使用步骤

1. **先将完整独立包解压到实际运行工作区根目录**，保留`domains/`、`scripts/`、`workflows/`等目录。单独导入JSON可以预览，不能自动安装工作区脚本。
2. 导入`workflows/pvdf.workflow.json`；页面若先显示原文预览，在“快速发起”载入可编辑副本后再运行。界面名称依平台版本而定。
3. 为各Agent选择实际可用的模型及网关。JSON未携带凭据，省略模型不等于自动使用平台当前模型：已测解析器会补为`nex-agi/Nex-N2-Pro`，运行前须确认或改选。
4. 将`domains/pvdf/run-spec.template.json`复制为`inputs/pvdf/run-spec.json`，将`domains/pvdf/input-columns.csv`复制为`inputs/pvdf/measurements.csv`。填真实数据及相对工作区的来源路径；未知项保留未知，不能填零或旧预测值。
5. 绑定已经可用的文献检索或全文工具，或提供有出处的本地论文。`mcpServers`默认为空，导入不会自动部署或连通检索、MinerU、Zotero等服务。
6. 从输入检查开始，经过证据整理、分析、方案生成和报告。业务阶段先交`gate`审查，再由`main`决定推进、返工或等待输入。产物保存在`outputs/pvdf/`。

需要补齐的资料包括整合CSV、旧模型代码与参数、原论文及补充材料、实验原始文件、设备范围、SOP和预先约定的判据。需求文件中提到某个路径或结果，不代表这些材料已提供。

## 快速检查

Python 3.10或更新版，无额外Python依赖。在包根目录运行：

```bash
python scripts/preflight.py --project pvdf --workspace . --stage intake
python scripts/preflight.py --project pvdf --workspace . --stage analysis
```

退出码`2`表示缺输入，`1`表示格式错误；`0`只表示基础格式检查完成，仍须领域审查。预检不证明原始值准确、方法可比、模型可靠或配方可执行。

安装官方ScienceEvolve命令行后，在示例根目录复查配置：

```bash
scievolve workflow validate workflows/pvdf.workflow.json
```

## 实验与结论边界

FTIR与XRD不同定义的β比例不直接平均；β相比例、结晶度和压电响应分别保存。`>95%`是下界，不能改为精确95.0。配液批次、批内拉伸子样和技术重复不混成独立样本。加工失败保留失败记录，不能填β=0。

普通Python完成数据整理、旧模型复现、分组验证及图表；本方向不额外引入LAMMPS、DFT或仪器控制。实际配液、纺丝、后拉伸和表征由实验人员按SOP执行，回传原始数据后再评价冻结预测。旧数据规模、R²或“β≈99.3%”等转述都不是本次验证结果。

2026年11月6日，当前公开JSON通过官方SDK固定提交`7c51eb49a53fdcf620badf145c286e12b80e7d3e`的配置校验，证据见`validation/official-sdk-validation.json`。旧Web/SDK记录只对应历史交付文件，不能用其哈希证明当前公开文件。配置通过不代表目标平台模型全流程或科学实验已经完成；`gate`是模型按提示词执行的软审查。

原始需求材料不随公开示例发布；请在实际项目中提供经过授权的来源文件，并按相对路径和哈希记录。
