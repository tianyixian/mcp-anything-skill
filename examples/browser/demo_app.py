"""Local notes fixture for actual browser acceptance; no account or external service."""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading

MAX_NOTES = 100
MAX_TITLE = 120
HTML = b"""<!doctype html><html lang="en"><meta charset="utf-8">
<title>MCP Anything notes demo</title><h1>Notes</h1>
<form id="create"><label for="title">Title</label>
<input id="title" required><button type="submit">Add note</button></form>
<p role="status">Loading</p><ol aria-label="Notes"></ol>
<script>
const list=document.querySelector('ol'), status=document.querySelector('[role=status]');
const input=document.querySelector('input'), button=document.querySelector('button');
function render(notes){list.replaceChildren();for(const note of notes){
 const li=document.createElement('li');li.textContent=note.title;
 li.dataset.noteId=String(note.id);list.append(li);}}
async function refresh(){const r=await fetch('/api/notes');if(!r.ok)throw Error('read');
 render((await r.json()).notes);status.textContent='Ready';}
document.querySelector('form').addEventListener('submit',async(event)=>{
 event.preventDefault();button.disabled=true;status.textContent='Saving';
 try{const r=await fetch('/api/notes',{method:'POST',headers:{'Content-Type':'application/json'},
 body:JSON.stringify({title:input.value})});if(!r.ok)throw Error('write');
 await refresh();input.value='';status.textContent='Saved';}
 catch(_){status.textContent='Error: note was not confirmed';}finally{button.disabled=false;}});
refresh().catch(()=>{status.textContent='Error: notes unavailable';});
</script></html>"""


def valid_title(value: object) -> bool:
    return (isinstance(value, str) and 1 <= len(value) <= MAX_TITLE and value == value.strip()
            and bool(value.strip()) and value.isprintable())


class NotesStore:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "notes.json"
        self.lock = threading.Lock()
        self.notes = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else []
        if not isinstance(self.notes, list) or len(self.notes) > MAX_NOTES:
            raise ValueError("Invalid notes store")
        for i, note in enumerate(self.notes, 1):
            if not isinstance(note, dict) or note != {"id": i, "title": note.get("title")} or not valid_title(note.get("title")):
                raise ValueError("Invalid notes store")

    def list_notes(self) -> list[dict]:
        with self.lock:
            return [dict(note) for note in self.notes]

    def create(self, title: str) -> list[dict]:
        if not valid_title(title):
            raise ValueError("Title must contain 1–120 characters without outer whitespace")
        with self.lock:
            if len(self.notes) >= MAX_NOTES:
                raise ValueError("Notes capacity reached")
            notes = [*self.notes, {"id": len(self.notes) + 1, "title": title}]
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(notes, ensure_ascii=False), encoding="utf-8")
            temporary.replace(self.path)
            self.notes = notes
            return [dict(note) for note in notes]


def make_server(directory: Path, port: int = 0) -> ThreadingHTTPServer:
    store = NotesStore(directory)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def send(self, code: int, content: bytes, kind: str = "application/json"):
            self.send_response(code)
            self.send_header("Content-Type", kind + "; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(content)

        def do_GET(self):
            if self.path == "/":
                self.send(200, HTML, "text/html")
            elif self.path == "/api/notes":
                self.send(200, json.dumps({"notes": store.list_notes()}, ensure_ascii=False).encode())
            else:
                self.send(404, b'{"error":"not found"}')

        def do_POST(self):
            if self.path != "/api/notes":
                self.send(404, b'{"error":"not found"}')
                return
            if self.headers.get("Origin") != server.origin:
                self.send(403, b'{"error":"origin mismatch"}')
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 2048 or self.headers.get_content_type() != "application/json":
                    raise ValueError("Invalid request")
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict) or set(data) != {"title"}:
                    raise ValueError("Invalid request")
                notes = store.create(data["title"])
                self.send(201, json.dumps({"notes": notes}, ensure_ascii=False).encode())
            except (ValueError, TypeError, UnicodeError):
                self.send(400, b'{"error":"invalid note"}')

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.origin = f"http://127.0.0.1:{server.server_port}"
    server.store = store
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = make_server(args.directory, args.port)
    print(server.origin, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
