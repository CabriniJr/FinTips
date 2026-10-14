"""Gera os arquivos da identidade a partir da marca que já existe no app.

A marca não foi inventada aqui: ela é o `ic_launcher_foreground.xml` do APK —
um painel âmbar com o canto superior direito chanfrado, carregando FT vazado no
preto do fundo. O chanfro é o gesto, e é o mesmo dos painéis da interface.

A tipografia vai em `path`, não em `text`. SVG com `text` depende da fonte
existir na máquina de quem olha, e Barlow Condensed não está em lugar nenhum
por padrão — a assinatura sairia com uma fonte qualquer, diferente a cada
leitor. Letra desenhada renderiza igual em todo lugar, e o desenho geométrico é
o que a linguagem já pedia.
"""
import pathlib

PAPER, CARD, INK, INK3 = "#080808", "#0d0c0b", "#f1efe6", "#bdad99"
ACCENT, SIGNAL = "#ffa342", "#ff4b35"

# Grade da letra: altura 30, haste 6, largura 18 — condensada e pesada.
H, ST, W = 30, 6, 18

LETRAS = {
    "F": f"M0,0 H{W} V{ST} H{ST} V12 H{W-3} V18 H{ST} V{H} H0 Z",
    "I": f"M0,0 H{ST} V{H} H0 Z",
    "N": f"M0,{H} V0 H{ST} L12,18 V0 H{W} V{H} H12 L{ST},12 V{H} Z",
    "T": f"M0,0 H{W} V{ST} H12 V{H} H{ST} V{ST} H0 Z",
    "P": f"M0,0 H{W} V18 H{ST} V{H} H0 Z M{ST},{ST} H12 V12 H{ST} Z",
    "S": f"M0,0 H{W} V{ST} H{ST} V12 H{W} V{H} H0 V24 H12 V18 H0 Z",
}
LARG = {"I": ST, **{k: W for k in "FNTPS"}}


def palavra(texto: str, x: float, y: float, cor: str, esc: float, vao: float = 5) -> tuple[str, float]:
    partes, cx = [], x
    for ch in texto:
        partes.append(
            f'<path d="{LETRAS[ch]}" fill="{cor}" fill-rule="evenodd" '
            f'transform="translate({cx:.1f},{y:.1f}) scale({esc:.4f})"/>'
        )
        cx += (LARG[ch] + vao) * esc
    return "\n    ".join(partes), cx - vao * esc


def marca(tam: int, fundo: str) -> str:
    """O painel chanfrado com FT — os mesmos paths do ícone do Android."""
    k = tam / 108
    return (
        f'<g transform="scale({k:.5f})">'
        f'<path d="M24,24H72L84,36V84H24Z" fill="{ACCENT}"/>'
        f'<path d="M36,40H49V45H41V50H48V55H41V67H36Z" fill="{fundo}"/>'
        f'<path d="M53,40H72V45H65V67H60V45H53Z" fill="{fundo}"/>'
        f"</g>"
    )


def regua(x: float, y: float, larg: float, cor: str, passo: float = 7) -> str:
    """Régua de instrumento: o tique longo a cada cinco, como no app."""
    t = []
    n = 0
    cx = x
    while cx < x + larg:
        alt = 9 if n % 5 == 0 else 4.5
        t.append(f'<rect x="{cx:.1f}" y="{y:.1f}" width="1.6" height="{alt}" fill="{cor}"/>')
        cx += passo
        n += 1
    return "\n    ".join(t)


def assinatura(claro: bool) -> str:
    """Marca + palavra + linha de posicionamento, dentro do painel chanfrado.

    A altura do painel da marca é a mesma da caixa alta da palavra, e os dois
    alinham pelo topo: é o que faz a assinatura ler como uma peça só em vez de
    um ícone colado ao lado de um texto.
    """
    fundo = "#f1efe6" if claro else PAPER
    tinta = PAPER if claro else INK
    sec = "#6b6256" if claro else INK3
    L, A = 1200, 300
    TOPO, CAIXA = 86, 87                      # topo e altura da caixa alta
    esc = CAIXA / 30                          # a letra é desenhada em 30 de altura

    # O painel da marca ocupa 24..84 dentro da caixa de 108: escalar por essa
    # razão faz o painel — e não a caixa — ter a altura da caixa alta.
    k = CAIXA / 60
    tam = 108 * k
    mx, my = 112 - 24 * k, TOPO - 24 * k
    fim_marca = 112 + CAIXA

    x_palavra = fim_marca + 44
    wm, fim_palavra = palavra("FINTIPS", x_palavra, TOPO, tinta, esc)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {L} {A}" width="{L}" height="{A}" role="img" aria-label="FinTips — uma vida em perspectiva">
  <rect width="{L}" height="{A}" fill="{fundo}"/>
  <!-- O quadro repete o chanfro da marca. É o gesto do sistema: painel
       retangular com o canto superior direito cortado. -->
  <path d="M64,52 H1088 L1136,100 V248 H64 Z" fill="none" stroke="{SIGNAL}" stroke-width="3"/>
  <g transform="translate({mx:.1f},{my:.1f})">{marca(tam, fundo)}</g>
  {wm}
  <rect x="{x_palavra}" y="{TOPO + CAIXA + 13}" width="{fim_palavra - x_palavra:.0f}" height="3" fill="{ACCENT}"/>
  <text x="{x_palavra}" y="{TOPO + CAIXA + 45}" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="21" letter-spacing="5.5" fill="{sec}">UMA VIDA EM PERSPECTIVA</text>
  <g>
    {regua(x_palavra, TOPO + CAIXA + 58, 430, sec)}
  </g>
</svg>
"""


def so_marca() -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 108 108" width="108" height="108" role="img" aria-label="Marca do FinTips">
  <rect width="108" height="108" fill="{PAPER}"/>
  {marca(108, PAPER)}
</svg>
"""


def paleta() -> str:
    cores = [
        ("--paper", PAPER, "fundo"), ("--card", CARD, "painel"),
        ("--ink", INK, "texto"), ("--ink-3", INK3, "texto 2"),
        ("--accent", ACCENT, "ação"), ("--signal", SIGNAL, "identidade"),
        ("#a4ec8c", "#a4ec8c", "registrado"), ("#e9c56e", "#e9c56e", "atenção"),
        ("#ff9c8c", "#ff9c8c", "erro"),
    ]
    larg, alt, pad = 130, 150, 16
    L = pad + len(cores) * (larg + pad)
    bl = []
    for i, (nome, hexv, papel) in enumerate(cores):
        x = pad + i * (larg + pad)
        bl.append(f"""<g transform="translate({x},{pad})">
    <path d="M0,0 H{larg-18} L{larg},18 V{alt-44} H0 Z" fill="{hexv}" stroke="{INK3}" stroke-opacity=".25"/>
    <text x="0" y="{alt-24}" font-family="ui-monospace,monospace" font-size="13" fill="{INK}">{nome}</text>
    <text x="0" y="{alt-6}" font-family="ui-monospace,monospace" font-size="12" fill="{INK3}">{papel}</text>
  </g>""")
    corpo = "\n  ".join(bl)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {L} {alt+pad}" width="{L}" height="{alt+pad}" role="img" aria-label="Paleta do FinTips">
  <rect width="{L}" height="{alt+pad}" fill="{PAPER}"/>
  {corpo}
</svg>
"""


d = pathlib.Path("docs/identidade")
d.mkdir(parents=True, exist_ok=True)
(d / "marca.svg").write_text(so_marca(), encoding="utf-8")
(d / "assinatura.svg").write_text(assinatura(False), encoding="utf-8")
(d / "assinatura-clara.svg").write_text(assinatura(True), encoding="utf-8")
(d / "paleta.svg").write_text(paleta(), encoding="utf-8")
for f in sorted(d.iterdir()):
    print(f, f.stat().st_size, "bytes")

# Rode da raiz do repositório:  python3 scripts/gerar-identidade.py
