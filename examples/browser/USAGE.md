# Notes browser MCP usage

This server lists and creates notes in the supplied local notes application through a real headless browser. The supported page contract is the one in `demo_app.py`; other websites require their own adapter and acceptance.

## Connect

Use Python with MCP SDK `1.30.0`, Node.js 20+, Playwright Core `1.62.1`, and an installed Chrome/Edge executable. Start `demo_app.py` with a dedicated data directory, then configure a stdio MCP command:

```json
{
  "command": "/absolute/path/python",
  "args": [
    "/absolute/path/examples/browser/server.py",
    "--url", "http://127.0.0.1:8765",
    "--node", "/absolute/path/node",
    "--browser", "/absolute/path/chrome"
  ]
}
```

Replace paths with the host's installed executables. The loopback URL refers to the demonstration running on that same host. No login credentials, personal browser profile or REA runtime is required. A successful `tools/list` proves the MCP process starts; a successful `list_notes` proves the page was loaded through the browser.

## Tools

| Tool | Input | Structured output and side effect |
| --- | --- | --- |
| `list_notes` | None | `{notes: [{id, title}], reloaded: true}`; reloads the page, returns at most 100 notes |
| `create_note` | `title`: printable string, 1–120 characters, no outer whitespace | `{note: {id, title}, confirmed_in_page: true}`; creates one persisted note and reads it back from the page |

The server owns its browser and serializes calls sharing the page. It does not operate unrelated tabs or accept a different target URL in a tool call.

## Tested recipe

On a fresh demonstration application:

```text
list_notes({})
→ {"notes": [], "reloaded": true}

create_note({"title": "科研验收 note"})
→ {"note": {"id": 1, "title": "科研验收 note"}, "confirmed_in_page": true}

list_notes({})
→ {"notes": [{"id": 1, "title": "科研验收 note"}], "reloaded": true}
```

These are actual acceptance outputs. See `validation.json` for the tested platform, browser and dependency versions. The read reloads the page; the verifier also checks persistence in a separate owned browser session.

## Recovery

Invalid titles fail without changing notes. After cancellation, timeout, lost response or missing control, inspect the saved list before retrying a create: repeating a create may add a duplicate. The affected worker is discarded after cleanup; the next explicit tool call starts a fresh browser session. No write is automatically replayed. A cleanup failure blocks reuse until the owned process is stopped. Check the configured executables and Playwright installation if a new worker cannot start.

Changed UI, authentication flows and multi-user access are not implemented. Normal shutdown closes the owned browser; it does not close a personal browser or delete the demo application's saved notes.
