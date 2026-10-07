"""Re-record the README demos from real btc-toolkit output.

Runs the btc-toolkit on your PATH inside a pseudo-terminal, so it prints its
real colours, and renders what it printed into:

    assets/demo.gif  typed `opreturn` session (the Liquid negotiation)
    assets/demo.png  `tx` screenshot

Nothing in the images is typed by hand: every character comes from the live
command against mainnet. Run it after each release (POSIX only, needs
network access to mempool.space and Pillow, which is not a project dependency):

    pip install pillow
    python .github/scripts/make_demo.py
"""

from __future__ import annotations

import os
import pty
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]

# Liquid Network negotiation: first contact, then the 2-byte reply that ended it.
GIF_TXIDS = [
    "c103de95817b43f2df635ec6f35ff126ca26a7c6d20570c4b01866b2b3e69a19",
    "d7e8837c51cc625c2c6365d371d376b035209fa01434d4933971d6428d6d6d52",
]
PNG_TXID = "f4ac7abcb689df30ec5e8d829733622f389ca91367c47b319bc582e653cd8cab"

BG = (255, 255, 255)
FG = (0, 0, 0)
DIM = (128, 128, 128)
ANSI = {  # macOS Terminal "Basic" palette
    30: (0, 0, 0), 31: (153, 0, 0), 32: (0, 166, 0), 33: (153, 152, 0),
    34: (0, 0, 178), 35: (178, 0, 178), 36: (0, 166, 178), 37: (191, 191, 191),
}
FONTS = [  # (path, regular index, bold path, bold index)
    ("/System/Library/Fonts/Menlo.ttc", 0, "/System/Library/Fonts/Menlo.ttc", 1),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 0,
     "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 0),
]

SGR = re.compile(r"\x1b\[([0-9;]*)m")
OTHER_ESCAPES = re.compile(r"\x1b\[[0-9;?]*[A-Za-ln-z]")

Style = tuple  # (fg or None, bold, dim)
Line = list  # [(text, Style), ...]


def run(args: list[str]) -> str:
    """Run btc-toolkit in a pty and return exactly what it printed."""
    exe = shutil.which("btc-toolkit")
    if exe is None:
        sys.exit("btc-toolkit not found on PATH")
    env = {k: v for k, v in os.environ.items() if k != "NO_COLOR"}
    master, slave = pty.openpty()
    proc = subprocess.Popen([exe, *args], stdin=subprocess.DEVNULL, stdout=slave, stderr=slave, env=env)
    os.close(slave)
    chunks = []
    while True:
        try:
            data = os.read(master, 65536)
        except OSError:  # EIO once the child closes the pty (Linux)
            break
        if not data:
            break
        chunks.append(data)
    os.close(master)
    if proc.wait() != 0:
        sys.exit(f"btc-toolkit {' '.join(args)} exited with {proc.returncode}")
    return b"".join(chunks).decode("utf-8").replace("\r\n", "\n")


def parse(text: str) -> list[Line]:
    """Split ANSI-coloured text into lines of (text, style) runs."""
    text = OTHER_ESCAPES.sub("", text)
    fg, bold, dim = None, False, False
    lines: list[Line] = [[]]
    pos = 0
    for m in [*SGR.finditer(text), None]:
        chunk = text[pos:m.start() if m else len(text)]
        for i, part in enumerate(chunk.split("\n")):
            if i:
                lines.append([])
            if part:
                lines[-1].append((part, (fg, bold, dim)))
        if m is None:
            break
        pos = m.end()
        for code in [int(c) if c else 0 for c in m.group(1).split(";")]:
            if code == 0:
                fg, bold, dim = None, False, False
            elif code == 1:
                bold = True
            elif code == 2:
                dim = True
            elif code == 22:
                bold = dim = False
            elif code in ANSI:
                fg = ANSI[code]
            elif code == 39:
                fg = None
    return lines


def strip_blank_edges(lines: list[Line]) -> list[Line]:
    def blank(line: Line) -> bool:
        return not "".join(t for t, _ in line).strip()

    while lines and blank(lines[0]):
        lines = lines[1:]
    while lines and blank(lines[-1]):
        lines = lines[:-1]
    return lines


def width(line: Line) -> int:
    return sum(len(t) for t, _ in line)


class Painter:
    def __init__(self, size: int, cols: int, rows: int) -> None:
        for path, idx, bold_path, bold_idx in FONTS:
            if Path(path).exists() and Path(bold_path).exists():
                self.font = ImageFont.truetype(path, size, index=idx)
                self.bold = ImageFont.truetype(bold_path, size, index=bold_idx)
                break
        else:
            sys.exit("no monospace font found (Menlo or DejaVu Sans Mono)")
        self.cell = self.font.getlength("M")
        self.line_h = round(size * 1.375)
        self.pad = round(size * 0.65)
        self.size = (round(self.cell * cols) + 2 * self.pad, self.line_h * rows + 2 * self.pad)

    def paint(self, lines: list[Line], cursor: tuple[int, int] | None = None) -> Image.Image:
        img = Image.new("RGB", self.size, BG)
        draw = ImageDraw.Draw(img)
        for row, line in enumerate(lines):
            col = 0
            for text, (fg, bold, dim) in line:
                color = DIM if dim and fg is None else (fg or FG)
                font = self.bold if bold else self.font
                for ch in text:  # cell by cell keeps box-drawing glyphs on the grid
                    draw.text((self.pad + col * self.cell, self.pad + row * self.line_h), ch, font=font, fill=color)
                    col += 1
        if cursor is not None:
            row, col = cursor
            x, y = self.pad + col * self.cell, self.pad + row * self.line_h
            draw.rectangle([x, y + 1, x + self.cell - 1, y + self.line_h - 2], fill=FG)
        return img


def make_gif(path: Path) -> None:
    sessions = []
    for txid in GIF_TXIDS:
        command = f"btc-toolkit opreturn {txid}"
        output = parse(run(["opreturn", txid]))
        while output and not width(output[-1]):
            output.pop()
        sessions.append((command, output))

    cols = max(max(len(c) + 2, *(width(line) for line in out)) for c, out in sessions) + 1
    rows = max(len(out) + 3 for _, out in sessions)
    painter = Painter(16, cols, rows)

    frames: list[Image.Image] = []
    durations: list[int] = []
    rhythm = [50, 40, 60, 40, 50, 30]
    for command, output in sessions:
        typed = "$ "
        for i, ch in enumerate(command):
            typed += ch
            frames.append(painter.paint([[(typed, (None, False, False))]], cursor=(0, len(typed))))
            durations.append(rhythm[i % len(rhythm)])
        durations[-1] = 550  # beat before Enter
        screen = [[("$ " + command, (None, False, False))], *output, [], [("$ ", (None, False, False))]]
        frames.append(painter.paint(screen[:-2], cursor=None))
        durations.append(800)  # network round trip
        frames.append(painter.paint(screen, cursor=(len(screen) - 1, 2)))
        durations.append(3500)

    palette = [f.convert("P", palette=Image.Palette.ADAPTIVE, colors=64) for f in frames]
    palette[0].save(path, save_all=True, append_images=palette[1:], duration=durations, loop=0, optimize=True)
    print(f"wrote {path.relative_to(ROOT)}: {painter.size[0]}x{painter.size[1]}, {len(frames)} frames")


def make_png(path: Path) -> None:
    output = strip_blank_edges(parse(run(["tx", PNG_TXID])))
    painter = Painter(26, max(width(line) for line in output) + 1, len(output))
    painter.paint(output).save(path, optimize=True)
    print(f"wrote {path.relative_to(ROOT)}: {painter.size[0]}x{painter.size[1]}")


def main() -> None:
    print(run(["--version"]).strip())
    make_gif(ROOT / "assets" / "demo.gif")
    make_png(ROOT / "assets" / "demo.png")


if __name__ == "__main__":
    main()
