#!/usr/bin/env python3
"""Extract speech-friendly audio from a local media file using ffmpeg."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def fail(message: str) -> "NoReturn":
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(2)


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract mono 16 kHz WAV audio")
    parser.add_argument("media", help="Path to a local video or audio file")
    parser.add_argument("--output-dir", required=True, help="Directory for the WAV output")
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--channels", type=int, default=1)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        fail("ffmpeg is required for audio extraction but was not found on PATH")
    media = Path(args.media).expanduser().resolve()
    if not media.is_file():
        fail(f"media file does not exist: {media}")
    if args.sample_rate <= 0 or args.channels <= 0:
        fail("sample rate and channel count must be positive")

    outdir = Path(args.output_dir).expanduser().resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    output = outdir / f"{media.stem}.wav"
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel", "error",
        "-y" if args.overwrite else "-n",
        "-i", str(media),
        "-vn",
        "-ac", str(args.channels),
        "-ar", str(args.sample_rate),
        "-c:a", "pcm_s16le",
        str(output),
    ]
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "ffmpeg returned a non-zero exit status"
        fail(detail[-2000:])
    if not output.is_file() or output.stat().st_size == 0:
        fail("ffmpeg completed but produced no audio file")
    print(output)
    return 0


if __name__ == "__main__":
    main()
