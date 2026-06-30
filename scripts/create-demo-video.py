from __future__ import annotations

from pathlib import Path
from textwrap import wrap

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "media" / "demo-assets"
OUTPUT = ROOT / "media" / "nexus-resolve-demo.mp4"
WIDTH = 1280
HEIGHT = 720
FPS = 1


SEGMENTS = [
    (
        "0:00-0:20",
        "Problem: repetitive P3-P5 infrastructure tickets consume time, but unsafe automation can copy bad precedent.",
        "01-replay-start.png",
        20,
    ),
    (
        "0:20-0:45",
        "Trigger: the selector now covers Windows, Database, IAM, VPN, Linux, Firewall, Backup, Service Desk, AD, Command Centre, and Cloud.",
        "01-replay-start.png",
        25,
    ),
    (
        "0:45-1:20",
        "Evidence: each scenario retrieves its SOP and compares safe, unsafe, and escalation historical tickets.",
        "02-sop-history-warning.png",
        35,
    ),
    (
        "1:20-1:50",
        "Governance moment: SOP beats history, so the unsafe ticket that deleted active logs is blocked as precedent.",
        "02-sop-history-warning.png",
        30,
    ),
    (
        "1:50-2:30",
        "Plan: the action review and Live AI Proof strip show target resources, model source, safeguards, approval, and validation steps.",
        "03-plan-policy-approval.png",
        40,
    ),
    (
        "2:30-3:10",
        "Approval: local live mode pauses for human approval before any mock remediation can continue.",
        "05-live-approval-hold.png",
        40,
    ),
    (
        "3:10-3:45",
        "Mock execution: the approved flow changes only synthetic state and validates scenario-specific recovery metrics.",
        "06-live-resolved.png",
        35,
    ),
    (
        "3:45-4:30",
        "Close: RCA, metrics, audit trail, deep-dive API JSON, and audit packet hash prove policy-grounded remediation.",
        "04-replay-rca-metrics.png",
        45,
    ),
]


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in (
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ):
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


TITLE_FONT = load_font(34)
CAPTION_FONT = load_font(25)
META_FONT = load_font(19)


def fit_image(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGB")
    image.thumbnail((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    frame = Image.new("RGB", (WIDTH, HEIGHT), "#eef2f6")
    x = (WIDTH - image.width) // 2
    y = (HEIGHT - image.height) // 2
    frame.paste(image, (x, y))
    return frame


def draw_caption(frame: Image.Image, timecode: str, caption: str) -> Image.Image:
    image = frame.copy()
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rectangle((0, 0, WIDTH, 74), fill=(15, 23, 42, 232))
    draw.text((28, 18), "NEXUS-RESOLVE Demo", fill="#ffffff", font=TITLE_FONT)
    draw.text((1048, 25), timecode, fill="#bfdbfe", font=META_FONT)

    box_top = HEIGHT - 142
    draw.rectangle((0, box_top, WIDTH, HEIGHT), fill=(15, 23, 42, 226))
    draw.rectangle((0, box_top, 10, HEIGHT), fill=(31, 111, 235, 255))
    y = box_top + 22
    for line in wrap(caption, 88):
        draw.text((32, y), line, fill="#ffffff", font=CAPTION_FONT)
        y += 33
    draw.text(
        (32, HEIGHT - 32),
        "Policy-grounded. Approval-gated. Mock-only. Audit-ready.",
        fill="#a7f3d0",
        font=META_FONT,
    )
    return image


def main() -> None:
    missing = [name for _, _, name, _ in SEGMENTS if not (ASSETS / name).exists()]
    if missing:
        raise SystemExit(f"Missing screenshot assets: {', '.join(missing)}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    frames: list[np.ndarray] = []
    for timecode, caption, screenshot, seconds in SEGMENTS:
        base = fit_image(ASSETS / screenshot)
        frame = draw_caption(base, timecode, caption)
        frames.extend(np.asarray(frame) for _ in range(seconds))

    imageio.mimsave(
        OUTPUT,
        frames,
        fps=FPS,
        codec="libx264",
        quality=8,
        macro_block_size=16,
    )
    print(f"Wrote {OUTPUT}")
    print(f"Duration: {sum(segment[3] for segment in SEGMENTS)} seconds")


if __name__ == "__main__":
    main()
