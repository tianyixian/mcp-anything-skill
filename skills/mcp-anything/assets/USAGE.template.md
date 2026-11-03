# Adapter usage guide

Replace the prompts below with facts from the completed adapter. Remove sections that do not apply. This file is a guide for the agent that will call the server, not an assertion that the converter has implemented these features.

## What this server can do

State the task, tested software version/host, and material limitations in two sentences. Identify the interface used (for example, CLI, vendor scripting or browser automation). Include only verified operations in a ready-to-use recipe; label implemented but unverified capabilities separately.

## Connect

Give a tested client configuration with the installed executable or deployment URL. Use environment variable names for credentials. List runtime prerequisites and the smallest readiness check. Keep setup/investigation tools separate; state whether REA is needed during normal use. For desktop/browser automation, explain the required session, login setup and ownership of windows/documents without distributing credentials or a browser profile. State which checks only prove the server is alive and which prove the upstream works.

## Tools

For each implemented tool, list input names, types, defaults, bounds, units and file formats; describe structured output fields, side effects and the observable completion condition. For file tools, include the exact minimal file format and permitted paths. For long jobs, explain submit, status, result and cancel with terminal states. Identify operations that share a session and must run serially.

## A tested recipe

Show the shortest useful sequence of actual tool calls with concrete small inputs and observed output. Identify the environment and software version. Redact credentials and private data without inventing results.

## Recovery

Explain missing dependencies, invalid inputs, timeouts and relevant upstream errors. For UI workflows, cover login expiry or a changed/missing control when applicable. State whether retrying can repeat a write, how to inspect an uncertain outcome, and whether a job survives a client disconnect or a server restart. Explain cleanup of owned resources. Include only behavior that was implemented and tested.
