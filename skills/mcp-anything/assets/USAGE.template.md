# Adapter usage guide

Replace the prompts below with facts from the completed adapter. Remove sections that do not apply. This file is a guide for the agent that will call the server, not an assertion that the converter has implemented these features.

## What this server can do

State the task, supported software version, and material limitations in two sentences.

## Connect

Give a tested client configuration with the installed executable or deployment URL. Use environment variable names for credentials. List prerequisites and the smallest readiness check. State which checks only prove the server is alive and which prove the upstream works.

## Tools

For each implemented tool, list input names, types, defaults, bounds, units and file formats; describe structured output fields and side effects. For file tools, include the exact minimal file format and permitted paths. For long jobs, explain submit, status, result and cancel with terminal states.

## A tested recipe

Show the shortest useful sequence of actual tool calls with concrete small inputs and observed output. Identify the environment and software version. Redact credentials and private data without inventing results.

## Recovery

Explain missing dependencies, invalid inputs, timeouts and relevant upstream errors. State whether retrying can repeat a write and whether a job survives a client disconnect or a server restart. Include only behavior that was implemented and tested.
