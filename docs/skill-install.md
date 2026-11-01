# Install MCP Anything 0.3.0

Install the skill in your existing coding agent. Running the skill does not require LAMMPS, a separate generator service, or an additional model API key. The Python helpers require Python 3.11+; the protocol checker additionally needs the official MCP Python SDK (`python -m pip install 'mcp>=1.26,<2'`). The target software may have its own installation and authentication requirements.

## From the repository

```sh
git clone https://github.com/tianyixian/mcp-anything-skill.git
```

Codex, macOS/Linux:

```sh
mkdir -p ~/.codex/skills
cp -R mcp-anything-skill/skills/mcp-anything ~/.codex/skills/
```

Codex, Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE/.codex/skills" | Out-Null
Copy-Item -Recurse ./mcp-anything-skill/skills/mcp-anything "$env:USERPROFILE/.codex/skills/"
```

For Claude Code, substitute `.claude/skills` for `.codex/skills`. Other hosts must support discovery of `SKILL.md` folders; follow their documented location. These are installation instructions, not claims of a completed end-to-end test in every host UI. If a folder already exists, compare/back it up before updating to avoid losing local edits.

## From the standalone ZIP

Extract `mcp-anything-skill-0.3.0.zip`. Copy the extracted `mcp-anything/` folder, including its scripts, references and assets, into your skills directory. Do not nest the entire ZIP directory there. The result should be `.../skills/mcp-anything/SKILL.md`.

Open a new agent session, then ask:

> Use $mcp-anything to turn this software into MCP tools. The source is … and I need … . Implement and test a real operation, then give me client configuration and a short usage guide.

In hosts that use slash-style skill invocation, use their normal skill selector or ask for “MCP Anything” by name. The skill's instructions are host-neutral; discovery syntax belongs to the host.

## Upgrading from github-to-mcp

The old name was `github-to-mcp`, under the MCP Everything project. The new canonical folder and invocation are `mcp-anything` and `$mcp-anything`. Install the new folder; remove the old folder only after preserving any personal edits. Existing generated adapters work independently of the converter skill and do not need to be regenerated.

## First checks

Ask the agent to inspect a small local repository and select one useful operation. The inventory helper must not execute that repository. A generated `adapter_info` returning `adapter_ready: false` is an expected unfinished scaffold, not a successful conversion. Completion requires a real tool call with an observable result. The full repository includes a lightweight SQLite example and the LAMMPS adapter; the standalone skill ZIP does not bundle those runtimes.
