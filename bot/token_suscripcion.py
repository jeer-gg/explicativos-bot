"""Genera el token de tu suscripción de Claude sin computadora.

GitHub ejecuta `claude setup-token` por ti y la conversación pasa por Telegram:
1. El bot te manda el enlace de autorización.
2. Lo abres, autorizas con tu cuenta de Claude y le respondes al bot con el código.
3. El bot te devuelve el token por Telegram para que lo guardes como secreto.

El token nunca se escribe en los registros de GitHub (que son públicos).

Uso: python -m bot.token_suscripcion
"""
import fcntl
import os
import pty
import re
import select
import struct
import subprocess
import termios
import time

import requests

from .claude import instalar_claude_code

ANSI = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b[@-_]")
URL = re.compile(r"https://[^\s\"'<>]*oauth[^\s\"'<>]*")
TOKEN = re.compile(r"sk-ant-oat[0-9A-Za-z_\-]+")
ESPERA_CODIGO = 7 * 60  # segundos para que respondas con el código


def _tg(metodo: str, **datos):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    r = requests.post(f"https://api.telegram.org/bot{token}/{metodo}", data=datos, timeout=60)
    r.raise_for_status()
    return r.json().get("result")


def _mensaje(texto: str):
    _tg("sendMessage", chat_id=os.environ["TELEGRAM_CHAT_ID"], text=texto,
        disable_web_page_preview="true")


def _ultimo_update() -> int:
    res = _tg("getUpdates", offset=-1, timeout=0)
    return res[-1]["update_id"] if res else 0


def _esperar_codigo(desde: int) -> str | None:
    chat = str(os.environ["TELEGRAM_CHAT_ID"])
    limite = time.time() + ESPERA_CODIGO
    offset = desde + 1
    while time.time() < limite:
        for up in _tg("getUpdates", offset=offset, timeout=20,
                      allowed_updates='["message"]') or []:
            offset = up["update_id"] + 1
            msg = up.get("message") or {}
            if str(msg.get("chat", {}).get("id")) == chat and msg.get("text"):
                texto = msg["text"].strip()
                if not texto.startswith("/"):
                    return texto
    return None


def _sin_secretos(texto: str, codigo: str) -> str:
    limpio = ANSI.sub("", texto).replace("\r", "")
    for parte in {codigo, *codigo.split("#")}:
        if len(parte) > 6:
            limpio = limpio.replace(parte, "[CODIGO]")
    limpio = TOKEN.sub("[TOKEN]", limpio)
    lineas = [l.rstrip() for l in limpio.splitlines() if l.strip()]
    return "\n".join(lineas[-40:]) or "(no mostró nada)"


class Terminal:
    """Ejecuta un programa como si estuviera en una terminal real."""

    def __init__(self, comando: list[str], entorno: dict):
        self.maestro, esclavo = pty.openpty()
        fcntl.ioctl(esclavo, termios.TIOCSWINSZ, struct.pack("HHHH", 60, 4000, 0, 0))
        self.proc = subprocess.Popen(comando, stdin=esclavo, stdout=esclavo, stderr=esclavo,
                                     env=entorno, close_fds=True, start_new_session=True)
        os.close(esclavo)
        self.texto = ""

    def leer_hasta(self, patron: re.Pattern, segundos: float):
        fin = time.time() + segundos
        while time.time() < fin:
            limpio = ANSI.sub("", self.texto)
            m = patron.search(limpio.replace("\r", ""))
            if m:
                return m
            listos, _, _ = select.select([self.maestro], [], [], 1)
            if listos:
                try:
                    datos = os.read(self.maestro, 65536)
                except OSError:
                    break
                if not datos:
                    break
                self.texto += datos.decode("utf-8", "replace")
            elif self.proc.poll() is not None:
                break
        return None

    def escribir(self, texto: str):
        os.write(self.maestro, texto.encode())
        time.sleep(0.5)
        os.write(self.maestro, b"\r")

    def cerrar(self):
        if self.proc.poll() is None:
            self.proc.terminate()


def generar() -> bool:
    instalar_claude_code()
    entorno = {k: v for k, v in os.environ.items()
               if k not in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN")}
    entorno.update({"TERM": "xterm-256color", "COLUMNS": "4000", "BROWSER": "true"})
    term = Terminal(["claude", "setup-token"], entorno)
    try:
        enlace = term.leer_hasta(URL, 120)
        if not enlace:
            print("No apareció el enlace de autorización. Salida (sin datos sensibles):")
            print(ANSI.sub("", term.texto)[-800:])
            _mensaje("No pude iniciar la creación del token. Vuelve a intentarlo en unos minutos.")
            return False
        desde = _ultimo_update()
        _mensaje(
            "Vamos a crear el token de tu suscripción de Claude.\n\n"
            "1. Abre este enlace e inicia sesión con tu cuenta de Claude:\n"
            f"{enlace.group(0)}\n\n"
            "2. Toca Autorizar.\n"
            "3. Copia el código que te muestra la página y respóndeme AQUÍ solo con ese código.\n\n"
            "Tienes 7 minutos."
        )
        print("Enlace enviado por Telegram. Esperando el código...")
        codigo = _esperar_codigo(desde)
        if not codigo:
            _mensaje("Se acabó el tiempo sin recibir el código. Vuelve a lanzar el diagnóstico para intentarlo otra vez.")
            return False
        inicio_respuesta = len(term.texto)
        term.escribir(codigo)
        token = term.leer_hasta(TOKEN, 45)
        if not token:
            term.escribir("")  # por si pide confirmar con Enter
            token = term.leer_hasta(TOKEN, 45)
        if not token:
            respuesta = _sin_secretos(term.texto[inicio_respuesta:], codigo)
            print("No apareció el token. Lo que mostró Claude Code:\n" + respuesta)
            _mensaje("No recibí el token. Esto es lo que respondió Claude Code (sin claves), "
                     "mándaselo a Claude en el chat:\n\n" + respuesta[-1500:])
            _mensaje("Para reintentar: lanza otra vez el diagnóstico y usa el enlace NUEVO que te llegue.")
            return False
        _mensaje(
            "Este es tu token. Guárdalo ya como secreto en GitHub:\n"
            "Settings → Secrets and variables → Actions → New repository secret\n"
            "Name: ANTHROPIC_API_KEY\n"
            "Secret: el texto de abajo (cópialo completo)."
        )
        _mensaje(token.group(0))
        _mensaje("Cuando lo hayas guardado, borra los dos mensajes anteriores de este chat por seguridad, "
                 "y vuelve a lanzar el diagnóstico para comprobar que todo funciona.")
        print("Token entregado por Telegram.")
        return True
    finally:
        term.cerrar()


if __name__ == "__main__":
    raise SystemExit(0 if generar() else 1)
