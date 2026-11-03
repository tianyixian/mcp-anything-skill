# Installed FFmpeg → MCP

This example connects an already installed program without fetching its source
repository. It inspects local WAV/FLAC audio and converts PCM 16-bit WAV to FLAC.
Each conversion checks the output's duration, channels and sample rate before
publishing a new file. The acceptance command also decodes the FLAC and compares
all audio samples with the original.

## Install and connect

Use Python 3.11+ and install the official MCP Python SDK in a dedicated environment:

```sh
python -m venv .venv
# Run the environment's Python executable for the following commands.
python -m pip install mcp==1.30.0
```

Install FFmpeg separately using its official distribution or an OS package
manager. Both `ffmpeg` and `ffprobe` are required. This example neither ships
FFmpeg nor downloads software at runtime. Set up a dedicated workspace containing
trusted audio files, then configure the MCP client using absolute paths:

```json
{
  "mcpServers": {
    "audio": {
      "command": "/absolute/path/to/.venv/bin/python",
      "args": [
        "/absolute/path/to/examples/ffmpeg/server.py",
        "--workspace", "/absolute/path/to/audio-workspace",
        "--ffmpeg", "/absolute/path/to/ffmpeg",
        "--ffprobe", "/absolute/path/to/ffprobe"
      ]
    }
  }
}
```

On Windows use the environment's `Scripts/python.exe` and actual `.exe` paths.
Use `Get-Command ffmpeg,ffprobe` to locate them. On Linux/macOS use
`command -v ffmpeg` and `command -v ffprobe`. Resolve package-manager links to
their installed executable if necessary. No executable or shell command is
accepted as a tool argument.

## Verify

```sh
python examples/ffmpeg/verify.py --output ffmpeg-validation.json
python -m pytest examples/ffmpeg -q
```

The verifier finds FFmpeg on PATH; `--ffmpeg` and `--ffprobe` override that
lookup. It uses a temporary workspace and creates its own one-second WAV.
The report refuses an existing destination. Tests requiring real FFmpeg skip
when either program is unavailable, so inspect the actual results.

See [validation.json](validation.json) for the recorded actual acceptance and
[USAGE.md](USAGE.md) for tool inputs, outputs and recovery.

## Scope

- One audio stream, mono/stereo, at most 96 kHz, 60 seconds and 64 MiB input.
- WAV-to-FLAC conversion accepts only PCM signed 16-bit little-endian WAV;
  this restriction avoids silent precision changes in the example.
- Relative paths in one operator-selected workspace; no URLs, playlists,
  arbitrary arguments, symlinks, Windows junctions or existing-output overwrite.
- FFmpeg uses one codec thread, a 30-second conversion deadline, a 32 MiB
  output limit and a 64 KiB combined diagnostic-output budget. Each ffprobe
  invocation has a 10-second deadline. The adapter serializes its operations.
- The workspace is trusted and must not be concurrently modified by another
  process. Path checks and restricted demuxers do not sandbox native FFmpeg
  against malicious media or hostile local writers.
- The server is local stdio; it has no shared-user authentication or GUI control.

FFmpeg has its own LGPL/GPL licensing depending on its build. Users provide
their installation; the project's MIT license covers this original adapter.
