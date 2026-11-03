"""Check real native-process behavior and the example's file boundaries."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


adapter = load("ffmpeg_example_adapter", "server.py")
sample = load("ffmpeg_example_sample", "make_sample.py")


@pytest.fixture
def binaries():
    paths = [shutil.which("ffmpeg"), shutil.which("ffprobe")]
    if not all(paths):
        pytest.skip("Real FFmpeg and ffprobe must be installed separately")
    return [Path(path).resolve() for path in paths]


@pytest.fixture
def service(tmp_path, binaries):
    sample.make_sample(tmp_path / "tone.wav")
    return adapter.AudioService(tmp_path, *binaries)


@pytest.mark.parametrize("name", ["../tone.wav", "/tone.wav", "C:/tone.wav", "tone.wav:alt",
                                  "https://example.com/a.wav", "//host/share/a.wav", "a/../tone.wav"])
def test_workspace_escape_and_network_names_rejected(service, name):
    with pytest.raises(ValueError):
        service.inspect_audio(name)


def test_conversion_refuses_existing_output_and_preserves_input(service, tmp_path):
    original = (tmp_path / "tone.wav").read_bytes()
    existing = tmp_path / "existing.flac"
    existing.write_bytes(b"existing user file")
    with pytest.raises(ValueError, match="already exists"):
        service.convert_audio("tone.wav", "existing.flac")
    assert existing.read_bytes() == b"existing user file"
    assert (tmp_path / "tone.wav").read_bytes() == original


def test_malformed_audio_leaves_no_output(service, tmp_path):
    (tmp_path / "bad.wav").write_bytes(b"not audio")
    with pytest.raises(ValueError, match="Audio operation failed"):
        service.convert_audio("bad.wav", "bad.flac")
    assert not (tmp_path / "bad.flac").exists()


def test_duration_limit_precedes_conversion(service, tmp_path):
    sample.make_sample(tmp_path / "long.wav", seconds=61)
    with pytest.raises(ValueError, match="60 seconds"):
        service.convert_audio("long.wav", "long.flac")
    assert not (tmp_path / "long.flac").exists()


def test_incomplete_conversion_is_not_published(service, tmp_path, monkeypatch):
    monkeypatch.setattr(adapter, "MAX_OUTPUT_BYTES", 512)
    with pytest.raises(ValueError):
        service.convert_audio("tone.wav", "truncated.flac")
    assert not (tmp_path / "truncated.flac").exists()
    assert not list(tmp_path.glob(".mcp-flac-*"))


def test_symlink_input_is_rejected(service, tmp_path):
    link = tmp_path / "linked.wav"
    try:
        link.symlink_to(tmp_path / "tone.wav")
    except OSError:
        pytest.skip("Creating symlinks requires OS privileges")
    with pytest.raises(ValueError, match="Links"):
        service.inspect_audio("linked.wav")


@pytest.mark.skipif(os.name != "nt", reason="Windows junction behavior")
def test_junction_output_parent_is_rejected(service, tmp_path):
    outside = tmp_path.parent / (tmp_path.name + "-outside")
    outside.mkdir()
    junction = tmp_path / "linked"
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(outside)], capture_output=True)
    if result.returncode:
        pytest.skip("OS did not permit a temporary test junction")
    try:
        with pytest.raises(ValueError, match="Links"):
            service.convert_audio("tone.wav", "linked/audio.flac")
        assert not list(outside.iterdir())
    finally:
        os.rmdir(junction)


def test_output_budget_terminates_child():
    with pytest.raises(ValueError, match="output limit"):
        adapter.run_bounded([sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'x'*200000)"], 5)


def test_deadline_terminates_child():
    with pytest.raises(ValueError, match="time limit"):
        adapter.run_bounded([sys.executable, "-c", "import time; time.sleep(30)"], 0.1)


@pytest.mark.asyncio
async def test_real_mcp_and_lossless_conversion(tmp_path, binaries):
    previous = sys.modules.get("make_sample")
    sys.modules["make_sample"] = sample
    try:
        acceptance = load("ffmpeg_example_verify", "verify.py")
    finally:
        if previous is None:
            sys.modules.pop("make_sample", None)
        else:
            sys.modules["make_sample"] = previous
    result = await acceptance.verify(tmp_path, *binaries)
    assert result["lossless_pcm_match"] is True
