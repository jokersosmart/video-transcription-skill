#!/usr/bin/env python3
"""Run a user-provided STT CLI without depending on a vendor SDK.

The command must contain {audio}. It may optionally contain {output}; when present,
the backend should write its result to that path. Otherwise stdout is captured.
"""
from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path


def fail(message: str) -> "NoReturn":
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(2)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a configurable STT command")
    parser.add_argument("--audio", required=True, help="Input audio path")
    parser.add_argument("--output", required=True, help="Transcript output path")
    parser.add_argument("--command", required=True, help="Command template containing {audio}")
    parser.add_argument("--timeout", type=int, default=3600)
    args = parser.parse_args()

    audio = Path(args.audio).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    if not audio.is_file():
        fail(f"audio file does not exist: {audio}")
    if "{audio}" not in args.command:
        fail("--command must contain the {audio} placeholder")
    output.parent.mkdir(parents=True, exist_ok=True)
    # The declared output is a fresh target for this invocation. Removing a stale
    # file prevents a backend that only prints to stdout from appearing successful.
    if output.exists():
        output.unlink()

    try:
        parts = shlex.split(args.command)
    except ValueError as exc:
        fail(f"invalid command quoting: {exc}")
    parts = [part.replace("{audio}", str(audio)).replace("{output}", str(output)) for part in parts]
    try:
        completed = subprocess.run(
            parts,
            capture_output=True,
            text=True,
            timeout=args.timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        fail(f"STT command timed out after {args.timeout} seconds")
    except OSError as exc:
        fail(f"could not start STT command: {exc}")

    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "command failed"
        fail(detail[-4000:])

    if not output.is_file() or output.stat().st_size == 0:
        if not completed.stdout.strip():
            fail("STT command succeeded but produced neither {output} nor stdout")
        output.write_text(completed.stdout, encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    main()
