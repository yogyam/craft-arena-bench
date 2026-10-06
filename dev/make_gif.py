"""Renders one recorded match as an animated GIF, top-down, for the README.

    python dev/make_gif.py replays/sumo-2hz/<pair>.replays.json.gz --match 1 --out docs/images/replay.gif [--speed 2] [--every 2]

Same view as the browser replay viewer: arena, two bots with facing lines, health bars, intents. Pillow only.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

A_COLOR, B_COLOR = (42, 120, 214), (214, 99, 42)
BG, FLOOR, WALL, GRID, INK, MUTED = (249, 249, 247), (232, 231, 223), (154, 153, 143), (216, 215, 207), (11, 11, 11), (82, 81, 78)


def font(size: int):
    for name in ("/System/Library/Fonts/SFNS.ttf", "/System/Library/Fonts/Helvetica.ttc", "/Library/Fonts/Arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render(doc: dict, replay: dict, width: int, every: int, speed: float, hold_frames: int) -> list[Image.Image]:
    arena = doc["arena"]
    min_x, min_z, max_x, max_z = arena["min"][0], arena["min"][2], arena["max"][0] + 1, arena["max"][2] + 1
    pad = 2.5
    scale = (width - 20) / (max_x - min_x + 2 * pad)
    height = int((max_z - min_z + 2 * pad) * scale) + 70
    ox, oz = 10 + pad * scale, 50 + pad * scale
    X = lambda x: ox + (x - min_x) * scale  # noqa: E731
    Z = lambda z: oz + (z - min_z) * scale  # noqa: E731
    f_big, f_small = font(int(scale * 1.1) + 6), font(max(11, int(scale * 0.55) + 6))
    names = (replay["meta"]["a"], replay["meta"]["b"])
    frames = replay["frames"]
    out = []
    last = frames[-1]
    for idx in range(0, len(frames), every):
        f = frames[idx]
        im = Image.new("RGB", (width, height), BG)
        d = ImageDraw.Draw(im)
        d.rectangle(
            [X(min_x), Z(min_z), X(max_x), Z(max_z)], fill=FLOOR, outline=WALL, width=4 if arena["kind"] == "walls" else 2
        )
        for gx in range(int(min_x), int(max_x) + 1, 4):
            d.line([X(gx), Z(min_z), X(gx), Z(max_z)], fill=GRID)
        for gz in range(int(min_z), int(max_z) + 1, 4):
            d.line([X(min_z), Z(gz), X(max_x), Z(gz)], fill=GRID) if False else d.line(
                [X(min_x), Z(gz), X(max_x), Z(gz)], fill=GRID
            )
        title = f"{doc['mode'].replace('_', ' ')} · {doc['tier_hz']} Hz · seed {replay['meta']['seed']} · {f[0] / 20:.1f} s"
        d.text((12, 12), title, fill=INK, font=f_big)
        for i, color in ((0, A_COLOR), (1, B_COLOR)):
            b = f[1 + i]
            x, z, yaw, health = X(b[0]), Z(b[2]), math.radians(b[3]), b[5]
            fallen = b[1] < arena["min"][1] - 1
            col = tuple(int(c * 0.5 + 128) for c in color) if fallen else color
            r = 0.4 * scale
            d.ellipse([x - r, z - r, x + r, z + r], fill=col)
            d.line([x, z, x - math.sin(yaw) * 0.9 * scale, z + math.cos(yaw) * 0.9 * scale], fill=col, width=3)
            bw, bh = 1.6 * scale, 0.22 * scale
            d.rectangle([x - bw / 2, z - 0.8 * scale - bh, x + bw / 2, z - 0.8 * scale], fill=(204, 204, 204))
            hc = (46, 158, 68) if health > 10 else (217, 162, 27) if health > 5 else (194, 59, 42)
            d.rectangle(
                [x - bw / 2, z - 0.8 * scale - bh, x - bw / 2 + bw * max(0, min(1, health / 20)), z - 0.8 * scale], fill=hc
            )
            label = f"{names[i]} · {f[3][i]}"
            tw = d.textlength(label, font=f_small)
            d.text((x - tw / 2, z + 0.9 * scale), label, fill=INK, font=f_small)
        if f is last or idx + every >= len(frames):
            w = replay["outcome"]["winner"]
            msg = "draw" if w is None else f"{names[0] if w == 'a' else names[1]} wins by {replay['outcome']['reason']}"
            tw = d.textlength(msg, font=f_big)
            d.rectangle(
                [width / 2 - tw / 2 - 12, height - 44, width / 2 + tw / 2 + 12, height - 10], fill=(252, 252, 251), outline=MUTED
            )
            d.text((width / 2 - tw / 2, height - 38), msg, fill=INK, font=f_big)
        out.append(im)
    out += [out[-1]] * hold_frames
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("replays_file")
    p.add_argument("--match", type=int, default=0, help="Index within the file's recorded matches")
    p.add_argument("--out", default="docs/images/replay.gif")
    p.add_argument("--width", type=int, default=720)
    p.add_argument("--every", type=int, default=2, help="Render every n-th tick (2 = 10 frames per second of play)")
    p.add_argument("--speed", type=float, default=1.0, help="Playback speed")
    p.add_argument("--start", type=float, default=0.0, help="Seconds of play to skip at the start")
    p.add_argument("--end", type=float, default=None, help="Seconds of play to stop at")
    p.add_argument("--names", default=None, help="Labels for A and B, comma-separated (default: the recorded names)")
    args = p.parse_args()
    doc = json.load(gzip.open(args.replays_file, "rt"))
    if "replays" not in doc:
        # A single match as `craft-arena-bench play` writes it: wrap it the way the service's pair files do.
        import sys

        sys.path.insert(0, "src")
        from craft_arena_bench.arena import make_arena

        arena = make_arena(doc["meta"]["mode"])
        bounds = arena.platform if doc["meta"]["mode"] == "sumo" else arena.bounds
        doc = {
            "mode": doc["meta"]["mode"],
            "tier_hz": doc["meta"]["tier_hz"],
            "arena": {
                "min": list(bounds.min),
                "max": list(bounds.max),
                "kind": "platform" if doc["meta"]["mode"] == "sumo" else "walls",
            },
            "replays": [doc],
        }
    replay = doc["replays"][args.match]
    frames = [f for f in replay["frames"] if f[0] >= args.start * 20 and (args.end is None or f[0] <= args.end * 20)]
    replay = dict(replay, frames=frames)
    if args.names:
        a_name, b_name = (n.strip() for n in args.names.split(",", 1))
        replay["meta"] = dict(replay["meta"], a=a_name, b=b_name)
    images = render(doc, replay, args.width, args.every, args.speed, hold_frames=int(10 / args.every))
    duration = int(1000 * args.every / 20 / args.speed)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    images[0].save(args.out, save_all=True, append_images=images[1:], duration=duration, loop=0, optimize=True)
    print(
        f"{args.out}: {len(images)} frames, {Path(args.out).stat().st_size / 1024:.0f} KB, {len(frames) / 20:.1f} s of play at {args.speed}x"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
