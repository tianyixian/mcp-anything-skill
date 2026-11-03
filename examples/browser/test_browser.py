"""State validation plus opt-in real browser/MCP acceptance."""
import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading

import pytest


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


demo = load("browser_example_demo", "demo_app.py")
adapter = load("browser_example_adapter", "server.py")


FIXTURE_WORKER = r"""
import json, pathlib, sys, time
state, log, ready = map(pathlib.Path, sys.argv[1:4])
mode = sys.argv[4]
for line in sys.stdin:
    request = json.loads(line)
    operation = request['operation']
    with log.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'operation': operation}) + '\n')
    notes = json.loads(state.read_text()) if state.exists() else []
    if operation == 'create_note':
        notes.append({'id': len(notes) + 1, 'title': request['arguments']['title']})
        state.write_text(json.dumps(notes))
        ready.write_text('write committed, response pending')
        if mode == 'slow':
            time.sleep(0.35)
    if mode == 'eof':
        break
    if mode == 'malformed-json':
        print('not JSON', flush=True)
    else:
        response_id = request['id'] + 100 if mode == 'mismatched-id' else request['id']
        print(json.dumps({'id': response_id, 'result': {'notes': notes, 'reloaded': True}}), flush=True)
    if operation == 'shutdown':
        break
"""


def fixture_bridge(tmp_path, monkeypatch, first_mode):
    """Real pipe/process behavior; this controlled worker is not browser acceptance."""
    state = tmp_path / "notes.json"
    log = tmp_path / "operations.jsonl"
    ready = tmp_path / "ready.txt"
    original_spawn = asyncio.create_subprocess_exec
    processes = []

    async def spawn(*args, **kwargs):
        if len(args) > 1 and str(args[1]).endswith("worker.mjs"):
            mode = first_mode if not processes else "normal"
            process = await original_spawn(sys.executable, "-u", "-c", FIXTURE_WORKER,
                                           str(state), str(log), str(ready), mode, **kwargs)
            processes.append(process)
            return process
        return await original_spawn(*args, **kwargs)

    monkeypatch.setattr(adapter.asyncio, "create_subprocess_exec", spawn)
    bridge = adapter.BrowserBridge("http://127.0.0.1:1", sys.executable, Path(sys.executable))
    return bridge, processes, state, log, ready


async def wait_for_file(path):
    async def wait():
        while not path.exists():
            await asyncio.sleep(0.01)
    await asyncio.wait_for(wait(), timeout=5)


def assert_one_write(log):
    operations = [json.loads(line)["operation"] for line in log.read_text().splitlines()]
    assert operations.count("create_note") == 1


def test_cancelled_write_discards_late_response_and_recovers_read(tmp_path, monkeypatch):
    bridge, processes, state, log, ready = fixture_bridge(tmp_path, monkeypatch, "slow")

    async def exercise():
        pending = asyncio.create_task(bridge.call("create_note", {"title": "one committed write"}))
        await wait_for_file(ready)
        pending.cancel()
        # A second cancellation must not interrupt owned-process cleanup.
        asyncio.get_running_loop().call_later(0.03, pending.cancel)
        with pytest.raises(asyncio.CancelledError):
            await pending
        assert processes[0].returncode == 0 and bridge.process is None
        try:
            result = await bridge.call("list_notes")
            assert result["notes"] == [{"id": 1, "title": "one committed write"}]
            assert len(processes) == 2
            assert_one_write(log)
        finally:
            await bridge.close()
        assert all(process.returncode == 0 for process in processes)

    asyncio.run(exercise())


def test_timeout_retires_worker_and_next_read_does_not_replay_write(tmp_path, monkeypatch):
    bridge, processes, state, log, ready = fixture_bridge(tmp_path, monkeypatch, "slow")
    monkeypatch.setattr(adapter, "REQUEST_TIMEOUT_SECONDS", 0.15)

    async def exercise():
        with pytest.raises(RuntimeError, match="timed out"):
            await bridge.call("create_note", {"title": "timed-out response"})
        assert ready.exists() and processes[0].returncode == 0 and bridge.process is None
        monkeypatch.setattr(adapter, "REQUEST_TIMEOUT_SECONDS", 5)
        try:
            result = await bridge.call("list_notes")
            assert result["notes"] == [{"id": 1, "title": "timed-out response"}]
            assert len(processes) == 2
            assert_one_write(log)
        finally:
            await bridge.close()

    asyncio.run(exercise())


@pytest.mark.parametrize("mode", ["mismatched-id", "malformed-json", "eof"])
def test_protocol_failure_retires_worker_without_replaying_write(tmp_path, monkeypatch, mode):
    bridge, processes, state, log, ready = fixture_bridge(tmp_path, monkeypatch, mode)

    async def exercise():
        with pytest.raises(RuntimeError):
            await bridge.call("create_note", {"title": "response lost"})
        assert ready.exists() and processes[0].returncode == 0 and bridge.process is None
        try:
            result = await bridge.call("list_notes")
            assert result["notes"] == [{"id": 1, "title": "response lost"}]
            assert len(processes) == 2
            assert_one_write(log)
        finally:
            await bridge.close()

    asyncio.run(exercise())


def test_demo_store_persists_and_rejects_invalid_updates(tmp_path):
    store = demo.NotesStore(tmp_path)
    assert store.create("preserved") == [{"id": 1, "title": "preserved"}]
    saved = store.path.read_bytes()
    for value in ["", " ", "x" * 121, " outer", "line\nbreak", 123, None]:
        with pytest.raises(ValueError):
            store.create(value)
        assert store.path.read_bytes() == saved
    assert demo.NotesStore(tmp_path).list_notes() == [{"id": 1, "title": "preserved"}]


@pytest.mark.parametrize("url", ["file:///private", "http://user:secret@example.com", "https://example.com/#fragment", "not a URL"])
def test_adapter_rejects_unscoped_target(url):
    with pytest.raises(ValueError):
        adapter.validate_url(url)


def test_real_browser_mcp():
    node = os.environ.get("BROWSER_MCP_NODE")
    browser = os.environ.get("BROWSER_MCP_EXECUTABLE")
    if not node or not browser or not Path(node).is_file() or not Path(browser).is_file():
        pytest.skip("Set BROWSER_MCP_NODE and BROWSER_MCP_EXECUTABLE to run actual browser acceptance")
    # Keep example imports local and avoid leaking a generic server module to other examples.
    old_path = list(sys.path)
    old_server = sys.modules.pop("server", None)
    old_demo = sys.modules.pop("demo_app", None)
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        verifier = load("browser_example_verifier", "verify.py")
        result = asyncio.run(verifier.verify(Path(node), Path(browser)))
        assert result["status"] == "passed"
    finally:
        sys.path[:] = old_path
        sys.modules.pop("server", None)
        sys.modules.pop("demo_app", None)
        if old_server is not None:
            sys.modules["server"] = old_server
        if old_demo is not None:
            sys.modules["demo_app"] = old_demo


def test_real_browser_blocks_other_origins_and_redirects(tmp_path):
    node = os.environ.get("BROWSER_MCP_NODE")
    browser = os.environ.get("BROWSER_MCP_EXECUTABLE")
    if not node or not browser or not Path(node).is_file() or not Path(browser).is_file():
        pytest.skip("Actual browser prerequisites not configured")
    seen = []
    finished = threading.Event()

    class Canary(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            seen.append(self.path)
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

    foreign = ThreadingHTTPServer(("127.0.0.1", 0), Canary)
    app = demo.make_server(tmp_path)
    foreign_url = f"http://127.0.0.1:{foreign.server_port}/outside"
    normal_get = app.RequestHandlerClass.do_GET

    def probe_get(handler):
        if handler.path == "/":
            script = ("<script>Promise.allSettled([fetch(" + repr(foreign_url)
                      + "),fetch('/redirect')]).then(()=>fetch('/probe-finished'));</script>")
            handler.send(200, demo.HTML + script.encode(), "text/html")
        elif handler.path == "/redirect":
            handler.send_response(302)
            handler.send_header("Location", foreign_url)
            handler.end_headers()
        elif handler.path == "/probe-finished":
            finished.set()
            handler.send(200, b"{}")
        else:
            normal_get(handler)

    app.RequestHandlerClass.do_GET = probe_get
    threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in (app, foreign)]
    for thread in threads:
        thread.start()

    async def exercise():
        bridge = adapter.BrowserBridge(app.origin, node, Path(browser))
        try:
            assert (await bridge.call("list_notes"))["notes"] == []
            assert await asyncio.to_thread(finished.wait, 5), "Browser never finished its outbound probes"
            assert seen == []
        finally:
            await bridge.close()

    try:
        asyncio.run(exercise())
    finally:
        for server in (app, foreign):
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join(timeout=5)
