"""Captura a interface embarcada em perfis temporários, com dados inventados.

Veja docs/media/README.md. Nunca lê config.yaml, data/ ou backups pessoais.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import mimetypes
from pathlib import Path
import subprocess
import tempfile
from urllib.parse import unquote, urlparse
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
WEB, OUTPUT = ROOT / "fintips/web", ROOT / "docs/media"
ORIGIN, DAY = "https://appassets.androidplatform.net", "2026-01-14"
LIFE = {
    "schema_version": 1,
    "tarefas": [dict(id=str(i), titulo=title, atributo=area, inicio=DAY, repetir=True)
                for i, (title, area) in enumerate([
                    ("Ler o próximo capítulo", "INT"), ("Caminhar por 20 minutos", "AGI"),
                    ("Revisar o plano da semana", "FOC"), ("Organizar a reserva", "OURO")])],
    "registros": [{"tarefaId": "1", "dia": DAY, "origem": "usuario"},
                  {"tarefaId": "2", "dia": DAY, "origem": "usuario"}],
    "planos": [{"id": "demo-plano", "titulo": "Aprender um novo idioma", "atributo": "INT",
                "porque": "Abrir espaço para novas conversas.",
                "proximoPasso": "Reservar duas sessões nesta semana", "prazo": "", "concluido": False}],
    "medidas": [],
}
READING = {"schema_version": 1, "livros": [{
    "id": "demo-livro", "titulo": "Horizontes de exemplo", "fonte": "librera",
    "chave": "Horizontes de exemplo.epub", "perfil": "demonstração", "prazo": "", "dias_semana": 3,
    "observacoes": [dict(dia=day, progresso_bp=progress,
                         tempo_ms=int(datetime.fromisoformat(day + "T12:00:00+00:00").timestamp()*1000),
                         origem="librera") for day, progress in [
                             ("2026-01-08", 1200), ("2026-01-11", 2000), (DAY, 3500)]]}]}


def serve(route):
    url = urlparse(route.request.url)
    if url.scheme != "https" or url.netloc != "appassets.androidplatform.net":
        return route.abort()
    path = (WEB / unquote(url.path.lstrip("/") or "index.html")).resolve()
    if not path.is_relative_to(WEB.resolve()) or not path.is_file():
        return route.fulfill(status=403, body="Bloqueado")
    mime = {".js": "text/javascript", ".css": "text/css", ".ttf": "font/ttf"}.get(
        path.suffix, mimetypes.guess_type(path.name)[0] or "application/octet-stream")
    route.fulfill(status=200, content_type=mime, body=path.read_bytes())


def hold(page, seconds=1):
    page.wait_for_timeout(seconds * 1000)


def scroll(page, y):
    page.evaluate("y => window.scrollTo({top:y,behavior:'smooth'})", y)
    hold(page, .7)


def daily(page):
    page.screenshot(path=str(OUTPUT / "hoje.png"))
    hold(page, 1.3)
    scroll(page, 260)
    page.get_by_role("checkbox", name="Ler o próximo capítulo", exact=False).check()
    hold(page, .8)
    page.get_by_role("checkbox", name="Organizar a reserva", exact=False).check()
    hold(page, .8)
    scroll(page, 0)
    page.get_by_label("100% das tarefas concluídas", exact=True).wait_for()
    hold(page, 1.3)
    nav = page.get_by_role("navigation", name="Navegação principal")
    nav.get_by_role("link", name="Planos", exact=True).click()
    page.get_by_role("heading", name="Planos", exact=True, level=1).wait_for()
    hold(page, 1.3)
    page.screenshot(path=str(OUTPUT / "planos.png"))
    nav.get_by_role("link", name="Hoje", exact=True).click()
    page.get_by_role("heading", name="Hoje", exact=True, level=1).wait_for()
    hold(page, 1.1)


def reading(page):
    y = page.locator(".reading-card").evaluate("e => e.getBoundingClientRect().top + scrollY - 18")
    scroll(page, y)
    page.screenshot(path=str(OUTPUT / "leitura.png"))
    hold(page, 1.4)
    page.get_by_role("button", name="Registrar posição", exact=True).click()
    hold(page, .9)
    page.get_by_label("Porcentagem de leitura", exact=True).fill("42")
    hold(page, .7)
    page.get_by_role("button", name="Salvar posição", exact=False).click()
    page.get_by_role("dialog").wait_for(state="hidden")
    hold(page, 1.1)
    page.get_by_role("button", name="Ajustar ritmo", exact=False).click()
    hold(page, .9)
    page.get_by_role("dialog").get_by_role("combobox").select_option("4")
    page.get_by_label("Prazo de leitura", exact=True).fill("2026-02-10")
    hold(page, .7)
    page.get_by_role("dialog").get_by_role("button", name="Ajustar ritmo", exact=False).click()
    page.get_by_role("dialog").wait_for(state="hidden")
    scroll(page, y + 250)
    hold(page, 1.6)


def record(browser, temporary, name, route_name, actions):
    context = browser.new_context(viewport={"width": 390, "height": 844}, locale="pt-BR",
                                  timezone_id="America/Sao_Paulo", color_scheme="dark",
                                  reduced_motion="no-preference", record_video_dir=temporary,
                                  record_video_size={"width": 390, "height": 844})
    context.route("**/*", serve)
    context.add_init_script("if (!sessionStorage.getItem('fintips.demo')) {"
                            "localStorage.setItem('fintips.vida.v1', " + json.dumps(json.dumps(LIFE)) + ");"
                            "localStorage.setItem('fintips.leitura.v1', " + json.dumps(json.dumps(READING)) + ");"
                            "sessionStorage.setItem('fintips.demo','1'); }")
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.clock.set_fixed_time(datetime(2026, 1, 14, 12, tzinfo=timezone.utc))
    page.goto(ORIGIN + "/#" + route_name)
    page.locator(".route-view.is-enter:not([inert])").wait_for()
    page.evaluate("document.fonts.ready")
    hold(page, .5)
    video = page.video
    actions(page)
    assert not errors, errors
    context.close()
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "0.6", "-i", str(video.path()),
                    "-filter_complex", "fps=12,split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];"
                    "[b][p]paletteuse=dither=none:diff_mode=rectangle", "-loop", "0",
                    str(OUTPUT / f"{name}.gif")], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", help="Caminho opcional de Chromium já instalado")
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p, tempfile.TemporaryDirectory(prefix="fintips-demo-") as tmp:
        browser = p.chromium.launch(executable_path=args.browser, args=["--no-sandbox"])
        try:
            record(browser, tmp, "hoje", "hoje", daily)
            record(browser, tmp, "leitura", "vida/INT", reading)
        finally:
            browser.close()
    assets = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in sorted(WEB.rglob("*")) if path.is_file()}
    (OUTPUT / "capture-info.json").write_text(json.dumps({
        "interface": "WebView embarcada; captura no Chromium, não em aparelho Android",
        "dados": "fictícios; cenário exclusivo em perfil temporário", "data_do_cenario": DAY,
        "viewport": [390, 844], "fps_gif": 12, "assets_embarcados_sha256": assets,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Demonstrações públicas gravadas em docs/media; nenhum workspace pessoal foi lido.")


if __name__ == "__main__":
    main()
