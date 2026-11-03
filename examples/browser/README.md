# A website workflow exposed through MCP

This example turns a fixed notes-page workflow into two MCP tools: list saved notes and create a note. A Python MCP server calls a Node Playwright worker, which operates the page through its labels and roles. It owns an isolated headless browser; it does not use your browser profile or an existing login.

The included application is a disposable local demonstration. Acceptance proves this page and these operations work through a real browser. It does not prove compatibility with arbitrary websites, personal accounts or desktop applications. Its loopback address is a test endpoint, not a published shared service.

## Requirements and installation

- Python 3.11+ and the official MCP Python SDK `1.30.0`.
- Node.js 20+.
- A separately installed Chromium-family browser, such as Chrome or Edge.
- `playwright-core` `1.62.1`; no browser is downloaded by this dependency.

Use an isolated Python environment, then run from this directory:

```sh
python -m pip install "mcp==1.30.0"
npm ci --ignore-scripts
```

The application, worker and MCP server are ordinary files in this directory. This example does not require REA: the page and its supported UI are already known.

## Verify a complete operation

Pass the actual absolute executable paths on your host:

```sh
python verify.py --node /absolute/path/node --browser /absolute/path/chrome --output validation-local.json
```

The verifier starts a local application in a temporary directory, uses MCP to create a note, reloads it, rejects invalid inputs without changing the saved data, opens another owned browser to check persistence, and checks normal worker shutdown. It removes the temporary application data afterward. The checked-in `validation.json` is the actual run record, with private paths omitted.

When reusing an existing Playwright installation instead of running `npm ci`, set `BROWSER_MCP_PLAYWRIGHT_PATH` to the absolute `playwright-core` package directory. This is an operator configuration option, never tool input. Omit it for the normal local `node_modules` installation.

The integration tests run only when `BROWSER_MCP_NODE` and `BROWSER_MCP_EXECUTABLE` identify available executables. Without those optional requirements, pytest reports skips rather than claiming browser acceptance:

```sh
python -m pytest test_browser.py -q
```

The real browser tests also use a second local server to verify that direct requests and redirects to another origin are blocked. They make no request to an external website.

Separate pipe-lifecycle regressions use a controlled Python worker. They commit one fixture write before delaying or corrupting its response, then verify cancellation/timeout cleanup and recovery through a new explicit read without replaying the write. These tests validate bridge behavior; they are not evidence of rollback or cancellation guarantees in an arbitrary website.

## Run the demonstration

Start the application with a dedicated data directory:

```sh
python demo_app.py --directory ./workspace/notes-demo --port 8765
```

In an MCP client, start the server using the same URL:

```sh
python server.py --url http://127.0.0.1:8765 --node /absolute/path/node --browser /absolute/path/chrome
```

The URL is fixed by the operator. Tools do not accept URLs, selectors, JavaScript, cookies or arbitrary action sequences. Other page origins and WebSocket connections are blocked. The browser uses a fresh context with service workers disabled. Page requests are checked before following redirects; this is a scoped automation boundary, not OS isolation.

## Behavior and limits

`create_note` checks that exactly one new note appears after submitting the form. `list_notes` reloads the page, proving saved state can be read. Each note has a printable, nonblank title of 1–120 characters, without outer whitespace. The demonstration holds at most 100 notes. One adapter serializes its operations; concurrent external writers are outside its acceptance scope.

Creating notes is not idempotent. If a write times out, is cancelled or loses its response, call `list_notes` to inspect state before deciding whether to retry. The adapter retires the affected worker and browser; the next explicit call creates a fresh session. It does not silently repeat writes. Missing runtime dependencies or changed page controls produce a tool error rather than a fabricated successful result. If process cleanup itself fails, further operations are blocked until cleanup succeeds.

Normal shutdown closes the owned browser and Node worker. Timeout handling closes the input channel and then terminates only the owned worker tree if it cannot stop. A forced host kill, third-party login recovery, UI redesigns and unattended shared hosting have not been verified. See [USAGE.md](USAGE.md) for the calling agent's guide.
