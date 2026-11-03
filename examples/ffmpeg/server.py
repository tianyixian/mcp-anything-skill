"""Expose bounded local audio inspection and WAV-to-FLAC conversion through MCP."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
import stat
import subprocess
import tempfile
import threading
from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

MAX_INPUT_BYTES = 64 * 1024 * 1024
MAX_OUTPUT_BYTES = 32 * 1024 * 1024
MAX_PROCESS_OUTPUT = 64 * 1024
MAX_DURATION_SECONDS = 60
PROBE_SECONDS = 10
CONVERT_SECONDS = 30
FileName = Annotated[str, Field(min_length=1, max_length=240, strict=True)]


class AudioInfo(BaseModel):
    file: str
    format: Literal["wav", "flac"]
    codec: str
    sample_rate_hz: int
    channels: int
    duration_seconds: float
    file_bytes: int


class Conversion(BaseModel):
    input: AudioInfo
    output: AudioInfo
    input_sha256: str


def reparse(path: Path) -> bool:
    attributes = path.lstat()
    return stat.S_ISLNK(attributes.st_mode) or bool(
        getattr(attributes, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def checked_directory(path: Path) -> Path:
    """Reject linked directories before resolve can hide them."""
    if ".." in path.parts:
        raise ValueError("Workspace must not contain parent traversal")
    path = path.absolute()
    for component in reversed((path, *path.parents)):
        if reparse(component):
            raise ValueError("Workspace must not pass through a link or reparse point")
    if not path.is_dir():
        raise ValueError("Workspace must be an existing directory")
    return path.resolve(strict=True)


def run_bounded(command: list[str], timeout: float) -> bytes:
    """Run a fixed argument array with a combined pipe budget and a deadline."""
    process = subprocess.Popen(
        command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, shell=False,
    )
    captured = [bytearray(), bytearray()]
    state = {"bytes": 0, "overflow": False}
    lock = threading.Lock()

    def read_pipe(pipe, index):
        try:
            while chunk := pipe.read(4096):
                with lock:
                    state["bytes"] += len(chunk)
                    if state["bytes"] > MAX_PROCESS_OUTPUT:
                        state["overflow"] = True
                    else:
                        captured[index].extend(chunk)
                if state["overflow"]:
                    try:
                        process.kill()
                    except OSError:
                        pass
        finally:
            pipe.close()

    readers = [
        threading.Thread(target=read_pipe, args=(process.stdout, 0), daemon=True),
        threading.Thread(target=read_pipe, args=(process.stderr, 1), daemon=True),
    ]
    for reader in readers:
        reader.start()
    expired = False
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        expired = True
        process.kill()
        process.wait(timeout=5)
    finally:
        for reader in readers:
            reader.join(timeout=5)
    if any(reader.is_alive() for reader in readers):
        raise ValueError("Audio process did not close its output streams")
    if expired:
        raise ValueError("Audio operation exceeded its time limit")
    if state["overflow"]:
        raise ValueError("Audio process exceeded its output limit")
    if process.returncode:
        # Keep native diagnostics out of the protocol: they can contain paths or metadata.
        raise ValueError("Audio operation failed; check the file format and configured FFmpeg installation")
    return bytes(captured[0])


class AudioService:
    def __init__(self, workspace: Path, ffmpeg: Path, ffprobe: Path):
        self.workspace = checked_directory(workspace)
        self.ffmpeg = self._executable(ffmpeg)
        self.ffprobe = self._executable(ffprobe)
        self.lock = threading.Lock()

    @staticmethod
    def _executable(path: Path) -> str:
        if not path.is_absolute():
            raise ValueError("Executable paths must be absolute operator configuration")
        path = path.resolve(strict=True)
        if not path.is_file() or (os.name != "nt" and not os.access(path, os.X_OK)):
            raise ValueError("Configured executable is not an executable file")
        if os.name == "nt" and path.suffix.lower() != ".exe":
            raise ValueError("Configure a native .exe on Windows, not a shell script")
        return str(path)

    def file_path(self, name: str, *, output: bool = False) -> Path:
        if not isinstance(name, str) or not 1 <= len(name) <= 240:
            raise ValueError("Use a workspace-relative file name of at most 240 characters")
        # Use one portable grammar; ':' also excludes URLs, drive names and NTFS streams.
        if any(ord(char) < 32 or char in '\\:*?"<>|' for char in name):
            raise ValueError("Use a local relative path with forward slashes")
        relative = PurePosixPath(name)
        if relative.is_absolute() or PureWindowsPath(name).drive:
            raise ValueError("Absolute paths and network addresses are not accepted")
        if any(part in {"", ".", ".."} for part in name.split("/")):
            raise ValueError("Parent traversal and empty path components are not accepted")
        for part in relative.parts:
            stem = part.split(".")[0].upper()
            if part.endswith((".", " ")) or stem in {
                "CON", "PRN", "AUX", "NUL", *{f"COM{i}" for i in range(1, 10)},
                *{f"LPT{i}" for i in range(1, 10)},
            }:
                raise ValueError("Use a portable ordinary file name")
        candidate = self.workspace.joinpath(*relative.parts)
        checked_directory(self.workspace)
        current = self.workspace
        for index, part in enumerate(relative.parts):
            current /= part
            last = index == len(relative.parts) - 1
            if last and output and not os.path.lexists(current):
                break
            if not os.path.lexists(current):
                raise ValueError("Input file or parent directory does not exist in the workspace")
            if reparse(current):
                raise ValueError("Links and reparse points are not accepted")
            if not last and not current.is_dir():
                raise ValueError("Output parent directories must already exist")
        if output:
            if candidate.suffix.lower() != ".flac":
                raise ValueError("Output must be a new .flac file")
            if candidate.exists():
                raise ValueError("Output already exists; choose a new file name")
        else:
            if candidate.suffix.lower() not in {".wav", ".flac"}:
                raise ValueError("Only local WAV and FLAC audio files are supported")
            attributes = candidate.stat()
            if not stat.S_ISREG(attributes.st_mode) or not 0 < attributes.st_size <= MAX_INPUT_BYTES:
                raise ValueError("Input must be a regular audio file of at most 64 MiB")
        return candidate

    def _probe(self, path: Path, name: str) -> AudioInfo:
        audio_format = path.suffix.lower()[1:]
        raw = run_bounded([
            self.ffprobe, "-v", "error", "-protocol_whitelist", "file",
            "-f", audio_format, "-i", str(path), "-show_entries",
            "stream=codec_type,codec_name,sample_rate,channels:format=duration",
            "-of", "json",
        ], PROBE_SECONDS)
        try:
            payload = json.loads(raw)
            streams = payload["streams"]
            if len(streams) != 1 or streams[0]["codec_type"] != "audio":
                raise ValueError()
            stream = streams[0]
            rate, channels = int(stream["sample_rate"]), int(stream["channels"])
            duration = float(payload["format"]["duration"])
            codec = stream["codec_name"]
            if (not 1 <= rate <= 96000 or channels not in {1, 2}
                    or not math.isfinite(duration) or not 0 < duration <= MAX_DURATION_SECONDS
                    or not isinstance(codec, str) or len(codec) > 64):
                raise ValueError()
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            raise ValueError("Use one mono/stereo audio stream, at most 96 kHz and 60 seconds") from None
        return AudioInfo(file=name, format=audio_format, codec=codec,
                         sample_rate_hz=rate, channels=channels,
                         duration_seconds=duration, file_bytes=path.stat().st_size)

    def inspect_audio(self, input_file: str) -> AudioInfo:
        with self.lock:
            return self._probe(self.file_path(input_file), input_file)

    def convert_audio(self, input_file: str, output_file: str) -> Conversion:
        with self.lock:
            source = self.file_path(input_file)
            destination = self.file_path(output_file, output=True)
            if source.suffix.lower() != ".wav":
                raise ValueError("Conversion accepts a PCM 16-bit WAV input")
            info = self._probe(source, input_file)
            if info.codec != "pcm_s16le":
                raise ValueError("Conversion accepts a PCM 16-bit WAV input")
            source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            # Only our private temporary output can be overwritten by the native process.
            with tempfile.TemporaryDirectory(prefix=".mcp-flac-", dir=self.workspace) as temporary:
                rendered = Path(temporary) / "audio.flac"
                run_bounded([
                    self.ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                    "-protocol_whitelist", "file", "-f", "wav", "-i", str(source),
                    "-map", "0:a:0", "-vn", "-sn", "-dn", "-map_metadata", "-1",
                    "-c:a", "flac", "-compression_level", "5", "-threads", "1",
                    "-fs", str(MAX_OUTPUT_BYTES), "-f", "flac", str(rendered),
                ], CONVERT_SECONDS)
                converted = self._probe(rendered, output_file)
                if (converted.file_bytes > MAX_OUTPUT_BYTES
                        or converted.sample_rate_hz != info.sample_rate_hz
                        or converted.channels != info.channels
                        or abs(converted.duration_seconds - info.duration_seconds) > 1 / info.sample_rate_hz):
                    raise ValueError("Converted output failed its audio integrity checks")
                if hashlib.sha256(source.read_bytes()).hexdigest() != source_hash:
                    raise ValueError("Input changed during conversion; no output was published")
                destination = self.file_path(output_file, output=True)
                created = False
                try:
                    with destination.open("xb") as output, rendered.open("rb") as completed:
                        created = True
                        shutil.copyfileobj(completed, output)
                except BaseException:
                    if created:
                        destination.unlink(missing_ok=True)
                    raise
            return Conversion(input=info, output=converted, input_sha256=source_hash)


def create_server(service: AudioService) -> FastMCP:
    server = FastMCP("ffmpeg-audio")

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False,
                                           idempotentHint=True, openWorldHint=False))
    def inspect_audio(input_file: FileName) -> AudioInfo:
        """Inspect one workspace-relative WAV/FLAC; mono/stereo, <=96 kHz, <=60 s, <=64 MiB."""
        return service.inspect_audio(input_file)

    @server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False,
                                           idempotentHint=False, openWorldHint=False))
    def convert_audio(input_file: FileName, output_file: FileName) -> Conversion:
        """Convert PCM 16-bit WAV to a new FLAC in the workspace; refuse existing output and preserve input."""
        return service.convert_audio(input_file, output_file)

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--ffprobe", type=Path, required=True)
    args = parser.parse_args()
    try:
        service = AudioService(args.workspace, args.ffmpeg, args.ffprobe)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    create_server(service).run(transport="stdio")


if __name__ == "__main__":
    main()
