#!/usr/bin/env python3
"""Render provenance-preserving CLI evidence for the Solidity Copilot smoke harness."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
SCREENSHOTS = PUBLIC / "screenshots"
GIF = PUBLIC / "gif" / "preview.gif"
SHORT = PUBLIC / "demos" / "short" / "short.mp4"
DETAILED = PUBLIC / "demos" / "detailed" / "detailed.mp4"
MEDIA = PUBLIC / "media.json"
WIDTH, HEIGHT = 1280, 720

COMMANDS = [
    {
        "filename": "01-smoke-report.png",
        "label": "Prompt-to-Solidity smoke report",
        "argv": ["sed", "-n", "1,18p", "smoke/REPORT.md"],
        "command": ["sed", "-n", "1,18p", "smoke/REPORT.md"],
        "expected": lambda output: "Prompt-to-Solidity smoke report" in output,
    },
    {
        "filename": "02-counter-spec.png",
        "label": "Structured Counter specification",
        "argv": ["sed", "-n", "1,40p", "smoke/prompts/01_counter.txt"],
        "command": ["sed", "-n", "1,40p", "smoke/prompts/01_counter.txt"],
        "expected": lambda output: "Return Solidity source only" in output,
    },
    {
        "filename": "03-output-format-failure.png",
        "label": "Raw model output format failure",
        "argv": ["sed", "-n", "1,40p", "smoke/raw/01_counter.raw.txt"],
        "command": ["sed", "-n", "1,40p", "smoke/raw/01_counter.raw.txt"],
        "expected": lambda output: output.startswith("```solidity"),
    },
    {
        "filename": "04-normalized-compile-candidate.png",
        "label": "Normalized compile candidate",
        "argv": ["sed", "-n", "1,80p", "smoke/contracts/Counter.sol"],
        "command": ["sed", "-n", "1,80p", "smoke/contracts/Counter.sol"],
        "expected": lambda output: "contract Counter" in output and "```" not in output,
    },
    {
        "filename": "05-counter-smoke-tests.png",
        "label": "Counter behavioral smoke tests",
        "argv": ["forge", "test", "--threads", "1", "--match-contract", "CounterSmokeTest"],
        "command": ["forge", "test", "--threads", "1", "--match-contract", "CounterSmokeTest"],
        "expected": lambda output: "3 tests passed, 0 failed" in output,
    },
    {
        "filename": "06-piggy-bank-smoke-tests.png",
        "label": "PiggyBank access-control smoke tests",
        "argv": ["forge", "test", "--threads", "1", "--match-contract", "PiggyBankSmokeTest"],
        "command": ["forge", "test", "--threads", "1", "--match-contract", "PiggyBankSmokeTest"],
        "expected": lambda output: "5 tests passed, 0 failed" in output,
    },
    {
        "filename": "07-simple-token-smoke-tests.png",
        "label": "SimpleToken behavior and revert tests",
        "argv": ["forge", "test", "--threads", "1", "--match-contract", "SimpleTokenSmokeTest"],
        "command": ["forge", "test", "--threads", "1", "--match-contract", "SimpleTokenSmokeTest"],
        "expected": lambda output: "4 tests passed, 0 failed" in output,
    },
    {
        "filename": "08-full-smoke-suite.png",
        "label": "Full Foundry smoke suite",
        "argv": ["forge", "test", "--threads", "1"],
        "command": ["forge", "test", "--threads", "1"],
        "expected": lambda output: "12 tests passed, 0 failed" in output,
        "displayTail": 12,
    },
]


def run_command(command: list[str]) -> str:
    env = os.environ.copy()
    forge_dir = str(Path.home() / ".foundry" / "bin")
    env["PATH"] = f"{forge_dir}:{env['PATH']}"
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, env=env)
    output = (result.stdout + result.stderr).strip()
    if result.returncode != 0:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}\n{output}")
    output = re.sub(
        r"finished in [0-9.]+(?:ms|µs) \([^)]*\)",
        "finished in <elapsed>",
        output,
    )
    return re.sub(
        r"(Ran \d+ test suites? in )[^(]+\([^)]*\)(:)",
        r"\1<elapsed>\2",
        output,
    )


def font(size: int, bold: bool = False):
    candidates = (
        ("/System/Library/Fonts/Menlo.ttc", 1 if bold else 0),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 0),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 0),
    )
    for path, index in candidates:
        try:
            return ImageFont.truetype(path, size=size, index=index)
        except OSError:
            continue
    return ImageFont.load_default()


def wrap_terminal_text(draw: ImageDraw.ImageDraw, text: str, max_width: int, body_font: Any) -> list[str]:
    lines: list[str] = []
    for raw_line in text.splitlines() or [""]:
        line = raw_line.expandtabs(2)
        if not line:
            lines.append("")
            continue
        current = ""
        for char in line:
            candidate = current + char
            if draw.textlength(candidate, font=body_font) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = char
        lines.append(current)
    return lines


def render_frame(label: str, argv: list[str], transcript: str, destination: Path) -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), "#0b1020")
    draw = ImageDraw.Draw(image)
    title_font = font(24, bold=True)
    command_font = font(20, bold=False)
    body_font = font(18, bold=False)

    draw.rounded_rectangle((24, 20, WIDTH - 24, HEIGHT - 20), radius=18, fill="#10192f", outline="#253655", width=2)
    draw.rounded_rectangle((25, 21, WIDTH - 25, 70), radius=16, fill="#16233e")
    draw.ellipse((49, 38, 61, 50), fill="#ff5f56")
    draw.ellipse((70, 38, 82, 50), fill="#ffbd2e")
    draw.ellipse((91, 38, 103, 50), fill="#27c93f")
    draw.text((126, 31), f"Solidity Copilot · {label}", font=title_font, fill="#e6edf7")

    command = "$ " + " ".join(argv)
    draw.text((54, 94), command, font=command_font, fill="#7ee787")
    wrapped = wrap_terminal_text(draw, transcript, WIDTH - 108, body_font)
    y = 136
    max_y = HEIGHT - 58
    for line in wrapped:
        if y + 25 > max_y:
            draw.text((54, y), "… output clipped for this frame", font=body_font, fill="#9fb3d1")
            break
        color = "#d9e2f2"
        if line.startswith("[PASS]"):
            color = "#7ee787"
        elif "failed" in line.lower() or "revert" in line.lower():
            color = "#ffbd2e"
        draw.text((54, y), line, font=body_font, fill=color)
        y += 25
    draw.text(
        (54, HEIGHT - 46),
        "Deterministic replay of asserted local CLI output. Experimental code, not deployment evidence.",
        font=font(14),
        fill="#9fb3d1",
    )
    image.save(destination, format="PNG", optimize=True)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def existing_youtube_url(section: str) -> str | None:
    if not MEDIA.exists():
        return None
    try:
        value = json.loads(MEDIA.read_text(encoding="utf-8")).get(section, {}).get("youtubeUrl")
    except (json.JSONDecodeError, OSError):
        return None
    return value if isinstance(value, str) and value else None


def create_video(frame_paths: list[Path], output: Path, seconds_per_frame: int) -> None:
    concat = output.with_suffix(".concat.txt")
    concat.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for frame in frame_paths:
        lines.append(f"file '{frame.as_posix()}'")
        lines.append(f"duration {seconds_per_frame}")
    lines.append(f"file '{frame_paths[-1].as_posix()}'")
    concat.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
                "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-movflags", "+faststart", str(output),
            ],
            check=True,
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
    finally:
        concat.unlink(missing_ok=True)


def main() -> None:
    for directory in (SCREENSHOTS, GIF.parent, SHORT.parent, DETAILED.parent):
        directory.mkdir(parents=True, exist_ok=True)

    states = []
    frame_paths = []
    for state in COMMANDS:
        transcript = run_command(state["command"])
        if not state["expected"](transcript):
            raise RuntimeError(f"assertion failed for {state['filename']}")
        output = SCREENSHOTS / state["filename"]
        display_transcript = transcript
        if "displayTail" in state:
            display_transcript = "\n".join(transcript.splitlines()[-state["displayTail"]:])
        render_frame(state["label"], state["argv"], display_transcript, output)
        frame_paths.append(output)
        states.append(
            {
                "label": state["label"],
                "filename": state["filename"],
                "returncode": 0,
                "artifactSha256": sha256(output),
                "transcriptSha256": hashlib.sha256(transcript.encode()).hexdigest(),
                "argv": state["argv"],
            }
        )

    curated_frame_paths = frame_paths[1:]
    frames = [Image.open(path).convert("P", palette=Image.Palette.ADAPTIVE) for path in curated_frame_paths]
    frames[0].save(GIF, save_all=True, append_images=frames[1:], duration=1500, loop=0, disposal=2)
    for frame in frames:
        frame.close()

    create_video(curated_frame_paths, SHORT, seconds_per_frame=10)
    create_video(curated_frame_paths, DETAILED, seconds_per_frame=27)

    short_youtube_url = existing_youtube_url("shortClip")
    long_youtube_url = existing_youtube_url("longClip")
    MEDIA.write_text(
        json.dumps(
            {
                "captureProvenance": {
                    "method": "deterministic rendered terminal-style replay of asserted local CLI output",
                    "servedUi": "local CLI",
                    "transcriptNormalization": [
                        "Foundry elapsed-time fields are replaced with <elapsed> before rendering and hashing.",
                    ],
                    "modelCallsMade": False,
                    "privateKeyAccessed": False,
                    "broadcastAttempted": False,
                    "states": states,
                },
                "shortClip": {
                    "localPath": "public/demos/short/short.mp4",
                    "youtubeUrl": short_youtube_url,
                },
                "longClip": {
                    "localPath": "public/demos/detailed/detailed.mp4",
                    "youtubeUrl": long_youtube_url,
                },
            },
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"screenshots": len(frame_paths), "gif": str(GIF.relative_to(ROOT)), "media": str(MEDIA.relative_to(ROOT))}))


if __name__ == "__main__":
    main()
