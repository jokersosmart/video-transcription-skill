#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RENDER = ROOT / "scripts" / "render_transcript.py"
RUN_STT = ROOT / "scripts" / "run_stt_command.py"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, *args], capture_output=True, text=True, check=False)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_timestamped_text(tmp: Path) -> None:
    source = tmp / "raw.txt"
    source.write_text("[00:00.0 - 00:02.5] Hello\n[00:02.5 - 00:04.0] world\n", encoding="utf-8")
    out = tmp / "out-text"
    result = run(str(RENDER), str(source), "--output-dir", str(out), "--source-url", "https://example.test/video")
    assert_true(result.returncode == 0, result.stderr)
    rendered = (out / "transcript.md").read_text(encoding="utf-8")
    assert_true("Hello" in rendered and "world" in rendered, "timestamped text was not rendered")
    assert_true("https://example.test/video" in rendered, "source URL was not rendered")


def test_srt(tmp: Path) -> None:
    source = tmp / "sample.srt"
    source.write_text("1\n00:00:00,000 --> 00:00:01,200\nFirst line\n\n2\n00:00:01,200 --> 00:00:02,400\nSecond line\n", encoding="utf-8")
    out = tmp / "out-srt"
    result = run(str(RENDER), str(source), "--output-dir", str(out))
    assert_true(result.returncode == 0, result.stderr)
    rendered = (out / "transcript.txt").read_text(encoding="utf-8")
    assert_true("First line" in rendered and "Second line" in rendered, "SRT was not rendered")


def test_json(tmp: Path) -> None:
    source = tmp / "sample.json"
    source.write_text(json.dumps({"segments": [{"start": 0, "end": 1.5, "text": "JSON line"}]}), encoding="utf-8")
    out = tmp / "out-json"
    result = run(str(RENDER), str(source), "--output-dir", str(out))
    assert_true(result.returncode == 0, result.stderr)
    rendered = (out / "transcript.md").read_text(encoding="utf-8")
    assert_true("JSON line" in rendered, "JSON was not rendered")


def test_custom_command(tmp: Path) -> None:
    audio = tmp / "audio.wav"
    audio.write_bytes(b"not-real-audio")
    output = tmp / "custom_raw.txt"
    command = f"{sys.executable} -c 'print(\"custom backend\")' {{audio}}"
    result = run(str(RUN_STT), "--audio", str(audio), "--output", str(output), "--command", command)
    assert_true(result.returncode == 0, result.stderr)
    assert_true(output.read_text(encoding="utf-8").strip() == "custom backend", "custom backend output was not captured")


def main() -> int:
    with tempfile.TemporaryDirectory() as directory:
        tmp = Path(directory)
        test_timestamped_text(tmp)
        test_srt(tmp)
        test_json(tmp)
        test_custom_command(tmp)
    print("all tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
