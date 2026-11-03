"""Run actual FFmpeg tools over MCP and verify lossless audio output."""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from make_sample import make_sample


async def verify(workspace: Path, ffmpeg: Path, ffprobe: Path) -> dict:
    source = workspace / "tone.wav"
    pcm = make_sample(source)
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    parameters = StdioServerParameters(command=sys.executable, args=[
        str(Path(__file__).with_name("server.py")), "--workspace", str(workspace),
        "--ffmpeg", str(ffmpeg), "--ffprobe", str(ffprobe),
    ])
    calls = []
    rejected = []
    async with stdio_client(parameters) as (reader, writer), ClientSession(reader, writer) as session:
        await session.initialize()
        tools = (await session.list_tools()).tools
        assert {tool.name for tool in tools} == {"inspect_audio", "convert_audio"}
        assert all(tool.outputSchema for tool in tools)
        for name, arguments in [
            ("inspect_audio", {"input_file": "tone.wav"}),
            ("convert_audio", {"input_file": "tone.wav", "output_file": "tone.flac"}),
            ("inspect_audio", {"input_file": "tone.flac"}),
        ]:
            result = await session.call_tool(name, arguments)
            assert not result.isError, result.content
            assert result.structuredContent
            calls.append({"tool": name, "input": arguments, "output": result.structuredContent})
        before = hashlib.sha256((workspace / "tone.flac").read_bytes()).hexdigest()
        for name, arguments in [
            ("convert_audio", {"input_file": "tone.wav", "output_file": "tone.flac"}),
            ("inspect_audio", {"input_file": "../tone.wav"}),
            ("inspect_audio", {"input_file": "https://example.com/audio.wav"}),
            ("inspect_audio", {"input_file": "tone.wav:alternate"}),
            ("convert_audio", {"input_file": "tone.wav", "output_file": "../outside.flac"}),
        ]:
            result = await session.call_tool(name, arguments)
            assert result.isError
            rejected.append({"tool": name, "input": arguments})
        assert hashlib.sha256((workspace / "tone.flac").read_bytes()).hexdigest() == before
    assert calls[0]["output"]["sample_rate_hz"] == 16000
    assert calls[0]["output"]["duration_seconds"] == 1
    assert calls[2]["output"]["codec"] == "flac"
    assert calls[2]["output"]["channels"] == 1
    assert calls[2]["output"]["duration_seconds"] == 1
    decoded = subprocess.run([
        str(ffmpeg), "-nostdin", "-v", "error", "-protocol_whitelist", "file,pipe",
        "-f", "flac", "-i", str(workspace / "tone.flac"),
        "-f", "s16le", "-c:a", "pcm_s16le", "pipe:1",
    ], capture_output=True, check=True, timeout=15).stdout
    assert decoded == pcm
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
    native_version = subprocess.run([str(ffmpeg), "-version"], capture_output=True,
                                    check=True, timeout=10).stdout.decode(errors="replace").splitlines()[0]
    return {
        "status": "passed", "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "kind": "installed FFmpeg executable via real MCP stdio calls; no repository source used",
        "platform": platform.system(), "python": platform.python_version(),
        "mcp_sdk": version("mcp"), "ffmpeg": native_version,
        "tools": [tool.name for tool in tools], "calls": calls, "rejected_inputs": rejected,
        "input_hash_unchanged": True, "existing_output_hash_unchanged": True,
        "decoded_pcm_sha256": hashlib.sha256(decoded).hexdigest(),
        "decoded_samples": len(decoded) // 2, "lossless_pcm_match": True,
        "not_tested": ["Malicious media", "Concurrent external workspace writers", "Remote HTTP deployment"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ffmpeg", type=Path)
    parser.add_argument("--ffprobe", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    binaries = [args.ffmpeg or shutil.which("ffmpeg"), args.ffprobe or shutil.which("ffprobe")]
    if not all(binaries):
        parser.error("Install FFmpeg/ffprobe separately or supply their absolute executable paths")
    with tempfile.TemporaryDirectory(prefix="ffmpeg-mcp-check-") as temporary:
        report = asyncio.run(verify(Path(temporary), *(Path(binary).resolve() for binary in binaries)))
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(serialized)
        print(f"Real FFmpeg MCP acceptance passed; report: {args.output.name}")
    else:
        print(serialized)


if __name__ == "__main__":
    main()
