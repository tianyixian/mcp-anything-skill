# 功能PI筛选 ScienceEvolve 工作流

独立交付包 0.1.1，2026-11-03。

本包将功能聚酰亚胺筛选组织成目标核查、样品证据准入、候选与模型审查、推荐卡交付。目标性质由使用者确定，不自动选择Tg。交付内容是流程配置、领域Skill、输入模板和预检脚本；未附实验数据、核验单体池、已验证模型或新的科研推荐。

## 文件入口

| 文件 | 用途 |
|---|---|
| `workflows/pi.workflow.json` | 导入ScienceEvolve的流程配置 |
| `domains/pi/SKILL.md` | 证据准入、化学约束、模型验证和推荐边界 |
| `domains/pi/run-spec.template.json` | 目标、条件、化学范围、约束和预算模板 |
| `domains/pi/input-columns.csv` | 样品级证据空表头 |
| `domains/pi/tool-inventory.md` | 需要的外部工具、可选计算和普通Python节点 |
| `domains/pi/NOTES.md` | 字段说明及原需求行号映射 |
| `validation/`、`MANIFEST.json` | 随包验证记录和文件校验值 |

## 使用步骤

1. **先将完整独立包解压到实际运行工作区根目录**，保留`domains/`、`scripts/`、`workflows/`等结构。单独导入JSON只可预览，不会自动部署工作区脚本。
2. 导入`workflows/pi.workflow.json`；若页面显示原文预览，再通过“快速发起”载入可编辑副本。界面名称依平台版本而定。
3. 为各Agent选择实际可用的模型及网关。JSON不包含凭据。已测解析器会将省略模型补为`nex-agi/Nex-N2-Pro`；这不保证平台可用，运行前需确认或改选。
4. 将`domains/pi/run-spec.template.json`复制为`inputs/pi/run-spec.json`，将`domains/pi/input-columns.csv`复制为`inputs/pi/measurements.csv`。填写明确目标、单位、测试条件、材料路线、化学范围和预算；未知项保持未知。
5. 提供有出处的文献及补充材料。已有单体池放`inputs/pi/monomers.csv`，化学约束放`inputs/pi/rules.json`，原文放`inputs/pi/sources/`；单体池最小字段见`NOTES.md`。
6. 绑定实际可用的检索、全文解析和化学身份查询能力。`mcpServers`默认为空，导入不会自动部署MinerU或PubChem MCP。没有在线服务时可读取可追溯本地资料，并说明覆盖缺口。
7. 启动输入检查，依次推进证据、分析、方案和报告。每个业务阶段先交`gate`审查，再由`main`调度；结果和审查记录保存在`outputs/pi/`。

## 快速检查

Python 3.10或更新版，无额外Python依赖。在包根目录执行：

```bash
python scripts/preflight.py --project pi --workspace . --stage intake
python scripts/preflight.py --project pi --workspace . --stage analysis
```

退出码`2`表示缺输入，`1`表示格式错误；`0`只表示基础格式检查完成，仍须领域审查。预检不会验证化学可行性、候选新颖性或预测性能。

已有ScienceEvolve／SCION-AR源码和依赖时，可复查配置：

```bash
node --import <已安装tsx的loader.mjs> scripts/validate_workflows.mjs --sdk-dir <scion-ar-sdk目录> --web-dir <scion-ar-main目录> --json
```

## 科研与工具边界

正文、SI、图读和模拟分别留出处；同一实验的图值与表值不能双计样本。T5/T10未达阈值应记删失，未知气氛不混入明确气氛主集。PAA分子量与最终PI分子量不能混用。

原需求的10000—100000组有效去重候选、独立模型验证及最终候选新颖性核查仍是后续科研门槛。本次没有完成这些筛选，不能用重复配比或小样例凑数。模型未通过时可交付证据目录或探索候选，不给已验证的精确排行榜。

普通Python承担RDKit结构处理、候选枚举、建模、验证及出图。机理模拟默认关闭；Packmol仅装填坐标，LAMMPS不自动提供PI拓扑或合格力场。既有LJ演示不等于PI的Tg服务；CP2K、DeePMD-kit和DP-GEN仅为有明确需求与预算后的可选扩展。

已有配置通过本地Web导入器0.1.0和SDK0.1.1解析；共享预检程序此前8项行为测试通过。这不代表目标平台模型全流程、在线工具或科研结论已经通过。**本独立包最终校验以`validation/`内随包记录为准。** `gate`是模型依据证据执行的软审查，不能称为科学正确性硬门禁。

原始需求材料不随公开示例发布；原文中的目标和接口示例不等于已经实现的能力。
