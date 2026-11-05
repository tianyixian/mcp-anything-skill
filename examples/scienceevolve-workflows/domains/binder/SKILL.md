---
name: self-healing-binder-workflow
description: Organize evidence and experimental handoffs for aqueous-processable self-healing polymer binders, including material recovery, electrolyte compatibility, silicon anodes and sulfur cathodes. Use for this binder workflow; does not operate laboratory equipment or certify unperformed experiments.
---

# 自愈合粘结剂工作流

围绕“材料能否稳定制备、恢复性能，并在匹配电池条件下可重复使用”推进。原需求是研发路线，不是已有实验数据或现成软件清单。详细四阶段职责见 [domain.json](domain.json)，输入及来源页码见 [NOTES.md](NOTES.md)，配置和数据表使用 [run-spec.template.json](run-spec.template.json) 与 [input-columns.csv](input-columns.csv)。

## 入口与交接

- 工作区输入：`inputs/binder/run-spec.json`、`inputs/binder/measurements.csv`及其中声明的原文/原始数据文件。按当前科研阶段读取相关资料，不要求在设计阶段就具备后续全部电池结果。
- 输出：`outputs/binder/{intake,evidence,analysis,proposal}.json`。统一字段是`status/input_hash/version/results/evidence/warnings/next_step`；`input_hash`为实际输入相对路径到SHA256的对象，版本`0.1.1`。
- 状态只用`completed/failed/needs_input/needs_review/unsupported/skipped`。`completed`只表示对应阶段动作完成，不能替代科学验收。等待人员实验或文件回传时用`needs_input`并列出清单。
- 科研阶段为设计→材料/介质→硅负极→硫正极。四个Agent工作阶段是对当前科研阶段进行输入、证据、分析和交接；两种“阶段”不能混淆。

## 材料设计边界

CS改性/组装和独立聚合物体系并列，不要求所有路线含CS。只有涉及CS时才检查CS规格、酸、pH、浓度、混合顺序和均匀性。NMP禁用，其余禁用项核对实验室清单；原料和助剂也要列清。

制备时要求高分子或前驱体溶于水。水分散、乳液、凝胶含水都不是水溶证据；成膜交联后网络不必仍然水溶。水凝胶中的自愈合不能替代干膜或目标电解液中的验证。

涉及合成或改性的候选保留适用的基本结构确认及样品对应记录；商品材料核实身份、规格和必要的SDS。基本确认与分子级动态交换机制证明分开，不能用“机理不是门槛”省略前者，也不强制指定一台仪器。

## G3—G8按实际证据判断

| 关卡 | 可支持判断的证据 | 常见误判 |
|---|---|---|
| G3 宏观恢复 | 无损、受损未修复、修复及匹配热史/浸泡史对照；绝对性能、恢复比例和重复 | 只看到裂口闭合就说力学恢复；分母/接触压力/修复次数不明 |
| G4 介质稳定与愈合 | 两类实际电解液分别记录吸液、干质量损失、湿态性能及修复 | 用湿重变化当浸出；忽略盐残留；把一个介质结论迁移到另一个 |
| G5 硅电极可加工 | 匹配配方、载量、涂布/干燥及湿态黏附 | 内聚破坏和界面脱黏混为一谈 |
| G6 硅电池可重复 | 首效、循环、倍率、极化及独立重复；EIS按现有条件 | 用循环改善证明电池内微裂纹已自主修复 |
| G7 硫介质接触稳定 | 膜/溶液变化及空白；有条件时UV-vis | 褪色直接等于吸附、催化或抑制穿梭 |
| G8 硫电池表现 | 固定宿主、硫载量、E/S、锂负极与电解液，比较循环、倍率、效率和硫利用 | 混淆宿主缓冲与粘结剂贡献；用吸附能预测寿命 |

阈值需来自run-spec和实验人员确认，不设跨材料通用合格数值。记录`pass/adjust/eliminate/needs_input/needs_review/not_applicable`及证据；资料缺失不等于材料淘汰。硅特有失败可单独归因，保留硫路线仍需材料及硫介质依据。

## 工具与预算

优先复用已配置的文献检索、PDF解析、SDS/供应商说明读取能力。没有服务时读取用户提供文件并记录覆盖缺口；原PDF中的文献条目须核对原文。普通Python做单位、统计、曲线和对照分析，不单独封MCP。

天平、拉伸/剥离、涂布和电池测试由人员执行，Agent读取导出文件。UV-vis、EIS按条件补充；SEM、原位表征、纯膜导锂和分子级机理不是通关门槛。机理计算默认关闭，有具体问题时才另行配置可信工具和预算；模拟不可用不阻碍有宏观证据支持的实验推进。

每次调整针对一个明确缺口，遵守预算和最多两轮返工。未获实验数据不填结果；不把资料整理、软件解析成功或停止于预算当作科学成功。最终报告先说可用交付与当前缺项，技术细节附后。
