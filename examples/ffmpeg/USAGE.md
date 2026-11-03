# Audio tools for an agent

Use these tools for short trusted audio files in the configured local workspace.
The operator supplies the FFmpeg installation and workspace when starting the
server; tools accept neither executable paths nor arbitrary command options.

## Tools

- `inspect_audio(input_file)`: inspect a workspace-relative `.wav` or `.flac`
  file. Returns `file`, `format`, `codec`, `sample_rate_hz`, `channels`,
  `duration_seconds` and `file_bytes`. This is read-only.
- `convert_audio(input_file, output_file)`: convert PCM 16-bit WAV to a new
  `.flac` path. Returns `input` and `output` audio information plus
  `input_sha256`. The input is preserved. Existing output is always rejected.

Names use forward slashes; subdirectories must already exist. Inputs are limited
to 64 MiB, 60 seconds, mono/stereo and 96 kHz. URLs, absolute paths, parent
traversal, links and Windows reparse points are rejected. The tools do not create
parent folders or accept an output-format option.

## Tested recipe

The acceptance command creates `tone.wav`, containing 16,000 signed 16-bit mono
samples at 16,000 Hz (one second):

1. `inspect_audio({"input_file":"tone.wav"})` reports `codec: "pcm_s16le"`,
   `sample_rate_hz: 16000`, `channels: 1`, `duration_seconds: 1.0`.
2. `convert_audio({"input_file":"tone.wav","output_file":"tone.flac"})`
   creates the FLAC and returns its verified audio information.
3. `inspect_audio({"input_file":"tone.flac"})` reports `codec: "flac"` with
   the same rate, channel count and duration. Independently decoding the output
   in the acceptance run reproduced all 16,000 original samples exactly.

The generated file's exact encoded bytes/size can vary between FFmpeg builds.
The sample comparison establishes the observed lossless result for this case.

## Recovery and retries

An MCP error is a failed operation, not audio data. If the input is missing,
check the relative name and configured workspace. For a format or size error,
use a supported input; do not bypass limits with an executable or command string.
For a missing/unusable FFmpeg installation, the operator must fix its startup
configuration. Metadata and process errors deliberately do not return native
stderr, which can contain local paths.

Read-only inspection is safe to retry on an unchanged file. Conversion is not
an overwrite operation: if the client disconnects, first inspect the requested
output. A completed output may exist even when the response was lost. Never
silently select a different output name and repeat a user write. Choose a new
destination only when the user intends another output.

No returned success means the tool has not established a completed conversion.
The adapter removes its private temporary directory on ordinary failure; it is
not a durable job queue or a sandbox against malicious media.
