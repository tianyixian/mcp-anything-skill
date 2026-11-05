# PVDF湿纺：工具接入清单

本方向优先复用文献检索和全文读取能力，普通Python分析直接运行，实验仪器采用人工文件交接。原需求没有明确的分子动力学或量子计算任务，首版无需新增LAMMPS、DFT或设备控制MCP。

| 能力 | 为什么需要 | 接入建议与当前边界 |
|---|---|---|
| 文献检索、题录核查 | 核对湿纺论文、争议样品和测量定义 | 优先已有检索工具；OpenAlex／Crossref可补元数据。保存查询式、时间、DOI和覆盖缺口。未在目标实例验证连接。 |
| PDF全文、表格和页码解析 | 将原文数值定位到具体样品、图表和方法 | 优先已有解析服务；MinerU是候选后端。缺接口时再用MCP Anything适配“提交—状态—结果”。解析不代替原页复核，本轮未部署MinerU。 |
| Zotero文献库 | 复用团队已整理的条目及附件 | 可选；已有库和访问配置才接。没有库先用有出处的文件清单。 |

“需要”指科研步骤所需能力，可由现有工具或用户提供的可追溯资料满足，不代表附带MCP已经部署。工作流的`mcpServers`默认留空；绑定时以实际工具发现及调用结果为准，不猜测工具名。

## 不单独封MCP的部分

- CSV／Excel整理、单位和缺失检查、logit及scikit-learn建模、分组验证、敏感性分析、随机化、绘图：普通Python节点。
- FTIR、XRD、DSC和力学曲线：处理实验人员导出的原始文件；方法、定标和样品映射仍需核查。
- 配液、泵、凝固浴、收卷、热拉伸及测量设备：实验人员按SOP操作，回传实际设置、执行记录和原始数据；本轮没有已验证控制接口。
- LAMMPS、QE、VASP等模拟软件：不在本方向首版需求内，不为完整工具清单而增加计算任务。

## 若确实缺接口，再怎么验收

检索接口至少检查已知论文、无结果和分页；输出来源及检索时间。PDF接口至少用一份有权读取的原PDF核对页码、表格和样品定位；失败时返回明确状态，不能以空文件报成功。长解析任务采用提交、查询、取结果的接口，并保存任务ID与版本。

可复用[MCP Anything 0.3.0](https://github.com/tianyixian/mcp-anything-skill/releases/tag/v0.3.0)完成缺失接口的实现与真实调用验收。上游资料：[OpenAlex](https://docs.openalex.org/)、[Crossref](https://www.crossref.org/documentation/retrieve-metadata/rest-api/)、[MinerU](https://github.com/opendatalab/MinerU)、[Zotero API](https://www.zotero.org/support/dev/web_api/v3/start)。这些是软件或API入口，不等于已经提供可用的MCP服务。

来源定位：原需求第49—85行给出Agent与工具分工，第91—124行涉及数据和建模，第208—259行涉及实际实验和文件交接。详细映射见`NOTES.md`。
