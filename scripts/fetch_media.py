#!/usr/bin/env python3
"""Fetch a media URL or discover a public embedded media URL.

The script intentionally uses only the Python standard library. It never executes
page-provided JavaScript and only saves a response after it is identified as media.
"""
from __future__ import annotations

import argparse
import html
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

USER_AGENT = "video-transcription-skill/0.1 (+https://agentskills.io/)"
DEFAULT_MAX_BYTES = 500 * 1024 * 1024
MEDIA_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v", ".mkv", ".avi", ".mp3", ".wav", ".m4a", ".ogg", ".flac"}
MEDIA_TYPES = ("video/", "audio/")


def log(message: str) -> None:
    print(message, file=sys.stderr)


def fail(message: str, code: int = 2) -> "NoReturn":
    log(f"error: {message}")
    raise SystemExit(code)


def extension_from_content_type(content_type: str) -> str | None:
    value = content_type.split(";", 1)[0].strip().lower()
    if value.startswith("video/") or value.startswith("audio/"):
        return mimetypes.guess_extension(value) or ".bin"
    return None


def extension_from_url(url: str) -> str | None:
    suffix = Path(urlparse(url).path).suffix.lower()
    return suffix if suffix in MEDIA_EXTENSIONS else None


def safe_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return value or "media"


def open_url(url: str, timeout: int):
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    return urlopen(request, timeout=timeout)


def read_limited(response, max_bytes: int) -> bytes:
    length_header = response.headers.get("Content-Length")
    if length_header and length_header.isdigit() and int(length_header) > max_bytes:
        fail(f"remote object exceeds limit of {max_bytes} bytes")
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = response.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            fail(f"remote object exceeds limit of {max_bytes} bytes")
        chunks.append(chunk)
    return b"".join(chunks)


def is_media_response(response, url: str) -> bool:
    content_type = response.headers.get("Content-Type", "").lower()
    return content_type.startswith(MEDIA_TYPES) or extension_from_url(url) is not None


def extract_candidates(page_url: str, body: bytes) -> list[str]:
    """Find public media URLs in HTML/JSON without executing page code."""
    text = html.unescape(body.decode("utf-8", errors="replace"))
    text = text.replace("\\/", "/").replace("\\u0026", "&").replace("\\u003d", "=")
    text = text.replace("\\u00253D", "%3D")
    patterns = [
        r'"(?:video_versions|playable_url|contentUrl|og:video)"\s*:\s*"(https?://[^"<>]+)"',
        r'(https?://[^"\'<>\s]+?\.(?:mp4|webm|mov|m4v)(?:\?[^"\'<>\s]*)?)',
    ]
    found: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            candidate = unquote(match.group(1)).replace("\\u0026", "&")
            if candidate.startswith("//"):
                candidate = "https:" + candidate
            if candidate.startswith("http") and candidate not in found:
                found.append(candidate)
    return found


def save_bytes(data: bytes, outdir: Path, extension: str, stem: str = "media") -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    destination = outdir / f"{safe_name(stem)}{extension}"
    fd, temporary = tempfile.mkstemp(prefix=".media-", suffix=".part", dir=outdir)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return destination.resolve()


def download_direct(url: str, outdir: Path, timeout: int, max_bytes: int, stem: str = "media") -> Path | None:
    try:
        with open_url(url, timeout) as response:
            final_url = response.geturl()
            content_type = response.headers.get("Content-Type", "")
            if not is_media_response(response, final_url):
                return None
            data = read_limited(response, max_bytes)
            extension = extension_from_content_type(content_type) or extension_from_url(final_url) or ".bin"
            return save_bytes(data, outdir, extension, stem=stem)
    except Exception as exc:
        log(f"warning: media download failed for {url}: {exc}")
        return None


def yt_dlp_fallback(url: str, outdir: Path, max_bytes: int) -> Path | None:
    executable = shutil.which("yt-dlp")
    if not executable:
        return None
    outdir.mkdir(parents=True, exist_ok=True)
    template = str((outdir / "media.%(ext)s").resolve())
    command = [
        executable,
        "--no-playlist",
        "--max-filesize", str(max_bytes),
        "--no-warnings",
        "--restrict-filenames",
        "-o", template,
        url,
    ]
    log("info: trying yt-dlp fallback")
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        if completed.stderr.strip():
            log(f"warning: yt-dlp: {completed.stderr.strip()[-1000:]}")
        return None
    candidates = sorted(outdir.glob("media.*"))
    return candidates[0].resolve() if candidates else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch public media for transcription")
    parser.add_argument("url", help="HTTP(S) media URL or public page URL")
    parser.add_argument("--output-dir", required=True, help="Directory for the downloaded media")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    parser.add_argument("--no-yt-dlp", action="store_true", help="Do not try yt-dlp when HTML extraction fails")
    args = parser.parse_args()

    parsed = urlparse(args.url)
    if parsed.scheme not in {"http", "https"}:
        fail("URL must use http:// or https://")
    outdir = Path(args.output_dir).expanduser().resolve()
    stem = safe_name(Path(parsed.path).stem or "media")

    direct = download_direct(args.url, outdir, args.timeout, args.max_bytes, stem=stem)
    if direct:
        print(direct)
        return 0

    try:
        with open_url(args.url, args.timeout) as response:
            page = read_limited(response, min(args.max_bytes, 50 * 1024 * 1024))
            candidates = extract_candidates(args.url, page)
    except Exception as exc:
        candidates = []
        log(f"warning: page fetch failed: {exc}")

    for index, candidate in enumerate(candidates, start=1):
        log(f"info: trying embedded media candidate {index}/{len(candidates)}")
        media = download_direct(candidate, outdir, args.timeout, args.max_bytes, stem="media")
        if media:
            print(media)
            return 0

    if not args.no_yt_dlp:
        media = yt_dlp_fallback(args.url, outdir, args.max_bytes)
        if media:
            print(media)
            return 0

    fail("could not locate an accessible public media file; upload the media or provide a direct media URL")
    return 2


if __name__ == "__main__":
    main()
