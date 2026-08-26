---
name: video-transcription
description: Turn a public video or audio URL, a Threads/Instagram/YouTube link, or a local media file into a timestamped verbatim transcript and Markdown/plain-text deliverables. Use when a user asks for a transcript, captions, subtitles, speech-to-text, or a word-for-word record of video/audio content.
license: MIT
metadata:
  author: Joker
  version: "0.1.0"
---

# Video Transcription

## Runtime requirements

Remote URLs require network access. Media preparation requires Python 3.9+ and `ffmpeg`. A speech-to-text backend must be available through the host agent, a local CLI, or a user-provided command.

## Purpose

Follow this workflow whenever the user gives a media URL or local media file and requests a transcript. Keep the workflow independent of any particular LLM vendor: use the host agent's available browser, shell, audio, or speech-to-text capability, then use the bundled scripts for deterministic media preparation and output formatting.

This Skill standardizes the **procedure and file contract**. It cannot give an LLM an audio capability that the host environment does not provide. If no speech-to-text backend is available, prepare the audio, report the exact path, and ask the user to provide or enable a backend instead of inventing content.

## When to use

Use this Skill for requests such as:

- “把這個影片做成逐字稿。”
- “幫我轉錄這個 Threads／Instagram／YouTube 影片。”
- “從這個 MP4 產生含時間碼的字幕或逐字紀錄。”
- “將這段錄音轉成文字，保留原話。”

Do not use it when the user only wants a summary, translation, fact check, or content analysis and does not need the spoken words transcribed.

## Workflow decision tree

1. **Classify the input.** Treat an existing local media file as local input. Treat `http://` and `https://` as remote input. Do not treat arbitrary text as a URL.
2. **Acquire the media.** Run `scripts/fetch_media.py` for a remote URL. For a local file, use the existing path directly or copy it into a working directory.
3. **Handle access barriers.** If the page requires login, CAPTCHA, a paywall, private access, DRM, or an authenticated browser session, do not bypass it. Use the user's authenticated browser when available, or ask the user to upload the media file or provide an accessible direct media URL.
4. **Extract audio.** Run `scripts/extract_audio.py` with the acquired media path. The default output is a mono 16 kHz WAV suitable for most speech-to-text systems.
5. **Select a speech-to-text backend.** Prefer the host agent's native audio/transcription capability. Otherwise use an available local CLI such as `manus-speech-to-text`, `whisper`, `faster-whisper`, `whisper.cpp`, or a user-supplied command. Never assume a vendor-specific API or model exists.
6. **Preserve raw results.** Save the backend's raw response before cleaning. If it produces timestamps, retain them. If it produces SRT, VTT, JSON, or timestamped plain text, pass that file to `scripts/render_transcript.py`.
7. **Render deliverables.** Produce both `transcript.md` and `transcript.txt` in the output directory. Include the source URL or local filename, duration when known, language when known, timestamped text, and a continuous-text section in Markdown.
8. **Quality-check.** Compare the rendered transcript with the raw response. Keep the source language and original wording by default. Mark genuinely unintelligible portions as `[聽不清楚]` or the equivalent in the transcript language; do not guess.
9. **Deliver.** Attach the Markdown transcript first and the plain-text transcript second. Mention any access limitation, backend limitation, or uncertain words briefly.

## Standard commands

Run commands from the Skill root so the relative script paths resolve correctly.

```bash
# Remote URL
python scripts/fetch_media.py "https://example.com/video" --output-dir work
python scripts/extract_audio.py work/media.mp4 --output-dir work

# Local media file
python scripts/extract_audio.py "/path/to/input.mp4" --output-dir work

# Use a host-provided or configured STT backend, then render its output
python scripts/render_transcript.py work/raw_transcript.txt \
  --output-dir work/output \
  --source-url "https://example.com/video"
```

The fetch script prints exactly one absolute media path on success. The audio script prints exactly one absolute audio path on success. Diagnostic messages go to stderr so an agent can safely capture stdout as a path.

## Speech-to-text backend selection

Use this priority order, adapting to the host environment:

1. Use a native audio or speech-to-text tool exposed by the host agent.
2. Use a preinstalled local command. `manus-speech-to-text` is a valid backend when present, but it is optional and must not be made a hard dependency of this Skill.
3. Use a user-configured command through `scripts/run_stt_command.py`. The command must contain `{audio}` and must write the transcript to stdout or to `{output}`.
4. Use a local open-source Whisper-compatible backend if the environment already has one and the user permits model downloads.
5. If none is available, stop after audio extraction and tell the user exactly what is missing. Do not claim that transcription succeeded.

Example for a custom backend:

```bash
python scripts/run_stt_command.py \
  --audio work/audio.wav \
  --output work/raw_transcript.txt \
  --command 'your-stt-cli --input {audio}'
```

The custom command is parsed without a shell, so `{audio}` and `{output}` are substituted as individual arguments. Do not put secrets in the command line; use the backend's normal environment configuration.

## Output contract

Always produce the following files when transcription succeeds:

| File | Required content |
| --- | --- |
| `transcript.md` | Source metadata, timestamped transcript, continuous transcript, and a short quality note. |
| `transcript.txt` | Plain-text timestamped transcript suitable for copying or downstream processing. |
| `raw_transcript.*` | The unmodified backend output, when the backend provides a file. |

Use the user's requested language and script. If the user asks for Traditional Chinese but the speech is Mandarin in Simplified Chinese, convert the characters only after preserving the raw transcript, and state that the character form was normalized. Do not silently translate spoken content into another language.

Default timestamp format is `[MM:SS.s–MM:SS.s]` for clips under one hour and `[HH:MM:SS.s–HH:MM:SS.s]` for longer media. Keep speaker labels when the backend supplies them. If the backend has no timestamps, state `時間碼：來源未提供` rather than fabricating timing.

## Verbatim and correction policy

“逐字稿” means preserve the spoken sequence, repetitions, colloquialisms, and meaningful fillers unless the user asks for an edited or cleaned transcript. Correct only obvious segmentation artifacts introduced by line wrapping. Do not silently repair a possible proper noun or technical term. If context suggests a recognition error, keep the recognized wording and add a short note such as `（辨識結果，疑似：……）` only when necessary.

Do not turn a transcript into a summary. Do not add claims that are not audible. Do not infer missing words from subtitles, comments, or the page caption without labeling them as external text.

## Platform and access handling

The acquisition script supports direct media URLs, common public page embeds, and `yt-dlp` when it is installed. It also attempts to locate public MP4/WebM URLs in page HTML, which is useful for public Threads and Instagram pages. This is a best-effort fallback, not an authentication bypass.

For a page that only loads media inside a logged-in browser, use the browser session to inspect or download the media when the user has authorized that access. If the browser shows a login wall, CAPTCHA, private post, or DRM-protected stream, ask the user to take over for login or upload the media. Never execute downloaded files or page-provided scripts; only treat the downloaded object as media input.

## Failure handling

Stop with a clear error when the URL is invalid, the media cannot be downloaded, `ffmpeg` is unavailable, or the selected transcription backend fails. Preserve partial artifacts in the working directory and report their paths. Retry a failed network operation at most twice, then switch to an alternative acquisition method or ask the user for the media file.

If a remote URL returns HTML instead of media and no embedded media URL can be found, report that the page was reached but the media was not accessible. Do not output a guessed transcript based on the title, caption, comments, or thumbnail.

## Bundled resources

- `scripts/fetch_media.py`: Download a direct media URL or discover a public embedded media URL.
- `scripts/extract_audio.py`: Extract mono 16 kHz WAV audio through `ffmpeg`.
- `scripts/run_stt_command.py`: Adapt any user-configured CLI that accepts an audio path.
- `scripts/render_transcript.py`: Normalize timestamped text, SRT, VTT, or common JSON into Markdown and plain text.
- `tests/`: Offline tests for transcript rendering and command substitution.

## Portability notes

This folder follows the open Agent Skills layout: one `SKILL.md` plus optional scripts and tests. Keep the root `SKILL.md` as the source of truth. Agents that support Agent Skills can install the folder in their personal or project Skill directory; agents that do not have automatic Skill discovery can still read this file and execute the same standard commands.

For Claude Code, install or symlink this folder under `~/.claude/skills/video-transcription/`. For Codex, install or symlink it under the Codex Skills directory used by the local version, commonly `~/.agents/skills/video-transcription/`. For another agent, place the folder in that agent's Skill directory or explicitly include `SKILL.md` in its instructions. The scripts themselves have no LLM-vendor dependency.

## References

- [Agent Skills specification](https://agentskills.io/specification)
- [Claude Code Skills documentation](https://code.claude.com/docs/en/skills)
- [OpenAI Skills documentation](https://developers.openai.com/cookbook/examples/skills_in_api)
