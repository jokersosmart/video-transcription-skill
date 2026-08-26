#!/usr/bin/env python3
"""Install this Skill into common local agent Skill directories."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

SKILL_NAME = "video-transcription"


def fail(message: str) -> "NoReturn":
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(2)


def install(source: Path, destination: Path, mode: str) -> Path:
    destination = destination.expanduser().resolve()
    if destination.exists() or destination.is_symlink():
        if not args.force:
            fail(f"destination exists; use --force to replace: {destination}")
        if destination.is_symlink() or destination.is_file():
            destination.unlink()
        else:
            shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if mode == "symlink":
        destination.symlink_to(source, target_is_directory=True)
    else:
        shutil.copytree(source, destination)
    return destination


parser = argparse.ArgumentParser(description="Install video-transcription for local agents")
parser.add_argument("--target", choices=("claude", "codex", "all", "custom"), default="all")
parser.add_argument("--dest", help="Custom Skill directory when --target custom is used")
parser.add_argument("--mode", choices=("copy", "symlink"), default="copy")
parser.add_argument("--force", action="store_true")
args = parser.parse_args()

source = Path(__file__).resolve().parents[1]
if not (source / "SKILL.md").is_file():
    fail(f"SKILL.md not found beside scripts: {source}")

home = Path.home()
targets: list[Path] = []
if args.target in {"claude", "all"}:
    targets.append(home / ".claude" / "skills" / SKILL_NAME)
if args.target in {"codex", "all"}:
    targets.extend([
        home / ".agents" / "skills" / SKILL_NAME,
        home / ".codex" / "skills" / SKILL_NAME,
    ])
if args.target == "custom":
    if not args.dest:
        fail("--dest is required with --target custom")
    targets.append(Path(args.dest).expanduser())

for target in targets:
    print(install(source, target, args.mode))
