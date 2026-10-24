#!/usr/bin/env python3
"""RafaLink CRM: um único comando para preparar e iniciar tudo.

    python start.py                 prepara o ambiente (só na 1ª vez) e abre o sistema no navegador
    python start.py --demo          também gera dados de demonstração (uma vez)
    python start.py --test          roda os testes automáticos e sai
    python start.py --dev           reinicia o servidor sozinho quando você edita o código
    python start.py --reset-db      apaga o banco local e recomeça do zero (pede confirmação)
    python start.py --port 8001     usa outra porta
    python start.py --no-browser    não abre o navegador

No Windows use `py start.py` se `python` não for encontrado; no Mac, `python3 start.py`.
"""
import argparse
import hashlib
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import venv
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
VENV = BACKEND / ".venv"
DATA = BACKEND / "data"
IS_WIN = os.name == "nt"
VENV_PY = VENV / ("Scripts/python.exe" if IS_WIN else "bin/python")


def say(msg: str) -> None:
    print(f"[rafalink] {msg}", flush=True)


def ensure_python() -> None:
    if sys.version_info < (3, 10):
        sys.exit(f"Precisa do Python 3.10 ou mais novo (este é o {sys.version.split()[0]}). Baixe em python.org.")


def ensure_venv(dev: bool) -> None:
    if not VENV_PY.exists():
        say("criando o ambiente virtual (só na primeira vez)...")
        venv.EnvBuilder(with_pip=True, clear=False).create(VENV)
    req = BACKEND / ("requirements-dev.txt" if dev else "requirements.txt")
    if not req.exists():
        sys.exit(f"Não achei {req}.")
    # requirements-dev.txt inclui o requirements.txt: junta os dois no cálculo da assinatura
    digest = hashlib.sha256(b"".join(p.read_bytes() for p in sorted({BACKEND / "requirements.txt", req}))).hexdigest()
    stamp = VENV / (".deps-dev" if dev else ".deps")
    if stamp.exists() and stamp.read_text() == digest:
        return
    say("instalando as dependências (pode levar um minuto)...")
    r = subprocess.run([str(VENV_PY), "-m", "pip", "install", "-q", "--disable-pip-version-check", "-r", str(req)])
    if r.returncode != 0:
        sys.exit("Falha ao instalar as dependências. Veja a mensagem acima (internet? pip desatualizado?).")
    stamp.write_text(digest)


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def is_rafalink(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/v1/health", timeout=2) as r:
            return b"rafalink-api" in r.read()
    except (urllib.error.URLError, OSError):
        return False


def reset_db() -> None:
    files = [p for p in DATA.glob("rafalink.db*")] if DATA.exists() else []
    if not files:
        say("não há banco para apagar.")
        return
    if input("Isso apaga TODOS os dados locais (usuários, leads, tudo). Digite SIM para confirmar: ").strip() != "SIM":
        sys.exit("Cancelado. Nada foi apagado.")
    for p in files:
        p.unlink()
    say("banco apagado. Ele será recriado com os dados de demonstração básicos.")


def run_tests(extra: list[str]) -> int:
    env = {**os.environ, "RAFALINK_NO_WORKER": "1"}
    return subprocess.run([str(VENV_PY), "-m", "pytest", *extra], cwd=BACKEND, env=env).returncode


def wait_until_up(port: int, proc: subprocess.Popen, seconds: int = 40) -> bool:
    for _ in range(seconds * 4):
        if proc.poll() is not None:
            return False
        if is_rafalink(port):
            return True
        time.sleep(0.25)
    return False


def main() -> None:
    ap = argparse.ArgumentParser(description="Prepara e inicia o RafaLink CRM.")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--dev", action="store_true", help="recarrega o servidor ao editar o código")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--demo", action="store_true", help="gera dados de demonstração (só se ainda não existirem)")
    ap.add_argument("--test", action="store_true", help="roda os testes e sai")
    ap.add_argument("--reset-db", action="store_true")
    args, pytest_args = ap.parse_known_args()

    ensure_python()
    ensure_venv(dev=args.test)
    if args.test:
        sys.exit(run_tests(pytest_args))
    if args.reset_db:
        reset_db()

    url = f"http://localhost:{args.port}/login.html"
    if port_in_use(args.port):
        if is_rafalink(args.port):
            say(f"o RafaLink já está rodando em {url}")
            if not args.no_browser:
                webbrowser.open(url)
            return
        sys.exit(f"A porta {args.port} está ocupada por outro programa. Use outra: python start.py --port {args.port + 1}")

    if args.demo:
        say("gerando dados de demonstração...")
        subprocess.run([str(VENV_PY), str(ROOT / "scripts" / "seed_demo.py")], check=False)

    cmd = [str(VENV_PY), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(args.port)]
    if args.dev:
        cmd.append("--reload")
    say("iniciando o servidor... (Ctrl+C para parar)")
    proc = subprocess.Popen(cmd, cwd=BACKEND)
    try:
        if not wait_until_up(args.port, proc):
            proc.terminate()
            sys.exit("O servidor não subiu. Leia a mensagem de erro acima.")
        say(f"pronto! Abra {url}")
        say("usuários: admin@rafalink.com / admin123  ·  gerente@rafalink.com / gerente123  ·  vendedor@rafalink.com / vendedor123")
        if not args.no_browser:
            webbrowser.open(url)
        proc.wait()
    except KeyboardInterrupt:
        say("encerrando...")
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()