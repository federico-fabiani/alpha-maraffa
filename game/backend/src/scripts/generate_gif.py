"""
generate_gif.py

Takes a contact-sheet image (NxM grid of frames on a green-screen background)
and produces an animated GIF with transparency.

Usage:
    python -m scripts.generate_gif \
        --input  <contact_sheet.png> \
        --output <animation.gif>    \
        [--cols 3] [--rows 3]       \
        [--fps 8]                   \
        [--green-tolerance 60]      \
        [--white-tolerance 240]     \
        [--no-stabilize]            \
        [--loop 0]

Dependencies: Pillow
"""

from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path
from statistics import median

from PIL import Image


# ---------------------------------------------------------------------------
# Chroma-key helpers
# ---------------------------------------------------------------------------

def _is_green(r: int, g: int, b: int, tolerance: int) -> bool:
    """Return True when the pixel is 'green-screen' green."""
    return g > 100 and g - r > tolerance and g - b > tolerance


def remove_green_screen(frame: Image.Image, tolerance: int = 60) -> Image.Image:
    """Convert green-screen pixels to fully transparent.

    The returned image is RGBA; non-green pixels keep their original colour
    and are fully opaque.
    """
    rgba = frame.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size

    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if _is_green(r, g, b, tolerance):
                pixels[x, y] = (0, 0, 0, 0)

    return rgba


# ---------------------------------------------------------------------------
# White-border removal (BFS flood-fill from image edges)
# ---------------------------------------------------------------------------

def _is_near_white(r: int, g: int, b: int, threshold: int) -> bool:
    """Return True when the pixel is near-white (all channels >= threshold)."""
    return r >= threshold and g >= threshold and b >= threshold


def remove_white_border(frame: Image.Image, threshold: int = 240) -> Image.Image:
    """Remove near-white pixels connected to the image border.

    Uses a BFS flood-fill seeded from every border pixel that is already
    transparent or near-white. Only pixels reachable from the outer edge are
    made transparent, so internal white detail inside the subject is preserved.
    """
    rgba = frame.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size

    visited = [[False] * height for _ in range(width)]
    queue: deque[tuple[int, int]] = deque()

    def _seed(x: int, y: int) -> None:
        if not visited[x][y]:
            r, g, b, a = pixels[x, y]
            if a == 0 or _is_near_white(r, g, b, threshold):
                visited[x][y] = True
                queue.append((x, y))

    for x in range(width):
        _seed(x, 0)
        _seed(x, height - 1)
    for y in range(height):
        _seed(0, y)
        _seed(width - 1, y)

    while queue:
        cx, cy = queue.popleft()
        pixels[cx, cy] = (0, 0, 0, 0)
        for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
            if 0 <= nx < width and 0 <= ny < height and not visited[nx][ny]:
                r, g, b, a = pixels[nx, ny]
                if a == 0 or _is_near_white(r, g, b, threshold):
                    visited[nx][ny] = True
                    queue.append((nx, ny))

    return rgba


# ---------------------------------------------------------------------------
# Frame stabilization
# ---------------------------------------------------------------------------

def _alpha_bbox(frame: Image.Image) -> tuple[int, int, int, int] | None:
    """Return bounding box of non-transparent content (left, top, right, bottom)."""
    alpha = frame.getchannel("A")
    return alpha.getbbox()


def _alpha_centroid(frame: Image.Image) -> tuple[float, float] | None:
    """Return alpha-weighted centroid of visible content."""
    alpha = frame.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        return None

    left, top, right, bottom = bbox
    px = alpha.load()
    total_weight = 0
    sum_x = 0
    sum_y = 0
    for y in range(top, bottom):
        for x in range(left, right):
            a = px[x, y]
            if a > 0:
                total_weight += a
                sum_x += x * a
                sum_y += y * a

    if total_weight == 0:
        return None
    return (sum_x / total_weight, sum_y / total_weight)


def stabilize_frames(
    frames: list[Image.Image],
    smoothing: float = 0.60,
    max_shift: int = 14,
) -> list[Image.Image]:
    """Stabilize content across frames using robust centroid alignment.

    Strategy:
    1) compute alpha-weighted centroid for each frame;
    2) choose a robust target center via median of larger-area frames;
    3) clamp per-frame shifts and smooth them over time.
    """
    if not frames:
        return frames

    centers: list[tuple[float, float] | None] = []
    areas: list[int] = []
    for frame in frames:
        bbox = _alpha_bbox(frame)
        if bbox is None:
            centers.append(None)
            areas.append(0)
            continue

        centroid = _alpha_centroid(frame)
        centers.append(centroid)

        left, top, right, bottom = bbox
        areas.append((right - left) * (bottom - top))

    if all(c is None for c in centers):
        return frames

    max_area = max(areas)
    area_threshold = max_area * 0.60
    robust_centers = [c for c, a in zip(centers, areas) if c is not None and a >= area_threshold]
    if not robust_centers:
        robust_centers = [c for c in centers if c is not None]

    target_center = (
        median(c[0] for c in robust_centers),
        median(c[1] for c in robust_centers),
    )

    smoothing = min(max(smoothing, 0.0), 0.95)
    max_shift = max(0, max_shift)

    stabilized: list[Image.Image] = []
    width, height = frames[0].size
    prev_dx = 0.0
    prev_dy = 0.0
    for frame, center in zip(frames, centers):
        if center is None:
            raw_dx = prev_dx
            raw_dy = prev_dy
        else:
            raw_dx = target_center[0] - center[0]
            raw_dy = target_center[1] - center[1]

        raw_dx = max(-max_shift, min(max_shift, raw_dx))
        raw_dy = max(-max_shift, min(max_shift, raw_dy))

        smoothed_dx = (prev_dx * smoothing) + (raw_dx * (1.0 - smoothing))
        smoothed_dy = (prev_dy * smoothing) + (raw_dy * (1.0 - smoothing))
        prev_dx = smoothed_dx
        prev_dy = smoothed_dy

        dx = int(round(smoothed_dx))
        dy = int(round(smoothed_dy))

        shifted = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        shifted.paste(frame, (dx, dy), frame)
        stabilized.append(shifted)

    return stabilized


# ---------------------------------------------------------------------------
# Contact-sheet splitter
# ---------------------------------------------------------------------------

def split_contact_sheet(
    path: Path, cols: int, rows: int
) -> list[Image.Image]:
    """Slice a contact sheet into individual frame images."""
    sheet = Image.open(path)
    total_w, total_h = sheet.size
    frame_w = total_w // cols
    frame_h = total_h // rows

    frames: list[Image.Image] = []
    for row in range(rows):
        for col in range(cols):
            left   = col * frame_w
            upper  = row * frame_h
            right  = left + frame_w
            lower  = upper + frame_h
            frames.append(sheet.crop((left, upper, right, lower)))

    return frames


# ---------------------------------------------------------------------------
# GIF assembly
# ---------------------------------------------------------------------------

def frames_to_gif(
    frames: list[Image.Image],
    output: Path,
    fps: int = 8,
    loop: int = 0,
) -> None:
    """Save a list of RGBA frames as an animated GIF with transparency.

    GIF supports only 1-bit transparency (one palette index is transparent).
    We convert each RGBA frame to a palette image, reserving index 0 for the
    transparent colour, so the transparency is preserved correctly.
    """
    duration_ms = max(1, round(1000 / fps))

    gif_frames: list[Image.Image] = []
    for rgba in frames:
        converted = rgba.convert("P", palette=Image.Palette.ADAPTIVE, colors=255)
        gif_frames.append(converted)

    gif_frames[0].save(
        output,
        format="GIF",
        save_all=True,
        append_images=gif_frames[1:],
        duration=duration_ms,
        loop=loop,
        transparency=0,
        disposal=2,
        optimize=False,
    )
    print(f"Saved {len(gif_frames)}-frame GIF → {output}  ({duration_ms} ms/frame)")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a green-screen contact sheet to a transparent animated GIF."
    )
    parser.add_argument("--input",  "-i", required=True,  type=Path, help="Contact-sheet image")
    parser.add_argument("--output", "-o", required=True,  type=Path, help="Output GIF path")
    parser.add_argument("--cols",         default=3,       type=int,  help="Columns in contact sheet (default 3)")
    parser.add_argument("--rows",         default=3,       type=int,  help="Rows in contact sheet (default 3)")
    parser.add_argument("--fps",          default=8,       type=int,  help="Frames per second (default 8)")
    parser.add_argument("--loop",         default=0,       type=int,  help="Loop count, 0 = infinite (default 0)")
    parser.add_argument(
        "--no-stabilize",
        action="store_true",
        help="Disable frame stabilization (enabled by default).",
    )
    parser.add_argument(
        "--stabilize-smoothing",
        default=0.75,
        type=float,
        help="Temporal smoothing for stabilization in [0, 0.95] (default 0.75).",
    )
    parser.add_argument(
        "--stabilize-max-shift",
        default=12,
        type=int,
        help="Maximum pixel shift per axis for each frame (default 12).",
    )
    parser.add_argument(
        "--green-tolerance", "-t",
        default=60, type=int,
        dest="tolerance",
        help="Chroma-key sensitivity: higher = stricter green detection (default 60)",
    )
    parser.add_argument(
        "--white-tolerance", "-w",
        default=None, type=int,
        dest="white_tolerance",
        help=(
            "Remove near-white border pixels connected to the frame edge "
            "(0–255, e.g. 240). Omit to skip white-border removal."
        ),
    )
    args = parser.parse_args()

    print(f"Reading contact sheet: {args.input}  ({args.cols}×{args.rows} grid)")
    raw_frames = split_contact_sheet(args.input, args.cols, args.rows)
    print(f"  → {len(raw_frames)} frames, each {raw_frames[0].size[0]}×{raw_frames[0].size[1]} px")

    print(f"Removing green screen (tolerance={args.tolerance}) …")
    rgba_frames = [remove_green_screen(f, args.tolerance) for f in raw_frames]

    if args.white_tolerance is not None:
        print(f"Removing white border (threshold={args.white_tolerance}) …")
        rgba_frames = [remove_white_border(f, args.white_tolerance) for f in rgba_frames]

    if not args.no_stabilize:
        print("Stabilizing frame alignment …")
        rgba_frames = stabilize_frames(
            rgba_frames,
            smoothing=args.stabilize_smoothing,
            max_shift=args.stabilize_max_shift,
        )

    frames_to_gif(rgba_frames, args.output, fps=args.fps, loop=args.loop)


if __name__ == "__main__":
    main()
