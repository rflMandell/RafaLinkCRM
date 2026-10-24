"""Etapa 9: roda o motor de automação em segundo plano, a cada 60 segundos."""
import threading
import time

from .automation import run_all
from .database import get_conn

_started = False


def start_worker(interval: int = 60) -> None:
    global _started
    if _started:
        return
    _started = True

    def loop():
        while True:
            time.sleep(interval)
            try:
                conn = get_conn()
                try:
                    run_all(conn)
                finally:
                    conn.close()
            except Exception as exc:       # o worker nunca pode morrer
                print("[automação] erro no ciclo:", exc)

    threading.Thread(target=loop, daemon=True, name="automation-worker").start()