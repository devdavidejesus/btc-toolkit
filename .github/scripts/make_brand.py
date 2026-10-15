"""Regenerate the btc-toolkit brand assets from code.

    assets/icon.svg            the Bitcoin logo (public domain), 64 x 64
    assets/logo.svg            README header for light backgrounds (also PyPI)
    assets/logo-dark.svg       README header for GitHub's dark theme
    assets/social-preview.png  1280 x 640 banner (GitHub Settings > Social preview)

The wordmark is JetBrains Mono ExtraBold and the copy IBM Plex Sans, both under
the SIL Open Font License. They are downloaded from their upstream
repositories at pinned commits and checked against a SHA-256 before use; the
SVGs carry the wordmark as outlines, so they look the same without the fonts.
Nothing is drawn by hand: run it again after changing the copy below.

    pip install pillow fonttools
    python .github/scripts/make_brand.py
"""

from __future__ import annotations

import hashlib
import re
import tempfile
import urllib.request
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "assets"

ORANGE = "#F7931A"
INK = "#0D1117"
PANEL = "#161B22"
LINE = "#30363D"
SLATE = "#8B949E"
WHITE = "#FFFFFF"
SNOW = "#E6EDF3"

_JB = "https://raw.githubusercontent.com/JetBrains/JetBrainsMono/19371302b95d218af43299bce79ddbddd0bc364d/fonts/ttf/"
_PLEX = ("https://raw.githubusercontent.com/IBM/plex/39276912b05f700ee1dd491950c35d8697214208/"
         "packages/plex-sans/fonts/complete/ttf/")
FONTS = {
    "mono-extrabold": (_JB + "JetBrainsMono-ExtraBold.ttf",
                       "ee43f7507a07ed15c4bf6211d5cc78fa0bacca58e7afbc170f4b1e38a5d0cde4"),
    "mono": (_JB + "JetBrainsMono-Regular.ttf",
             "e6fd0d7e91550b3ed2b735d4312474362c4716edc4fc0577a0f61ed782d5aed1"),
    "sans-medium": (_PLEX + "IBMPlexSans-Medium.ttf",
                    "331c8639d7598b2cde62a911a71db195e30cb655cd6bdf2e324a7e984955f907"),
    "sans": (_PLEX + "IBMPlexSans-Regular.ttf",
             "975dcda37d80f038dcd143c22e33ca2d97a0cc5a929aace1c749153b0fe1afa5"),
}

# The Bitcoin logo's "B", in a 64 x 64 box (public domain artwork).
BITCOIN_B = (
    "M46.1 27.4c.6-4.2-2.6-6.5-7-8l1.4-5.7-3.5-.9-1.4 5.5c-.9-.2-1.9-.4-2.8-.7l1.4-5.5-3.5-.9-1.4 5.7"
    "c-.8-.2-1.5-.3-2.2-.5l0 0-4.8-1.2-.9 3.7s2.6.6 2.5.6c1.4.4 1.7 1.3 1.6 2l-1.6 6.5c.1 0 .2.1.3.1"
    "l-.3-.1-2.3 9.1c-.2.4-.6 1.1-1.6.8 0 0-2.5-.6-2.5-.6l-1.7 4 4.5 1.1c.8.2 1.7.4 2.5.7l-1.4 5.8 3.5.9"
    " 1.4-5.7c1 .3 1.9.5 2.8.7l-1.4 5.7 3.5.9 1.4-5.8c5.9 1.1 10.4.7 12.3-4.7 1.5-4.3-.1-6.8-3.2-8.4"
    " 2.3-.5 4-2.1 4.4-5.2zm-7.9 11.1c-1.1 4.3-8.3 2-10.7 1.4l1.9-7.6c2.3.6 9.9 1.7 8.8 6.2zm1.1-11.2"
    "c-1 3.9-7 1.9-9 1.4l1.7-6.9c2 .5 8.3 1.4 7.3 5.5z"
)

WORDMARK = "btc-toolkit"
HEADLINE = [[("Read and verify Bitcoin", WHITE)], [("from your ", WHITE), ("terminal.", ORANGE)]]
FEATURES = ["OP_RETURN & inscriptions · raw-tx decoding", "offline address checks · Merkle-proof verify"]
INSTALL = "pipx install btc-toolkit"
ALSO = "also uv · brew · pip"


def font_file(name: str) -> Path:
    url, sha = FONTS[name]
    path = Path(tempfile.gettempdir()) / "btc-toolkit-brand-fonts" / url.rsplit("/", 1)[1]
    if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
        path.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=60) as resp:  # noqa: S310 (fixed https URL)
            data = resp.read()
        if hashlib.sha256(data).hexdigest() != sha:
            raise SystemExit(f"{url}: SHA-256 mismatch, refusing to use it")
        path.write_bytes(data)
    return path


# --- the Bitcoin logo as polygons (for the PNG) ---------------------------------

_ARGS = {"m": 2, "l": 2, "c": 6, "s": 4, "z": 0}


def logo_polygons(d: str = BITCOIN_B, steps: int = 24) -> list[list[tuple[float, float]]]:
    """Flatten the logo's path (M m l c s z only) into one polygon per subpath."""
    tokens = re.findall(r"[MmLlCcSsZz]|-?(?:\d+\.\d*|\.\d+|\d+)", d)
    polys: list[list[tuple[float, float]]] = []
    x = y = sx = sy = 0.0
    last_ctrl: tuple[float, float] | None = None
    i, cmd = 0, ""
    while i < len(tokens):
        if tokens[i].isalpha():
            cmd = tokens[i]
            i += 1
            if cmd in "Zz":
                x, y = sx, sy
                last_ctrl = None
                continue
        n = _ARGS[cmd.lower()]
        a = [float(t) for t in tokens[i:i + n]]
        i += n
        rel = cmd.islower()
        ox, oy = (x, y) if rel else (0.0, 0.0)
        if cmd in "Mm":
            x, y = ox + a[0], oy + a[1]
            sx, sy = x, y
            polys.append([(x, y)])
            cmd = "l" if rel else "L"  # extra pairs after a moveto are linetos
            last_ctrl = None
        elif cmd in "Ll":
            x, y = ox + a[0], oy + a[1]
            polys[-1].append((x, y))
            last_ctrl = None
        else:
            if cmd in "Cc":
                c1 = (ox + a[0], oy + a[1])
                c2, end = (ox + a[2], oy + a[3]), (ox + a[4], oy + a[5])
            else:  # Ss: the first control point mirrors the previous curve's second
                c1 = (2 * x - last_ctrl[0], 2 * y - last_ctrl[1]) if last_ctrl else (x, y)
                c2, end = (ox + a[0], oy + a[1]), (ox + a[2], oy + a[3])
            p0 = (x, y)
            for k in range(1, steps + 1):
                t = k / steps
                u = 1 - t
                polys[-1].append((
                    u**3 * p0[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t**3 * end[0],
                    u**3 * p0[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t**3 * end[1],
                ))
            last_ctrl = c2
            x, y = end
    return polys


def draw_logo(draw: ImageDraw.ImageDraw, left: float, top: float, size: float) -> None:
    k = size / 64
    draw.ellipse((left, top, left + size, top + size), fill=ORANGE)
    outer, *holes = logo_polygons()
    draw.polygon([(left + px * k, top + py * k) for px, py in outer], fill=WHITE)
    for hole in holes:
        draw.polygon([(left + px * k, top + py * k) for px, py in hole], fill=ORANGE)


# --- the social preview -------------------------------------------------------------

def social_preview(scale: int = 2) -> Image.Image:
    """The 1280 x 640 banner, drawn at `scale`x and downsampled for smooth edges."""
    s = scale
    W, H = 1280, 640
    img = Image.new("RGB", (W * s, H * s), INK)
    d = ImageDraw.Draw(img)

    def font(name: str, px: float) -> ImageFont.FreeTypeFont:
        return ImageFont.truetype(str(font_file(name)), round(px * s))

    def baseline(top: float, line_h: float, f: ImageFont.FreeTypeFont) -> float:
        """Where CSS puts the baseline of a line box `line_h` tall starting at `top`."""
        asc, desc = f.getmetrics()
        return top * s + (line_h * s - (asc + desc)) / 2 + asc

    def text(x: float, y_base: float, runs: list[tuple[str, str]], f: ImageFont.FreeTypeFont,
             tracking: float = 0.0) -> float:
        cx = x * s
        for chunk, color in runs:
            if tracking:
                for ch in chunk:
                    d.text((cx, y_base), ch, font=f, fill=color, anchor="ls")
                    cx += f.getlength(ch) + tracking * s
            else:
                d.text((cx, y_base), chunk, font=f, fill=color, anchor="ls")
                cx += f.getlength(chunk)
        return cx / s - x

    wordmark, headline, body = font("mono-extrabold", 76), font("sans-medium", 40), font("sans", 21)
    mono, small = font("mono", 22), font("mono", 17)
    pill_h = (sum(mono.getmetrics()) / s) + 20
    blocks = 76 + 22 + 2 * 48 + 22 + 2 * 31.5 + 30 + pill_h
    top = (H - blocks) / 2

    coin = 248
    draw_logo(d, 88 * s, (H - coin) / 2 * s, coin * s)

    x = 88 + coin + 72
    y = top
    text(x, baseline(y, 76, wordmark), [(WORDMARK, WHITE)], wordmark, tracking=-0.03 * 76)
    y += 76 + 22
    for line in HEADLINE:
        text(x, baseline(y, 48, headline), line, headline)
        y += 48
    y += 22
    for feature in FEATURES:
        text(x, baseline(y, 31.5, body), [(feature, SLATE)], body)
        y += 31.5
    y += 30
    cmd_w = mono.getlength("$ " + INSTALL) / s
    d.rounded_rectangle((x * s, y * s, (x + cmd_w + 32) * s, (y + pill_h) * s), radius=10 * s,
                        fill=PANEL, outline=LINE, width=s)
    text(x + 16, baseline(y + 10, pill_h - 20, mono), [("$ ", ORANGE), (INSTALL, WHITE)], mono)
    also_x = x + cmd_w + 32 + 18
    also_h = sum(small.getmetrics()) / s
    text(also_x, baseline(y + (pill_h - also_h) / 2, also_h, small), [(ALSO, SLATE)], small)
    right = also_x + small.getlength(ALSO) / s
    if right > W - 56:
        raise SystemExit(f"social preview: text ends at x={right:.0f}, past the 56 px margin")
    return img.resize((W, H), Image.Resampling.LANCZOS)


# --- SVGs ---------------------------------------------------------------------------

def outline(text: str, font: TTFont, px: float, x: float, base: float, tracking: float) -> tuple[str, float]:
    """`text` as one SVG path in `font` at `px`, left edge `x`, baseline `base`; returns (d, width)."""
    k = px / font["head"].unitsPerEm
    cmap, glyphs, hmtx = font.getBestCmap(), font.getGlyphSet(), font["hmtx"]
    parts, cx = [], x
    for i, ch in enumerate(text):
        name = cmap[ord(ch)]
        pen = SVGPathPen(glyphs)
        glyphs[name].draw(TransformPen(pen, (k, 0, 0, -k, cx, base)))
        parts.append(pen.getCommands())
        cx += hmtx[name][0] * k + (tracking if i < len(text) - 1 else 0)
    return " ".join(p for p in parts if p), cx - x


def _num(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


def logo_svg(wordmark_fill: str) -> str:
    font = TTFont(str(font_file("mono-extrabold")))
    pad, coin, gap, px = 2, 88, 22, 58
    hhea = font["hhea"]
    em = font["head"].unitsPerEm
    content = (hhea.ascent - hhea.descent) / em * px
    base = pad + coin / 2 - content / 2 + hhea.ascent / em * px
    path, width = outline(WORDMARK, font, px, pad + coin + gap, base, -0.03 * px)
    path = re.sub(r"-?\d+\.\d+", lambda m: _num(float(m.group())), path)
    w, h = pad + coin + gap + width + pad, coin + 2 * pad
    k = coin / 64
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_num(w)}" height="{_num(h)}" '
        f'viewBox="0 0 {_num(w)} {_num(h)}" role="img" aria-label="btc-toolkit">'
        f'<circle cx="{_num(pad + coin / 2)}" cy="{_num(pad + coin / 2)}" r="{_num(coin / 2)}" fill="{ORANGE}"/>'
        f'<path transform="translate({pad} {pad}) scale({_num(k)})" d="{BITCOIN_B}" fill="{WHITE}"/>'
        f'<path d="{path}" fill="{wordmark_fill}"/></svg>\n'
    )


ICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64" role="img" '
    f'aria-label="btc-toolkit"><circle cx="32" cy="32" r="32" fill="{ORANGE}"/>'
    f'<path d="{BITCOIN_B}" fill="{WHITE}"/></svg>\n'
)


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    (ASSETS / "icon.svg").write_text(ICON_SVG, encoding="utf-8")
    (ASSETS / "logo.svg").write_text(logo_svg(INK), encoding="utf-8")
    (ASSETS / "logo-dark.svg").write_text(logo_svg(SNOW), encoding="utf-8")
    social_preview().save(ASSETS / "social-preview.png", optimize=True)
    for name in ("icon.svg", "logo.svg", "logo-dark.svg", "social-preview.png"):
        print(f"wrote assets/{name}")


if __name__ == "__main__":
    main()
