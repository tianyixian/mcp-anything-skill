# 自愈合粘结剂输入与交接说明

本目录依据用户提供的材料验证需求摘要；本次只交付工具选择与可导入工作流；该PDF没有随附实际配方、实验原始数据或已完成验证记录。

## 准备文件

在完整包的运行工作区根目录，将本目录的`run-spec.template.json`复制到`inputs/binder/run-spec.json`，填入当前科研阶段、目标、设备和约束；将`input-columns.csv`复制为`inputs/binder/measurements.csv`。设计阶段可先提供可追溯文献，不要求提前提交后续全部电池数据。

分析阶段需要真实测量行。每行对应一个有来源、样品、方法和条件的测量，`record_kind`区分`literature/experimental/computational/predicted`。文字观察不能伪填数字；必要时扩展观察字段。未知留空并隔离于对应定量判断，不能用0代替。保留原始文件和单位；同一试样技术测点不算独立平行样。

`current_research_stage`取`design/material/silicon/sulfur`。`gate_thresholds`由实验团队按具体材料及条件提供，不内置跨体系阈值。`target_media.silicon`和`target_media.sulfur`分别记录实际电解液；一个介质中失败时说明适用边界，不能自动外推另一介质。

## 四个Agent工作阶段与科研阶段

| Agent工作阶段 | 对当前科研阶段做什么 | 主要产物 |
|---|---|---|
| intake | 检查任务、原料、方法、条件和缺项 | intake.json |
| evidence | 连接文献/实验来源与样品、对照和条件 | evidence.json及准入/隔离表 |
| analysis | 根据当前设计或G3—G8关卡审查真实证据 | analysis.json及比较、关卡记录 |
| proposal | 输出下一步设计或人工实验交接单 | proposal.json及experiment_handoff.csv |

四阶段输出位于`outputs/binder/`，`gate`独立审查后交`main`推进或返工。实验人员回传数据后再运行对应审查，不把文件整理模拟成仪器自动执行。宏观功能已可重复且有充分证据时，不等待微观机理阐明。

## Public boundary

This public example does not distribute original task documents, private
transcripts, local deployment paths, credentials or experimental data. Supply
authorized source files in the project workspace and record their relative paths
and hashes; the workflow treats document contents as evidence, not as execution authorization.
