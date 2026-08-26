#!/usr/bin/env python3
"""Render common STT output formats into transcript.md and transcript.txt."""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class Segment:
    start: str | None
    end: str | None
    text: str
    speaker: str | None = None


TIMESTAMPED_LINE = re.compile(
    r"^\s*\[(?P<start>\d{1,2}:\d{2}(?::\d{2})?(?:[\.,]\d+)?)\s*(?:-|–|—|to|-->)\s*(?P<end>\d{1,2}:\d{2}(?::\d{2})?(?:[\.,]\d+)?)\]\s*(?P<text>.*)\s*$",
    flags=re.IGNORECASE,
)
SRT_LINE = re.compile(
    r"^\s*(?P<start>\d{2}:\d{2}:\d{2}[\.,]\d{1,3})\s*-->\s*(?P<end>\d{2}:\d{2}:\d{2}[\.,]\d{1,3})(?:\s+.*)?$"
)


def fail(message: str) -> "NoReturn":
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(2)


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(clean_text(item) for item in value).strip()
    return re.sub(r"\s+", " ", str(value)).strip()


def normalize_timestamp(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        seconds = float(value)
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        remainder = seconds % 60
        if hours:
            return f"{hours:02d}:{minutes:02d}:{remainder:04.1f}"
        return f"{minutes:02d}:{remainder:04.1f}"
    return str(value).replace(",", ".").strip()


def from_json_object(value: Any) -> list[Segment]:
    if isinstance(value, list):
        output: list[Segment] = []
        for item in value:
            output.extend(from_json_object(item))
        return output
    if isinstance(value, dict):
        # Prefer segment arrays and common response containers.
        for key in ("segments", "utterances", "results", "transcript"):
            if key in value and isinstance(value[key], (list, dict)):
                nested = from_json_object(value[key])
                if nested:
                    return nested
        text = value.get("text") or value.get("transcript") or value.get("content")
        if text is not None:
            start = value.get("start", value.get("start_time", value.get("startTime")))
            end = value.get("end", value.get("end_time", value.get("endTime")))
            speaker = value.get("speaker", value.get("speaker_label"))
            body = clean_text(text)
            return [Segment(normalize_timestamp(start), normalize_timestamp(end), body, clean_text(speaker) or None)] if body else []
    return []


def parse_json_text(text: str) -> list[Segment]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return []
    return from_json_object(value)


def parse_caption_text(text: str) -> list[Segment]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    segments: list[Segment] = []
    current_start: str | None = None
    current_end: str | None = None
    current_text: list[str] = []
    in_caption = False

    def flush() -> None:
        nonlocal current_start, current_end, current_text
        body = clean_text(" ".join(current_text))
        if body:
            segments.append(Segment(current_start, current_end, body))
        current_start = None
        current_end = None
        current_text = []

    for line in lines:
        stripped = line.strip().lstrip("\ufeff")
        if not stripped or stripped.upper() == "WEBVTT" or stripped.startswith("NOTE"):
            if current_start is not None and current_text:
                flush()
            continue
        timestamped = TIMESTAMPED_LINE.match(stripped)
        if timestamped:
            if current_start is not None:
                flush()
            segments.append(Segment(timestamped.group("start"), timestamped.group("end"), clean_text(timestamped.group("text"))))
            continue
        srt = SRT_LINE.match(stripped)
        if srt:
            if current_start is not None:
                flush()
            current_start = srt.group("start")
            current_end = srt.group("end")
            current_text = []
            in_caption = True
            continue
        if in_caption:
            if re.fullmatch(r"\d+", stripped) and not current_text:
                continue
            current_text.append(stripped)
    if current_start is not None:
        flush()

    if segments:
        return segments
    # No timing markers: preserve the input as one untimed transcript segment.
    body = clean_text(" ".join(line.strip() for line in lines if line.strip()))
    return [Segment(None, None, body)] if body else []


def parse_input(path: Path) -> list[Segment]:
    text = path.read_text(encoding="utf-8", errors="replace")
    segments = parse_json_text(text) if path.suffix.lower() == ".json" else []
    if not segments:
        segments = parse_caption_text(text)
    return segments


def display_segment(segment: Segment) -> str:
    body = segment.text
    if segment.speaker:
        body = f"{segment.speaker}: {body}"
    if segment.start and segment.end:
        return f"[{segment.start}–{segment.end}] {body}"
    return body


def markdown_escape_metadata(value: str) -> str:
    return value.replace("\n", " ").strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Render transcript files")
    parser.add_argument("input", help="Raw transcript file: TXT, SRT, VTT, or JSON")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--source-url", default="")
    parser.add_argument("--source-file", default="")
    parser.add_argument("--language", default="unknown")
    parser.add_argument("--title", default="Video Transcript")
    parser.add_argument("--note", default="Automatic speech recognition output; verify proper nouns and unclear words.")
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.is_file():
        fail(f"transcript input does not exist: {input_path}")
    segments = parse_input(input_path)
    if not segments:
        fail("no transcript text was found in the input file")

    outdir = Path(args.output_dir).expanduser().resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    source = args.source_url or args.source_file or str(input_path)
    timestamped = [display_segment(segment) for segment in segments]
    continuous = "".join(segment.text for segment in segments)
    if not continuous:
        continuous = "\n".join(segment.text for segment in segments)
    has_timestamps = any(segment.start and segment.end for segment in segments)
    timestamp_note = "來源有提供時間碼。" if has_timestamps else "時間碼：來源未提供。"

    md = [
        f"# {markdown_escape_metadata(args.title)}",
        "",
        f"> 來源：{markdown_escape_metadata(source)}",
        f"> 語言：{markdown_escape_metadata(args.language)}；{timestamp_note}",
        f"> {markdown_escape_metadata(args.note)}",
        "",
        "## 含時間碼逐字稿" if has_timestamps else "## 逐字稿",
        "",
    ]
    md.extend(f"**{line.split('] ', 1)[0]}]** {line.split('] ', 1)[1]}" if line.startswith("[") and "] " in line else line for line in timestamped)
    md += ["", "## 連續全文", "", continuous, ""]
    (outdir / "transcript.md").write_text("\n".join(md), encoding="utf-8")
    (outdir / "transcript.txt").write_text("\n".join(timestamped) + "\n", encoding="utf-8")
    print(outdir / "transcript.md")
    print(outdir / "transcript.txt")
    return 0


if __name__ == "__main__":
    main()
