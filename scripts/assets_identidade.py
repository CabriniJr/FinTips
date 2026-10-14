"""Exporta a identidade pública sem ler registros ou compilar o aplicativo.

Fontes locais viram contornos: nenhum SVG depende de fontes ou serviços remotos.
campanha.png é uma peça gerada separadamente, não uma saída deste script.
"""
from __future__ import annotations
import io
import math
from pathlib import Path
import cairosvg
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/identidade"
PAPER, CARD, INK, MUTED = "#080808", "#0d0c0b", "#f1efe6", "#bdad99"
AMBER, RED = "#ffa342", "#ff4b35"
FONTS = {weight: TTFont(ROOT / f"web/src/fonts/BarlowCondensed-{weight}.ttf")
         for weight in ("Black", "SemiBold")}


def lettering(value: str, x: float, top: float, height: float, color: str,
              weight: str = "SemiBold", tracking: float = 0) -> tuple[str, float]:
    """Posiciona pela altura de caixa alta, não pelo tamanho nominal da fonte."""
    font = FONTS[weight]
    scale = height / font["OS/2"].sCapHeight
    glyphs, cmap = font.getGlyphSet(), font.getBestCmap()
    pieces, cursor = [], x
    for char in value:
        name = cmap[ord(char)]
        pen = SVGPathPen(glyphs)
        glyphs[name].draw(pen)
        pieces.append(f'<path d="{pen.getCommands()}" fill="{color}" '
                      f'transform="translate({cursor:.3f},{top + height:.3f}) '
                      f'scale({scale:.6f}, {-scale:.6f})"/>')
        cursor += font["hmtx"][name][0] * scale + tracking
    return "".join(pieces), cursor - tracking


def symbol(x: float, y: float, size: float, color: str = AMBER) -> str:
    # Mesmos contornos do Android, normalizados de 24..84 para 0..60.
    # FT é vazado de verdade, inclusive nas versões transparentes.
    path = ("M0 0H48L60 12V60H0Z "
            "M12 16H25V21H17V26H24V31H17V43H12Z "
            "M29 16H48V21H41V43H36V21H29Z")
    return (f'<path d="{path}" fill="{color}" fill-rule="evenodd" '
            f'transform="translate({x},{y}) scale({size / 60:.6f})"/>')


def lockup(x: float, y: float, height: float, color: str = INK,
           mono: bool = False) -> str:
    name, _ = lettering("FINTIPS", x + height * 1.28, y, height, color, "Black", 1)
    return symbol(x, y, height, color if mono else AMBER) + name


def svg(width: int, height: int, body: str, label: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title">'
            f'<title id="title">{label}</title>{body}</svg>\n').replace("><", ">\n  <")


def ruler(x: int, y: int, width: int, color: str = MUTED) -> str:
    return "".join(f'<path d="M{x+i} {y}v{12 if i % 40 == 0 else 5}" '
                   f'stroke="{color}" stroke-width="1"/>' for i in range(0, width, 8))


def instruments(cx: int, cy: int, radius: int) -> str:
    """Arcos decorativos, sem scores ou telemetria inventados."""
    pieces = []
    for index, factor in enumerate((1, .83, .63, .43)):
        r = radius * factor
        pieces.append(f'<circle cx="{cx}" cy="{cy}" r="{r:.2f}" fill="none" '
                      f'stroke="{AMBER if index % 2 else RED}" '
                      f'stroke-width="{14 if index in (0, 2) else 3}" '
                      f'stroke-dasharray="{r * 1.16:.2f} {r * .32:.2f}" '
                      f'transform="rotate({index * 37 - 90} {cx} {cy})"/>')
    for angle in range(0, 360, 5):
        theta = math.radians(angle)
        inner, outer = radius + 18, radius + (33 if angle % 30 == 0 else 25)
        coords = [cx + inner * math.cos(theta), cy + inner * math.sin(theta),
                  cx + outer * math.cos(theta), cy + outer * math.sin(theta)]
        pieces.append(f'<path d="M{coords[0]:.2f} {coords[1]:.2f}L{coords[2]:.2f} '
                      f'{coords[3]:.2f}" stroke="{MUTED}" stroke-width="1"/>')
    pieces.append(f'<path d="M{cx-radius-42} {cy}H{cx+radius+42} '
                  f'M{cx} {cy-radius-42}V{cy+radius+42}" stroke="{MUTED}" '
                  'stroke-width="1" opacity=".4"/>')
    pieces.append(symbol(cx - 24, cy - 24, 48))
    return "".join(pieces)


def banner(width: int, height: int, social: bool = False) -> str:
    k = width / 1600
    logical_h = height / k
    h = 108 if social else 128
    y = 125 if social else 112
    body = f'<rect width="{width}" height="{height}" fill="{PAPER}"/>'
    art = (f'<path d="M48 48H1496L1552 104V{logical_h-48:.1f}H48Z" '
           f'fill="none" stroke="{RED}" stroke-width="2"/>'
           f'<rect x="48" y="48" width="7" height="70" fill="{RED}"/>')
    art += lockup(96, y, h)
    title, _ = lettering("UMA VIDA EM PERSPECTIVA", 98, y + h + 32, 22, MUTED, tracking=2)
    art += title
    if social:
        for line, ty in (("SEUS PLANOS.", 334), ("SEU CONTEXTO.", 406)):
            text, _ = lettering(line, 96, ty, 53, INK, "Black", 1)
            art += text
    art += ruler(96, int(logical_h - 150), 530)
    bottom, _ = lettering("VIDA  /  PLANOS  /  CONTEXTO", 96, logical_h - 107, 17, AMBER, tracking=2)
    art += bottom
    radius = 190 if social else min(150, int(logical_h / 2 - 96))
    art += instruments(1230, int(logical_h / 2), radius)
    art += f'<path d="M900 90V{logical_h-90:.1f}" stroke="{RED}" stroke-width="1" opacity=".6"/>'
    body += f'<g transform="scale({k:.5f})">{art}</g>'
    return svg(width, height, body, "FinTips — uma vida em perspectiva; arte de marca")


def signature(light: bool) -> str:
    bg, fg = (INK, PAPER) if light else (PAPER, INK)
    body = f'<rect width="1200" height="300" fill="{bg}"/>'
    body += f'<path d="M40 40H1104L1160 96V260H40Z" fill="none" stroke="{RED}" stroke-width="2"/>'
    body += lockup(96, 82, 96, fg)
    text, _ = lettering("UMA VIDA EM PERSPECTIVA", 222, 205, 19, fg, tracking=2)
    return svg(1200, 300, body + text, "FinTips — uma vida em perspectiva")


def palette() -> str:
    values = [("PAPER", PAPER), ("CARD", CARD), ("INK", INK), ("INK 3", MUTED),
              ("ACCENT", AMBER), ("SIGNAL", RED), ("REGISTRO", "#a4ec8c"),
              ("ATENÇÃO", "#e9c56e"), ("ERRO", "#ff9c8c")]
    body = '<rect width="1330" height="180" fill="#080808"/>'
    for i, (name, color) in enumerate(values):
        x = 16 + i * 146
        body += f'<path d="M{x} 16h110l18 18v84H{x}Z" fill="{color}" stroke="{MUTED}" stroke-width=".5"/>'
        for value, y, size in ((name, 133, 12), (color.upper(), 154, 10)):
            text, _ = lettering(value, x, y, size, INK, tracking=1)
            body += text
    return svg(1330, 180, body, "Paleta da identidade FinTips")


def export(name: str, source: str, png: bool = True) -> None:
    (OUT / f"{name}.svg").write_text(source, encoding="utf-8")
    if png:
        cairosvg.svg2png(bytestring=source.encode(), write_to=str(OUT / f"{name}.png"))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    export("simbolo", svg(512, 512, symbol(32, 32, 448), "Símbolo FT do FinTips"))
    avatar = svg(1024, 1024, '<rect width="1024" height="1024" fill="#080808"/>'
                 + symbol(176, 176, 672), "Ícone FinTips — FT âmbar sobre preto")
    export("icone", avatar, png=False)
    export("marca", svg(108, 108, '<rect width="108" height="108" fill="#080808"/>'
                          + symbol(24, 24, 60), "Marca do FinTips"), png=False)
    for size in (1024, 512, 256, 128, 64):
        cairosvg.svg2png(bytestring=avatar.encode(), output_width=size, output_height=size,
                        write_to=str(OUT / f"icone-{size}.png"))
    favicon = svg(64, 64, '<rect width="64" height="64" fill="#080808"/>'
                  + symbol(8, 8, 48), "Favicon FinTips")
    export("favicon", favicon, png=False)
    for size in (16, 32):
        cairosvg.svg2png(bytestring=favicon.encode(), output_width=size, output_height=size,
                        write_to=str(OUT / f"favicon-{size}.png"))
    ico = cairosvg.svg2png(bytestring=favicon.encode())
    Image.open(io.BytesIO(ico)).save(OUT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    for name, color, mono in (("logo-escuro", INK, False), ("logo-claro", PAPER, False),
                              ("logo-mono-branco", "#ffffff", True), ("logo-mono-preto", "#000000", True)):
        export(name, svg(700, 180, lockup(24, 30, 120, color, mono), "Logo FinTips; fundo transparente"))
    export("assinatura", signature(False), png=False)
    export("assinatura-clara", signature(True), png=False)
    export("paleta", palette(), png=False)
    export("banner-readme", banner(1600, 600))
    export("banner-social", banner(1280, 640, social=True))
    export("banner-opengraph", banner(1200, 630, social=True))
    export("banner-release", banner(1600, 480))
    print(f"Identidade exportada em {OUT.relative_to(ROOT)} (SVG, PNG e ICO)")
