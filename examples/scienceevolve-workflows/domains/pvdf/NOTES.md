# PVDF 域使用说明

本目录交付工作流指令和输入模板，未附真实 PVDF 数据，未重训模型、未制样、未控制仪器。普通 Python 分析由现有脚本承担；仅文献等外部能力需要接入现有工具。

1. 将 `run-spec.template.json` 复制到 `inputs/pvdf/run-spec.json`，填入真实目标、资料路径、设备/SOP、预算和判据。`source_files` 填相对于运行工作区的原始文件路径列表。`null` 表示尚未确认，不能解释为零或沿用旧候选值。
2. 按 `input-columns.csv` 的空表头整理为 `inputs/pvdf/measurements.csv`；保留原文件。`source_locator` 填页码/图表/实验记录位置，`source_value_kind` 区分 reported、digitized、calculated、estimated；`evidence_status` 区分 confirmed、needs_review、excluded。
3. `beta_*_raw` 保存原文；例如原文 `>95%` 对应边界数值 95、relation 为 `>`，不是精确测量。关系还可为 `=`、`>=`、`<`、`<=`；无法确定的单元格留空。区间值保留原文并说明，不强填单点。
4. `independent_preparation_id` 表示独立制样单位，`subsample_id` 表示批内子样，`technical_repeat_id` 表示技术重复。加工失败使用 `run_status` 和 `reason_code`，保留响应缺失。
5. 主工作流按 `domain.json` 的四阶段指令运行；各阶段 JSON 路径位于 `outputs/pvdf/`。资料不齐时交付 `needs_input` 与补资料清单；方案可执行但尚未实验时仍为 `needs_input`，`next_step` 说明等待人工实验与原始文件回传。未提供原始数据时，不要求产生非空证据或预测表。

阶段 `status` 统一取 `completed / failed / needs_input / needs_review / unsupported / skipped`，`completed` 仅表示阶段交付完成。

当前缺口：需求提及的整合 CSV、旧模型脚本/参数、Excel 和 Word 报告、原始论文/补充材料、实验原始文件及设备/SOP尚不能仅凭这份需求说明认定已提供。文件中的旧数据规模、R² 和候选 β 预测不是本交付的验证结果。

## Public boundary

This public example does not distribute original task documents, private
transcripts, local deployment paths, credentials or experimental data. Supply
authorized source files in the project workspace and record their relative paths
and hashes; the workflow treats document contents as evidence, not as execution authorization.
