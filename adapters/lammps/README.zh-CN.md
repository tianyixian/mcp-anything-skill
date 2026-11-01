# LAMMPS MCP 使用说明

这层接口让 AI 按标准格式提交 LAMMPS 计算、查进度、取消任务、取日志。默认用小型 Lennard-Jones 演示证明“能调用真实引擎”，不把它表述为“已能预测聚合物 Tg”。

先进入本目录（完整仓库的 `adapters/lammps`，或独立软件包解压后的根目录），用 Python 3.11+ 执行 `python -m pip install '.[engine]'`。Windows 的 LAMMPS wheel 还需要 Microsoft MPI；缺少 `msmpi.dll` 时先安装对应运行库。完整配置见 [英文说明](README.md)。

`LAMMPS_MCP_WORKSPACE` 必须是专用工作目录的绝对路径。MCP 客户端启动 `python -m lammps_mcp` 时，默认通过标准输入输出连接，不监听网络端口。v0.2.0 另提供按 URL 连接的 Streamable HTTP 服务。

**Windows 还要先在独立终端启动任务管理进程**：`python -m lammps_mcp.supervisor --workspace C:/work/lammps-jobs`。客户端配置相同目录。保持它运行，任务才不会因 MCP 客户端清理整棵进程树而中断。

在启智等平台共享 HTTP 服务时，部署者执行：

```sh
export LAMMPS_MCP_WORKSPACE=/absolute/path/lammps-jobs
export LAMMPS_ALLOW_TRUSTED_INPUT=0
export LAMMPS_MCP_ALLOWED_HOSTS=实际平台代理域名
export LAMMPS_MCP_ALLOWED_ORIGINS=https://实际平台代理域名
python -m lammps_mcp --transport streamable-http --host 0.0.0.0 --port 8765 --path /mcp
```

随后通过平台正常的 HTTP 路由开放这个端口，给调用者平台上的 `/mcp` 地址。`127.0.0.1` 只能在服务所在机器使用，不能作为共享链接。`/health` 查看服务状态，`/` 显示版本和路径；MCP 客户端连接 `/mcp`。软件本身不创建平台网关或外网隧道。

Host 和 Origin 白名单必须填写实际代理值，多个值用逗号分隔，不支持通配符。HTTP 模式只允许受限算例和任务管理，禁止启用可信自定义脚本。该服务使用共享演示目录；知道任务编号的调用者可以读取或取消该任务，因此不要放入私人研究输入。路由白名单不等于用户身份认证。

调用顺序：

1. `lammps_probe`：确认引擎可用、任务管理进程就绪。
2. `lammps_run_lj`：传 `{"cells":4,"steps":100,"timeout_seconds":60}`，提交 256 原子、100 步演示，立即返回任务编号。
3. `job_status`：查询进度。
4. `job_result`：完成后读取状态、输入哈希、引擎版本和温度/能量摘要。
5. `artifact_read`：分页读取原始日志；`job_cancel` 请求取消。

任务由独立进程管理，MCP 服务关闭、重启后仍能查询；超时和取消也由独立进程执行。若工作进程自身异常退出，则报告 `stale`，不冒充成功。文件保存在 `工作目录/jobs/任务编号/`。

自定义脚本默认禁用。管理员在本地 stdio 部署中设置 `LAMMPS_ALLOW_TRUSTED_INPUT=1` 后，才允许 `lammps_submit` 提交脚本和配套文件；共享 HTTP 模式会拒绝这一设置。**启用后只能接收可信脚本：它拥有运行账户的文件和命令权限，不是沙箱。** 捕获日志总量限 16 MiB，附件包限 4 MiB；可信脚本另写的其他文件不受日志上限约束。

用于聚合物 Tg 还需确定结构、力场、平衡与冷却协议、拟合方法及实验对照。本交付先解决可重复调用、任务管理和结果留痕。
