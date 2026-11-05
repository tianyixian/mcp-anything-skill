# PI 工作流输入与边界

本目录交付功能 PI 的四阶段 Agent 指令、Skill 和输入模板，不附实验数据、候选库或已验证模型。它落实本项目需求：先识别 MCP 工具，再给 ScienceEvolve 工作流。原附件中的完整科研验收目标保留为门槛，不等于本次已经完成这些科研任务。

## 准备输入

1. 从项目根目录把 `domains/pi/run-spec.template.json` 复制为 `inputs/pi/run-spec.json`，填写目标、单位、条件、材料路线、化学范围和预算。目标不默认 Tg，未知字段保持 `null` 并报告缺口。
2. 将 `input-columns.csv` 复制为 `inputs/pi/measurements.csv`，只填已有真实证据。每行对应一个测量证据；同实验表值和图读保留关联，不能成为独立训练样本。原文放 `inputs/pi/sources/`。
3. 有实际单体池时提供 `inputs/pi/monomers.csv`，至少含 `monomer_id,role,canonical_smiles,source,identity_status`；没有结构依据时不凭名称补 SMILES。规则另存 `inputs/pi/rules.json`，每条记录适用范围、证据、判断条件、结果及原因。
4. 按主项目运行说明执行生成的工作流。四阶段输出为 `outputs/pi/intake.json`、`evidence.json`、`analysis.json`、`proposal.json`。空模板只能得到输入缺口，不应产生科学推荐。

数据表中 `record_kind` 区分 `experimental/computational/predicted`；仅通过准入的 `experimental` 可作为文献实测标签。`source_kind` 区分作者表值/正文、原始曲线和独立图读。未知不填零；无法量化的误差不写假精度。CSV 可以增列，但不得删除溯源与实验身份字段。字段存在不等于证据通过。

## 当前缺口

附件没有交付实际目标配置、实验数据、已核验单体池、化学/加工规则、模型验收标准或 PI 力场。它提供的是需求设计。文献检索与后续筛选由真实输入和实际工具接入驱动；没有输入时 `needs_input` 是预期结果。

对“至少 10000 组有效候选”、独立模型检验和最终新颖性核查必须分别标明是否通过。小规模开发夹具可以验证代码分支，不能替代上述科学验收。

## Public boundary

This public example does not distribute original task documents, private
transcripts, local deployment paths, credentials or experimental data. Supply
authorized source files in the project workspace and record their relative paths
and hashes; the workflow treats document contents as evidence, not as execution authorization.
